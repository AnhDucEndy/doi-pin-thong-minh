# Phase 8 — Technical review Recovery 8A

## Cập nhật sau phản hồi người dùng — 29/10/2026

**DESIGN READY FOR FINAL APPROVAL**, thay thế kết luận NEEDS APPROVAL của bản review ban đầu bên dưới về hướng nghiệp vụ. Người dùng đã chấp thuận R8A-01 (custody ngoài ngăn, xác minh hai phía), R8A-02 (trả đúng pin cũ cho đúng khách trong mô phỏng) và R8A-03 (manual reconciliation có thẩm quyền, tách luồng tự động). Chưa có phê duyệt mọi chi tiết API/Database.

Đề xuất kỹ thuật cụ thể được lưu tại [PHASE8_APPROVED_DESIGN_PROPOSAL.md](PHASE8_APPROVED_DESIGN_PROPOSAL.md), phiên bản P8-REC-0.1: structured evidence với nguồn Simulator/Technician/Customer riêng, hai bảng operation/attestations và pointer case; các mở rộng schema/API có phiên bản; quy trình service handover có durable ledger/fence; transition theo bằng chứng và kiểm tra tiền/tài sản; lock graph, migration/grants dự kiến và test matrix. Các thay đổi này là đề xuất để người dùng duyệt cuối, không sửa hợp đồng gốc trong lượt này.

Ba điểm R8A ở mục7 bên dưới được giữ làm lịch sử câu hỏi, **không còn là câu hỏi xin duyệt lại hướng nghiệp vụ**. Những giới hạn proof vật lý và P7-A01 vẫn có hiệu lực: không dùng ACK/EXECUTED/slot rỗng làm delivery; không cho record đổi custody; settle mới quyết định dưới guards; refund và charge tách biệt; không giải phóng holds trước terminal guards. Phương án mới dùng proof có cấu trúc thay vì fake SNAPSHOT/note hoặc UPDATE DB tay.

Git đầu lượt vẫn HEAD e4fb9f5, main đồng bộ origin/main, hai báo cáo Phase8 untracked. Lượt này thêm proposal và cập nhật tài liệu này; giữ gap analysis, không production code/migration/DB/ledger/commit/push/delete. Các đoạn “chưa được chấp thuận” bên dưới mô tả thời điểm trước phản hồi mới.

---

Ngày 29/10/2026. **Kết luận: NEEDS APPROVAL cho toàn bộ phạm vi 8A.** Ba operation đã có hợp đồng, nhưng bằng chứng xác minh khách giữ pin cũ, việc trả/quyết toán pin cũ sau thu hồi và quy tắc đối soát sau deadline chưa đủ chi tiết để triển khai mọi nhánh an toàn. Đây là khoảng trống thiết kế, không phải blocker runtime mới được tái hiện. Không thay source/hợp đồng hoặc thực hiện kiểm thử trong lượt review.

## 1. Nguồn, hiện trạng và phạm vi

Đối chiếu AGENTS, START_HERE/HANDOFF, IMPLEMENTATION_PLAN/STATUS, PHASE8_GAP_ANALYSIS, PHASE7_ACCEPTANCE/P7_A01_FIX; QD01–09 approved/config; FR12/16, UC10/14, BR05/08/09; AD-04b, SM-03b/04, INVARIANTS6–8; API catalog/OpenAPI và schema. Source trọng tâm: application/swaps.py, payments.py, device.py, identity.py; workers/device.py,payment.py,retry.py; simulator device main.py và payment; grants runtime. Bảng và đề xuất dưới đây không thay mã FR/UC/BR/TC hoặc đánh số handoff.

Hiện `swaps.review`/`payments.review` tạo một recovery_cases theo swap, giữ last-known custody và holds. Chưa có recovery API/service. `swaps.advance` chỉ xử lý AWAITING_RETURN,RETURN_ACCEPTED,AWAITING_PICKUP; không tự tiếp tục REVIEW_REQUIRED. Worker không biến reconnect thành được phép giao pin. Payment SUCCEEDED được giữ riêng với swap state.

