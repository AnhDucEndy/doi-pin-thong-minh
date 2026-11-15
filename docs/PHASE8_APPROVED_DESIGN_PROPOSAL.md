# Recovery 8A — đề xuất thiết kế để duyệt cuối

Phiên bản đề xuất **P8-REC-0.1**, 29/10/2026. Tên file có APPROVED nhưng **chỉ các hướng nghiệp vụ R8A-01/02/03 đã được người dùng chấp thuận**, qua phản hồi trong cuộc trò chuyện ngày29/10. Các endpoint/schema/migration/quy tắc kỹ thuật dưới đây là đề xuất, chưa được duyệt riêng. Không sửa baseline GĐ1/GĐ2. Tài liệu này là phụ lục thiết kế dự kiến, chưa là hợp đồng runtime.

**DESIGN READY FOR FINAL APPROVAL.** Đã xác định một phương án cụ thể để duyệt trước code; không còn yêu cầu người dùng chọn lại ba hướng nghiệp vụ. Những tham số/chi tiết phụ lục dưới đây vẫn cần phê duyệt cuối. Phạm vi là mô phỏng nghiệp vụ có kiểm chứng, không xác minh phần cứng/pin thật.

## 1. Quyết định và ranh giới

| Quyết định đã chấp thuận | Thiết kế cụ thể đề xuất |
|---|---|
| R8A-01 xác minh custody ngoài ngăn, ưu tiên hai phía | Một hồ sơ kiểm tra có ngữ cảnh bất biến; ba nguồn riêng: adapter mô phỏng quan sát serial/vị trí, Technician kiểm tra, Customer xác nhận chính mình đang giữ/nhận pin qua session. Một nguồn đơn lẻ không đủ |
| R8A-02 trả đúng pin cũ cho đúng khách khi đã trả mà không nhận pin mới và phải bù trừ | Quy trình service handover mô phỏng, chỉ pin cũ của đúng swap, recipient=customer của swap; có durable service ledger và xác nhận hai phía; Backend settlement mới đổi holder. Không hoàn phí thay nghĩa vụ tài sản |
| R8A-03 manual reconciliation tách Phase7 | record chỉ nhận/xác minh evidence; settle là quyết định dưới khóa. Không sửa command state/deadline/event timestamp; manual decision có audit riêng, không gọi advance với guard bị bỏ qua |

Nguồn truy vết: FR12/16 (liên quan FR11/13/14/15/17); UC10/14; BR01/02/04/05/06/07/08/09/10/11/12; AD-04b, SM-03b/04 và INVARIANTS6–8. QD01–09 giữ nguyên: network pin/một dòng/2×6/mock/thu trước/roles riêng. Không thêm tiền thật, chính sách giữ luôn pin cũ, định giá tài sản, manual unlock hoặc quyền Admin kế thừa Technician.

## 2. Mô hình proof và trust boundary

### 2.1 Hai bảng đề xuất, không nhân đôi các bảng hiện có

**recovery_operations**: một ý định kiểm tra/bàn giao có ngữ cảnh bất biến, không phải device command hoặc payment intent.

- id UUID ngẫu nhiên; case_id FK recovery_cases; swap_id,station_id,customer_id,pin_id lấy từ swap bằng Backend; pin_id có thể null duy nhất cho vật lạ; expected_serial; purpose; context_hash; created_by Technician FK users; created_at/expires_at UTC; base_case_version/base_swap_version; consumed_at nullable.
- Purpose dự kiến: VERIFY_OLD_POSSESSION, RETURN_OLD_TO_CUSTOMER, VERIFY_NEW_DELIVERY, RETURN_FOREIGN_OBJECT. Đây là mã kỹ thuật mới trong phụ lục, không thêm enum swap/payment/command gốc.
- Context hash gồm purpose,IDs,serial,source/destination,recipient,case version và tập command liên quan tại lúc tạo. Unique một operation chưa consumed cùng case/purpose (partial index); khi operation hết hạn muốn tạo mới phải có bước đóng operation cũ dưới khóa và audit, không đổi thời hạn operation cũ. Dùng cancelled_at nullable để đóng operation không dùng; CHECK không vừa consumed vừa cancelled.
- Bản đề xuất chọn hạn operation **120s** (tham số recovery mới, không ghi đè reservation/command TTL). Hết hạn không xóa evidence, không rollback tác động đã xảy ra; muốn kết luận cần tái kiểm/operation mới liên kết lịch sử cũ. Không giữ transaction trong120s.

