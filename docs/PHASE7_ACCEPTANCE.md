# Nghiệm thu độc lập Phase 7 — 28/10/2026

## Kết luận cập nhật 29/10/2026 — hoàn tất các hạng mục còn thiếu

### Chốt bàn giao Git — 29/10/2026

Người dùng đã chấp thuận kết luận PASS trong phạm vi kiểm chứng và yêu cầu commit riêng bản sửa/acceptance coverage. Hai giới hạn Browser bên dưới tiếp tục có hiệu lực. Bằng chứng raw giữ local, không đưa hàng loạt vào Git. Có thể tái hiện từ source đã commit, tại workspace đã chuẩn bị `.env`, `.venv` và PostgreSQL theo README (không dùng schema demo cho fixture):

```powershell
$env:TEST_REPORT_ROOT='PHASE7_TESTS'
# Mỗi lần chọn LABEL mới, runner từ chối ghi đè thư mục bằng chứng đã có.
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_deadline pytest tests/test_phase7_acceptance.py tests/test_phase7_deadline.py tests/test_phase7_postfix_acceptance.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_full pytest tests
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_e2e script tools/smoke_phase7.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_missing script tools/smoke_phase7.py --scenario missing-pickup
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_restart script tools/smoke_phase7.py --scenario restart-between
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_return_time script tools/smoke_phase7_deadline.py --step return
.\.venv\Scripts\python.exe tools/run_phase6_fix.py verify_p7_pickup_time script tools/smoke_phase7_deadline.py --step pickup
```

Chạy tuần tự, giữ trống ports8020–8022; các script tạo schema PostgreSQL riêng và ledger test mới, giữ lại để điều tra, không reset demo/volume. Để kiểm tra Browser, thêm `--serve` vào scenario phù hợp; Vite chạy với `DEV_API_TARGET=http://127.0.0.1:8020`. Runner ghi đường dẫn `.cache/phase7_*/connection.json` chứa credential fixture: chỉ đọc local, tuyệt đối không commit/chia sẻ. API RBAC: `python tools/check_phase7_browser_rbac.py .cache/phase7_<run>/connection.json` khi fixture còn chạy. Kết thúc bằng tạo file `STOP` trong đúng thư mục fixture; runner tự dừng child do nó tạo. Không xóa ledger/schema. Các lệnh trên là hướng dẫn tái hiện, không phải kết quả chạy mới trong lượt chuẩn bị commit.

**PASS trong phạm vi nghiệm thu kỹ thuật Phase 7 đã giao; đề xuất người dùng chốt nghiệm thu với các giới hạn Browser bên dưới.** Không có Blocker/Major chưa xử lý được xác nhận. Đây không phải tuyên bố mọi Browser workflow hoặc mọi crash window đã Passed. Các kết luận CHƯA ĐẠT/Not Run ở phần lịch sử phía dưới được giữ nguyên và được thay thế bởi ma trận cập nhật này cho những ô có bằng chứng mới.

### Ma trận cuối và nguồn bằng chứng