QD giữ nguyên:2×6/một họ pin/network; thu trước9.000VND/mock; pin sai giữ xử lý kỹ thuật; QR một lần/RFID mô phỏng; Admin/Technician riêng; ngưỡng demo/TTL approved; kế hoạch và thẩm quyền duyệt QD08/09. Refund FULL_ADMIN_REVIEWED là bắt buộc MVP, chưa nằm trong code8A. ACK15s, physical60s từ command.created_at, evidence freshness15s và P7-A01 vẫn áp dụng luồng tự động.

## 2. Ba operation theo hợp đồng gốc

| Operation | Actor/quyền | Request và preconditions | Kết quả/side effects được đề xuất |
|---|---|---|---|
| getRecovery: GET /v1/swaps/{swap_id}/recovery | UserBearer; Admin hoặc Technician đúng trạm. Customer/DEVICE/PAYMENT không được gọi | Swap/case tồn tại; mỗi request kiểm tài khoản/session/assignment hiện hành. Không cần trạm online để đọc hồ sơ đã lưu | HTTP200 RecoveryCases; chỉ các fields schema, không payment secret/lịch sử khách toàn mạng; không mở case/đổi state/custody/holds khi đọc |
| recordRecoveryEvidence: POST /v1/swaps/{swap_id}/recovery/evidence | Chỉ Technician đúng trạm; Admin không kế thừa | Idempotency-Key UUID; body required expected_version,evidence_event_id,note; additionalProperties=false. Case chưa resolved; state swap thuộc nhánh recovery hợp lệ. Version đề xuất là recovery_cases.version vì response là case; cần ghi rõ trong đặc tả triển khai | HTTP200 RecoveryCases. Xác minh event, diễn giải Backend thành new_pin_delivered; lưu evidence/note/actor/version/audit nguyên tử. Không nhận YES/NO/state/custody do client khai. Việc ghi evidence không tự cho refund/release/đổi custody |
| settleRecovery: POST /v1/swaps/{swap_id}/recovery/settle | Chỉ Technician đúng trạm | Idempotency-Key; body required expected_version,evidence_event_id,resolution_note; additionalProperties=false. Kiểm lại toàn bộ evidence/state/resource/payment dưới khóa, không chỉ đọc kết luận cũ | HTTP200 RecoveryCases; chỉ đặt old_pin_settled khi chứng minh được; các transition đóng/resume phải đủ guards theo ma trận mục5. Không API mở cửa tùy ý, không force-complete |

Các operation đều trả RecoveryCases gồm id,swap_id,state,assigned_to,evidence_event_id,new_pin_delivered,old_pin_settled,resolution_note,version,created_at. CaseState chỉ OPEN/EVIDENCE_RECORDED/RESOLVED. Không thêm enum “APPROVED” hay endpoint “force”. Đề xuất OPEN→EVIDENCE_RECORDED sau evidence hợp lệ kể cả kết luận UNKNOWN; chỉ RESOLVED khi nhánh xử lý thực sự kết thúc, không chỉ vì Technician đã đọc/ghi chú. Đây là chi tiết triển khai đề xuất, chưa phải state-machine case riêng đã được duyệt.

HTTP lỗi theo OpenAPI:401 auth,403 role/scope,404 không thấy,409 version/state/idempotency/resource conflict,422 schema/evidence không hợp lệ,503 nguồn/dịch vụ không sẵn sàng; không dùng503 để cấm đọc hồ sơ offline. Catalog không chốt enum đầy đủ của Error.code (string); khi triển khai tái sử dụng mã hiện có phù hợp và ghi mapping cụ thể trước test, không tuyên bố đã có mã RECOVERY_* mới. Không có lỗi/HTTP mới được triển khai trong review này.

## 3. Evidence pipeline và giá trị chứng minh

