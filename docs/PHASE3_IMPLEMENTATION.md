# Phase 3 – F3 Battery & BMS Management

Nghiệm thu ngày 24/10/2026, Asia/Bangkok. Kế thừa c396cfd và 21cbe44. Dừng tại F3; không triển khai Phase 4. Không sửa tài liệu gốc GĐ1/GĐ2.

## Nguồn, phạm vi và truy vết

Đọc AGENTS, README, kế hoạch/tiến độ, PHASE2_IMPLEMENTATION, START_HERE, handoff/modules/tests, approved decisions/config, baseline CSV và DOCX, SM-01, ERD-01/02, OpenAPI, DDL/invariants. QD approved ưu tiên các ghi chú cũ chưa xác nhận. Module F3 thuộc nhóm 2 của handoff gốc; Phase 3 là số thứ tự người dùng giao mới.

| Nguồn | Phần thực hiện | Bằng chứng/giới hạn |
| --- | --- | --- |
| FR06 / UC06 / TC06 | Hồ sơ/serial duy nhất, initial placement XOR ngăn/khách/unknown, lifecycle; không sửa vị trí pin đang phục vụ | API/DDL uniqueness, FK/partial unique, replay, concurrent version. Chuyển custody qua swap chưa triển khai; không tuyên bố hoàn tất bước chuyển vị trí của TC06 gốc |
| FR07 / UC07 / TC07 | Đọc SOC/SOH/nhiệt độ/cờ lỗi/thời điểm đo; validation BMS dùng chung; đánh giá thiếu/cũ/không đáng tin | PostgreSQL fixture và read API Passed. Gửi telemetry qua thiết bị + inbox/worker và thử cấp pin qua swap Not Run, dành Phase 4+ |
| FR08 / UC08 / TC08 | Technician đúng trạm ACTIVATE/QUARANTINE/RESTORE; kiểm bằng chứng và resolve cảnh báo nguyên tử | Lifecycle, dữ liệu lỗi/stale, ACK chưa resolved, phục hồi hợp lệ và rollback Passed. Tự phát hiện lỗi/cách ly từ pipeline thiết bị chưa triển khai |
| BR02, BR10, BR11, BR12 | Điều kiện cấp, ACK không gỡ lỗi, online/fresh, không hard delete | Predicate chia sẻ F2/F3, tests, audit append-only |
| BR01 / invariants liên quan | Không bypass active swap/reservation; vị trí duy nhất | Guard pin/ngăn, unique DB và transaction/version |

Working tree ban đầu sạch tại main/21cbe44. Không có file test bổ sung rời hoặc báo cáo manual chưa commit trong checkout thực tế; không reset/xóa/ghi đè phần còn tồn. Giữ nguyên 18 tests Phase 1 và 37 tests Phase 2, chỉ mở rộng danh sách endpoint được phép trong test hợp đồng để thêm đúng F3 và tiếp tục loại trừ device/events.

## API

| Method/path | Operation | Quyền |
| --- | --- | --- |
| GET /v1/batteries | listBatteries | Admin toàn mạng; Technician chỉ pin hiện ở ngăn thuộc trạm được giao |
| POST /v1/batteries | createBattery | Admin, 201, Idempotency-Key UUID |
| POST /v1/batteries/{battery_id}/actions | changeBattery | Admin chỉ RETIRE; Technician đúng trạm ACTIVATE/QUARANTINE/RESTORE; 200 |
| GET /v1/batteries/{battery_id}/telemetry | listTelemetry | Admin hoặc Technician đúng trạm; phân trang mới nhất trước |

Customer bị 403 FORBIDDEN. Không có GET chi tiết pin riêng hoặc PATCH pin trong OpenAPI: UI chọn hồ sơ từ list và đọc telemetry; không thêm endpoint ngoài hợp đồng. Không có API sửa số BMS/vị trí hoặc API thiết bị mới.

Body tạo gồm serial/family/location_kind và optional compartment_id/holder_user_id. Body action gồm expected_version/action/reason, optional evidence_event_id/resolve_alert_ids. Tất cả extra fields bị từ chối. Schema và operationId/x-roles giữ theo bản duyệt. Lỗi có cấu trúc Error: 401 AUTH_REQUIRED/SESSION_INVALID, 403 FORBIDDEN/STATION_FORBIDDEN, 404 RESOURCE_NOT_FOUND, 409 RESOURCE_CONFLICT/VERSION_CONFLICT/STATE_CONFLICT/ACTIVE_TRANSACTION/BATTERY_CUSTOMER_HELD, 422 BATTERY_FAMILY_INVALID/BATTERY_LOCATION_INVALID/BATTERY_HOLDER_INVALID/EVIDENCE_REQUIRED/UNRESOLVED_ALERTS/INVALID_ALERTS/INVALID_CURSOR. Dùng lại exception mapping 503 và idempotency/audit Phase 1.