| Nhóm | Kết quả | Bằng chứng |
|---|---|---|
| P7-A01, return/pickup deadline | Passed kế thừa | Hai probe gốc; targeted40; deadline20; không sửa expected/skip/xfail |
| Full Phase1–7 | 415 Passed,0 Failed,0 Errors,0 Skipped;910.566s | Đọc lại XML p7a01_full_03; không chạy lại |
| E2E sau sửa | 17 checks Passed kế thừa | acceptance_postfix_e2e_01 |
| Real-time deadline return/pickup | Passed kế thừa | p7a01_realtime_return_01/pickup_01;60s thật, evidence vẫn mới, review/custody/holds/payment đúng |
| Hai independent probes | 2 Passed kế thừa | acceptance_postfix_probes_02; không cộng vào415 |
| Thiếu pickup sau return | 4 checks Passed | remaining_pickup_02: return custody bền vững, pin cấp chưa giao,3holds,Payment SUCCEEDED,không completion audit; ledger effects0/1 |
| Restart đúng sau return commit | 5 checks Passed | remaining_restart_01: checkpoint RETURN_ACCEPTED/1command/3holds; sau restart COMPLETED,1return audit/1completion audit/1charge |
| Browser AWAITING_PICKUP/payment độc lập/timeout review | Passed từ lượt Browser ngay trước gián đoạn | remaining_browser_evidence/pickup.png,mobile.png,review.png; fixture6ae3ff3ff9. Review được quan sát sau reload/login, không dùng bằng chứng này để khẳng định auto-poll transition |
| Browser COMPLETED | Passed chạy mới | completed_resume.txt; Customer nhìn thấy hai mốc trả/nhận pin; E2E kiểm custody và hai command OBSERVED trước Browser |
| Browser Admin/Technician | Passed phạm vi đọc/menu | admin_resume.txt,technician_resume.txt; Admin xem phiên; Technician không có menu QR/reservation |
| API RBAC trực tiếp | 7 checks Passed chạy mới | rbac_resume.json: GET /v1/swaps/{id}:Customer/Admin200,Technician403 FORBIDDEN; GET /v1/users:Admin200,Customer/Technician403 FORBIDDEN; anonymous swap401. Không dựa vào menu để kết luận bảo mật |
| Mobile cơ bản | Passed giới hạn | 390x844, DOM scrollWidth375<=390; đã xem ảnh mobile.png, nội dung pickup/payment hiển thị trong cột, không tràn ngang. Không suy ra mọi thiết bị/viewport |
| Browser thông báo riêng sai pin | Chưa xác minh; Not Run đối với assertion thông báo chuyên biệt | wrong_return_resume.txt: khi mở đã là REVIEW_REQUIRED/DEVICE_OFFLINE, không phải COMMAND_OBSERVATION_MISMATCH. Generic review và không báo hoàn tất đã quan sát; không gán Passed cho thông báo sai pin |
| Full Browser QR→Reservation→Consent | Not Run | Fixture đã thực hiện phần này bằng HTTP. UI không giữ Device-Key; bước xác minh thuộc adapter. Chưa chạy Browser cùng adapter từ đầu; không thêm nút/API ngoài hợp đồng |
| Validator/hash/dependencies/build | Passed kế thừa | p7a01_VALIDATION và báo cáo sửa; không chạy lại vì không đổi production/dependency |

Lượt tiếp tục này còn chạy hai fixture để phục hồi Browser: `remaining_browser_completed_03` và `remaining_browser_wrong_02`, **mỗi lượt4 checks Passed,exit0,demo_unchanged=true**. Đây là kiểm chứng fixture phục vụ Browser, không cộng vào415 hoặc17. `remaining_browser_completed_02` thất bại setup trước fixture vì PostgreSQL đang recovery; log được giữ, không phải test nghiệp vụ Failed. Docker Desktop được khởi động lại, PostgreSQL tự recovery tới accepting connections, không reset volume. Browser cũ không còn tab, Backend/worker cũ đã dừng. Screenshot mới không chụp được (Unable to capture screenshot); đã lưu DOM thực tế, không giả ảnh.

### Review nguồn, test-only và thời gian quyết định

FR11/UC10/TC11, BR04/05/06; nhánh FR12/TC12; AD-02b, SM-03a/03b, INVARIANTS4–6 và phê duyệt ACK15/physical60/freshness15 vẫn là nguồn nghiệp vụ. Không thay baseline. Bản sửa production duy nhất đang tồn tại vẫn là swaps.py từ lượt sửa P7-A01, SHA256 `FC83F25683855D2800A1A41AE2D0462DE02119FD60A0AE02A8EB738896B1E7D2`; lượt nghiệm thu này không sửa nó.

Guard cuối kiểm cùng clock sau các đọc evidence, trước writes custody dưới khóa; physical deadline từ created_at không gia hạn bởi ACK/restart. SQL writes/audit/release cùng transaction, lỗi rollback. Commit có thể xảy ra sau deadline nếu quyết định hợp lệ trước đó; hợp đồng được chốt là deadline tại custody decision, không có yêu cầu commit-before-deadline tuyệt đối. Không tự bổ sung chính sách khác hoặc khẳng định bảo đảm realtime của DB.

