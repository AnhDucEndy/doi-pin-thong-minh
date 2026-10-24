# Phase 4 – IoT Simulator & Device Communication

Nghiệm thu 24/10/2026, Asia/Bangkok. Kế thừa HEAD 2f35ec3; working tree ban đầu sạch. Chỉ Phase 4; dừng trước Phase 5. Không sửa baseline, FR/UC/BR, OpenAPI hoặc QD approved.

## 1. Truy vết và phạm vi

Đã đọc AGENTS, README, plan/status, PHASE2/3_IMPLEMENTATION, START_HERE, handoff/modules/tests, baseline CSV/DOCX, thiết kế DOCX, ARCH-01, ERD, invariants, DDL, enums/OpenAPI và cấu hình approved. Phần source đã hoạt động được giữ lại.

**Lưu ý tên:** “F4” trong yêu cầu là nhãn Phase 4 IoT. Baseline gọi IoT/giám sát/cảnh báo là **F7**, còn F4 baseline là QR/RFID và chưa triển khai. Không đổi mã yêu cầu để đồng nhất hai cách gọi.

| Nguồn | Phần thực hiện |
| --- | --- |
| FR17 / UC15 / TC17 | Device-Key, inbox, scope trạm/pin/command, event/sequence dedup, polling, command adapter, simulator ledger |
| FR19 / UC17 / TC19 | Phát hiện fault/quá nhiệt/dữ liệu không đáng tin, alert dedup, chặn/cách ly, ACK/resolve theo quyền và bằng chứng |
| FR18 / UC16 / TC18 | Dashboard read-only, online/offline/maintenance/inactive qua projection F2, số alert chưa đóng và swap REVIEW_REQUIRED theo scope |
| FR07 / UC07 / TC07 | Telemetry BMS thực sự đi qua nguồn được xác thực, inbox và worker; không nâng seed chưa xác minh thành chứng cứ |
| FR11 / UC10 | Chỉ adapter/chứng cứ command DOOR/PRESENCE; không chuyển custody, không hoàn tất swap |
| BR01/02/10/11/12 | Giữ tài nguyên khi chưa rõ; lọc pin, cảnh báo không tự gỡ, online/fresh, giữ lịch sử |
| CT04/06/09/10/11 | ACK không là physical proof; restart không tác động hai lần; stale/out-of-order; scope; retry/conflict |

Trong checkout có **103 tests** Phase 1–3: 18+37+48. Năm probe nghiệm thu bổ sung đã được người dùng dọn, không khôi phục và không tính là 108 regression. Phase 4 thêm 44 ca, tổng **147 Passed**.

## 2. Kiến trúc và giao thức

Theo ARCH-01: modular monolith FastAPI và worker Python cùng schema PostgreSQL; simulator là tiến trình độc lập. **HTTP events + poll commands**, không MQTT/WebSocket/broker, không hạ tầng hoặc dependency mới. SQLite chỉ dùng ledger simulator, không thay PostgreSQL nghiệp vụ.

```text
Simulator S01/S02 (.local/*.sqlite3)
  -> POST /v1/device/events -> PostgreSQL inbox -> worker -> projection/BMS/alert/audit
  <- GET /v1/device/commands <- adapter command nội bộ của luồng nghiệp vụ tương lai
React -> devices/stations/batteries/alerts/dashboard (UserBearer, scope)
```

Simulator mặc định đúng hai controller, mỗi controller sáu ngăn; IDs khớp seed. Một boot UUID mới mỗi lần khởi động, seq tăng trong boot, outbox ghi trước HTTP. Key qua env, hash ở Backend; client chỉ gửi loopback và không dùng proxy môi trường. Trạng thái vật lý/ledger lưu SQLite WAL, synchronous FULL, trong workspace. Không đọc/ghi trực tiếp DB nghiệp vụ từ simulator.

## 3. API và phân quyền

| Method/path | Operation | Quyền/kết quả |
| --- | --- | --- |
| POST /v1/device/events | receiveDeviceEvent | X-Device-Key của chính controller; **202 EventReceipt** |
| GET /v1/device/commands | pollCommands | X-Device-Key; **200 DeviceCommandsPage**, chỉ lệnh của thiết bị |
| GET /v1/alerts | listAlerts | Admin toàn mạng, Technician đúng trạm; **200 AlertsPage** |
| POST /v1/alerts/{id}/acknowledge | ackAlert | Technician đúng trạm; expected_version + Idempotency-Key; **200 Alerts** |
| POST /v1/alerts/{id}/resolve | resolveAlert | Technician đúng trạm; version/evidence/note + key; **200 Alerts** |
| GET /v1/dashboard | dashboard | Admin/Technician, scope station; **200 Dashboard** |