**recovery_attestations**: append-only các sự kiện có cấu trúc, gồm id,event_id UUID unique,operation_id FK,source_kind (TECHNICIAN/CUSTOMER/SIMULATOR),actor_user_id hoặc device_id,observed_at,received_at,canonical payload/hash,source_boot/source_seq nullable,source_event_id nullable FK device_events.

- Payload theo tagged schema, không free JSON cho phép đổi custody. Fields: operation_id/context_hash,observation type,actual serial,subject/recipient (đối chiếu context),source/destination,supporting event IDs và outcome confirm/reject; actor thực lấy từ session/key. simulation_only=true bắt buộc.
- CHECK XOR user/device theo source; UNIQUE operation+source_kind cho lời chứng cuối mỗi phía. Nội dung đã ghi không UPDATE/DELETE: lỗi sửa bằng operation mới có supersedes/reference, không ghi lại lịch sử. EventID cùng hash replay trả receipt; khác hash409. DB FK và unique không thay kiểm tra role/trạm/serial liên bảng tại service.
- Customer/Technician lời chứng bị từ chối có thể ghi audit lý do đã redact; không ghi là chứng cứ accepted. Bất đồng xác nhận không được override bằng nguồn khác.

Recovery_cases giữ nguyên fields gốc; đề xuất thêm `operation_id` nullable FK recovery_operations làm anchor mới. `evidence_event_id` vẫn chỉ FK device_events, không trỏ UUID sai bảng. Case latest pointer/version thay đổi không làm mất attestations/audit cũ. Không dùng resolution_note làm kho chứng cứ.

Đây là số bảng tối thiểu đề xuất: operation cần quản lý challenge/expiry/context/consumption; attestations cần lưu nhiều nguồn append-only. Không thêm bảng pin mới/refund trùng/audit mới. Tất cả mutation phải qua service; không cho API SQL tùy ý.

### 2.2 Ý nghĩa và giới hạn từng nguồn

Chi tiết thời gian/version đề xuất: expected_version luôn là version hiện tại của recovery case. Việc append các lời chứng của chính operation làm tăng version case nhưng không tự làm context vô hiệu; context gắn các facts nghiệp vụ ban đầu và operation ID, không yêu cầu case version cuối bằng base_case_version. Thay đổi recipient/pin/custody/command outcome/boot phải tái đánh giá, không chỉ tăng version rồi bỏ qua. Hạn120s là hạn hoàn thành operation, không phải kéo dài guard evidence hiện tại15s; snapshot current vẫn phải mới tại quyết định cuối. Các attestations phải sau kiểm tra hoặc tác động service mà chúng xác nhận; lời chứng trước bàn giao không được tái dùng cho lần bàn giao sau.

| Nguồn | Xác thực/provenance | Chứng minh được và giới hạn |
|---|---|---|
| Device SNAPSHOT/event lịch sử | X-Device-Key→device/trạm, inbox accepted+processed,hash/boot/seq/observed_at,command/swap/ngăn đúng | Trạng thái trong ngăn và chain lệnh. Không chứng minh người giữ ngoài ngăn; ACK/EXECUTED không là delivery |
| Simulator service observation | Key thiết bị đúng trạm; operation được Backend cấp,context hash,source boot/seq riêng,ledger service bền vững | Quan sát/thao tác trong **mô hình vật lý mô phỏng**, actual serial và destination. Không dùng expected_serial trả lại nguyên xi như quan sát; đọc model riêng và có fault scenario. Không chứng nhận pin thật |
| Technician attestation | UserBearer,role và assignment kiểm tại request và tại settle; actor từ server | Xác nhận đã kiểm actual serial/thực hiện quy trình. Lời khai có trách nhiệm, không đủ một mình; không thay adapter hoặc Customer |
| Customer confirmation | UserBearer,customer_id=swap.customer_id,session còn hạn/không bị revoke; context immutable | Xác nhận danh tính và đang giữ/đã nhận đúng serial trong mô phỏng; không đủ một mình để chuyển holder |
| DB custody/audit | Dữ liệu server đã commit,append-only audit | Last-known custody và nghĩa vụ; không tự là chứng minh hiện đang giữ pin. Dùng để phát hiện mâu thuẫn, không suy luận từ ngăn rỗng |