Metadata bổ sung trên GET telemetry: **X-Battery-Available**, **X-Battery-Assessed-At**, **X-BMS-Limits** (SOC min, SOH min, T max, stale seconds). Đây là đánh giá suy ra ở thời điểm đọc để UI không tự đoán từ số BMS; không phải lifecycle mới, không phải xác nhận bàn giao vật lý. JSON body giữ nguyên BatteryTelemetryPage; không đổi baseline. Metadata là phần bổ sung triển khai tương thích, cần giữ khi proxy API. UI chỉ công bố đủ điều kiện từ cờ Backend và thời điểm đánh giá, tự hết hiệu lực hiển thị theo stale seconds.

## BMS và vòng đời

Ngưỡng đọc từ approved_policy: SOC≥80, SOH≥80, T≤40, mới 15 giây. Là giả định mô phỏng, không phải thông số an toàn nhà sản xuất. BMSPayload kiểm SOC/SOH 0..100, numeric đúng kiểu, loại NaN/Infinity, cho phép null theo contract và nhận cờ lỗi; dùng khi seed và làm interface tối thiểu cho inbox tương lai. Không tạo producer/worker ingest.

Khả dụng phải thỏa cả IN_SERVICE, đúng họ, custody ở ngăn khớp serial, ngăn ACTIVE/CLOSED/có pin, observation mới, device enabled/online/current boot snapshot, sample mới nhất accepted/processed đúng device/boot/ngăn, đủ trường/quality/no faults, không reservation/swap/alert. Sample xấu mới không được fallback sample tốt cũ. Cùng predicate dùng cho số khả dụng F2 và metadata F3. Không coi heartbeat/ACK là BMS hay bằng chứng bàn giao.

ACTIVATE REGISTERED→IN_SERVICE; QUARANTINE từ REGISTERED/IN_SERVICE→QUARANTINED; RESTORE QUARANTINED→IN_SERVICE; RETIRE từ ba trạng thái chưa retired→RETIRED, terminal. Không có MAINTENANCE lifecycle cho pin trong schema; bảo trì ngăn và cách ly pin là hai khái niệm riêng.

ACTIVATE/RESTORE cần snapshot mới cùng device/boot, payload khớp pin/ngăn, cửa đóng, online, dữ liệu BMS mới và không lỗi/quá nhiệt, không command pending/ACK/UNKNOWN. Không yêu cầu slot đã ACTIVE để tránh vòng phụ thuộc với phục hồi ngăn F2; slot vẫn không khả dụng trước khi được F2 phục hồi. SOC/SOH thấp không tự đồng nghĩa lifecycle không được IN_SERVICE: bộ lọc cấp riêng vẫn từ chối; có test chứng minh không bị đánh dấu sẵn sàng sai.

RESTORE có thể resolve pin-specific alerts đã chỉ định, kèm reason/evidence/actor và audit, trong cùng transaction với lifecycle. Alert còn OPEN/ACKNOWLEDGED chưa resolve chặn phục hồi; không dùng phục hồi một pin để xóa fault chung của trạm/ngăn. Thiếu hoặc sai evidence/alert rollback toàn bộ. Không tạo chức năng quản lý cảnh báo tổng thể ngoài phạm vi F3.

Admin RETIRE bị chặn khi khách giữ, có active swap hoặc reservation chưa release. Các thay đổi lifecycle không sửa custody, không giải phóng resource. Khóa parent station, slot rồi battery và expected_version, unique index DB bảo vệ tranh tài nguyên. Register CUSTOMER khóa user và xác minh CUSTOMER; register ngăn khóa trạm/ngăn, kiểm trống theo custody và không có observation trái ngược. UNKNOWN không được kích hoạt khi thiếu chứng cứ vị trí. Pin ở ngăn seed chỉ REGISTERED, không mặc định physical ready.

## Database, migration và seed

Schema baseline đã đủ; **không tạo migration mới**, head **0002_user_approval**. Test thực hiện empty schema→0001→có marker data→head→head, marker tồn tại. Không chạy lại schema.sql trên demo. Provision mở INSERT/UPDATE batteries và UPDATE đúng các cột resolve của alerts cho runtime; không thêm quyền DELETE lịch sử hoặc ghi telemetry cho API.

