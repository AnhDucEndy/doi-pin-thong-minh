# Phase 8A — Browser acceptance thủ công

## Ghi chú sau lượt automation 14/11/2026

Người dùng đã chuyển sang Playwright, không cần thao tác Chrome thủ công theo các bước lịch sử bên dưới. Xem kết quả mới nhất trong [PHASE8A_IMPLEMENTATION](PHASE8A_IMPLEMENTATION.md) và [automated runner](../apps/web/e2e/README.md): 14 scenarios Passed, một Minor terminal-label Failed; chưa chốt Browser gates. Runtime tự động dùng 5190/8070/8071 riêng và đã dừng process sau test, không còn URL live ở các port đó. Các listener manual cũ 5180/8030/8031 được giữ nguyên, không xóa fixture/credentials/ledger. Thông tin bàn giao lịch sử phía dưới không phải một yêu cầu mới bắt người dùng thao tác.

## Phiên bàn giao hiện tại — 14/11/2026

**FIXTURE READY FOR USER STAGED VERIFICATION**, chưa phải Browser gates Passed.

- Frontend http://127.0.0.1:5180/; Backend http://127.0.0.1:8030, Backend thứ hai 8031.
- Swap **5236e3bb-378e-43ce-b99d-02d68509e1fa**; schema phase5_test_e0e6127e6a44.
- Runtime .cache/p8-E-849cb1eca3; metadata manual.json; credentials admin/customer/technician chỉ trong private.json cùng thư mục.
- Backend listener PIDs 13760/25804; Vite 27500; operator Python launcher 7448 và process thực 19832 (đúng runtime). Worker đang xử lý snapshot thật.
- Preflight API login/me/logout của từng role 200, frontend/proxy/API health 200. Recovery OPEN v1, operation_count=0, old_pin_settled=false, Payment SUCCEEDED, active holds=3, service effects=0. Các phiên kiểm login đã logout riêng; không phải phiên witness của người dùng.
- [Evidence preflight](PHASE8A_TESTS/manual_staged_resume_20261114_01/ready_checks.json). Đây là setup/readiness API, không tính Browser.

### Thao tác ngay trên phiên này

Đọc hết bước A–G và chuẩn bị các lệnh trước khi tạo receipt. Bạn tự mở hai Chrome contexts độc lập: cửa sổ thường/profile thứ nhất cho technician, Incognito/profile thứ hai cho customer. Login cả hai và tra cứu swap mới. Không logout phiên đã làm witness hoặc dùng chung một context cho hai role.

**A. Technician** nhập ghi chú, chọn mục đích RETURN_FOREIGN_OBJECT và bấm Tạo operation. Sao chép operation UUID mới từ UI. Chưa có operation UUID tại bàn giao vì chưa gửi mutation này thay người dùng.

**B. Operator INSPECT**, bạn chạy tại workspace:

```powershell
$runtime='.cache/p8-E-849cb1eca3'
$op='DAN_OPERATION_UUID_TU_UI'
.\.venv\Scripts\python.exe tools/phase8a_manual_operator.py --request $runtime --action INSPECT --operation $op
```

Phải thay giá trị $op bằng UUID thật trước khi chạy. Xem request-*.result.json mới và cả UI sau refresh. Accepted PRE receipt phải đúng operation/context/stage, có receipt ID/hash từ Backend; result completed=true không tự chứng minh Backend đã accepted. Không lấy receipt cũ làm mới bằng sửa timestamp.

**C. Hai human PRE confirmations.** Hai tab refresh ngay, Technician nhập actual serial SIMULATED-WRONG-BATTERY đã được simulator quan sát, chọn CONFIRM PRE; Customer kiểm principal/serial/context rồi CONFIRM PRE. Expected POST evidence 200 và confirmations 201. Hoàn tất khi proof còn mới ≤15 giây. Chỉ xác nhận điều đúng theo fixture. Khi stale/expired, giữ refusal và kết quả thực tế, không ép flow.

