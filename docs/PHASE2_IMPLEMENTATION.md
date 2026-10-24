# Nghiệm thu Phase 2 – F2

Ngày 24/10/2026. Chỉ FR03–FR05, UC03–UC05; kế thừa Phase 1. Không thay baseline, QD01–QD09, OpenAPI, ERD hoặc invariants. F3, ingestion telemetry, simulator, QR/RFID, reservation/payment API và quy trình đổi pin chưa triển khai.

## API và quyền

| Method/path | Chức năng | Quyền |
| --- | --- | --- |
| GET /v1/stations | Phân trang, trạng thái vận hành, số pin đủ BR02 | Cả ba vai trò |
| POST /v1/stations | Tạo trạm | Admin |
| GET /v1/stations/{station_id} | Chi tiết trạm | Admin, Technician được phân công |
| PATCH /v1/stations/{station_id} | Tên, địa chỉ, trạng thái; expected_version | Admin |
| GET /v1/devices | Danh sách, không key/hash | Admin; Technician theo trạm |
| POST /v1/devices | Đăng ký controller; trả device_key_once | Admin |
| PATCH /v1/devices/{device_id} | Kích hoạt/vô hiệu hóa | Admin |
| GET /v1/stations/{station_id}/compartments | Danh sách ngăn | Admin, Technician đúng trạm |
| POST /v1/stations/{station_id}/compartments | Thêm ngăn BLOCKED/UNKNOWN | Admin |
| POST /v1/compartments/{compartment_id}/actions | SET_MAINTENANCE, RESTORE, RETIRE | Admin/Technician đúng trạm; RETIRE chỉ Admin |

POST tạo trả 201; GET/PATCH/action trả 200; lỗi 401/403/404/409/422/503 theo hợp đồng. Không thêm enum hoặc vai trò. OpenAPI runtime chỉ công bố operation thực sự triển khai, giữ schema và x-roles bản duyệt. Các mã lỗi nghiệp vụ có cấu trúc Error; hợp đồng không liệt kê enum mã lỗi.

## Nhất quán và an toàn

- Dùng lại session/auth/RBAC, idempotency, audit append-only và exception handler Phase 1. Scope được Backend kiểm tra mỗi request, cả khi replay idempotency. Customer không truy cập thông tin quản trị.
- Khóa trạm/slot và kiểm expected_version trước thay đổi. Chặn maintenance/retire hoặc ngừng trạm khi có active swap hay reservation chưa release; không suy diễn release từ thời gian hết hạn. Kiểm cả reservation riêng trên pin.
- SET_MAINTENANCE không thay door/presence/serial/custody. RETIRE terminal, chỉ từ MAINTENANCE và đã quan sát trống. RESTORE yêu cầu snapshot accepted/processed cùng device/boot, còn mới, khớp projection, cửa đóng, không pending/unknown command hoặc alert chưa RESOLVED; pin hiện có phải được xác minh, không QUARANTINED. Không tạo lệnh mở cửa.
- Vô hiệu hóa thiết bị chuyển giao dịch có tài nguyên sang REVIEW_REQUIRED, giữ reservation; COMPENSATING giữ nguyên để không lùi trạng thái. VERIFIED chưa có đủ tài nguyên bị từ chối 409 nguyên tử: CHECK baseline không cho chuyển REVIEW_REQUIRED khi thiếu IDs/amount. Cần kết thúc xác thực hoặc giữ tài nguyên qua module sau trước khi vô hiệu hóa, không tự tạo dữ liệu giả hay sửa baseline.
- FR05 chỉ đọc projection/bằng chứng nền: device enabled, heartbeat mới, snapshot current boot, ngăn ACTIVE/cửa CLOSED/pin đúng serial-custody, không reservation/swap/alert; sample mới nhất hợp lệ, đúng họ, IN_SERVICE, SOC≥80, SOH≥80, T≤40 và còn mới 15 giây. Không fallback sample tốt cũ nếu sample mới xấu. Không tạo API F3.
- Khóa thiết bị đăng ký mới được dẫn xuất HMAC từ secret local và actor/idempotency key, chỉ lưu hash thiết bị. Cache idempotency/audit không lưu plaintext key. Giữ DEVICE_KEY_DERIVATION_SECRET ổn định và sao lưu riêng an toàn cùng .env; đổi secret làm retry đăng ký cũ không khôi phục được key (409). List không trả key. Frontend chỉ giữ token và key vừa cấp trong bộ nhớ tab.

## Database và seed

Không cần migration mới: baseline Phase 1 đã đủ bảng/FK/enum. Head vẫn **0002_user_approval**; đã chạy current/upgrade head và seed hai lần trên DB demo. Provision grants thêm ghi assets và chỉ UPDATE(state, review_reason, version) của swaps cho tác động vô hiệu hóa thiết bị; không thêm quyền xóa lịch sử.

Demo 2 trạm × 6 ngăn, không reset password/custody/version/observations. Ngăn ban đầu BLOCKED/UNKNOWN; không có telemetry giả trong DB demo. Khả dụng 0 và RESTORE bị từ chối khi thiếu chứng cứ là hành vi đúng. Seed không giới hạn số trạm/ngăn mà Admin có thể thêm: QD01 quy định dữ liệu demo, OpenAPI chỉ yêu cầu slot_no≥1.

Test dùng schema riêng phase2_test_*, giữ lại bằng chứng; fixture vật lý/telemetry/giao dịch chỉ trong transaction rollback. API thực thi SET LOCAL ROLE doi_pin_runtime; bootstrap chỉ dùng ghi fixture. Không DROP/TRUNCATE/reset volume. Các lượt test tạo schema riêng, có thể làm DB tăng dần; không tự dọn schema vì chứa bằng chứng và cần duyệt riêng.