1. `evidence_event_id` là tham chiếu vào DB, không phải payload chứng cứ tự khai. Source đi qua X-Device-Key→device identity→station scope→durable inbox→worker; 202 chưa có nghĩa accepted. Kỹ thuật không được gửi event với DEVICE identity bằng user token.
2. Xác minh accepted=true/processed_at, payload hash/đúng schema; device/station đúng swap, ngăn đúng hai tài nguyên, command/swap correlation đúng khi có. Kiểm boot/seq, thứ tự thời điểm quan sát, latest accepted projection và event đến sau mốc cần đối soát. Không nâng accepted=false/rejected thành true chỉ để recovery dùng được.
3. Snapshot mới có thể là anchor trỏ đến các event/commands lịch sử Backend truy xuất; body một ID không đồng nghĩa chỉ kiểm một hàng. Các event lịch sử giữ nguyên observed_at/received_at và lý do reject; current snapshot phải fresh/đúng boot và ordering đã chấp nhận. Không tự áp15s để xóa lịch sử bền vững; cũng không coi lịch sử cũ là current state mới.
4. Snapshot chỉ có slots{compartment_id,door_state,present,observed_serial} và command_ledger{command_id,status NOT_EXECUTED/EXECUTED/UNKNOWN}. Nó **không có customer holder observation, biên bản trả pin cho khách hoặc transfer/custody chứng nhận độc lập**. Simulator lưu effects/body ở SQLite local nhưng snapshot chỉ gửi ID/status. File .local hoặc `--inspect` không phải dữ liệu xác thực mà API đang tự đọc từ máy Technician.
5. EXECUTED là actuator effect, ACK là nhận lệnh. Không cái nào tự xác minh lấy/trả pin. Snapshot vắng pin chỉ cho biết vị trí không còn thấy pin; không chứng minh khách nào đã lấy. NOT_EXECUTED của một command không chứng minh mọi command khác đều không thể tác động. Cần cả tập lệnh và history, interlock, event chain, không mâu thuẫn.

### new_pin_delivered

- **YES:** nguyên tắc đủ bằng chứng gắn đúng phiên/serial/ngăn/chuỗi physical và quyền giữ pin, không phải ACK/EXECUTED/vắng pin. Nếu custody pickup đã được commit hợp lệ trong Phase7 và audit khớp, đó là sự kiện lịch sử đã xác minh; không ghi custody lần hai. Nếu chỉ có evidence late/deadline failed, quy tắc chuyển thành YES/COMPLETED qua manual reconciliation còn cần duyệt ở R8A-03.
- **NO:** có thể triển khai nhánh hẹp với snapshot accepted mới xác nhận đúng serial pin cấp vẫn ở ngăn, cửa đóng, lịch sử nhất quán và chưa từng có OPEN_SUPPLY có thể tác động. Phải kiểm no-command dưới station lock, chặn dispatch cạnh tranh. Sau khi đã dispatch/UNKNOWN, snapshot một thời điểm đơn lẻ không đủ kết luận chắc chắn NO; giữ UNKNOWN cho tới chính sách đối soát được duyệt.
- **UNKNOWN:** thiếu/mâu thuẫn evidence, offline/reboot ledger không đầy đủ, không liên kết được chain, không rõ ai lấy pin. Cần có thể ghi evidence hợp lệ mà kết luận vẫn UNKNOWN; không ép NO để refund demo chạy được. Kết luận cũ phải được kiểm lại tại action tài chính/custody, không tái sử dụng vô điều kiện.

## 4. old_pin_settled — ma trận sáu tình huống

`old_pin_settled` là nghĩa vụ tài sản đã giải quyết cho nhánh bù trừ, **không đồng nghĩa return_observed_at có giá trị**. Nhận pin cũ vào mạng lưới là custody return hợp lệ nhưng chưa chứng minh đã trả lại/quyết toán khi đổi bị hủy. Bool false hiện không phân biệt chưa xử lý/thiếu bằng chứng; phải giữ false và ghi lý do, không thêm enum trái schema.