**D. INTENT/ACK.** Technician bấm Yêu cầu authorization intent khi đủ PRE proof. Bạn chạy:

```powershell
.\.venv\Scripts\python.exe tools/phase8a_manual_operator.py --request $runtime --action ACK --operation $op
```

Refresh Technician để thấy intent/acknowledgment ID đã được Backend lưu. Transport flush cũng có thể gửi ACK đã có task hợp lệ. Chưa có physical effect; intent vẫn effect_allowed=false.

**E. Activation/HANDOVER.** Technician bấm Chủ động yêu cầu activation. Khi Backend chấp nhận, bạn chạy:

```powershell
.\.venv\Scripts\python.exe tools/phase8a_manual_operator.py --request $runtime --action HANDOVER --operation $op
```

Chỉ chạy sau khi activation hợp lệ và proof còn hạn. Không gửi lại HANDOVER để chữa UNKNOWN hoặc response loss. Ledger/fence quyết định có thể tác động hay không.

**F. POST.** Cả hai tab refresh, chờ accepted POST_ACTION_RECEIPT đúng operation và recipient. Receipt phải có ID/hash mới đúng POST, không dùng PRE reference. Sau đó Technician và Customer CONFIRM POST ở hai phiên độc lập khi receipt còn mới. Expected 200/201, đúng hai human POST attestations và một simulator POST receipt. Không coi receipt đơn lẻ là lời xác nhận Customer.

**G. Settlement/replay.** Technician refresh version và bấm settlement khi đủ proof. Expected 200, operation consumed, đúng một FOREIGN_OBJECT_RETURN_SETTLED audit, một service effect. Recovery vẫn review nhánh nghĩa vụ pin cũ; old_pin_settled=false, Payment SUCCEEDED, network custody không đổi, ba holds vẫn giữ. Không chấm COMPLETED cho việc trả vật lạ. Lưu Idempotency-Key/body của request dưới dạng bằng chứng đã che Authorization; nếu DevTools có chức năng replay request, thử nguyên key/body và đối chiếu cùng result/identity, không thêm audit/effect. Nếu không có chức năng đó, ghi replay Browser Not Run, không dùng HANDOVER như replay thanh toán/settlement.

Ghi HTTP trong Network theo đúng role/path/status/code và context/receipt. Chụp UI tránh form password, private.json, Authorization, token hoặc HAR thô. Đọc DB theo schema mới bằng read-only: recovery_cases/operations/attestations, audit_events, payments, resource_reservations và hai battery custody records. Ledger ledgers/S01.sqlite3 chỉ mở mode=ro; service effect count=1 sau action hợp lệ. Có thể yêu cầu đối soát sau mỗi bước; không UPDATE SQL để làm fixture thành công.

### Các nhánh tiếp theo

Chỉ sau khi người dùng hoàn tất E mới lập phiên riêng cho PRE/POST REJECT, successor reboot + expiry thật, closure NEVER_PREPARED, negative RBAC/ownership/version/revoke và duplicate/response-loss. Không consume/cancel/reject rồi tái dùng operation đó như ca dương. Giữ các runtime cũ và dùng nhãn runner mới, không ghi đè. Chưa chạy hoặc chấm Passed các nhánh này trong lượt bàn giao.

### Quản lý phiên

Runner không có hạn tự tắt 900s ở nhánh handoff; thao tác operator chỉ xảy ra khi bạn tạo request. Session/operation/proof vẫn hết hạn đúng quy tắc. Nếu máy sleep/Docker dừng/runner bị ngắt, kiểm health và ownership trước khi tiếp tục; không giả định phiên còn sống. Operator token cũng có TTL; 401 cần lập phiên hợp lệ, không reset rate limits hoặc tăng TTL.