JSON schema, operationId, x-roles và mã HTTP giữ theo OpenAPI gốc. DeviceEvent union gồm HEARTBEAT, TELEMETRY, DOOR, PRESENCE, COMMAND_ACK, SNAPSHOT, FAULT. Có format UUID/time, seq integer≥0, trường bắt buộc/extra fields và validation BMS. Không thêm role người dùng DEVICE vào bảng users; đây là danh tính thiết bị tách biệt. UserBearer không gọi được hai API thiết bị; Customer không gọi được quản trị/cảnh báo/dashboard.

Lỗi HTTP: 401 DEVICE_AUTH_REQUIRED/DEVICE_KEY_INVALID; 403 DEVICE_DISABLED/DEVICE_STATION_FORBIDDEN/BATTERY_SCOPE_INVALID/COMMAND_SCOPE_INVALID; 404 RESOURCE_NOT_FOUND; 409 EVENT_ID_CONFLICT/EVENT_SEQUENCE_CONFLICT/COMMAND_CONFLICT/COMMAND_INTERLOCK_FAILED; 422 DEVICE_EVENT_INVALID/SNAPSHOT_DUPLICATE_SLOT/SNAPSHOT_DUPLICATE_COMMAND. Guard miền lưu trữ BIGINT/NUMERIC tránh overflow thành lỗi DB. Các API người dùng tái sử dụng Error handler và VERSION_CONFLICT/FORBIDDEN/STATION_FORBIDDEN/STATE_CONFLICT/EVIDENCE_REQUIRED/RECONCILIATION_REQUIRED.

EventReceipt gồm event_id, duplicate, processing_state **QUEUED/PROCESSED/REJECTED**. 202 nghĩa đã lưu bền vững, không phải đã thay đổi nghiệp vụ. Nhận lại cùng ID/body trả receipt hiện hành; khác body/device trả 409. Cùng device/boot/seq nhưng ID khác trả 409. Error reason bất đồng bộ nằm ở processing_error và audit; không thêm trường ngoài EventReceipt approved. Ví dụ EVENT_OUT_OF_ORDER, SNAPSHOT_REQUIRED, BOOT_REPLAY, EVENT_STALE_OR_FUTURE, COMMAND_LATE_OR_UNKNOWN.

## 4. Inbox, tính mới và boot

API xác thực device enabled, kiểm scope mọi slot/pin/command/swap, validate/hash rồi insert inbox cùng transaction commit trước 202. received_at dùng giờ nhận thực của Backend, không dùng PostgreSQL now() vốn cố định ở đầu transaction. Worker đọc bản ghi chưa processed và processing_error IS NULL; **bỏ qua SIMULATION_SEED_UNVERIFIED** của Phase 3.

Worker kiểm lại scope/enabled/observed_at/freshness trong transaction có lock. Event cũ/sai thứ tự/future/boot cũ giữ lại REJECTED, không làm mới device/projection. Boot mới và reconnect bắt buộc snapshot đầy đủ các ngăn cùng trạm và ledger nhất quán trước khi sử dụng dữ liệu. Boot đã từng accepted không được quay lại thay boot mới hơn. Heartbeat không cập nhật observed_at hay BMS; telemetry không giả làm heartbeat.

Snapshot/heartbeat hợp lệ cập nhật last_received_at; quá 15s theo approved config là offline. Worker tạo DEVICE_OFFLINE, giữ timestamp liên lạc gần nhất để UI hiển thị; không xóa nó để làm trạng thái kết nối. Online/offline là giá trị suy ra, không phải door/service_state. Snapshot reconnect không tự phục hồi lifecycle hoặc service_state và không tự resolve alert. Timeout job độc lập không cần event mới, xử lý command deadline và stale BMS.

## 5. BMS, quan sát và cảnh báo

