# Phase 7 — Battery Swap Transaction

Ngày 27/10/2026, Asia/Bangkok. Base thực tế `d0abfd3` (đã đồng bộ origin/main). Tiếp tục source đang dở, không xây dựng lại Phase 1–6. Kết quả cuối đã đối chiếu ngày 28/10/2026; các lượt lỗi trước được giữ làm lịch sử.

## Phạm vi và nguồn

Nguồn: AGENTS, START_HERE, CODEX_HANDOFF, QD01–09 approved, AD-02a/02b, SM-03a/03b, ERD-02, schema và INVARIANTS. Không sửa bộ thiết kế gốc.

| Phạm vi | Truy vết |
|---|---|
| Nhận pin cũ, cấp pin mới, hoàn tất | FR11 / UC10 / TC11, BR04/05/06, AD-02b |
| Lỗi/timeout, giữ tài nguyên để review | Phần FR12 / UC10 / TC12; chưa thực hiện refund/settle Phase8 |
| Đọc trạng thái/lịch sử đúng chủ | FR13 / UC11 / TC13, API đã có |
| Tài nguyên và evidence | BR01/02/10/11; tích hợp FR07, FR17/19 và Phase4–6 |

Không có endpoint mở cửa hoặc complete công khai trong OpenAPI. Không tạo endpoint mới. Customer theo dõi phiên của mình; Admin đọc các phiên; Technician tiếp tục chỉ xem dữ liệu thiết bị/phạm vi trạm được giao, không được API swap cho phép chỉ vì có giao diện.

## Luồng và transaction

1. Worker tìm phiên `AWAITING_RETURN`, kiểm Payment SUCCEEDED, consent, số tiền/tiền tệ, đúng ba hold, trạm/ngăn/pin và evidence.
2. Ghi `OPEN_RETURN` vào `device_commands` bền vững. Poll/ledger cũ chịu trách nhiệm dispatch và chống tác động lặp; không gọi HTTP trong lock.
3. Chuỗi cùng device/boot/swap/command/ngăn: DOOR OPEN → PRESENCE đúng serial → DOOR CLOSED. ACK không đủ.
4. Trong transaction xử lý closing event: accepted inbox/projection/command evidence, pin cũ chuyển từ CUSTOMER vào ngăn nhận và bỏ holder, `return_observed_at`, `RETURN_ACCEPTED`, audit. Lỗi SQL/audit rollback cùng nhau; inbox giữ lại để xử lý lại.
5. Worker tiếp tục từ state bền vững, kiểm lại pin cấp BMS/alert/family/lifecycle, ngăn nhận đã giữ pin cũ, cửa/evidence còn hiệu lực. Ghi `OPEN_SUPPLY` và `AWAITING_PICKUP` cùng commit.
6. Chuỗi mở cửa → pin cấp không còn trong ngăn → đóng cửa hợp lệ: cùng transaction chuyển pin mới cho Customer, `pickup_observed_at`, `COMPLETED`, `closed_at`, giải phóng ba hold và audit. Không thay lifecycle thành IN_SERVICE tự động.
7. NACK/UNKNOWN/timeout/pin sai/mất evidence/điều kiện đổi: `REVIEW_REQUIRED`, giữ holds, tạo recovery case và audit. Không tự refund, release hoặc cấp pin khác. Recovery case chỉ là đầu vào Phase8, chưa có workflow đối soát mới.

Khóa PostgreSQL: station advisory → users → swaps → slots UUID → batteries UUID, bao gồm pin cũ đang do khách giữ. Hai worker/các API dùng cùng station lock; unique command(swap,kind) và resource uniqueness giữ nguyên. Không dùng mutex in-memory. Retry55P03/backoff của Phase6 giữ nguyên; hết budget vẫn dừng có log.

Custody pin trả theo INVARIANTS §4 dựa trên chuỗi bằng chứng, serial/family/holder. Không áp ngưỡng SOC/SOH cấp pin để từ chối pin trả, không biến BMS seed chưa xác minh thành bằng chứng. BMS pin cấp vẫn phải đủ/đã xác minh/fresh. BMS lỗi/alert tiếp tục đi nhánh review; không tự phục hồi pin.

## Quyết định thời gian được người dùng xác nhận trong lượt này