Chống giả mạo: caller không tự chọn customer/station/pin mục tiêu khác swap; operation UUID không là quyền truy cập; không dùng token chung gửi qua URL. Context hiển thị cho cả hai người gồm serial,phiên,trạm,purpose,người nhận; Backend không tin field actor/role từ body. Customer xác nhận qua session của mình, không để Technician xác nhận thay. Hai principal thực sự riêng; không cho cùng user tự nhận cả hai vai dù role vừa đổi.

Ba nguồn thống nhất chỉ là proof của hệ mô phỏng. Nếu các bên cùng khai sai hoặc model không phản ánh vật lý thật, hệ thống không phát hiện chắc chắn; báo cáo/UI phải nêu giới hạn này. Không cung cấp nút “đánh dấu pin thật đã xác minh”.

## 3. API phụ lục đề xuất

Không thay các operationId/path/roles gốc. Dùng schema hợp thành có phiên bản, giữ request cũ hợp lệ, không nới additionalProperties tùy ý.

| API | Giữ/mở rộng đề xuất | Vai trò/đầu ra |
|---|---|---|
| GET /v1/swaps/{id}/recovery — getRecovery | Giữ body request; response RecoveryCasesV0_3 gồm fields gốc + active_operation tóm tắt context và tình trạng bằng chứng, không raw secret/ledger | ADMIN,TECHNICIAN đúng trạm;200. Customer vẫn không có quyền endpoint này |
| POST /v1/swaps/{id}/recovery/evidence — recordRecoveryEvidence | `oneOf` legacy RecoveryEvidence{expected_version,evidence_event_id,note} và RecoveryStructuredEvidence{expected_version,statement,note}. statement tagged: BEGIN_OPERATION{purpose}, TECHNICIAN_ATTEST{operation_id,context_hash,actual_serial,observation}, hoặc ATTACH_OPERATION{operation_id}; IDs/actor khác do server suy ra | TECHNICIAN đúng trạm;200 case kèm operation. BEGIN chỉ tạo ý định kiểm tra, không thực hiện bàn giao; các nhánh không đổi custody/holds/tiền |
| POST /v1/swaps/{id}/recovery/settle — settleRecovery | `oneOf` legacy{expected_version,evidence_event_id,resolution_note} và structured{expected_version,operation_id,resolution_note}; Backend chọn transition từ proof, không nhận desired_state/old_pin_settled từ client | TECHNICIAN;200 case. Legacy không thể tự chứng minh external holder nếu không có attestations |
| **Mới** POST /v1/swaps/{id}/recovery/confirmations | Body operation_id,context_hash,confirm:boolean. Không có serial/recipient override. Idempotency-Key; xác nhận/reject đúng context | CUSTOMER chính chủ;201 receipt tối thiểu; không mở quyền xem recovery toàn bộ |
| **Mới** GET /v1/device/recovery-tasks | Poll các operation service được authorize đúng thiết bị/trạm; cùng task có thể được gửi lại | DEVICE key,200 task context/version/expiry. Không lệnh mở khóa; không nhận task ngoài purpose/case cụ thể |
| **Mới** POST /v1/device/recovery-observations | Body event_id,operation_id,context_hash,boot_id,seq,observed_at,typed observation. actor/device/station từ key; không có state/holder update. Inbox bền vững trước receipt | DEVICE key,202 receipt; không có nghĩa proof đã đủ hoặc custody đã chuyển |

Ba endpoint mới là cần thiết cho hai trust boundary chưa biểu diễn được: Customer độc lập và adapter service độc lập (poll + durable receipt). Không giả dạng DEVICE SNAPSHOT, không nhét token/model observation vào note, không endpoint manual unlock. Các path/status/schema trên là **đề xuất chờ duyệt**, chưa tồn tại. Header idempotency UUID cho user mutations theo nền hiện có; source eventID/hash chống trùng cho device receipt.

UI Customer lấy context trong receipt hoặc danh sách swap chính chủ: đề xuất bổ sung optional recovery_confirmation context tối thiểu vào SwapTransactions response; không raw note kỹ thuật/ledger. Nếu không có field này người dùng vẫn có thể mở operation từ workflow có swapID nhưng API phải trả context chính chủ trước khi xác nhận; ưu tiên field optional thay thêm GET mới. Technician không nhờ Customer copy session/token.