Khi chủ động kết thúc, tạo file rỗng .cache/p8-E-849cb1eca3/stop. Runner dừng đúng child của phiên này và lưu fingerprint; không xóa runtime/schema/ledger/private file. Nguyên nhân listener phiên cũ p8-E-72062a0670 biến mất vẫn **Unknown**: không còn process/listener, Vite log chỉ ghi ready, không có shutdown traceback/result đầy đủ. Không kết luận do Computer Use, Windows sleep hay lỗi production.

Các metadata/URL/ID bên dưới thuộc checkpoint cũ; dùng mục phiên hiện tại này trước.

## Operator đã kiểm chứng bằng tiến trình thật

Ngày 14/11, năm scenario E/K/J/U/S và 25 targeted tests đạt. Các action INSPECT, ACK, HANDOVER, REINSPECT, CLOSE và ACK_CLOSURE đã đi qua Backend/worker/simulator process thật trên cổng test riêng. [Ma trận và giới hạn](PHASE8A_IMPLEMENTATION.md), [DB/ledger/HTTP](PHASE8A_TESTS/operator_verified_20261114_01/summary.json). Đây không phải Browser Passed.

Điều chỉnh thực hành theo kết quả:

- Sau HANDOVER, chờ **accepted POST receipt** trên UI; completed=true ở file operator chỉ là kết quả adapter, không tự chứng minh Customer nhận vật thể. Outbox retry ở các chu kỳ sau không tạo effect mới.
- Khi POST đã accepted, ACTION có thể không còn trong task-list. HANDOVER mới sẽ bị từ chối; không dùng việc này để cố thực hiện lại effect.
- ACK và closure acknowledgment có thể được flush vận chuyển khi đã có task hợp lệ. CLOSE có thể hoàn tất acknowledgment sau khi Backend commit; không suy fence CLOSED từ riêng closure intent. Đọc state thật; ACK_CLOSURE thêm lần nữa chỉ là replay.
- Chỉ attest POST khi receipt còn mới trong 15 giây. EVENT_STALE không được xử lý bằng sửa timestamp. Chuẩn bị hai role contexts trước effect.
- Sau reboot, POST proof boot cũ không dùng để settle trực tiếp. Khi predecessor thật đã expired, dùng successor và current observation như hướng dẫn.
- PREPARED/UNKNOWN vẫn bị chặn ở closure, dù Backend đã tạo closure intent. Giữ fence/review và không gửi effect mới.
- Session operator cố định của fixture cũng có TTL. Nếu thao tác bị 401/phiên không còn hợp lệ, lập fixture mới hợp lệ; không reset counters hoặc kéo dài expiry.

Fixture 5180 cũ không bị thay đổi trong lượt verification, nhưng diagnostic cuối không thấy cổng đang lắng nghe. Các URL/ID ở phần sau là checkpoint lịch sử, cần kiểm health và dùng metadata mới trước thao tác. Để mở phiên mới, dùng lệnh --branch E --manual-browser với LABEL_MOI và đọc manual.json/private.json của runtime mới. Không ghi đè runtime cũ. Browser POST/successor/closure và negative UI vẫn cần người dùng kiểm trực tiếp.

## Cập nhật fixture tương tác 14/11/2026

Người dùng báo đã trực tiếp login Chrome và xác nhận UI cơ bản hoạt động. Ghi **Passed — user-reported manual smoke** cho kết quả tổng quát đó. Chưa có HTTP/screenshot từng stage hoặc thông tin từng role, vì vậy các flow riêng bên dưới vẫn Not Run; không chuyển hàng loạt thành Passed.

Phiên staged mới tách biệt phiên PRE cũ. Mở http://127.0.0.1:5180/; Backend http://127.0.0.1:8030, API thứ hai 8031. PID listener lúc bàn giao lần lượt 28236/29084/25700. Schema phase5_test_da667ba53f98, swap 20669b58-b66e-44b6-b7b5-bc390d0a6ca3. Credentials admin/customer/technician chỉ trong .cache/p8-E-72062a0670/private.json. Metadata .cache/p8-E-72062a0670/manual.json; ledger riêng cùng runtime trong ledgers/S01.sqlite3. Setup đã dùng API/domain services, worker và simulator để tạo wrong-return thật, chờ deadline gốc. Recovery OPEN, version 1, chưa có operation, pin cấp chưa giao, nghĩa vụ pin cũ chưa giải quyết. Frontend và proxy health đều HTTP 200. Không tự xác nhận human trong fixture mới.