Người dùng đã chấp thuận diễn giải hai mốc approved: nhận/ACK lệnh trong15 giây; **sau ACK hợp lệ**, bằng chứng vật lý được chờ tối đa60 giây tính từ lúc tạo lệnh. Evidence vẫn phải mới tối đa15 giây. Lệnh chưa ACK không được tự kéo dài hạn. Đúng deadline được coi là hết hạn. Không đổi giá trị QD hoặc baseline.

Command tạo lúc đồng hồ ứng dụng hiện tại, không dùng thời điểm bắt đầu transaction của PostgreSQL làm thời điểm tạo. Kiểm cuối trước enqueue/poll/transition dùng đồng hồ sau các đọc DB, cả received_at và observed_at/measured_at. Bản sửa BMS/door ordering giữ nguyên: timestamp giảm/bằng nhau không bị seq cao hơn vượt qua.

E2E phát hiện simulator trên Windows đôi lúc phát PRESENCE và DOOR CLOSED cùng timestamp. Backend từ chối đúng EVENT_OUT_OF_ORDER. Simulator nay đợi đồng hồ thật tiến thêm, tối đa1 giây với sleep1ms; clock không tiến thì fail closed, không tự cộng timestamp tương lai. Ledger cũ được giữ.

## API và Frontend

- GET `/v1/swaps`, `/v1/swaps/{swap_id}`: trạng thái server, evidence timestamps và review_reason; Customer đúng chủ/Admin.
- GET `/v1/swaps/{swap_id}/payment`: thông tin thu phí riêng, không phải bằng chứng bàn giao.
- GET `/v1/device/commands`, POST `/v1/device/events`: Device-Key và correlation/validation hiện có; 202 inbox chưa có nghĩa đã hoàn tất.
- QR/RFID, reserve, consent, cancel giữ API/idempotency của Phase5–6; cancel sau thu không được tự giải phóng.

`SwapProgress` trong màn hình QR/RFID và giữ tài nguyên giải thích AWAITING_RETURN, RETURN_ACCEPTED, AWAITING_PICKUP, COMPLETED và REVIEW_REQUIRED; chỉ hiển thị hoàn tất theo Backend. Có thông báo pin sai, evidence thiếu/hết hạn, pin cấp không còn đủ điều kiện và timeout. Payment text được sửa để không nói “chưa bàn giao” khi phiên đã COMPLETED. Không thêm nút điều khiển cửa.

## Database, dependencies và file

Không migration mới; tái sử dụng Alembic head0002, device_events/commands, batteries, compartments, swap_transactions, resource_reservations, recovery_cases, audit. Không cài dependency, không seed/migrate schema demo.

- Mới: application/swaps.py; apps/web/src/SwapProgress.tsx; tests/test_phase7.py; tools/smoke_phase7.py; báo cáo này.
- Sửa: application/device.py (guard lúc dispatch, created_at); workers/device.py (locks, custody/inbox atomic, orchestration, timeout, review audit); simulator main.py (clock, wrong-return); Reservations.tsx, Payment.tsx; run_phase6_fix.py (chọn thư mục báo cáo Phase7); IMPLEMENTATION_STATUS.md.
- `.vs/` là file untracked của môi trường người dùng, giữ nguyên và không commit.

## Kiểm thử và bằng chứng

Các suite PostgreSQL chạy tuần tự trên schema riêng; không chạy đồng thời bộ dùng trùng advisory keys. Runner tái sử dụng `tools/run_phase6_fix.py`, đặt `TEST_REPORT_ROOT=PHASE7_TESTS` để không ghi đè bằng chứng Phase6. Mỗi label mới chỉ được tạo một lần.

| Lượt | Kết quả thực tế |
|---|---|
| targeted_02 (lượt trước) |6 Passed, kết quả lịch sử |
| resume_targeted_01 |6 setup errors: Docker chưa chạy; chưa kiểm nghiệp vụ |
| resume_targeted_02 |6 Passed mới sau mở Docker/container existing |
| targeted_03 |12 Passed/2 Failed: query test rollback đếm nhầm 10 seed event chưa xác minh; sửa scope query theo swap và pending thật |
| targeted_04 |17 Passed, gồm rollback/replay/concurrency/timing/clock |
| e2e_01 |Failed happy path, simulator timestamp bằng nhau; giữ bằng chứng |
| e2e_02 |Failed vì port giữa scenario chưa đóng kịp; thêm bounded wait, không kill tiến trình lạ |
| e2e_03 |17 checks Passed, 4 scenario: physical/ack-only/wrong-return/crash-after-ledger; demo fingerprint không đổi |
| full_02 |393 Passed, 0 Failed, 0 Errors, 0 Skipped; 375 hồi quy + 18 Phase7; XML và exit0 đã xác minh |
| Validators/hash/dependencies/build |Passed mới; Browser sẽ báo riêng |