Lỗi tái sử dụng401/403/404/409/422/503; phụ lục phải khai báo mã lỗi cụ thể cho expired context/mismatch/partial proof, phân biệt record hợp lệ nhưng UNKNOWN với request sai. Không tự gán mã runtime đã có nếu chưa code/duyệt; đây là một mục phải hoàn tất trong contract patch khi phê duyệt phụ lục.

## 4. Service adapter và durable handover

Adapter nằm trong tiến trình simulator hiện có nhưng có namespace ledger/service events riêng; không thay semantics OPEN_RETURN/OPEN_SUPPLY. Thêm các bảng SQLite service_tasks/service_observations và mô hình custody ngoài ngăn (serial→holder trong môi trường mô phỏng). Model không lấy DB custody trả ngược thành proof: seed mô tả trạng thái ban đầu, operator thực hiện bước kiểm tra/handover có actual observation; tests phải tiêm mismatch/absent/wrong recipient được.

Quy trình RETURN_OLD_TO_CUSTOMER đề xuất:
1. Backend chỉ authorize operation khi new delivered=NO được kiểm chứng,swap đang REVIEW_REQUIRED/COMPENSATING,không command có thể tác động,đúng old serial trong ngăn nhận và3holds vẫn hợp lệ. Context chốt customer,source compartment,destination customer,serial.
2. Technician thực hiện thao tác service **có chủ đích trong simulator**, không Backend tự mở cửa khi tạo operation. Adapter kiểm purpose/context/expiry, đọc actual model đúng pin/source và recipient; ghi PREPARED bền vững trước tác động. Crash sau PREPARED mà kết quả không rõ → UNKNOWN, không làm lại. Không expose thao tác mở khóa tổng quát; đây là lấy/trả pin qua truy trình kỹ thuật mô phỏng, không firmware hoặc cách mở tủ thật.
3. Tác động model service một lần; cập nhật slot trống và external holder trong cùng SQLite transaction cùng event ledger; adapter xuất trạng thái slot thực tế qua snapshot chuẩn, service observation qua endpoint riêng. Không giả cửa mở/đóng hoặc command OBSERVED nếu không có action tương ứng. TaskID/context dedup; restart chỉ replay receipt/history, không tái bàn giao. Nếu không kiểm chứng được thao tác service an toàn, dừng UNKNOWN.
4. Technician attestation và Customer confirmation **sau** observation bàn giao, cùng actual serial/context. Xác nhận sớm trước observation không đủ, phải mở operation kiểm chứng mới nếu context/chuỗi không hợp lệ. Backend record không đổi holder; trong khoảng model đã giao nhưng DB last-known chưa cập nhật, tài nguyên giữ blocked/review, không cấp pin mới. Không cố rollback tác động bên ngoài bằng SQL.
5. settle kiểm các nguồn + latest accepted snapshot mới, không command mâu thuẫn, không có outcome delivery mới. Trong transaction đổi pin cũ COMPARTMENT→CUSTOMER chính chủ,old_pin_settled=true,consume operation/audit/idempotency. Payment không đổi; chỉ release ở điều kiện terminal mục6. Crash/restart tiếp tục từ evidence đã lưu, không lặp service effect.

VERIFY_OLD_POSSESSION không tác động slot/model transfer: adapter quan sát actual serial/holder bên ngoài ngăn, Technician kiểm tra, Customer xác nhận đang giữ. Đủ ba nguồn + history nhất quán mới đặt old_pin_settled khi settle. Ngăn rỗng/DB holder một mình không đủ.

VERIFY_NEW_DELIVERY dùng để khẳng định người nhận pin cấp hiện tại: positive adapter observation+Technician+Customer nhận/đang giữ đúng pin cấp, kết hợp chain/lịch sử trạm. Không tạo hành động cấp pin mới qua service task này. RETURN_FOREIGN_OBJECT chỉ trả vật thể có observed_serial liên kết sự kiện sai pin cho **người đã xác minh là người trình vật thể của phiên**, không khẳng định quyền sở hữu vật lạ. Nếu không chứng minh người trình/người nhận, giữ UNKNOWN. Không tạo record battery mạng lưới cho vật này; việc xử lý vật lạ không thay kiểm tra pin cũ thực sự của khách.