Telemetry chỉ gắn pin đang có custody tại đúng ngăn/trạm thiết bị; không tạo pin mới hoặc sửa vị trí. SOC/SOH 0..100, finite numeric; null khác trường bị thiếu (null hợp schema nhưng quality không đủ, thiếu trường 422). Threshold lấy approved_policy: SOC≥80, SOH≥80, T≤40, mới 15s; chỉ là giả định demo. quality_ok chỉ biểu thị dữ liệu đo đầy đủ/đối chiếu nguồn, không đồng nghĩa an toàn: T41 có thể là phép đo hợp lệ nhưng bị chặn/cách ly.

**SOC/SOH thấp chỉ là bộ lọc cấp**, không tự phát minh lifecycle mới. Cờ lỗi, quá nhiệt, thiếu dữ liệu tin cậy/mismatch tạo alert, đưa pin liên quan vào QUARANTINED (không đổi RETIRED) và ngăn ACTIVE→BLOCKED. MAINTENANCE/RETIRED không bị biến thành ACTIVE. Good data sau đó không phục hồi hoặc xóa alert. Snapshot/PRESENCE lưu observed_serial khi mâu thuẫn, giữ last-known custody; không tự gán pin lạ vào kho.

Mẫu mới xấu không fallback mẫu cũ tốt; FAULT accepted mới cũng vô hiệu sample tốt trước fault dù còn trong TTL. Phase 3 quality predicate được bổ sung guard cho nguồn FAULT mới này, giữ các hành vi cũ đã kiểm thử. Alert ACK chỉ ACKNOWLEDGED; resolve cần snapshot/BMS mới, current boot, không còn command pending/UNKNOWN. Health-fault cần heartbeat OK mới. Command timeout/mâu thuẫn cần reconciliation, chưa cho UI xóa dấu vết để bỏ qua tình trạng chưa rõ. Battery RESTORE vẫn dùng cơ chế resolve nguyên tử Phase 3, không tự phục hồi do ingest.

## 6. Command lifecycle và actuator

Không có POST tạo/mở cửa cho Admin/Customer. `enqueue_command()` là adapter nội bộ, có khóa station/user/swap/slot, version/unique(swap,kind) và guard lại trước dispatch: trạm online, slot phục vụ/cửa đóng/observations mới, reservation đúng swap, payment SUCCEEDED/consent, trạng thái lượt phù hợp, pin/quality/alert và thời hạn. Chỉ OPEN_RETURN/OPEN_SUPPLY đã duyệt; không tạo API/lệnh CLOSE/LOCK ngoài contract.

QUEUED→DISPATCHED khi poll; retry trả cùng ID, không tạo ID thay thế. ACK ACCEPTED→ACKNOWLEDGED, REJECTED→REJECTED, UNKNOWN→UNKNOWN. **ACK không cập nhật cửa, presence hay custody.** QUEUED hết hạn→EXPIRED; DISPATCHED/ACKNOWLEDGED không có bằng chứng hết hạn→UNKNOWN; giữ reservation và đánh dấu swap đủ dữ liệu REVIEW_REQUIRED, không lùi COMPENSATING. VERIFIED thiếu resource IDs không bị ép REVIEW_REQUIRED trái CHECK baseline; để phase nghiệp vụ xử lý tiếp.

OBSERVED chỉ khi có chuỗi DOOR OPEN → PRESENCE đúng trạng thái/serial → DOOR CLOSED cùng device/boot/slot/swap/command và thời hạn. Không suy ra từ snapshot ledger EXECUTED hoặc ACK. OBSERVED chỉ là chứng cứ actuator/sensor của command, **không phải hoàn tất lượt đổi**, không chuyển custody/thu/hoàn tiền. Late/duplicate ACK không lùi terminal state. UNKNOWN không tự dispatch lại.

Simulator ghi UNKNOWN vào ledger trước tác động; crash giữa các bước trả UNKNOWN sau restart và không thực thi lại. Hash command không khớp cũng UNKNOWN. ACK/NACK kết quả được cache bền vững để replay đúng kết quả. Trạng thái NOT_EXECUTED/EXECUTED/UNKNOWN đúng enum snapshot ledger. Cửa và `lock_released` boolean là vật lý mô phỏng cục bộ; Backend chỉ nhận door/presence theo schema đã duyệt, không thêm trường lock trên DB/API. `--inspect` xem lock/ledger ở local mà không gửi event.