| Nhánh | Evidence hiện có cho biết gì? | Kết luận an toàn hiện tại | Còn thiếu/cách xử lý |
|---|---|---|---|
| A. Chưa trả pin cũ | DB có last-known holder=customer, không return commit; ngăn nhận rỗng; có thể có command NOT_EXECUTED | Không suy ra khách **hiện vẫn giữ** pin từ ngăn rỗng hoặc chỉ từ DB. old_pin_settled=false khi chưa có xác minh tích cực | Invariant8 yêu cầu xác minh khách còn đúng pin. Chưa có evidence typed cho việc quan sát serial+holder ở ngoài ngăn; R8A-01 cần duyệt |
| B. Đã trả/chưa lấy pin mới | Return audit/custody cũ ở ngăn nhận; pin cấp còn trong ngăn theo snapshot | Giữ pin cũ tại mạng lưới, new delivered NO chỉ khi đủ guard mục3; old_pin_settled chưa true chỉ vì pin đã nhận;3holds/charge giữ | Chưa có quy trình có chứng cứ trả lại/quyết toán pin cũ sau return. R8A-02; hoàn phí8B sau này không tự giải quyết phần này |
| C. Pickup chưa rõ | OPEN_SUPPLY đã phát/UNKNOWN hoặc chain thiếu; slot có thể rỗng | new_pin_delivered=UNKNOWN; không refund/cấp thêm/release; giữ last-known custody/old_pin_settled chưa chứng minh | Chờ snapshot/ledger/history hợp lệ. Không cho một note xác nhận khách đã lấy/chưa lấy; R8A-03 nếu cần kết luận sau deadline |
| D. Đã xác minh lấy pin mới | Có custody pickup commit hợp lệ + return commit + charge đã verified; hoặc chỉ evidence cần đối soát | Trường hợp đã COMPLETED không xử lý lại/release lại/đặt cờ bù trừ cho đẹp. Nếu REVIEW_REQUIRED cần đủ cả hai custody+charge trước manual completion | Không cần “trả pin cũ” trong lượt đổi thành công: pin cũ hợp lệ thuộc mạng lưới. Đừng đặt old_pin_settled=true để cho refund nhánh này; refund bị chặn. Reconciliation chuyển custody chưa commit cần R8A-03 |
| E. Trả sai pin | observed_serial khác expected, case/alert/BLOCKED; last-known old battery vẫn giữ nguyên | Không gán pin lạ vào hồ sơ pin cũ/kho, không sửa serial/holder; không cấp pin mới; old_pin_settled=false nếu chưa chứng minh | Cần quy trình kỹ thuật nhận diện/trả vật lạ và xác minh pin cũ thực sự khách giữ. Payload slot không chứng minh danh tính người nhận; R8A-01/02 |
| F. Offline/evidence muộn | Inbox/ledger/history còn, nhưng source current state chưa đủ/new boot có thể UNKNOWN | Cho GET hồ sơ, không tự finalize. Late/rejected evidence giữ làm lịch sử; không dùng received_at mới để làm mới measurement hay hồi sinh command | Reconnect snapshot đúng nguồn/ordering rồi đối soát. Nếu vẫn không rõ giữ review/holds; không đổi created_at/TTL/processed flags; R8A-03 cho nhánh manual cần thời gian mới |

**Kết luận ưu tiên:** hợp đồng hiện không đủ để tự động đặt old_pin_settled=true cho tất cả A/B/E. Một ghi chú Technician và chữ ký xác thực request chỉ chứng minh ai khai, không chứng minh pin đã được giao cho ai. Không có điều kiện “note khác rỗng là settled”.

## 5. Ma trận transitions, tiền và tài nguyên