Mọi operation có tác động dịch chuyển phải dừng nếu có bằng chứng new pin delivered hoặc UNKNOWN; không chấp nhận trả old pin rồi mới kiểm pickup. Station fence ở mục7 là điều kiện bắt buộc, không chỉ kiểm ở lúc authorize.

## 5. Manual proof sau deadline

Nguồn lịch sử dù quá15s vẫn giữ để chứng minh sự kiện đã xảy ra; không tự biến thành current observation. Tại **manual decision** cần snapshot accepted đúng boot/serial/ngăn mới≤15s,không quan sát mới mâu thuẫn, tất cả command có thể tác động đã phân giải. Những clock này độc lập: operation120s là đề xuất mới; ACK15/physical60/guard tự động P7-A01 không đổi.

- YES khi positive current holder/delivery proof đúng khách/serial + return chain/custody hợp lệ + snapshot/ledger đầy đủ không mâu thuẫn. Expired event/ACK/EXECUTED hay ngăn trống một mình không đủ. Manual settle tạo MANUAL_RECOVERY_* audit riêng, không sửa event rejected→accepted hoặc command UNKNOWN→OBSERVED.
- NO khi positive snapshot đúng pin cấp vẫn ở ngăn cùng history và tất cả service/commands liên quan không còn tác động; kiểm các lệnh QUEUED/DISPATCHED/ACKNOWLEDGED/UNKNOWN chứ không chỉ OPEN_SUPPLY đầu tiên. Có UNKNOWN chưa phân giải thì giữ UNKNOWN, không suy từ hết TTL rằng chắc chắn không thực thi.
- Có cửa sổ bằng chứng tạm thời mâu thuẫn/boot thiếu/late event có hậu quả thì UNKNOWN và dừng action. Record evidence có thể update kết luận về UNKNOWN khi điều kiện thay đổi; action tài chính/kỹ thuật không được chỉ đọc cờ NO cache.
- Đối soát xác nhận return đã thực sự xảy ra nhưng custody tự động chưa commit do deadline: cần authenticated history đúng serial+current snapshot pin cũ ở đúng ngăn+positive customer/Technician/service proof nếu chain thiếu; không chỉ gọi advance để “chạy lại”. Settlement được duyệt ghi custody lịch sử có provenance thủ công và kiểm BMS pin cấp tại bước mới. Không dùng manual reconciliation để hợp thức giao hàng khác khách hoặc bỏ qua mâu thuẫn.

## 6. Ma trận A–F: state, custody, tiền, holds

Tất cả record: case OPEN→EVIDENCE_RECORDED kể cả kết luận UNKNOWN; custody/tiền/holds chưa đổi. Settle chỉ Technician đúng trạm, case version hiện hành. Case RESOLVED khi nhánh recovery thực sự kết thúc; resume chỉ ghi EVIDENCE_RECORDED (case chưa đóng), worker/terminal finalizer đóng khi điều kiện cuối đạt. Không thêm enum swap/case gốc.

