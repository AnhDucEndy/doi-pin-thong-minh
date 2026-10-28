# Hệ thống quản lý trạm đổi pin thông minh

Phase 1–7: FastAPI, React/TypeScript/Vite, PostgreSQL 17, Authentication/RBAC, trạm/ngăn, Battery/BMS, HTTP device inbox/worker, QR/RFID, reservation, Mock Payment và quy trình bàn giao pin mô phỏng theo QD01–QD09. Báo cáo và kết quả kiểm chứng: [docs/PHASE7_IMPLEMENTATION.md](docs/PHASE7_IMPLEMENTATION.md). Chưa triển khai Phase8 hoặc phần cứng/thanh toán thật.

## Phase 7 — Bàn giao pin mô phỏng

Device worker hiện điều phối OPEN_RETURN/OPEN_SUPPLY từ phiên đã thu phí và bằng chứng thiết bị. Không có API/nút mở cửa tự do. Màn hình QR/RFID và giữ tài nguyên hiển thị tiến trình từ Backend; chỉ COMPLETED mới là hoàn tất. ACK chỉ xác nhận nhận lệnh.

Simulator `normal` chỉ ACK; để chủ động demo bàn giao, chạy `python -m simulators.device.main --station both --scenario physical` trong `.venv` với `PYTHONPATH=services/backend`. Lệnh này làm thay đổi dữ liệu mô phỏng theo phiên đang hoạt động; không chạy vào DB demo chỉ để thử lỗi. Dùng `tools/smoke_phase7.py` cho E2E với schema/ledger test riêng. Hạn nhận/ACK15s, bằng chứng vật lý sau ACK tối đa60s từ lúc tạo lệnh, freshness15s. Lỗi/timeout giữ tài nguyên ở REVIEW_REQUIRED; không tự refund/cấp thêm. Không migration/dependency mới; giữ nguyên DB và `.local`.

## Phase 6 — Thanh toán mô phỏng

Giữ .env, DB và ledger hiện có. Chạy `.venv/Scripts/python.exe tools/init_payment_env.py` để chỉ bổ sung cấu hình còn thiếu; `tools/dev.ps1 migrate` cập nhật grants trên các bảng đã có (head0002, không DDL/migration mới). Không cần cài dependency mới. Mở terminal riêng cho `tools/dev.ps1 payment` (private provider8001), `tools/dev.ps1 payment-worker`; tùy chọn `tools/dev.ps1 payment-callbacks` để gửi callback HTTP từ ledger. Backend, device worker và Frontend giữ lệnh đang dùng.

Customer mở **QR/RFID và giữ tài nguyên**, giữ đủ pin+hai ngăn qua evidence hợp lệ, xem quote rồi **Đồng ý phí và thanh toán mô phỏng**. Phí từ Backend/policy approved là9.000VND. Admin có thể **Đối soát cùng khoản thu** PENDING/UNKNOWN. UNKNOWN giữ tài nguyên và chỉ query cùng provider_key. SUCCEEDED chỉ xác nhận thu phí mô phỏng; chưa mở cửa, giao pin hoặc hoàn tất Swap. Cửa/BMS đổi hoặc cũ sau thu khiến phiên REVIEW_REQUIRED. Không bật kịch bản lỗi trên DB demo; dùng `tools/smoke_phase6.py` để chạy success/failure/mất response/restart trên schema và ledger test riêng.

Giữ `.local/payment/ledger.sqlite3` cùng DB; không xóa ledger để retry. Không có cổng thanh toán thật hoặc API cho Browser chọn kết quả. Các đoạn hướng dẫn phase trước bên dưới là lịch sử nâng cấp, không thay thế báo cáo Phase6.

Từ Phase4 lên Phase5: giữ .env/DB/ledger, chạy `tools/dev.ps1 migrate` để cập nhật grants (không migration cấu trúc mới, head0002), khởi động lại Backend và worker. Frontend thêm qrcode theo package-lock; dùng npm ci trong apps/web nếu dependency mới chưa có. Menu **QR/RFID và giữ tài nguyên** dành Customer/Admin. Reader mô phỏng chạy bằng `.venv/Scripts/python.exe -m simulators.device.authenticate --station S01 --method QR` (hoặc RFID), PYTHONPATH=services/backend; nhập credential ẩn trong terminal, không truyền token qua argv và không đưa Device-Key lên browser. Hướng dẫn demo/test schema riêng trong báo cáo Phase5; không có nút mở cửa/thu phí trước Phase6–7.