Seed giữ 2×6, một family, 11 pin có sẵn, thêm 10 raw samples (5/trạm): số ở ngưỡng, SOC thấp, SOH thấp, quá nhiệt, trường thiếu. Tất cả **quality_ok=false**, event **accepted=false**, chưa processed, boot seed khác boot thiết bị. Không làm mới heartbeat/cửa/presence hoặc lifecycle. Chạy lại không refresh timestamp/trùng row; nếu đã có lịch sử khác của pin thì bỏ qua việc chen sample seed mới. Không giả tạo pin đủ điều kiện bằng dữ liệu seed.

Schema test riêng mới chứa fixture accepted snapshot/telemetry cùng các trạng thái/ràng buộc để kiểm đủ điều kiện và cách ly. Fixture rollback; không ghi fixture vào demo. Mẫu lifecycle không được sử dụng (REGISTERED/QUARANTINED), ngưỡng đạt/trượt và dữ liệu thiếu đều có trong kiểm thử. Không tự cách ly hồ sơ demo có sẵn để tạo kịch bản cho đẹp.

Đã chạy seed hai lần trên demo sau khi test schema đạt. Hash toàn bộ users/stations/compartments/batteries trước/sau giống nhau; chỉ thêm raw event/reading. Xem PHASE3_DATABASE_CHECK.json. Không xóa/reset DB hoặc volume. Schema test giữ bằng chứng, tăng DB một lượng nhỏ qua mỗi lượt chạy.

## Frontend

Menu **Pin và BMS** cho Admin/Technician; danh sách, **Xem hồ sơ và BMS**, lifecycle, vị trí/holder, SOC/SOH/T/fault/quality/measured time, cảnh báo dữ liệu chưa xác minh/cũ/thiếu, đánh giá Backend kèm thời điểm/ngưỡng demo. Admin có **Đăng ký pin** và **Ngừng sử dụng**. Technician có thao tác đúng lifecycle, ID snapshot và alert IDs khi phục hồi. Không form sửa BMS/custody. Loading, empty, error, forbidden và lỗi trạng thái được hiển thị; retry giữ idempotency key cho cùng nội dung. Đổi tài khoản quay về menu trạm để không giữ trang quản trị của phiên trước.

Browser đã kiểm tra Admin list 11 pin và chi tiết BMS, Technician list 5 pin S01, Customer không menu Pin/BMS, login/logout. PHASE3_UI.png là bằng chứng Admin; các thao tác lifecycle ghi trên browser demo **Not Run** để giữ dữ liệu chính. Không tuyên bố browser E2E đầy đủ; hành động ghi và rollback kiểm bằng PostgreSQL tests. UI hiển thị tối đa 100 sample mới nhất; API có cursor cho toàn lịch sử.

## Nghiệm thu và lệnh

| Nhóm | Kết quả thực chạy |
| --- | --- |
| Regression Phase 1 | 18 Passed |
| Regression Phase 2 | 37 Passed |
| F3 unit/integration/contract | 48 Passed |
| Tổng pytest | **103 Passed, 0 Failed, 0 Skipped** |
| HTTP smoke qua Vite | **16 Passed**, không asset mutation thành công trong demo |
| TypeScript/Vite build | Passed |
| OpenAPI, approved JSON Schema, 278 SQL statements, baseline hashes | Passed |
| pip check | Passed |
| Empty/upgrade/repeat migration, repeat seed, bảo toàn demo | Passed |
| Browser đọc/role flows | Passed phần đã nêu; ghi lifecycle bằng browser Not Run |
| Telemetry ingest/auto-quarantine từ worker, custody swap, phần tích hợp TC06/07 cần module sau | **Not Run**, ngoài phạm vi |

Biên đã chạy: SOC/SOH 0/100/79.99/80, nhiệt độ 40/40.01, NaN/Infinity/số sai kiểu, null, stale, wrong boot/snapshot, fault, quality=false, cửa/vị trí mâu thuẫn, cách ly, reservation, alert ACK, duplicate serial, XOR, holder sai role, ngăn trùng, trái quyền, missing ID, cursor, idempotency, version cũ và hai request retire đồng thời (200/409). Hồi quy F2 tiếp tục kiểm sample xấu mới nhất không fallback.

Lượt đầu 100 Passed/1 Failed ở test tập endpoint vì nhãn FR07 kéo cả device/events chưa triển khai. Sửa tập endpoint test, không sửa OpenAPI/triển khai IoT. Các lượt sau Passed. Hai deprecation warnings hiện hữu (Starlette/httpx và validate_spec), không tự nâng dependency.

Lệnh chính (tại workspace, PYTHONPATH=services/backend):