| Nhánh | Minimum proof / trước | Settle và state sau | Custody và tài chính / holds |
|---|---|---|---|
| A chưa trả old | VERIFY_OLD_POSSESSION ba nguồn; current snapshot pin cấp vẫn tại trạm; no-effect command ledger; REVIEW_REQUIRED | Đặt old_pin_settled=true nếu nghĩa vụ old đã giải quyết. Charge FAILED cuối/no effects→CANCELLED+RESOLVED. Charge SUCCEEDED+NO→giữ REVIEW_REQUIRED chờ8B. Muốn tiếp tục đổi chỉ khi chưa có OPEN_RETURN cần chạy lại và interlock đủ→AWAITING_RETURN | Old vẫn Customer, new vẫn ngăn. Charge không sửa. Giữ3holds khi chờ hoàn/resume; CANCELLED chỉ release holds của chính phiên sau kiểm mọi effects |
| B đã trả old/chưa nhận new | Return proof/custody + new=NO; RETURN_OLD_TO_CUSTOMER đủ3nguồn sau action service | Settle trả old cho Customer,old_pin_settled=true; vẫn REVIEW_REQUIRED/COMPENSATING chờ8B–8C. Nếu lựa chọn tiếp tục đổi thay vì trả old: không handover service,return đúng/chưa phát OPEN_SUPPLY và interlock đủ→AWAITING_PICKUP cùng tạo một command | Old về Customer khi settle handover, new ở ngăn; charge SUCCEEDED giữ nguyên; refund chưa có/REQUESTED/PENDING/UNKNOWN/FAILED đều chưa đủ đóng;3holds giữ |
| C pickup UNKNOWN | Thiếu positive proof hoặc command UNKNOWN | Case EVIDENCE_RECORDED,new_pin_delivered=UNKNOWN;giữ REVIEW_REQUIRED; từ chối final settle/hoàn/cấp thêm | Last-known old/new custody không sửa;charge không sửa;3holds giữ |
| D verified đã nhận new | VERIFY_NEW_DELIVERY ba nguồn + return custody/chain + charge verified SUCCEEDED;không command còn mâu thuẫn; không refund pending/succeeded | Manual settle→COMPLETED+RESOLVED nếu đủ. Nếu đã COMPLETED: replay/no-op,không audit custody lần hai. Nếu refund đã bắt đầu thì không tự complete,giữ review theo xung đột tài chính | Old ở trạm,new Customer; chuyển custody thiếu bằng chứng bị chặn;không trả old cho khách ở nhánh này. Charge SUCCEEDED,không refund;release3holds cùng completion/audit |
| E sai pin | Event wrong serial + task RETURN_FOREIGN_OBJECT có đủ nguồn xác minh người trình/nhận, và VERIFY_OLD_POSSESSION cho đúng old | Xử lý vật lạ riêng. Không đủ một trong hai→giữ review/settledfalse. Đủ và newNO→settledtrue,giữ review chờ8B–8C | Không đăng ký pin lạ vào mạng lưới/không đổi old serial. Old hợp lệ vẫn Customer;new ngăn;charge giữ;3holds giữ đến terminal guards |
| F offline/restart/late | Historical evidence retained;fresh authenticated reconnect snapshot/current model + full service/command ledger + bilateral proof theo nhánh | Offline đọc case được;thiếu current proof thì UNKNOWN. Khi đủ→phân nhánh A/B/D bằng manual settle,không reset timestamp/deadline/reissue command | Custody/Payment/holds không đổi chỉ vì reconnect;đối soát đủ mới chuyển nguyên tử. UNKNOWN giữ holds |

Các transition qua settle8A: REVIEW_REQUIRED→AWAITING_RETURN (chưa tác động,chưa có command cũ phải reissue);→AWAITING_PICKUP (return proof,chưa từng phát OPEN_SUPPLY);→COMPLETED (đủ hai custody+verified charge,không refund mâu thuẫn);→CANCELLED (FAILED cuối,chưa physical effect). Không nhận target_state từ client: Backend suy ra từ operation purpose/proof/current state. Nếu có nhiều nhánh khả dĩ, không tự chọn gây action vật lý; operator chọn purpose inspection/resume trong statement phụ lục, Backend chỉ cho các purpose được duyệt và guards. Đề xuất thêm purpose RESUME_SWAP để thể hiện ý định tiếp tục mà không bịa YES/NO/state; purpose này không service effect và vẫn cần proof tương ứng. Đây là phần schema đề xuất cùng phụ lục, không có endpoint resume riêng.

REVIEW_REQUIRED→COMPENSATING là **Admin refund request8B**, không settle Technician. COMPENSATING→CLOSED_COMPENSATED là **finalizer8C** sau refundSUCCEEDED+oldsettled được recheck+no possible actuation; consume resources/audit nguyên tử. Nếu các điều kiện đến trái thứ tự, cả settle lẫn refund callback phải gọi cùng finalizer idempotent trong8C. Không có refund trong8A thì nhánh này chỉ giữ trạng thái, không dùng fixture outcome trong production.

## 7. Transaction và concurrency

Hiện API idempotent lấy advisory idem trước execute; worker station_locks lấy station→users sorted→swaps sorted→slots sorted→batteries sorted; payment lock cũng lấy station trước nghiệp vụ. Thiết kế8A phải kế thừa **cùng helper**, không chỉ lock swap hoặc case độc lập.