`tools/phase7_acceptance_process.py` chỉ được `tools/smoke_phase7.py` gọi cho hai scenario acceptance. Tìm tham chiếu trong services/simulators không có import/activation production. Wrapper worker mở session đọc trạng thái đã commit rồi đóng session trước checkpoint; runner xác nhận RETURN_ACCEPTED/custody/holds trước khi dừng chính worker test và khởi động worker thật. Wrapper simulator chỉ ACK-only OPEN_SUPPLY trong fixture missing-pickup; không sửa evidence, timeout hoặc custody. Pipeline thật vẫn xử lý Inbox/ledger. Default bốn scenario của runner giữ nguyên. Test API mới chỉ login và GET, không in/lưu credentials, không thay dữ liệu nghiệp vụ.

Không phát hiện lỗi nghiệp vụ mới. Giới hạn UI review_reason hiện tại có thể phản ánh offline đến sau sai pin; chưa xác minh thông báo sai pin trước thời điểm offline trong Browser, không suy diễn đã mất lịch sử audit hoặc gán thêm Major. Không có bằng chứng cho toàn bộ tải dài hạn, mọi crash window hoặc tự động cập nhật UI qua mọi transition.

### File bàn giao và bảo toàn

Đề xuất đưa vào commit sau khi người dùng duyệt (không commit trong lượt này):
- `services/backend/app/application/swaps.py` — bản sửa P7-A01 có sẵn.
- `tests/test_phase7_acceptance.py`, `tests/test_phase7_deadline.py`, `tests/test_phase7_postfix_acceptance.py` — giữ probes gốc, boundary/concurrency và integration mới.
- `tools/smoke_phase7_deadline.py`, `tools/smoke_phase7.py`, `tools/phase7_acceptance_process.py`, `tools/check_phase7_browser_rbac.py` — runners/test-only cần tái hiện.
- `docs/PHASE7_P7_A01_FIX.md`, `docs/PHASE7_ACCEPTANCE.md`, `docs/IMPLEMENTATION_STATUS.md` — báo cáo và lịch sử nguyên vẹn.

Giữ bằng chứng gốc independent_deadline và p7a01, các acceptance_postfix, remaining_pickup/restart/browser cùng XML/log/ảnh/JSON để người dùng quyết định lưu trữ; không stage hàng loạt artifact trong commit source. Không commit .cache/connection.json (có credential fixture), .env, .local ledger, .vs, dist, node_modules, .venv, DB, logs/screenshot/JSON trung gian. Không xóa bất kỳ file/schema/ledger nào. Các fixture mới kết thúc bằng STOP marker, runner chỉ dừng child của chính nó; Vite test đã dừng. Docker/PostgreSQL được giữ chạy. Hai runner mới xác nhận fingerprint demo không đổi.

Git vẫn main ahead origin/main1, HEAD81ade59; tracked modified: swaps.py,tools/smoke_phase7.py,docs/IMPLEMENTATION_STATUS.md. Report/tests/runners mới vẫn untracked cùng bằng chứng cũ; `git diff --check` sạch (chỉ cảnh báo CRLF→LF). Không stage/commit/push/Phase8.

Tự kiểm tra: fixture riêng → Customer → “QR/RFID và giữ tài nguyên” → “Tiến trình đổi pin mô phỏng”. AWAITING_PICKUP chỉ có mốc trả; timeout REVIEW_REQUIRED giữ tài nguyên; COMPLETED phải có hai mốc được Backend xác nhận. Admin đọc phiên; Technician bị API từ chối đọc swap. Không dùng dữ liệu demo để tạo lỗi và không nhập Device-Key vào UI. Các mục Browser bổ sung Not Run nêu trên là ngoại lệ công khai, không được đổi thành Passed khi chốt biên bản.

---

## Bổ sung sau sửa P7-A01 — 28/10/2026