Simulator mặc định `normal`/`ack-only` không tự nhận/trả pin. `physical` chỉ dùng fixture/schema test để phát chuỗi cảm biến kiểm command; không tự hoàn thành swap. Control chỉ poll sau khi worker đã xử lý các receipt hiện tại, không lấy 202 làm trạng thái ready. Sự kiện lịch sử bị reject được giữ như lịch sử, không phát lại thành dữ liệu mới. Mất kết nối ở chế độ chạy liên tục giữ outbox và thử lại chu kỳ kế tiếp; one-shot báo lỗi rõ.

## 7. Transaction, Database và audit

Schema Phase 1 đã đủ inbox/events, telemetry, commands, alerts, unique/FK/index. **Không migration cấu trúc mới, head 0002_user_approval**. Empty/upgrade/repeat migration và marker data được fixture hồi quy kiểm lại. Không chạy schema.sql, không reset DB/volume, không đổi seed 2×6 hoặc mật khẩu/key hiện có. Chỉ cập nhật grants INSERT/UPDATE inbox/commands/alerts và INSERT telemetry cho cùng runtime API/worker; không DELETE lịch sử.

Parent station lock thống nhất với F2/F3; worker khóa user→swap→slot UUID→pin UUID rồi device/event trong phạm vi station. Commit inbox, processed flag, projection/telemetry/alert và audit được quản lý bằng transaction. Savepoint lỗi nghiệp vụ rollback projection trước khi ghi receipt REJECTED; lỗi DB không nuốt mất rollback. Audit có DEVICE/SYSTEM/USER actor, aggregate device_event/device_command/alert đúng mục đích; không ghi key, token hoặc payload chứa credential.

Backend worker và simulator là hai tiến trình độc lập, không nhúng loop vào request API. Không chạy worker trong Frontend. Ledger SQLite `.local/` được gitignore nhưng là dữ liệu cần giữ cùng DB khi backup/restart, không coi là cache.

## 8. Frontend và demo

Menu **Thiết bị và IoT** cho Admin/Technician: thiết bị được phân công, heartbeat/time, enabled, vận hành ONLINE/OFFLINE/MAINTENANCE/INACTIVE, seq; dashboard counts và alert chưa xử lý, version/occurrences. GET dashboard chỉ count REVIEW_REQUIRED, không lộ lịch sử khách. Refresh lấy dashboard_poll_seconds từ Backend qua header X-Dashboard-Poll-Seconds (approved 3s), không đưa Device-Key lên browser.

Technician có **Xác nhận đã đọc** và **Đóng cảnh báo có bằng chứng** theo đúng endpoint approved; Admin chỉ xem alert. Không nút mở cửa ngoài luồng. Door/presence xem ở Trạm và ngăn; BMS/quality/cách ly xem ở Pin và BMS. Command và lock ledger xem CLI `--inspect`; không mở quyền DeviceKey cho user để dựng UI điều khiển.

Browser đã chạy trên frontend test 5174/API 8002/schema E2E riêng: Technician chỉ S01, thấy offline/cảnh báo, bấm ACK; DB xác nhận ACKNOWLEDGED nhưng pin vẫn QUARANTINED, ngăn BLOCKED. PHASE4_UI_RESULTS.json/PHASE4_UI.png. Bản GUI chính :5173 cũng đã kiểm dashboard đúng scope (Tech 0 online/1 offline, không có dữ liệu sim được giả nhận trong demo), ảnh PHASE4_DASHBOARD_UI.png. Đã logout các phiên kiểm thử. Các server GUI test đã dừng, data/ledger test giữ nguyên.

## 9. Kiểm thử và lỗi đã sửa

| Nhóm | Kết quả |
| --- | --- |
| Regression Phase 1/2/3 | **18 + 37 + 48 = 103 Passed** |
| Phase 4 IoT/dashboard/alerts | **44 Passed** |
| Tổng pytest cuối | **147 Passed, 0 Failed, 0 Skipped** |
| E2E subprocess thật | **8 checks Passed**: API+worker+hai simulator, command fixtures chỉ schema test |
| HTTP live Phase 4 | **13 Passed**, không asset mutation thành công trên demo |
| HTTP hồi quy F2/F3 | **14 + 16 Passed**; helper F3 chấp nhận health phase≥3 khi chạy bản mới |
| OpenAPI/JSON Schema/278 SQL/hash baseline | Passed |
| TypeScript/Vite, pip check | Passed; không cài dependency |
| Browser device/dashboard/ACK | Passed phần mô tả trên |