Không cộng targeted vào full hoặc cộng số check E2E thành pytest. Không thay expected nghiệp vụ để che Failed. Luồng rollback mới kiểm riêng pin cũ và pin mới; hai worker dùng kết nối PG riêng; E2E có hai HTTP backend cạnh tranh consent, provider ledger1charge và command effects≤1.

Lượt full_01 đã kết thúc: **391 Passed,1 Failed,0 Errors,0 Skipped**, tổng392 (375 cũ+17 Phase7). Failed là `test_payment_and_device_processes_recover_same_schema` giữ assertion Phase6 `device_commands==0`. Với Phase7, Device worker hợp lệ có thể enqueue OPEN_RETURN khi Payment worker đã settlement trước nó; thứ tự ngược lại để tick sau enqueue. Ca này vẫn kiểm đúng P6-A03 (cả hai process retry/recover, một lần settlement, inbox processed, giữ3holds), nay kiểm thêm tối đa một command QUEUED đúng swap/kind, chưa evidence/custody và chưa chuyển bước. Không skip/xfail; không đổi expected double-charge/rollback. Source assertion trước Phase7 còn nguyên trong commit d0abfd3 và log/XML full_01 giữ local.

IoT smoke cũ đợi20s cho ACK timeout; điều chỉnh thời gian chờ runner thành `physical_step_timeout_seconds+10` sau phê duyệt60s, không đổi expected UNKNOWN/REVIEW_REQUIRED. Lượt resume_targeted_05 gặp Docker tắt:4Passed/18Errors setup, không coi lỗi kết nối là kết quả nghiệp vụ. Sau mở Docker existing, resume_targeted_06 đạt22Passed (17Phase7+5worker). Bổ sung probe `test_two_event_workers_commit_pickup_once` dùng hai kết nối PG xử lý cùng closing event, nằm trong full_02 đã Passed.

## Khởi động và demo

DB hiện có cần healthy. Mỗi lệnh chạy ở terminal riêng trong workspace:

```powershell
.\tools\dev.ps1 backend
.\tools\dev.ps1 worker
.\tools\dev.ps1 payment
.\tools\dev.ps1 payment-worker
.\tools\dev.ps1 frontend
$env:PYTHONPATH='services/backend'
.\.venv\Scripts\python.exe -m simulators.device.main --station both --scenario physical
```

Chỉ chạy `physical` khi chủ động demo; nó mô phỏng thao tác cửa/pin và cập nhật dữ liệu theo workflow thật. `normal` chỉ ACK, không bàn giao; sẽ review khi hết hạn. Không tự chạy simulator vào demo trong lượt triển khai. Tài khoản demo có tên admin/customer/technician; mật khẩu đọc `.env` local, không in ở đây. Cần pin/ngăn được phục hồi hợp lệ và BMS simulator trước reserve; không tự activate toàn bộ seed.

Customer: cấp QR → bộ đọc mô phỏng xác thực → giữ pin và hai ngăn → đồng ý phí mô phỏng → theo dõi tiến trình. Simulator `physical` thực hiện hai thao tác; UI phải chờ COMPLETED từ server. `wrong-return`, `ack-only` và `crash-after-ledger` chỉ thử trong fixture riêng; không tạo lỗi lên DB demo.

```powershell
$env:TEST_REPORT_ROOT='PHASE7_TESTS'
.\.venv\Scripts\python.exe tools/run_phase6_fix.py NEW_TARGET pytest tests/test_phase7.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py NEW_FULL pytest tests
.\.venv\Scripts\python.exe tools/run_phase6_fix.py NEW_E2E script tools/smoke_phase7.py
```

E2E cần port8020/8021/8022 trống; chỉ dừng child processes do script tạo trong finally. Schema test và ledger `.local/phase7_*` được giữ, không DROP/reset. `--scenario physical --serve` giữ fixture sau hoàn tất để kiểm Browser; file connection.json chỉ trong cache local, không commit. Tạo file STOP tại thư mục cache của chính fixture để script đóng processes an toàn.

## Giới hạn và bàn giao