Phần dưới mục này là báo cáo lịch sử trước sửa, được giữ nguyên. HEAD81ade59, bản sửa swaps.py chưa commit. Lượt này không sửa source nghiệp vụ, không chạy lại full415.

### Ma trận bằng chứng

| Nhóm | Bằng chứng hợp lệ | Trạng thái và phần còn thiếu |
|---|---|---|
| P7-A01 / decision deadline | p7a01_full_03 XML415/0/0/0; targeted40;20deadline tests | Passed kế thừa, hai probe gốc nguyên vẹn |
| Return/pickup real deadline | p7a01_realtime_return_01 và pickup_01:60.35/60.43s, freshness7.15/7.23s | Passed kế thừa; REVIEW_REQUIRED, custody/3holds/Payment bảo toàn |
| Custody/state machine | test_phase7 + mới test_return_custody_survives_missing_pickup_and_reservation_expiry | Passed; đã trả pin nhưng thiếu pickup không release/complete; expiration không lấy lại holds của swap đang bàn giao |
| Concurrency/idempotency | full415:hai worker, timeout/evidence, rollback, reservation conflict; E2E hai Backend consent | Passed trong phạm vi có test; chưa có E2E restart đúng sau return commit và trước OPEN_SUPPLY |
| Payment–Swap | mới test_late_payment_callback_does_not_reopen_completed_swap | Passed; callback SUCCEEDED/PENDING/FAILED sau COMPLETED không mở lại phiên, không thêm command, Payment không đổi |
| IoT ordering/correlation | full415 gồm P4/P5 ordering, P7chain/ACK/replay | Passed kế thừa; không tuyên bố đã thử mọi crash window |
| Real-process E2E sau sửa | acceptance_postfix_e2e_01:17checks/4scenarios | Passed chạy mới:physical,ack-only,wrong-return,crash-after-ledger |
| Browser sau sửa | Review tĩnh SwapProgress.tsx:state/review_reason từ Backend | Not Run browser mới, mobile, full UI QR→consent→swap; review source không thay Browser Passed |
| API RBAC | full415 có ownership/role/session tests | Passed kế thừa; chưa thêm Browser truy cập trực tiếp route trái quyền |
| Validators/build/dependencies | p7a01_VALIDATION và báo cáo sửa | Passed kế thừa, không chạy mới |

### Review decision → commit

Nguồn: AD-02b, SM-03a/03b, INVARIANTS4–6, phê duyệt ACK15/physical60 từ created_at/freshness15. Bản sửa kiểm cùng một clock sau các đọc DB, ở cả return và pickup; command deadline không dịch theo ACK/retry/restart. Các writes pin/state/audit/holds cùng transaction, giữ station/user/resource locks và không gọi provider/HTTP sau guard.

Yêu cầu sửa P7-A01 đã chốt kiểm tại **quyết định custody (A)**; chưa tìm thấy quy định commit bắt buộc hoàn tất trước deadline tuyệt đối (B). DB scheduling/commit có thể qua mốc sau quyết định hợp lệ; không chỉ từ khả năng này gán Blocker. Chưa có probe chứng minh hậu quả nghiệp vụ của một commit muộn sau quyết định hợp lệ. Không đổi policy. Nhánh review bảo toàn custody/Payment/holds; command OBSERVED không tự đồng nghĩa custody được phép chuyển.

### Kết quả chạy mới

- `acceptance_postfix_e2e_01`: exit0, **17 checks Passed**. Backend8020/8021, Payment Provider8022, Payment/Device workers và hai simulator trên schema test riêng. Happy path custody hai pin/COMPLETED/release đúng; ACK-only không trả pin; sai pin review; restart worker sau command creation. Ledger provider một charge, mỗi command effects≤1; fingerprint demo không đổi. Bốn scenario này chưa bao phủ E2E thiếu pickup và restart giữa hai bước. Probe PG mới bao phủ thiếu pickup nhưng không thay thế E2E đó.
- `acceptance_postfix_probes_01`:1Passed/1Failed do UUID trong dữ liệu PostgreSQL không JSON serializable trước khi gửi callback. Lỗi test harness, chưa tới endpoint; giữ log/XML. Sửa duy nhất jsonable_encoder(payload), không đổi assertion/expected result.
- `acceptance_postfix_probes_02`:**2Passed/0Failed/0Errors/0Skipped**,exit0,7.00s. File `tests/test_phase7_postfix_acceptance.py`. Không cộng thành full417 vì chưa chạy chung suite; full415 là kết quả kế thừa hợp lệ.