### Chuẩn bị trước từng proof

Mở hai Chrome profile/incognito context độc lập cho Technician và Customer để giữ hai phiên đăng nhập đồng thời. Đăng xuất Technician sau khi attestation có thể làm proof phiên đó bị revoke; không dùng cùng tab để đổi role trong happy path. Admin dùng context thứ ba khi cần negative account tests. Mỗi context tự đăng nhập bằng file private, mở Recovery và tra cứu swap mới. ID operation xuất hiện sau khi Technician bấm “Tạo operation”; sao chép đúng ID này cho lệnh operator. state.json cục bộ là mirror read-only của Technician GET, có dữ liệu nội bộ; không đưa nguyên file vào ảnh/báo cáo Customer.

Khi hai người/tab đã sẵn sàng, operator gửi một lệnh từ PowerShell tại workspace:

```powershell
.\.venv\Scripts\python.exe tools/phase8a_manual_operator.py --request .cache/p8-E-72062a0670 --action INSPECT --operation OPERATION_UUID
```

Thay OPERATION_UUID bằng ID thật từ UI. Lệnh tạo request-UUID.json trong runtime; operator fixture xử lý rồi ghi request-UUID.result.json. completed=true chỉ chứng minh adapter đã chạy, phải kiểm accepted receipt trên UI/API. completed=false không phải bằng chứng no-effect. Không gửi HANDOVER lại khi trạng thái effect UNKNOWN; giữ review và ledger.

Mỗi action lấy task đang được Backend cho phép, đúng operation/context. Không có task khớp thì bị từ chối. Các lệnh là thao tác operator simulator được người dùng chủ động yêu cầu; không phải API generic unlock. Không command nào tự tạo Customer/Technician confirmation, INTENT, activation hoặc settlement.