## Chuẩn bị

- Windows 11, Python 3.12, Node.js 24 LTS/npm, Git, Docker Desktop/WSL2 đang chạy.
- Giữ nguyên bộ tài liệu `doi-pin-giai-doan-2/` trong workspace: ứng dụng đọc approved policy/schema và hợp đồng tại đó; validator/test đối chiếu bản gốc. Bộ DOCX/ảnh thiết kế không nằm trong commit source Phase 1 theo yêu cầu; khi khôi phục source từ Git cần đặt lại bộ hồ sơ này từ bản bàn giao đã giữ.
- Không cài thêm PostgreSQL native. Một `.venv/` và một bộ node_modules tại apps/web.

Tại gốc workspace, dùng Python 3.12 đã cài của bạn:

```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --cache-dir .cache/pip -r requirements.lock.txt
npm.cmd --prefix apps/web ci --cache .cache/npm
```

Không tạo lại venv nếu đã hoạt động. `requirements.in` mô tả giới hạn dependency trực tiếp; requirements.lock.txt đóng băng bộ Python đã test; package-lock.json đóng băng npm. Không nâng cấp công cụ toàn hệ thống để chạy dự án.

## Cấu hình local

Copy `.env.example` thành `.env` nếu chưa có, thay toàn bộ REPLACE_* bằng secret ngẫu nhiên riêng. Các URL phải khớp password tương ứng; nếu dùng ký tự đặc biệt, URL-encode phần password. Không ghi mật khẩu thật vào README hoặc terminal chia sẻ.

`.env` hiện tại trong workspace đã được tạo bằng secret ngẫu nhiên và bị Git ignore; không copy đè nếu đã có DB. Biến POSTGRES_PASSWORD chỉ khởi tạo mật khẩu lần đầu của volume trống; thay file env không tự đổi mật khẩu DB đã có.

## Cập nhật từ Phase 1 lên F2

Giữ nguyên `.env` và volume. Bổ sung `DEVICE_KEY_DERIVATION_SECRET` ngẫu nhiên tối thiểu 32 ký tự vào `.env` (xem `.env.example`), giữ ổn định để retry đăng ký thiết bị trả cùng khóa. Không in/chia sẻ secret. Chạy `tools/dev.ps1 migrate` để bảo đảm head và cập nhật DB grants; `tools/dev.ps1 seed` chạy lại an toàn. Không có migration cấu trúc mới.

Sau đăng nhập, chọn **Trạm và ngăn tủ**. Customer chỉ thấy khả dụng tổng hợp; Technician xem và bảo trì ngăn đúng trạm; Admin quản lý trạm/thiết bị/ngăn. Ngăn seed BLOCKED/cửa UNKNOWN; khả dụng bằng 0 khi chưa có dữ liệu hợp lệ. RESTORE cần SNAPSHOT mới đã xử lý, không có nút mở cửa. Admin có mục Tài khoản riêng giữ chức năng Phase 1.

## Khởi tạo lần đầu

Từ Phase 3 lên Phase 4: `tools/dev.ps1 migrate` cập nhật grants inbox/worker, head vẫn 0002, không có migration cấu trúc mới. Không cần seed lại hoặc chạy schema.sql. Mở terminal riêng cho `tools/dev.ps1 backend`, `tools/dev.ps1 worker`, `tools/dev.ps1 frontend`, và khi muốn chạy demo hợp lệ: `tools/dev.ps1 simulator` (hai trạm). Key simulator lấy DEMO_DEVICE_KEY_S01/S02 từ .env, không nhập lên Frontend. Simulator mặc định chỉ snapshot/heartbeat/BMS và ACK; không tự kích hoạt pin/ngăn hoặc đổi custody. CLI và các kịch bản lỗi/schema test xem báo cáo Phase 4.

Ledger `.local/device/*.sqlite3` là dữ liệu bền vững, đã gitignore; giữ và sao lưu cùng DB khi cần khôi phục. Không xóa ledger để retry command. Menu **Thiết bị và IoT** hiển thị heartbeat, online/offline, dashboard theo scope và cảnh báo; ACK không gỡ cách ly. Không có nút mở cửa tùy ý. `--scenario physical/hot/fault/...` chỉ dùng trên schema test; xem `tools/smoke_phase4.py` để chạy E2E tách biệt.