```powershell
git status --short
git log -3 --oneline
.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.cache/pytest-phase3-reviewed --junitxml=docs/PHASE3_TEST_RESULTS.xml
npm.cmd --prefix apps/web run build
.venv/Scripts/python.exe tools/validate_contracts.py docs/PHASE3_CONTRACT_VALIDATION.json
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe tools/provision_database.py grants
.venv/Scripts/python.exe -m alembic -c services/backend/alembic.ini current
.venv/Scripts/python.exe -m app.seed
.venv/Scripts/python.exe tools/smoke_phase3.py
git diff --check
```

Seed demo lần đầu qua script gọi cùng seed() hai lần, so hash trước/sau; báo cáo không chứa credentials. Kiểm Docker/ports/read SQL và du read-only. Backend local được khởi động lại để nạp F3, Vite hiện có tái sử dụng. Không cài thêm dependency/công cụ, không đổi PATH Windows. Kiểm staged secret/artifact trước commit; thông điệp `feat: implement battery and BMS management`, không push. Commit hash xem git log sau khi hoàn tất (không tự tham chiếu hash trong cùng commit).

## File, khởi động và dung lượng

Mới: backend api/batteries.py, api/battery_schemas.py, application/batteries.py, domain/bms.py; web src/Batteries.tsx; tests/test_phase3.py; tools/smoke_phase3.py; docs/PHASE3_IMPLEMENTATION.md và PHASE3_* bằng chứng.

Sửa: backend main.py, application/assets.py (predicate dùng chung), seed.py; web main.tsx/index.html; tools/provision_database.py/dev.ps1; tests/conftest.py/test_phase1.py; README, IMPLEMENTATION_PLAN/STATUS. Không sửa test_phase2.py hoặc baseline, không thêm migration/file dependency. Evidence test môi trường ghi PHASE3_TEST_ENVIRONMENT.json, không ghi đè bằng chứng Phase 2.

Chạy lại: `tools/dev.ps1 database`, `tools/dev.ps1 migrate` (head/grants), `tools/dev.ps1 seed`; `tools/dev.ps1 backend`, terminal khác `tools/dev.ps1 frontend`. DB 127.0.0.1:5432, Backend :8000/docs, Frontend :5173. Hai server đang chạy lúc bàn giao, tránh khởi động trùng port. Login bằng admin/technician/customer và mật khẩu từ .env local; không có secret mặc định trong source. Technician S01: mở BMS, quan sát sample chưa xác minh; không dùng chúng làm evidence phục hồi.

Đo gần cuối lượt: .venv 95,84 MiB, node_modules 56,39 MiB, dist 0,24 MiB, .cache 146,43 MiB, docs khoảng 0,24 MiB trước báo cáo cuối; PostgreSQL data 84 MiB (không phải kích thước VHDX). Raw demo chỉ 10 mẫu; tăng DB chủ yếu từ các schema kiểm thử giữ lại. Không tải thư viện/build tree mới; UI PNG ~159 KiB.

Không tự dọn. .cache và apps/web/dist tái tạo được; chỉ cân nhắc dọn sau khi giữ bằng chứng cần thiết. .venv/node_modules có thể cài lại từ lockfiles nhưng cần tải lại và phải dừng server. Giữ source, migrations, .git, thiết kế, báo cáo bằng chứng, .env và DB. Không dùng down -v/prune volumes; schema test cần kiểm tra/sao lưu và duyệt riêng trước khi dọn.

Lưu ý cho Phase 4: raw seed events có accepted=false và processing_error=SIMULATION_SEED_UNVERIFIED; không tự nhận lại các bản ghi này thành chứng cứ accepted. Inbox/worker phải giữ nguyên việc từ chối mẫu seed và xác minh thiết bị/boot/sequence theo hợp đồng. Đây là công việc tích hợp tiếp theo, không đã hoàn thành trong F3.

| Nghiệm thu cuối Phase 3 | Trạng thái |
| --- | --- |
| Bốn API F3, vòng đời, scope, BMS/khả dụng, audit/idempotency | Passed trong phạm vi đã triển khai |
| 103 tests và hồi quy, build, validator, DB/seed, 16 HTTP checks | Passed |
| Browser đọc ba vai trò | Passed; ghi lifecycle qua browser Not Run |
| Ingest thiết bị, chuyển custody qua swap, tích hợp TC06/07 tương ứng | Not Run, phụ thuộc phase sau |
| Blocker bắt buộc trong F3 | Không có |

**Kết luận:** phần F3 theo bốn operation approved đủ điều kiện bàn giao để bắt đầu Phase 4 IoT khi người dùng giao. Không có test bắt buộc thuộc phạm vi F3 Failed/Blocked. Không suy ra toàn hệ thống đã nghiệm thu. Dừng sau Phase 3.