| Flow tiếp theo | Thao tác Browser và lệnh operator | Expected / trạng thái bằng chứng hiện tại |
|---|---|---|
| PRE hai human proofs | Technician chọn RETURN_FOREIGN_OBJECT, nhập ghi chú và tạo operation. Operator INSPECT. Cả hai tab refresh, Technician nhập serial thực tế SIMULATED-WRONG-BATTERY rồi CONFIRM; Customer kiểm PRE/context/receipt rồi CONFIRM. | Simulator observation accepted, human requests 200/201; đúng stage/context/receipt. **Not Run trên Browser**. Cần hoàn tất trong freshness 15 giây, không kéo dài ngưỡng. |
| Authorization | Khi PRE đủ proof, Technician bấm authorization intent. Operator dùng action ACK cho cùng operation, Technician refresh để thấy acknowledgment ID. | Intent effect_allowed=false; ACK không phải physical proof. Chưa có service effect. **Not Run**. |
| Activation/handover/POST | Technician chủ động activation; operator HANDOVER cho cùng operation ngay khi permit và proof còn hợp lệ. Refresh để thấy durable POST_ACTION_RECEIPT, đúng actual serial và recipient. | Một effect; một accepted POST receipt; custody mạng lưới/Payment/holds giữ nguyên. **Not Run**. Receipt không tự chứng minh người nhận đã xác nhận. |
| POST confirmations và settlement | Hai tab sẵn sàng trước HANDOVER. Sau receipt, Technician và Customer refresh rồi CONFIRM ở POST; Technician settle sau khi đủ hai lời chứng. | 200/201; settle 200 khi guards hợp lệ, một success audit; old_pin_settled vẫn false. **Not Run**. Nếu stale/expired thì phải chặn, không đổi timestamp để thử lại. |
| POST REJECT | Dùng một fixture mới với effect/receipt hợp lệ; Customer hoặc Technician REJECT theo đúng stage; thử settle. | Lời chứng append-only, settle bị từ chối; không effect lần hai, giữ review/fence/holds. **Not Run**, cần phiên nhánh E mới riêng để không phá nhánh CONFIRM. |
| Successor hiện tại | Ở operation đã effect nhưng chưa consumed, chờ expiry thật, Technician yêu cầu successor inspection. Operator REINSPECT với ID successor; cả hai tab refresh rồi attest/CONFIRM successor; Technician settle chain. | RECONCILIATION_INSPECTION chỉ đọc, original receipt là lịch sử, không thêm effect. Ba current proofs đúng stage mới được consume chain. **Not Run**. Nếu operation đã settle thì cần fixture mới. |
| Durable no-effect closure | Ở một operation PRE khác CHƯA HANDOVER, chờ expiry, Technician yêu cầu closure. Operator CLOSE với ID predecessor. Refresh; sau Backend commit closure, operator ACK_CLOSURE. | NEVER_PREPARED và durable deny phải đủ. Chỉ ACK_CLOSURE sau receipt commit mới đóng local fence; 0 service effect, không release holds. **Not Run**, phải dùng nhánh riêng với history chưa effect. |
| Freshness/expiry/consumed/replay | Dùng từng nhánh riêng. Chờ expiry thật rồi refresh, kiểm disabled/rejected mutation. Với replay dùng cùng request identity từ Network, ghi số accepted proofs/audit trước/sau. | 409/422 theo code thực, không success giả, append-only. **Not Run**. Không dùng receipt đã stale làm happy path. |
| Ownership, ngoài trạm, revoke | Admin tạo tài khoản test phụ qua UI rồi kiểm Customer không sở hữu swap hoặc Technician không được assign trạm. Revoke dùng tài khoản fixture, giữ một Admin hợp lệ. | API 403/404 hoặc 401 phù hợp, không chỉ menu ẩn. **Not Run**; tài khoản phụ phải được cấp hợp lệ trước, hiện chưa tạo. |