E2E chạy `tools/smoke_phase4.py`: tạo schema phase4_e2e_* mới, migration/seed riêng; khởi API :8002, worker và hai subprocess simulator; xác minh snapshot/HB/BMS accepted, ACK không mở cửa/custody, NACK, ACK timeout UNKNOWN/REVIEW_REQUIRED, dừng gửi quá 15s thực và thấy offline, restart new boot/ledger không tác động lặp, hot→quarantine và good data không tự restore. Fingerprint tám bảng asset/evidence **demo chính không đổi**; seed Phase 3 vẫn có 10 event chưa xác minh; không release reservation test. Dữ liệu swap/payment chỉ là fixture để kiểm interlock, không triển khai API/module tiền/đặt chỗ.

Các ca tự động còn kiểm UUID/schema/numeric/time, key disabled, sai device/station/pin/command, ID/body/seq conflict, duplicate receipt/ACK, out-of-order/old boot, reconnect snapshot, stale, fault/ACK không clear, atomic rollback, create command idempotency, physical chain OBSERVED không custody, simulator crash/restart và replay cached ACK/NACK, concurrency receive once, dashboard scoped counters. Test received_at ban đầu dùng transaction now() làm nhiều fixture bị nhận nhầm future; đã sửa thành giờ nhận thực, chạy lại đạt. Một lượt E2E chạy lại gặp cổng 8002 còn phục vụ GUI test; đã dừng test server, thêm preflight port check và chạy lại Passed. Không dùng reset/xóa DB để làm test đạt.

Hai deprecation warnings Starlette/httpx và OpenAPI validate_spec hiện hữu; không nâng library. **Not Run:** phần cứng thật; Browser đầy đủ mọi scenario; real-process chuỗi nhận/trả physical và hoàn tất custody/swap; QR/RFID/reservation/payment mock/reconciliation tổng thể. Chuỗi physical command đã kiểm bằng simulator ledger + HTTP/TestClient/PostgreSQL tests, không tuyên bố real hardware hay full swap E2E. Không còn Failed/Blocked bắt buộc trong phạm vi Phase 4.

## 10. Khởi động và demo lại

Các lệnh tại root workspace, terminal riêng; giữ .env local, không in secret:

```powershell
.\tools\dev.ps1 database
.\tools\dev.ps1 migrate    # head hiện có + grants; không DDL gốc
.\tools\dev.ps1 backend    # 127.0.0.1:8000
.\tools\dev.ps1 worker     # terminal khác
.\tools\dev.ps1 frontend   # 127.0.0.1:5173
.\tools\dev.ps1 simulator  # khi muốn bắt đầu gửi snapshot/HB/BMS hai trạm
```

Backend/Frontend/worker chính đang chạy lúc bàn giao; simulator trên demo chính chưa tự bật, để người dùng chủ động bắt đầu nguồn quan sát. Không chạy trùng port. Worker không nhận seed chưa xác minh. Khi simulator normal gửi thành công vẫn không tự ACTIVATE pin hoặc RESTORE ngăn.

CLI chi tiết:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'services/backend'
.\.venv\Scripts\python.exe -m simulators.device.main --station both
.\.venv\Scripts\python.exe -m simulators.device.main --inspect
# Dừng simulator bằng Ctrl+C, giữ API/worker; quá 15s xem OFFLINE, timestamp cuối còn nguyên.
# Chạy lại cùng ledger: boot mới, snapshot + ledger trước khi tiếp tục; không tự gỡ cách ly.
```

Demo lỗi và command thực hiện **trong schema test**, không fixture trên doi_pin:

```powershell
.\.venv\Scripts\python.exe tools/smoke_phase4.py
# Tự tạo schema riêng; cần port 8002 rảnh, dừng API GUI test trước nếu còn dùng port.
.\.venv\Scripts\python.exe tools/smoke_phase4.py --live-readonly
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=docs/PHASE4_TEST_RESULTS.xml
```

Scenario CLI có normal/ack-only/nack/physical/crash-after-ledger/offline/hot/fault/missing-bms/low-soc/low-soh, --cycles N và --ledger-dir. Muốn tự chạy lỗi: dùng schema test (DATABASE_SCHEMA chỉ đặt trong terminal test), API test port riêng và `--url http://127.0.0.1:8002 --ledger-dir .local/<schema>`; đừng trỏ hot/fault/physical vào demo chính. Không có public command producer nên CLI mặc định không tự tạo swap để có lệnh; tool E2E chuẩn bị fixture và gọi adapter nội bộ đúng guard.