Chưa triển khai refund/settle/khôi phục custody thủ công của Phase8, phần cứng thật hoặc tiền thật. Không tuyên bố tải dài hạn, mọi crash boundary, Browser toàn bộ hay an toàn BMS nhà sản xuất. Giữ file code/test/runner và báo cáo làm regression. Logs/XML/JSON trung gian trong docs/PHASE7_TESTS, cache/dist có thể cân nhắc dọn sau nghiệm thu; chưa xóa. Phải giữ DB, `.local` command/provider ledgers, `.env`, source và bằng chứng lỗi gốc. Số đo dung lượng và kết luận cổng kỹ thuật ở phần kết quả cuối bên dưới.

## Tiếp tục ngày 28/10/2026

Đối chiếu full_02 XML:393Passed,0Failed,0Errors,0Skipped (375Phase1–6+18Phase7), SHA256 trong FINAL_VERIFICATION.json. Không chạy lại full vì source nghiệp vụ và pytest không đổi sau lượt đạt. Runner chỉ bổ sung chuẩn bị thư mục ledger trước subprocess và xuất connection fixture sớm để Browser theo dõi live; không sửa hợp đồng hoặc dữ liệu production.

final_e2e_04 dừng khi simulator S01 từ chối đường dẫn ledger trong lúc các process tạo chung thư mục cha. Guard vẫn giữ nguyên; runner tạo sẵn cha trước launch. final_e2e_05 đạt17checks/4scenario, gồm fingerprint bảng tài nguyên và payments/payment_events/outbox_messages/device_commands/audit_events không đổi. Không khẳng định đã tái hiện mọi race filesystem Windows.

Browser dùng Vite5174 → Backend8020, schema riêng, tài khoản fixture; không reset counter, không in credential. Customer COMPLETED/Payment/timestamps đã kiểm ở lượt27/10; lượt28/10 tái sử dụng schema cũ để Admin đọc COMPLETED và Technician không có menu Swap. Fixture live mới xác minh AWAITING_PICKUP → COMPLETED theo polling Backend thật; fixture ACK-only hiển thị AWAITING_RETURN dù PaymentSUCCEEDED. Fixture wrong-return hiển thị REVIEW_REQUIRED, giữ tài nguyên; khi quan sát, lý do mới nhất đã thành DEVICE_OFFLINE do simulator fault giữ outbox bị từ chối. Vì vậy chưa tuyên bố Browser đã nhìn thấy thông báo riêng COMMAND_OBSERVATION_MISMATCH; audit/E2E giữ bằng chứng lỗi đầu tiên.

## Kết quả cuối và cổng bàn giao — 28/10/2026