- Khóa transaction đề xuất: user-mutation idem lock (chỉ API)→station advisory→recheck actor/assignment và users gồm Customer/Technician theoUUID→swaps→slots→batteries→commands→payment→refund→case→operation. Hoàn thiện một lock graph dùng chung cho recovery/refund: không đường nào giữ case/operation rồi đợi station. Quyền/role đổi phải serialize với users; assignment recheck với writer gán trạm dưới user lock. Tại triển khai rà lại từng caller trước thêm khóa actor tránh đảo UUID với helper cũ.
- READY FOR APPROVAL không có nghĩa lock graph này đã được runtime chứng minh. Targeted deadlock test bắt buộc trước nghiệm thu; nếu cần thêm actor lock vào helper hiện tại phải review riêng regression và không giữ Customer đã lock rồi lấy Technician trái thứ tự. Worker không cần lock idem; không tạo vòng station→idem. Refund8B dùng station rồi payment/refund tương thích, không đảo thành payment→station.
- Một operation service được authorize dưới station lock tạo **fence bền vững**: worker/poll/resume/refund phải đọc trạng thái operation và không phát lệnh xung đột cho swap. Fence không xóa sau TTL một cách tự động nếu có PREPARED/UNKNOWN effect. Mọi queue command cũ phải phân giải theo ledger trước authorize; expiry không là chứng minh no effect.
- Gọi adapter/provider và chờ xác nhận bên ngoài transaction. Mỗi attestation nhận/ghi atomically,proof chỉ READY logic khi đủ3nguồn đúng context. Tại settle: lock toàn graph,recheck proof/permissions/expiry/current snapshot/freshness/payment/commands,consume operation,custody/case/version/audit/idempotent response cùng commit. Không UPDATE DB tay. Nếu telemetry sau settle báo mâu thuẫn, mở review/evidence mới; không xóa custody audit đã commit.
- Mất quyền giữa các bước: recheck Customer và Technician identities/còn ACTIVE/role/scope tại final decision; mất quyền hoặc context version đổi thì không chấp nhận lời chứng cũ để force settle, cần operation mới/tái xác nhận. Version compare chỉ các trường nghiệp vụ ảnh hưởng; telemetry unrelated không tự invalidate mọi proof, nhưng boot/custody/command/recipient/source thay đổi phải re-evaluate.
- Crash sau adapter effect trước DB: ledger service query/replay cùng operation,không làm effectlầnhai; backend giữ review/holds cho tới reconciled. Crash DB trước commit rollback; sau commit response mất replay same principal/path/key. Khác key/version cũ409 hoặc terminal no-op theo contract,không double custody/release/audit success. P6 retry55P03 giữ bounded budget/backoff ngoài transaction rollback; không nuốt lỗi khác.

## 8. Database/migration/grants và khả năng quay lui

Đề xuất migration thuận tiến sau head Alembic hiện có, tên/version thực tế chọn khi triển khai (không đoán head mới). Tạo hai bảng cùng FK/index/check và pointer case; không backfill old_pin_settled/new_pin_delivered thành đúng cho case cũ. Giữ nguyên trạng thái case lịch sử cho đến khi có bằng chứng mới, không đưa case đã resolved về OPEN. Grants SELECT/INSERT attestations, không UPDATE/DELETE; SELECT/INSERT và UPDATE duy nhất cancelled_at/consumed_at operation; UPDATE case cho fields nghiệp vụ. DB role không thay kiểm tra actor tại API.

Adapter nâng SQLite ledger theo CREATE TABLE IF NOT EXISTS/version kiểm; không drop/reset commands/events/payment ledger cũ. Rollback ứng dụng: tắt recovery mới,giữ bảng/evidence/history và giữ review/holds. Không downgrade xóa bảng đã có chứng cứ. Mọi schema/runtime grants test riêng với role runtime thật; không áp schema.sql gốc lên DB đã migrate. Cần kiểm FK/index schema thực trước tạo, không lấy baseline DDL làm bằng chứng migration đã chạy.

Không thêm dependency/hạ tầng mới; auth user/device,SQLAlchemy/Alembic/PostgreSQL và SQLite hiện có đủ. Không public exposure hoặc broker. Thiết kế thêm service model là mock adapter có ledger, không phần cứng thật. Secrets dùng env hiện có,không đưa Device-Key vào Frontend.

## 9. Kế hoạch và test matrix