ACK/NACK/timeout xem PHASE4_E2E_RESULTS.json hoặc CLI inspect ledger của schema ghi trong file đó. Để kiểm chuỗi physical riêng: pytest `-k command_physical_chain_observed_without_custody` và `-k simulator_restart_no_second_actuator_effect`. Để test scope/ACK trên browser, dùng schema E2E giữ lại và cấu hình frontend/API test trong .cache; cổng 5174/8002 chỉ phục vụ test, đã dừng sau kiểm tra.

Lệnh đã chạy bổ sung: git status/log/diff --check; Docker info/ports read-only; Alembic current; grants; contract validator; pip check; npm build; pytest các lượt regression/integration/cuối; smoke_phase2.py/smoke_phase3.py; smoke_phase4.py E2E/live; SQL read-only sau GUI ACK; du trong container và đo folder. Không cài/thay PATH/tool hệ thống, không push.

## 11. File và tài nguyên

Mới: backend domain/device.py, application/device.py, api/device.py, workers/__init__.py/device.py; simulators/__init__.py, simulators/device/__init__.py/main.py; web src/Devices.tsx; tests/test_phase4.py; tools/smoke_phase4.py; báo cáo và PHASE4_* bằng chứng cuối.

Sửa: .gitignore (.local), web main.tsx, backend main.py, api/assets.py (poll metadata), application/assets.py (fault-after-good guard), tools/provision_database.py/dev.ps1/smoke_phase3.py; tests/conftest.py (schema/report Phase4) và test_phase1.py (danh sách endpoint implemented); README, IMPLEMENTATION_PLAN/STATUS. Không sửa test_phase2.py/test_phase3.py, migrations, lockfiles/dependency hoặc thiết kế gốc. Dữ liệu seed gốc không đổi.

E2E log trong .cache/phase4_e2e_*; GUI test config .cache/phase4-ui-vite.mjs; SQLite ledger .local/phase4_e2e_*; pytest temp .cache/phase4-* và __pycache__. Không commit chúng. Giữ chứng cứ test cuối trong docs; kết quả integration trung gian được giữ ở .cache, không commit báo cáo tạm. Mỗi lượt kiểm thử giữ schema riêng, kể cả lượt setup không hoàn tất; không tự dọn schema vì có dữ liệu/bằng chứng.

Dung lượng đo trong PHASE4_DISK_USAGE.json: .venv≈95.84 MiB, node_modules≈56.39 MiB, dist≈0.24 MiB, cache≈146.43 MiB, ledger≈1.90 MiB; PostgreSQL data 110 MiB theo `du -sh` cuối lượt (không phải kích thước VHDX), container healthy. Không image/library mới, không clone/copy dự án. Không tự dọn source, DB, volume, .git hoặc ledger.

Cache/build có thể tái tạo (.cache, dist) nhưng giữ log/bằng chứng cần thiết trước khi dọn; .venv/node_modules cần cài lại từ lockfile và dừng server. **Ledger không phải cache**: bảo toàn cùng DB để không phát lại lệnh sau khôi phục. Không down -v/prune volumes, không xóa schema test hoặc ledger khi chưa được duyệt.

## Bảng nghiệm thu cuối

| Hạng mục Phase 4 | Trạng thái |
| --- | --- |
| HTTP device auth/inbox/sequence/scope và worker atomic | Passed |
| Heartbeat/offline/reconnect, BMS trusted vs seed, cảnh báo/cách ly | Passed |
| Command adapter/poll/ACK-NACK/deadline/duplicate/ledger restart | Passed |
| Dashboard/alerts scoped, GUI ACK không phục hồi | Passed phần đã kiểm |
| 147 tests, 8 real-process E2E, 13 HTTP live, regression HTTP/build/contracts | Passed |
| Toàn bộ Browser scenarios/real hardware/full swap & custody | Not Run / ngoài phạm vi |
| Blocker bắt buộc Phase 4 | Không có |

**Kết luận:** Phase 4 đủ điều kiện bàn giao trong phạm vi IoT Simulator & Device Communication. Commit sau rà soát an toàn: `feat: implement IoT simulator and device communication`; hash xem git log sau khi tạo commit. Không tự push. Dừng sau Phase 4, chưa triển khai Phase 5.