| Nhóm | Kết quả đã kiểm chứng | Bằng chứng local trong PHASE7_TESTS |
|---|---|---|
| Backend/Frontend Phase7 | Đã triển khai AD-02b, không có API điều khiển ngoài hợp đồng | Source và 18 tests Phase7 |
| Targeted |22 Passed (17 Phase7 +5 worker recovery), trước khi thêm probe closing race cuối |resume_targeted_06|
| Full Phase1–7 |393 Passed,0 Failed,0 Errors,0 Skipped;375 cũ+18 Phase7 |full_02/results.xml, run.log; exit0|
| Swap real-process |17 checks Passed,4 scenarios, demo fingerprint không đổi |final_e2e_05/reports/PHASE7_TESTS/E2E_RESULTS.json|
| Payment real-process |12 checks Passed |payment_regression_01|
| Receipt conflict real-process |5 checks Passed |receipt_regression_01|
| IoT real-process |8 checks Passed |iot_regression_01|
| Reservation real-process |8 checks Passed, TTL120s/worker restart |reservation_http_01|
| HTTP smoke |28 checks Passed, tách khỏi8E2E |reservation_http_01|
| OpenAPI/JSON Schema/SQL/baseline hashes |Passed;278SQL statements, không chạy DDL demo |CONTRACT_VALIDATION.json|
| Python/npm dependencies, TypeScript/Vite |Passed từ lượt triển khai; source/build inputs không đổi sau kiểm |Không thêm dependency; build287.68kB JS|
| Browser |Các bước dưới đây Passed trong phạm vi đã quan sát |browser/*.txt,*.png; FINAL_VERIFICATION.json|
| Blocker đã xác nhận còn mở |Không có trong phạm vi kiểm chứng |Không suy rộng sang mọi crash window/tải dài hạn|

Chuỗi E2E chạy tuần tự, report JSON đều result=Passed và số checks khớp log. Kết quả393 không cộng thêm targeted hoặc checks E2E. Không chạy lại full sau resume vì source nghiệp vụ/tests không đổi. Các thay đổi runner sau full chỉ chuẩn bị ledger parent và xuất connection fixture sớm; E2E mới/Browser chạy lại runner này thành công. Log/XML full_01 và các lượt lỗi vẫn giữ local; không skip/xfail để che lỗi.

Browser thực sự quan sát: Customer đăng nhập, đọc PaymentSUCCEEDED; AWAITING_RETURN khi chỉ ACK; AWAITING_PICKUP chưa hoàn tất; polling chuyển COMPLETED kèm hai mốc custody; ACK timeout thật chuyển REVIEW_REQUIRED/COMMAND_TIMEOUT; nhánh wrong-return vẫn review không hoàn tất. Admin đọc phiên hoàn tất, không có nút complete; Technician không có menu Swap. Menu không thay thế bảo mật API: regression Phase5 có403 cho GET/v1/swaps của Technician, ownership Customer và quyền Admin; HTTP smoke chạy mới cũng kiểm RBAC. Không báo Browser direct-route/API-bypass probe Passed vì không thực hiện qua Browser.

Browser NotRun: toàn bộ cấp QR/reserve/consent bằng UI (fixture tạo quaHTTP), mobile/accessibility toàn diện, thông báo riêng trả sai pin trước lỗi DEVICE_OFFLINE kế tiếp. Không có reset counter/auth bypass. Các fixture Browser mới kết thúc bằng STOP và chỉ dừng child processes của runner; Vite test port5174 cũng đã dừng. Schema, SQLite ledgers và cache giữ nguyên.

Các lệnh kiểm thử chính: `TEST_REPORT_ROOT=PHASE7_TESTS` cùng `tools/run_phase6_fix.py LABEL pytest tests` hoặc `script tools/smoke_phase7.py`; hồi quy dùng lần lượt smoke_phase6.py, smoke_phase6_fix.py, smoke_phase4.py, smoke_phase5.py --http-smoke. Lệnh build: `npm --prefix apps/web run build`; validator: `.venv/Scripts/python.exe tools/validate_contracts.py docs/PHASE7_TESTS/CONTRACT_VALIDATION.json`; dependency: `python -m pip check`, `npm --prefix apps/web ls --depth=0`. Không thay baseline, không migrate/seed demo hoặc thêm dependency.

Giữ trong commit: README; Payment.tsx/Reservations.tsx/SwapProgress.tsx; application/device.py/swaps.py; workers/device.py; simulator main.py; tests/test_phase7.py và test_phase6_worker_recovery.py; run_phase6_fix.py, smoke_phase4.py, smoke_phase7.py; báo cáo này, IMPLEMENTATION_STATUS.md và FINAL_VERIFICATION.json (tổng hợp/hash không credential). Các file hồi quy mới cần giữ lâu dài. Không stage raw log/XML/JSON trung gian/screenshots, .vs, cache, dist, ledger hoặc DB. Full file list cuối được kiểm bằng git staged diff.

Dung lượng đã đo trước bàn giao (MiB, gồm tài nguyên cũ):.venv95.84;node_modules60.77;dist0.28;.cache153.92;.local73.46;.vs1.43; reportsPhase7 khoảng0.23 trước thêm screenshots/E2E cuối. Không coi các số này là dung lượng tăng riêng Phase7. Cache/dist có thể tạo lại; logs/XML/screenshots chỉ dọn sau người dùng nghiệm thu và giữ bằng chứng cần thiết. Cache có connection.json chứa credential fixture: giữ local, không chia sẻ/commit. Không dọn .local, DB/volumes, source, migrations, .env hoặc bằng chứng lỗi gốc. Không tự xóa tài nguyên nào trong lượt này.

**Kết luận:** Phase7 đủ cổng kỹ thuật để nghiệm thu độc lập, cho phép tạo commit `feat: implement battery swap transaction`. Chưa khẳng định nghiệm thu độc lập hoặc vận hành phần cứng thật; các giới hạn Browser và Phase8 ở trên vẫn còn. Không tự push hoặc triển khai Phase8. Hash commit sẽ được báo sau khi Git tạo commit để tránh tham chiếu tự vòng trong nội dung commit.