| Trạng thái/điều kiện | Transition SM-03b | Custody/Payment/holds |
|---|---|---|
| REVIEW_REQUIRED, charge verified SUCCEEDED, chắc chắn chưa có tác động, interlocks đủ, chưa có command ngăn trả cũ cần phát lại | AWAITING_RETURN | Không chuyển pin tại action resume; không tạo charge mới. Giữ holds. Worker hiện có chỉ tạo command nếu chưa tồn tại; nếu command cũ đã kết thúc thì không đổi ID/deadline để chạy lại |
| REVIEW_REQUIRED, return custody đúng, chưa phát OPEN_SUPPLY, interlocks đủ | AWAITING_PICKUP theo SM-03b | Cần đảm bảo tạo OPEN_SUPPLY duy nhất đúng transaction/worker integration; không vào AWAITING_PICKUP rỗng command khiến worker đợi mãi. Return custody giữ nguyên, payment SUCCEEDED,3holds |
| REVIEW_REQUIRED, đủ hai custody và thu verified | COMPLETED theo AD-04b | Chỉ đối soát có căn cứ; release đúng holds/audit cùng commit. Nhánh sau deadline cần R8A-03, không gọi advance bỏ guard |
| REVIEW_REQUIRED, charge FAILED cuối cùng, xác minh chưa tác động vật lý và không lệnh còn có thể tác động | CANCELLED | Payment vẫn FAILED; không refund, custody không đổi, release holds của chính phiên nếu có |
| REVIEW_REQUIRED, charge SUCCEEDED, chắc chắn chưa giao pin cấp và không lệnh còn tác động | COMPENSATING qua Admin request refund8B | Technician không thực hiện transition này bằng settle; giữ custody/3holds |
| COMPENSATING, refund SUCCEEDED và old_pin_settled có chứng cứ | CLOSED_COMPENSATED | Payment vẫn SUCCEEDED; refund riêng; close/release/audit nguyên tử. Đây là8C, không giả lập refundSUCCEEDED trong8A |
| Charge CREATED/PENDING/UNKNOWN, hoặc physical UNKNOWN | Giữ REVIEW_REQUIRED/nhánh đang bảo vệ | Admin query charge theo UC13; không chốt FAILED từ timeout; không settle custody/hoàn tiền chỉ vì worker restart |

Đây là mục tiêu tích hợp theo SM-03b; vị trí operation nào thực hiện từng resume/complete chưa được đặc tả đầy đủ: recordEvidence mô tả ghi kết luận, settle có mục tiêu xử lý pin cũ. Đề xuất recordEvidence chỉ lưu case; settle là điểm quyết định kỹ thuật dưới guards, worker tiếp tục bước đã authorize sau commit. Cần người dùng chấp thuận phân công này trong R8A-03 trước khi tạo transitions chưa có ở source.

## 6. Transaction, idempotency, audit và restart

Đề xuất triển khai kỹ thuật không đổi BR:

- Mutation dùng session transaction hiện có và `identity.idempotent`: principal+HTTP method/path+key+canonical body, cùng key/body trả response đã commit; khác body409; HTTP key không thay command/provider key. Vẫn kiểm auth/assignment hiện hành trước replay. GET không có idempotency mutation. `expected_version` case guard cộng lock/version swap/pins/commands liên quan.
- Khóa theo cùng hệ thống station advisory→user→swap→slots UUID→batteries UUID của device worker; bổ sung case/payment/refund theo thứ tự chung đã kiểm call graph. Tuyệt đối không lock case trước station ở API trong khi worker làm ngược. Không gọi simulator/provider HTTP hoặc chờ người trong transaction.
- Đọc lại case, swap, cả pin/ngăn/holds, tất cả command có khả năng tác động và payment; kiểm nguồn evidence/boot/current snapshot sau khóa. Tại final decision lấy clock mới, kiểm freshness, eligibility và policy_snapshot, không `now()` tại transaction start thay clock quyết định.
- Case/version/kết luận/custody transition hợp lệ/holds/audit/idempotency response cùng commit. Audit append-only có Technician actor, before/after,anchor+supporting event IDs,command IDs,reason,correlation. Một pointer case có thể thay qua version nhưng không mất evidence cũ: audit giữ reference mỗi lần; không ghi QR/key/token. Không đánh dấu RESOLVED trước các điều kiện tài sản/tiền đạt.
- Crash trước commit rollback cả response/effects; sau commit/mất response replay trả kết quả cũ; key mới phải tái kiểm terminal/version và không release/command lần hai. Worker restart đọc state bền vững, không reset UNKNOWN/deadline/ledger. 55P03 chỉ retry ngoài transaction đã rollback theo helper P6-A03; hết budget dừng có log, không nuốt lỗi khác.
- Offline không cản đọc audit/case đã lưu; mutation không đủ chứng cứ current giữ an toàn. Record event mới vào inbox không tự làm case resolved. Không thay Payment SUCCEEDED, không thêm command nếu đã phát OPEN_SUPPLY, không dùng ACK làm custody.