Không phát hiện Blocker/Major mới trong các kiểm tra đã thực hiện. P7-A01 đã đạt kiểm chứng. **Chưa chốt nghiệm thu toàn bộ Phase7**: Browser tương tác/mobile, E2E thiếu evidence pickup và restart đúng giữa hai bước còn Not Run. Đây là khoảng trống kiểm chứng, không phải lỗi nghiệp vụ đã xác nhận hoặc hạn chế môi trường đã chứng minh. Cần hoàn tất các ô này trước kết luận đạt toàn bộ.

### Bảo toàn và bàn giao

Giữ regression mới test_phase7_postfix_acceptance.py, hai probes gốc, test_phase7_deadline.py, runner deadline, toàn bộ historical independent_deadline/p7a01 và ba thư mục acceptance_postfix_* mới. E2E báo cáo schema/ledger/log trong E2E_RESULTS.json; không xóa schema, .local, .cache hoặc bất kỳ dữ liệu demo. Chỉ bổ sung báo cáo này, tiến độ và test mới; source P7-A01 giữ nguyên. Git main ahead1 với thay đổi chưa commit và untracked cũ; không stage/commit/push/Phase8.

Tự kiểm tra UI bằng fixture an toàn: đăng nhập Customer → “QR/RFID và giữ tài nguyên” → quan sát “Tiến trình đổi pin”; AWAITING_RETURN/ACK chưa trả pin, AWAITING_PICKUP chưa hoàn tất, COMPLETED chỉ theo server, REVIEW_REQUIRED vẫn giữ tài nguyên. Đối chiếu GET/v1/swaps/{id} và /payment bằng cùng user; payment SUCCEEDED riêng không chứng minh custody. Sai pin hiển thị thông báo khi review_reason=COMMAND_OBSERVATION_MISMATCH. Không dùng demo chính để phát lỗi; không reset login counters. Các hướng dẫn này chưa được đánh dấu Browser Passed trong lượt này.

---

**CHƯA ĐẠT. Phát hiện P7-A01 (Blocker): deadline vật lý không được kiểm lại tại quyết định custody. Cuộc nghiệm thu chưa bao phủ hết danh sách yêu cầu; không đủ điều kiện chuyển Phase8.**

HEAD81ade59; source nghiệp vụ không sửa.81 file untracked trước nghiệm thu được giữ. Nguồn đối chiếu: AD-02b, INVARIANTS mục4–6, FR11/UC10/TC11 BR04/05/06, nhánh FR12/TC12; phê duyệt ACK15s/physical60s từ created_at/freshness15s. Không thay baseline.

## Kết quả chạy mới

| Nhóm | Kết quả |
|---|---|
| independent_deadline_01 |1Passed/19Errors setup: Docker chưa chạy; chưa đánh giá nghiệp vụ PostgreSQL|
| independent_deadline_02 |18Passed/2Failed/0Errors/0Skipped;28.59s|
| Hai probe mới |2Failed: return và pickup|
| Hồi quy tests/test_phase7.py |18Passed trong cùng lượt|
| Full393, E2E17/12/5/8/8, HTTP28, Browser/build/validators |Bằng chứng triển khai lịch sử, không chạy mới trong nghiệm thu này|
| E2E độc lập trì hoãn thật, Browser độc lập, concurrency bổ sung, full regression độc lập |NotRun|

## P7-A01 — deadline TOCTOU tại custody