Để dựng nhánh riêng tiếp theo sau khi kết thúc phiên này, tạo stop marker rồi chạy lại runner nhãn mới, schema/ledger mới:

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe tools/run_phase6_fix.py LABEL_MOI script tools/smoke_phase8a.py --branch E --manual-browser
```

Không chạy hai fixture staged đồng thời vì dùng chung 8030/8031/5180. Giữ toàn bộ runtime cũ. Đọc manual.json/private.json mới để lấy swap và credentials mới. Không tái dùng operation có REJECT, consumed, cancelled hoặc UNKNOWN để làm một ca dương khác.

### Đối soát và điểm dừng

Ghi kết quả Browser từng hàng bằng ảnh UI đã che credential, HTTP method/path/status/code, operation/stage/receipt, version và thời điểm. Đối chiếu DB read-only theo schema mới và SQLite mode=ro như hướng dẫn cuối tài liệu. Theo dõi payments, hai network battery holders, ba active resource_reservations, recovery case/operations/attestations và audit_events. Đọc command/service effect count, fence, deny records; EXECUTED không đồng nghĩa delivery. Snapshot mới do model thật tạo, không refresh receipt cũ.

Operator vẫn gửi heartbeat/snapshot theo telemetry_interval_seconds approved. Không tự polling action; chỉ xử lý các request file người dùng tạo. File result ngăn chạy lại cùng request; ledger vẫn là bảo vệ bền vững nếu crash trong khoảng trước khi ghi result. UNKNOWN/PREPARED không được reissue để ép thành công.

Dừng staged fixture bằng file rỗng .cache/p8-E-72062a0670/stop. Runner ghi fingerprint demo và giữ schema/ledger. private.json/state.json và raw logs không đưa vào Git. Bộ operator được kiểm bằng **25 targeted tests Passed**, gồm 6 ca tooling mới và 19 fence/closure, dùng SQLite thật + fixture HTTP; không tính là Browser hoặc E2E transport mới.

**Trạng thái hiện tại PARTIAL.** Adapter cho các stage đã có nhưng chưa có người dùng chạy Browser các nhánh trên và chưa có smoke real-process positive cho từng action operator mới. Cửa sổ 15 giây đòi hỏi phối hợp tab/operator; nếu không kịp, ghi Blocked/rejected đúng thực tế. Chưa xác nhận các Browser gates đạt.

Checklist trước Independent Acceptance: tất cả hàng bắt buộc có evidence Browser; role/ownership/revoke và response loss được kiểm; từng nhánh có DB/ledger trước-sau; duplicate/replay không thêm effect/audit; production hashes vẫn khớp snapshot full 587; phạm vi tooling mới có regression; mọi Major xử lý xong; Browser matrix được người dùng xác nhận. Independent Acceptance chỉ bắt đầu sau bước xem xét đó.

## Nhật ký hướng dẫn fixture PRE cũ, trước khi người dùng báo smoke

Ngày bàn giao 14/11/2026. Tại checkpoint cũ, fixture chỉ sẵn sàng cho login/read-only/expired-state và chưa có Browser Recovery flow Passed. Người dùng tự mở Chrome, nhập credentials và thực hiện mutation. Kết quả user-reported và fixture staged mới ở phần đầu tài liệu được ưu tiên.

## Phiên đang chạy

- Frontend http://127.0.0.1:5178/
- Backend http://127.0.0.1:8040
- Schema test phase5_test_f46737c22990.
- Swap 91c2590e-cba6-4c14-8b25-23633473fd0b.
- Operation PRE 36cdb526-73e5-4c5e-9619-cacf87d3e25c.
- Credentials chỉ trong .cache/customer-browser-533e8144c9/private.json. Đọc file cục bộ để lấy password; không chụp màn hình file hoặc đưa vào Git.
- Usernames admin, customer, technician. Chúng là tài khoản fixture mới, mật khẩu độc lập với demo.
- Runtime .cache/customer-browser-533e8144c9 chứa public.json, logs, inspection.sqlite3 và private.json. public.json không có password/token.
- Hai cổng bind 127.0.0.1. Tại kiểm tra bàn giao, listener API PID 27308, Vite PID 4988; public.json ghi PID launcher Python 23656. Vite proxy /v1 và /health tới 8040; proxy /health trả 200.

Runner --manual giữ Backend/Vite đến khi tạo stop marker, không còn tự tắt sau 900 giây. Operation TTL, session expiry, freshness 15 giây vẫn chạy bình thường. Simulator setup đã đóng sau khi tạo PRE inspection; không có service operator đang chạy. Proof ban đầu có thể stale/expired khi người dùng mở UI. Không có cam kết availability nếu Windows sleep, Docker dừng hoặc phiên chạy bị kết thúc. Kiểm lại /health trước mỗi đợt thao tác.

## Bắt đầu và lưu bằng chứng

1. Mở đúng URL frontend trên Chrome. So thanh địa chỉ với public.json, kiểm /health đạt trước login.
2. Mở DevTools → Network. Không xuất HAR nguyên bản vì có Authorization, login body và token. Chỉ ghi method, path, status, business code, thời điểm, operation và receipt reference đã che dữ liệu nhạy cảm.
3. Lấy password cho role cần kiểm từ private.json rồi đóng file. Đăng nhập bằng form ứng dụng.
4. Chọn Recovery, điền ID phiên ở trên, bấm “Tra cứu trạng thái Backend”.
5. Sau mỗi flow ghi kết quả Actual/Expected/Passed/Failed/Blocked/Not Run, role, schema, swap/operation, thời gian và ảnh UI đã kiểm không chứa credentials/token. Để ảnh vào thư mục evidence mới, không ghi đè ảnh cũ.
6. Đăng xuất trước khi đổi role. Không sửa dữ liệu tài khoản demo.

## Ma trận thao tác

Các HTTP dưới đây là expected theo contract, chưa được ghi Browser Passed. Nút bị disabled có thể không gửi request. Với dữ liệu stale, UI hoặc Backend phải chặn; không yêu cầu nó trả status của happy path.

| Flow và fixture | Các bước thủ công | Expected UI/HTTP và tiêu chí |
|---|---|---|
| Login/logout, cả ba role; fixture hiện tại | Đăng nhập, xem role, đăng xuất rồi thử tra cứu lại | Login POST /v1/auth/login 200, GET /v1/me 200. Logout 200; UI về login. Request cũ khi session revoked phải 401. Không đưa token vào ảnh. |
| Customer projection PRE; fixture hiện tại | Login customer → Recovery → tra cứu swap → đọc operation/context/stage/receipt → reload | GET /v1/swaps/{id} 200, stage PRE_ACTION_INSPECTION và accepted receipt reference khớp Backend. Fields serial/actor/recipient không phải input sửa tự do. Reload có thể cần login lại vì token chỉ ở memory; sau login phải lấy representation từ Backend. |
| Customer expired/stale; fixture hiện tại | Làm mới rồi kiểm nút CONFIRM/REJECT khi proof stale hoặc operation expired | Không báo mutation thành công giả. Nếu request được gửi, Backend phải từ chối theo code thực (409/422); ghi code Network. Operation chưa consumed, không có human success audit mới. |
| Customer PRE CONFIRM và REJECT dương; BLOCKED | Cần hai operation mới riêng, inspection actual mới sau khi Customer đã sẵn sàng. Bấm CONFIRM ở ca thứ nhất, REJECT ở ca thứ hai | POST confirmations 201; proof gắn đúng PRE receipt, nguồn CUSTOMER. Không dùng cùng operation để xác nhận ngược sau khi đã append-only. Runner hiện chưa hỗ trợ cấp fixture theo nhịp thao tác này. |
| Customer legacy; BLOCKED | Cần operation 0.1 mới qua workflow chuẩn rồi tra cứu và xác nhận | GET owner 200; confirmation 201 khi đủ proof/expiry. Không dùng ID PRE 0.2 thay fixture legacy. |
| Customer POST; BLOCKED | Cần action hợp lệ, durable accepted POST_ACTION_RECEIPT mới rồi mới click CONFIRM/REJECT trên hai ca riêng | Stage và receipt ID/hash chính xác. POST 201 khi hợp lệ; thiếu/nhầm receipt phải bị chặn. Một receipt không tự chứng minh Customer đã nhận vật thể. |
| Customer successor; BLOCKED | Cần predecessor đã effect và expired, successor chỉ đọc cùng current observation. Tra cứu rồi xác nhận theo stage | RECONCILIATION_INSPECTION đúng operation và current receipt; không tái dùng lịch sử như current proof. Chưa có fixture này trong phiên. |
| Technician read-only; fixture hiện tại | Login technician → Recovery → tra cứu → xem PRE/SIMULATOR receipt/context/expiry | GET /v1/swaps/{id}/recovery 200, UI biểu diễn đúng stage; không coi ACK là handover. |
| Technician attestation/INTENT/activation/settlement; BLOCKED cho happy path | Khi có fixture đúng stage còn mới, nhập ghi chú, serial thực tế đã kiểm và attestation. Sau ACK mới bấm activation; sau POST và hai human statements mới settle | Evidence 200, Customer confirmations 201, settle 200 chỉ khi đủ guards. Ghi expected_version và Idempotency-Key qua Network nhưng không chụp Authorization. UI không phát physical effect; operator simulator phải thực hiện riêng theo permit. Phiên hiện tại không cấp action tự động. |
| ER-02 closure; BLOCKED | Cần expired operation NEVER_PREPARED thật và simulator còn có thể ghi deny/receipt. Sau đó dùng control closure | Chỉ closure intent không chứng minh fence đã đóng. Cần receipt Backend commit và simulator acknowledgment. Không dùng expiry/missing receipt/PREPARED/UNKNOWN làm no-effect. Phiên hiện tại thiếu operator closure. |
| Admin RBAC; fixture hiện tại | Login admin → Recovery → tra cứu; đối chiếu nút và thông báo | GET recovery 200; chỉ xem, không có quyền attest/settle thay Technician. Không coi menu ẩn là đủ RBAC; negative API cần bằng chứng request thật và 403. |
| Đổi principal/responsive; fixture hiện tại | Customer tra cứu → logout → Admin/Technician login → xem dữ liệu đã reset. DevTools device toolbar kiểm 390px và desktop | Không giữ dữ liệu private từ principal trước. Không tràn/mất nút quan trọng; ghi viewport và ảnh. Chưa thực hiện trong lượt chuẩn bị. |
| Ownership/out-of-station/duplicate/version/network error; BLOCKED một phần | Cần Customer thứ hai, Technician ngoài trạm và hai context/version hợp lệ; dùng các fixture riêng | 403/404 khi trái quyền theo endpoint; VERSION_CONFLICT 409 phải refresh, không retry bằng version cũ. Double click không thêm proof/audit. Khi Network offline, không báo success hoặc tự gửi lại action. Phiên hiện chỉ có một Customer và Technician S01, chưa đủ negative fixture cho mọi nhánh. |

## Đối chiếu DB/audit/effects

Ghi snapshot trước và sau bằng kết nối read-only trên đúng schema test trong public.json. Không dùng Database demo. Kiểm recovery_cases (version, old_pin_settled, state), recovery_operations (context/stage, consumed_at/cancelled_at), recovery_attestations (operation_id, stage, source_kind, reference_receipt_id), payments, resource_reservations và audit_events theo swap/case. Technician GET recovery và Customer GET swap là các view được phân quyền; không sao chép raw proof nội bộ vào báo cáo Customer.

Trong ledger fixture inspection.sqlite3, mở SQLite ở mode=ro để xem service_operations, recovery_station_fence và recovery_action_ledger. Đối chiếu effects theo operation. PRE inspection phải effect=0. Khi chưa terminal guard, custody/Payment/ba holds phải giữ đúng theo contract. POST/closure/successor cần ledger riêng được workflow hợp lệ tạo; không tự chèn hoặc sửa ledger.

Quy tắc chấm: Passed chỉ khi đã click thật, có UI/HTTP đúng và DB/effect đúng khi cần. Failed khi actual khác expected trên fixture hợp lệ. Blocked khi chưa có fixture/receipt/operator hoặc môi trường không hoạt động. Không ghi Passed cho mutation chỉ từ build/API-only/SSR.

## Giới hạn và dừng môi trường

Full bộ fixture yêu cầu chưa hoàn tất. Cần bổ sung runner theo stage với thao tác operator do người dùng chủ động yêu cầu, current model observation, durable ledger và readiness signal trước khi cấp proof. Không làm mới timestamp cũ, kéo dài expiry/freshness, tự CONFIRM thay người dùng hoặc ép custody bằng SQL. Chưa có fixture POST/successor/closure dương ổn định để nghiệm thu thủ công toàn cổng.

Để dừng đúng phiên này, tạo file rỗng .cache/customer-browser-533e8144c9/stop bằng File Explorer hoặc PowerShell. Runner sẽ dừng các child do nó tạo và ghi result.json chứa demo fingerprint check. Giữ nguyên thư mục, schema, ledger và evidence. Không xóa private.json trong lượt này; file nằm trong .cache ignored, không đưa vào Git.

Không chạy Computer Use, Browser automation hoặc Independent Acceptance trong lượt chuẩn bị này. Browser Recovery vẫn chưa có flow Passed.