## Kiểm thử

**Kết quả cuối: 55 Passed, 0 Failed, 0 Skipped** (18 ca Phase 1 + 37 ca F2). Xem PHASE2_TEST_RESULTS.xml. Bao gồm toàn bộ 18 ca Phase 1 và TC03–05 mở rộng: seed 2×6, CRUD/idempotency, RBAC/scope, schema phản hồi, lỗi dữ liệu/version, trạng thái cửa độc lập, retirement, snapshot an toàn, pending ACK, alert ACK không được coi resolved, quarantine, reservation hết hạn vẫn giữ, availability fail closed, sample xấu mới nhất và cập nhật đồng thời (200/409).

- Frontend TypeScript/Vite build: Passed.
- HTTP qua Vite và Backend/DB demo: 14 checks Passed, không mutation assets (PHASE2_HTTP_SMOKE_RESULTS.json).
- OpenAPI validator, approved JSON Schema, parse 278 SQL statements, hash thiết kế gốc: Passed (PHASE2_CONTRACT_VALIDATION.json).
- pip check: Passed.
- Migration DB rỗng/nâng cấp có dữ liệu/chạy lại và seed chạy lại: Passed.
- Browser E2E tương tác đầy đủ: Not Run; không suy ra từ build hoặc HTTP smoke.
- F3/IoT/đổi pin/payment E2E: Not Run, ngoài phạm vi.

Lượt đầu 39 Passed/2 Failed do fixture sai tên cột credential, đã sửa và chạy lại thành công. Hai dependency deprecation warnings hiện hữu (Starlette/httpx, OpenAPI validate_spec) không làm fail. Không tự nâng thư viện trong lượt này.

## File thay đổi

- Backend mới: app/api/asset_schemas.py, app/api/assets.py, app/application/assets.py.
- Backend sửa: app/main.py, app/application/identity.py (aggregate_type audit, tương thích lời gọi cũ).
- Frontend mới src/Stations.tsx; sửa src/main.tsx, src/styles.css.
- Config/tool: .env.example, tools/provision_database.py, tools/dev.ps1, tools/smoke_phase2.py. .env local bổ sung secret nhưng không commit.
- Test: tests/test_phase2.py mới; sửa tests/conftest.py, tests/test_phase1.py (tập endpoint cho phép thêm F2).
- Tài liệu: README.md, docs/IMPLEMENTATION_PLAN.md, IMPLEMENTATION_STATUS.md, báo cáo này và PHASE2_* bằng chứng. Không sửa tài liệu gốc doi-pin-giai-doan-2/.

## Lệnh đã chạy

Đường dẫn công cụ dùng bản đã cài; PYTHONPATH=services/backend cho lệnh app/Alembic/pytest.

```powershell
git status --short
git diff --check
# Docker Desktop đang tắt: đã khởi động bản đã cài (cửa sổ ẩn), rồi start container hiện có
docker compose --env-file .env -f deploy/compose.yaml start db
docker compose --env-file .env -f deploy/compose.yaml ps
.venv/Scripts/python.exe tools/provision_database.py grants
.venv/Scripts/python.exe -m alembic -c services/backend/alembic.ini current
.venv/Scripts/python.exe -m alembic -c services/backend/alembic.ini upgrade head
.venv/Scripts/python.exe -m app.seed # chạy 2 lần
.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.cache/pytest-phase2-final --junitxml=docs/PHASE2_TEST_RESULTS.xml
npm.cmd --prefix apps/web run build
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe tools/validate_contracts.py docs/PHASE2_CONTRACT_VALIDATION.json
./tools/dev.ps1 backend
npm.cmd --prefix apps/web run dev -- --host 127.0.0.1
.venv/Scripts/python.exe tools/smoke_phase2.py
docker compose --env-file .env -f deploy/compose.yaml exec -T db sh -c 'du -sh /var/lib/postgresql/data'
```

Các lượt pytest trước dùng basetemp riêng r2/r3 để giữ dấu vết, không cài lại dependency. Git stage chọn lọc, kiểm secret/artifact và commit sau khi kiểm thử đạt; không push.

## Chạy lại và dung lượng

`tools/dev.ps1 database`, `tools/dev.ps1 backend`, terminal khác `tools/dev.ps1 frontend`. Frontend http://127.0.0.1:5173; Backend http://127.0.0.1:8000/docs; DB loopback5432. Server đang chạy tại thời điểm bàn giao; tránh chạy trùng port. Demo account và password lấy từ .env local, không có credential mặc định trong source.

Số đo: .venv≈95,84 MiB; node_modules≈56,39 MiB; dist≈0,23 MiB; .cache≈146,42 MiB; PostgreSQL data≈75 MiB (du trong container, không phải kích thước VHDX). Không tạo bản sao dự án, không tải/cài thêm thư viện. Không xóa file/volume nào.

Khi cần tiết kiệm dung lượng: dừng server rồi chỉ cân nhắc .cache (download/test cache) và apps/web/dist (build lại bằng npm run build). .venv và node_modules có thể tái tạo từ lockfiles nhưng cần tải lại, không nên dọn khi đang phát triển. Giữ source, migrations, thiết kế, docs bằng chứng, lockfiles, .git, .env local và DB; sao lưu .env riêng an toàn. Không dùng down -v hoặc prune volumes. Schema test chỉ dọn khi đã kiểm tra/sao lưu bằng chứng và được chấp thuận.