| Lát | Module/API/UI | Acceptance gate |
|---|---|---|
| 8A | Recovery service/ba API gốc và phụ lục evidence/Customer confirmation/adapter; schema/grants/service ledger; UI proof tối thiểu để hai phía xác nhận | TC12/CT07/08 phần recovery; old_pin_settled chỉ khi đủ proof; UNKNOWN giữ an toàn; manual decisions không bypass luồng tự động P7; PG và real-process evidence/custody tests |
| 8B | Full mock refund, Admin request/reconcile, worker/outbox/callback/provider ledger và Customer refund read | TC16/CT13: một intent, full amount không vượt charge, UNKNOWN query cùng key; P6-A01–03 không hồi quy; refund success đơn lẻ chưa release |
| 8C | Compensation finalizer và UI tích hợp Customer/Admin/Technician, lịch sử review | TC12/16, CT07/08/13 đầu–cuối; refund và old settlement đủ mới closed/release; charge SUCCEEDED riêng; full regression/Browser có bằng chứng |

PG test schema riêng, không dùng SQLite/mock thay transaction concurrency:

- Duplicate event cùng hash, retry cùng key; khác hash/body trả409; hai Technician cùng operation; sai serial/customer/station/device; forged actor; Customer reject/confirm trước observation; observation không khớp context.
- Role/session/assignment bị revoke sau attestation trước settle; hai process settle; lock contention giữa recovery và payment/device worker; closing event muộn/telemetry/reconnect boot cạnh tranh settle; provider query/refund callback cạnh tranh old settlement; không deadlock, partial write hoặc double release.
- Rollback sau cập nhật pin, trước audit/response; consumed chỉ commit cùng custody; retry đúng key; terminal replay; operation hết hạn hoặc PREPARED/UNKNOWN vẫn giữ holds.
- Giữ regression P6 savepoint/callback conflict, freshness boundary,55P03 exhaustion và P7 return/pickup deadline60/freshness15/ordering; service proof namespace riêng tuyệt đối không đổi expired command thành OBSERVED.

Real-process gồm hai Backend, PostgreSQL, worker, provider và hai simulators có service ledger: A kiểm tra khách giữ pin; B trả old pin sau khi thiếu pickup; C adapter crash sau PREPARED hoặc sau effect rồi restart/reconcile; D positive custody proof cho manual completion sau deadline trong khi auto guard vẫn từ chối; E xử lý vật lạ riêng; F reboot/late/unavailable. Kiểm API/DB/ledger về số effects, holds, audit, payment/refund trước–sau và fingerprint demo không đổi. Trong8B/8C thêm refund timeout/query/retry/restart chỉ một refund, callback success trước/sau settlement, pickup UNKNOWN chặn refund. Ghi kết quả Passed/Failed/Blocked/Not Run thực tế; không cộng checks E2E vào pytest.

UI chỉ là nguồn ý định và xác nhận authenticated, không tự đặt settled/new delivery. Customer thấy serial, purpose, nhãn mô phỏng và người nhận; Technician thấy proof còn thiếu/UNKNOWN; Admin không được attest/settle, Technician không được refund. Gọi API trực tiếp trái quyền phải bị Backend chặn. UI tối thiểu8A phục vụ bilateral proof, không kéo Phase9/10 vào đây.

## 10. Phụ lục cần duyệt cuối và kết luận

Đề nghị duyệt trọn P8-REC-0.1 hoặc chỉ rõ mục cần đổi: hai bảng cùng pointer/grants; typed statement/purpose kể cả RESUME_SWAP; ba endpoint cho các trust boundary mới và context đọc tối thiểu; operation120s; durable model service handover/fence; manual positive proof/transition mapping; tương thích request/response có phiên bản. Không đổi timeout QD cũ. Sau duyệt, triển khai contract overlay riêng trong docs/implementation-contracts/P8-REC-0.1 và migration/test, không ghi baseline. Đường dẫn này mới là đề xuất, chưa tạo file contract.

Không còn quyết định **hướng nghiệp vụ** cần hỏi lại ngoài ba hướng đã được duyệt; thiếu evidence thì giữ UNKNOWN và không ép đóng. Với vật lạ không xác minh được người trình thì giữ case, không tự đặt chính sách sở hữu. Để bắt đầu code toàn8A cần người dùng duyệt **chi tiết kỹ thuật phụ lục** nói trên; DESIGN READY FOR FINAL APPROVAL không phải READY TO DEPLOY hoặc đã phê duyệt API/DB.

Lượt này chỉ tạo tài liệu và cập nhật review cũ; không code production, migration, runtime, DB/ledger, commit/push hoặc xóa dữ liệu. Giữ PHASE8_GAP_ANALYSIS và mọi evidence1–7. Tests mới: Not Run vì chỉ review thiết kế.