Đã có Phase 2: chạy `tools/dev.ps1 migrate` để cập nhật grants F3 (head vẫn 0002), rồi `tools/dev.ps1 seed`; không chạy DDL gốc. Seed chỉ bổ sung mẫu SOC/SOH/nhiệt độ **chưa xác minh**, không đổi vị trí/lifecycle/cửa/heartbeat. Chọn menu **Pin và BMS**, **Xem hồ sơ và BMS** để xem dữ liệu; Admin đăng ký/ngừng pin, Technician đúng trạm kích hoạt/cách ly/phục hồi bằng SNAPSHOT hợp lệ. Mẫu seed không phải bằng chứng để kích hoạt/phục hồi; khả dụng vẫn 0 cho đến khi có đủ chứng cứ của module thiết bị. Không có form sửa BMS hoặc vị trí pin đang phục vụ.

Các lệnh sau tạo DB/container/volume nếu chưa có; cần đồng ý trước khi dùng trên máy mới. Sự đồng ý đã có cho lượt triển khai hiện tại.

```powershell
.\tools\dev.ps1 database
.\tools\dev.ps1 provision
.\tools\dev.ps1 migrate
.\tools\dev.ps1 seed
.\tools\dev.ps1 validate
```

PostgreSQL chỉ bind 127.0.0.1:5432; schema doi_pin. Provision tạo role migrator/runtime nếu thiếu, không thay mật khẩu role có sẵn. Migration dùng role riêng; seed không ghi đè dữ liệu có sẵn. Không chạy DDL gốc thêm lần nữa. Không downgrade hoặc xóa schema/volume để sửa lỗi.

Nếu không chạy được file .ps1 do chính sách, không cần thay Execution Policy: gọi trực tiếp các lệnh Python/npm tương đương trong file hoặc mở bằng PowerShell 7 với chính sách sẵn có của bạn.

## Chạy ứng dụng

Mở hai terminal tại gốc:

```powershell
# Terminal 1
.\tools\dev.ps1 backend

# Terminal 2
.\tools\dev.ps1 frontend
```

Frontend: http://127.0.0.1:5173. Backend: http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/health. Vite proxy /v1 và /health sang Backend nên không cần public CORS.

Tài khoản demo: admin, customer, technician. Password lấy từ DEMO_ADMIN_PASSWORD, DEMO_CUSTOMER_PASSWORD, DEMO_TECHNICIAN_PASSWORD trong `.env` local. Token chỉ nằm trong bộ nhớ tab; tải lại trang yêu cầu đăng nhập lại. Admin quản lý tài khoản; hai vai trò còn lại có màn hình phiên của mình. Không cung cấp mật khẩu mặc định công khai.

Chạy Backend trực tiếp nếu cần:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'services/backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

## Kiểm tra

```powershell
.\tools\dev.ps1 test
npm.cmd --prefix apps/web run build
.\.venv\Scripts\python.exe -m pip check
```

Test cần quyền kết nối localhost và role admin/migrator để chuẩn bị schema test riêng; không chạy bằng SQLite. Bằng chứng: docs/PHASE1_TEST_RESULTS.xml, docs/TEST_ENVIRONMENT.json và docs/CONTRACT_VALIDATION.json. TC01/02 bao phủ login/role, wrong-password/rate limit, concurrent failures, expiry/logout, account locking/revocation, create/update/assignments, idempotency/version conflict và bảo toàn lịch sử. Không coi đó là nghiệm thu TC03–19.

## Dừng và dung lượng

Ctrl+C ở từng terminal để dừng web/API. Dừng DB mà giữ dữ liệu:

```powershell
# Dùng docker.exe tại đường dẫn đã cài nếu CLI chưa trên PATH
docker compose --env-file .env -f deploy/compose.yaml stop db
```

Không dùng `down -v`, `docker volume prune`, `DROP DATABASE/SCHEMA` hoặc xóa .git/ để dọn máy. DB và các schema test nằm trong volume Docker, ngoài workspace; không di chuyển VHDX thủ công.

`.venv/`, apps/web/node_modules và apps/web/dist có thể tạo lại từ dependency/lockfile, nhưng xóa venv/node_modules sẽ cần cài lại. `.cache/pip`, `.cache/npm` và thư mục pytest tạm là cache có thể tái tạo; kiểm tra đúng đường dẫn trong workspace trước khi dọn. Giữ source, migrations, lockfile, tài liệu gốc, docs bằng chứng, `.env` local và DB/ledger quan trọng để khôi phục.