## 7. Các quyết định cần người dùng phê duyệt

Các ID R8A dưới đây chỉ là câu hỏi review cục bộ, **không phải QD10/FR/BR mới và chưa được chấp thuận**. Hợp đồng gốc giữ nguyên.

| ID | Thiếu gì / ảnh hưởng | Đề xuất tối thiểu để duyệt |
|---|---|---|
| R8A-01 | A/E: evidence xác minh tích cực đúng serial pin cũ và người giữ ngoài ngăn. FR12/16,UC10/14,BR05/08/09,Invariant8. Hiện không có field/kind phù hợp | Duyệt thiết kế bổ sung có phiên bản cho bằng chứng kiểm tra custody do Technician đúng trạm thực hiện qua adapter mô phỏng: case/swap,serial,định danh người nhận/giữ,thời điểm,nguồn quan sát,tham chiếu event và operator. Backend đối chiếu holder/chain; lời khai đơn lẻ không đủ. Giữ request recovery hiện tại nếu anchor event có thể biểu diễn sau khi schema evidence mở rộng được duyệt; không nhét JSON vào note hoặc giả dạng SNAPSHOT. Cần chốt mức chứng minh/actor xác nhận và điều kiện từ chối trước triển khai |
| R8A-02 | B/E: cách trả lại/giải quyết pin cũ/vật lạ; ai giữ cuối và bằng chứng gì. Không có recovery command/transfer trong transport hiện tại | Đề nghị MVP chọn **trả lại đúng pin cũ cho đúng khách qua quy trình kỹ thuật mô phỏng có kiểm chứng**; không tự quyết toán tài sản bằng hoàn9.000VND. Nếu nhóm chọn cách khác phải định nghĩa quyền giữ pin/đồng thuận riêng. Cần thiết kế adapter thực thi nghiệp vụ có interlock/durable ID/chain/recipient proof, không endpoint manual unlock; chỉ đưa sửa đổi contract vào phụ lục phiên bản sau khi duyệt. Cho tới đó không đặt settled/release/closed ở các nhánh này |
| R8A-03 | C/D/F: reconciliation sau60s, evidence late/boot mới, và operation nào được authorize resume/complete. Nguy cơ bypass P7-A01 | Đề nghị phân biệt quyết định tự động Phase7 (giữ nguyên deadline) với manual reconciliation riêng có thẩm quyền, snapshot mới+history/ledger không mâu thuẫn và positive delivery proof đã được định nghĩa. Record chỉ lưu evidence; settle đánh giá nhánh kỹ thuật, không cấp thêm nếu OPEN_SUPPLY đã phát. Không chỉ dùng expired event để complete. Cần duyệt tiêu chuẩn proof/độ mới, nhánh được phép và audit riêng; nếu không duyệt, giữ review sau deadline, không triển khai complete-late |

Không có phương án nào được tự chọn trong review này. Có thể cho phép triển khai **phần hẹp** GET + ghi evidence/UNKNOWN + no-side-effect guards trước; đó không phải READY cho toàn8A và không đủ TC12/16/CT07. Nếu muốn chốt toàn8A cần quyết định cả ba điểm, đồng thời review schema/migration tương ứng; không thể chỉ trả lời “cho Technician sửa DB”.

## 8. Thứ tự triển khai8A–8C và cổng nghiệm thu