Probe `tests/test_phase7_acceptance.py::test_physical_deadline_rechecked_at_custody[return]` và `[pickup]` sử dụng fixture PostgreSQL mới, rollback per-test. Tạo QR/reservation/consent/payment qua helper có sẵn; command được dispatch và ACK hợp lệ. Fixture đặt created_at cách thời điểm xử lý command50s, expires_at=created+15. Không thay policy. Event physical mới gửi POST/v1/device/events, trả202 inbox. Tại service custody, đồng hồ kiểm thử là created+61s; evidence vẫn mới khoảng11s nên freshness15s không thể thay deadline60s.

Expected: không chuyển custody hoặc hoàn tất khi bước xử lý đã vượt deadline; giữ tài nguyên và đi review/timeout theo hợp đồng. Actual đọc PostgreSQL trong transaction fixture:
- return: battery CUSTOMER→COMPARTMENT, swap RETURN_ACCEPTED.
- pickup: battery COMPARTMENT→CUSTOMER, swap COMPLETED.

Assertion kiểm custody thất bại trước assertion holds; chưa dùng lượt này để khẳng định riêng số holds sau lỗi. Source completion có release nhưng cần probe bổ sung xác nhận audit/release cụ thể. Provider ledger không nằm trong probe này; Payment dùng transport fixture, PostgreSQL thật.

Nguyên nhân: `services/backend/app/workers/device.py::command_event` kiểm deadline bằng clock ban đầu. `services/backend/app/application/swaps.py::proof`, `physical_context`, `advance` đọc lại clock/freshness nhưng không kiểm `command.created_at + physical_step_timeout_seconds` ở điểm quyết định cuối. Transaction/lock không ngăn thời gian trôi qua. Cả hai nhánh custody dùng đường này. Đây là mô phỏng deterministic của chậm xử lý trong transaction, chưa chứng minh bằng sleep/process E2E thực; giữ giới hạn này rõ ràng.

Đề xuất nhỏ nhất cho lượt sửa: kiểm deadline command tại quyết định cuối trước custody/transition dưới cùng khóa, cùng với freshness; quá hạn phải bảo toàn custody/holds và lưu review/evidence phù hợp. Không gia hạn60s hoặc dùng received_at thay created_at. Bổ sung boundary59.999/60/60.001, delayed worker thật, audit/holds/rollback và race timeout trước khi đóng blocker. Chưa sửa source.

## Review các vùng liên quan và phần chưa hoàn tất

AD-02b được thể hiện bằng hai transaction custody; inbox/closing evidence và audit cùng transaction, bước RETURN_ACCEPTED bền vững, nhánh review giữ tài nguyên. 18 regression đã chạy kiểm happy path, thiếu chain, sai pin, BMS pin cấp, ACK, replay, rollback, concurrency và cửa sổ ACK; các kết quả này không phủ timing gap mới.

Thay đổi test P6-A03 phù hợp phần tích hợp Phase7: cho phép0 hoặc1 OPEN_RETURN do thứ tự hai worker --once; vẫn kiểm đúng swap/kind/QUEUED/no evidence, AWAITING_RETURN/no timestamps, custody chưa đổi,3holds và một PAYMENT_SUCCEEDED audit. Không skip/xfail. Chưa chạy lại riêng test này trong nghiệm thu độc lập.

Còn phải nghiệm thu độc lập: source review đầy đủ Payment/outbox/ledger, identity/boot/replay, mọi timing boundary, hai process cạnh tranh, rollback sau release, E2E tám kịch bản, Browser trực tiếp URL/API, validators/build mới. Không coi các mục này Passed từ kết quả lịch sử. Báo cáo này là kết quả một phần có blocker xác nhận, không phải hoàn tất toàn bộ ma trận nghiệm thu.

## Bằng chứng và bảo toàn

Giữ `tests/test_phase7_acceptance.py` làm failing regression; giữ `docs/PHASE7_TESTS/independent_deadline_01/` và `independent_deadline_02/` (run.log/results.xml/report fixture). Runner tái sử dụng run_phase6_fix.py với TEST_REPORT_ROOT=PHASE7_TESTS, không tạo runner trùng. Không xóa artifact hoặc schema; không sửa demo, không reset volume/.local. Chỉ tạo báo cáo này, probe và cập nhật tiến độ. Không commit/push/Phase8.