1. Chốt proof model/R8A trước. 8A: recovery read/evidence/classification,settlement/resume được duyệt và tests. Tái sử dụng recovery_cases/device_events/audit/idempotency. Grants hiện chỉ INSERT recovery_cases nên cần quyền UPDATE tối thiểu. Không tạo bảng/cột trùng; bổ sung schema mới chỉ nếu proof model được duyệt cần và migration test chứng minh thiếu. Không áp DDL gốc lên DB Alembic.
2. 8B: full Admin refund theo SM-04,refund/outbox/callback/query/provider ledger; giữ P6-A01 freshness,P6-A02 receipt conflict savepoint/inbox,P6-A03 bounded retry. UNKNOWN chỉ query cùng key,một intent/payment,charge vẫn SUCCEEDED. Không dựng fake refund cho8A.
3. 8C: đóng compensation+release sau cả tài sản và tiền, UI tối thiểu. Admin đọc/yêu cầu hoàn, Technician đúng trạm thu evidence/settle; Customer chỉ xem charge/refund và trạng thái của mình. Không mở quyền Technician xem lịch sử Customer toàn mạng. Chưa có route list case mới ngoài hợp đồng; dùng recovery ID đúng ngữ cảnh, không thêm endpoint để tiện UI trong lượt này.

PostgreSQL thật trên schema riêng: hai Technician khác key/same key/old version; evidence vs telemetry/boot/door; settle vs pickup closing/timeout; settle vs refund callback/charge conflict; hai APIprocess/worker contention; revoke assignment trong lúc xử lý; rollback sau pin/holds/audit trước commit. Kiểm counts/custody/version/unique command/Payment và không partial write. Terminal replay không release hoặc audit custody thành công lần hai.

E2E tiến trình thật: Backend2process+worker+provider+2simulators; ACK-only/UNKNOWN→reconnect→fresh evidence nhưng chưa đủ vẫn review; return committed/restart không duplicate; sai pin giữ custody; nhánh positive proof/settlement được duyệt; refund mất response/restart/query cùng key; refund success trước settle chưa release; settle đủ+refundsuccess mới closed; đã delivery không refund. Giữ ledger/schema/evidence và fingerprint demo. Không rút60s hoặc làm mới timestamp cũ để testsPassed.

AC gốc: TC12 gián đoạn không mất pin/holds và có lối đối soát có chứng cứ; TC16 Admin-only/chưa giao chắc chắn/full amount/không vượt charge; CT07 đã trả chưa nhận: refund và tài sản hai việc độc lập; CT08 pickup UNKNOWN giữ review/không hoàn hay cấp thêm; CT13 refund timeout cùng intent/key không double refund. TC16/CT13 chỉ đóng ở8B/8C, không báo8A Passed thay toànPhase8. Regression P4BMS/P5door/P6A01–03/P7A01 bắt buộc; Browser/API RBAC,validators/build có bằng chứng khi triển khai.

## 9. Git và kết luận bàn giao

Đầu lượt: HEAD `e4fb9f5`, main đồng bộ origin/main; untracked `docs/PHASE8_GAP_ANALYSIS.md` từ lượt trước được giữ. Lượt này chỉ thêm `docs/PHASE8_DESIGN_REVIEW.md` (tên đúng theo yêu cầu, không tạo thư mục hay ký tự escape trong tên). Không source/contract/migration/dependency change; không chạy test hoặc ghi DB/ledger, không commit/push/xóa dữ liệu/Phase9–10.

**NEEDS APPROVAL.** Đủ cơ sở thiết kế các bảo vệ và thao tác đọc/ghi evidence hẹp; chưa đủ căn cứ chốt toàn bộ8A vì old_pin_settled A/B/E và manual reconciliation C/D/F còn quyết định bắt buộc. Người dùng cần duyệt proof ngoài ngăn, quy trình giải quyết pin cũ, và điều kiện/thẩm quyền đối soát sau deadline trước khi triển khai các nhánh này.
