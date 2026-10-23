# Trạng thái triển khai hệ thống đổi pin thông minh

Cập nhật: 24/10/2026 (Asia/Bangkok).

**Phase 1 hoàn tất và đã kiểm thử thành công. Dừng tại Phase 1, chưa bắt đầu Phase 2.** Phase 0 được người dùng xác nhận hoàn thành; P0-01/02/03 đã giải quyết theo [IMPLEMENTATION_DECISIONS.md](IMPLEMENTATION_DECISIONS.md).

## Tiến độ

| Phase | Trạng thái | Bằng chứng |
| --- | --- | --- |
| 0 Baseline/hợp đồng | Hoàn tất | 15 static checks ban đầu; validator chuẩn chạy bổ sung ở Phase 1 |
| 1 Nền tảng/định danh | Passed | 18 tests, build web, 5 HTTP smoke checks; bằng chứng bên dưới |
| 2 Trạm/ngăn/pin | Not Run | Chưa triển khai endpoint |
| 3 Thiết bị/bằng chứng | Not Run | Chưa triển khai |
| 4 Xác thực tại trạm/giữ chỗ/thu | Not Run | Chưa triển khai |
| 5 Trả/nhận/khôi phục | Not Run | Chưa triển khai |
| 6 Hoàn thiện UI/lịch sử/cảnh báo | Not Run | Chỉ có UI tài khoản thuộc Phase 1 |
| 7 Tích hợp/nghiệm thu toàn hệ thống | Not Run | Không suy ra từ TC01/02 |

## Môi trường đã xác minh

| Công cụ | Phiên bản/kết quả |
| --- | --- |
| Windows/WSL | Windows 11 build 26300.9711; WSL 3.0.3.0; docker-desktop chạy WSL2 |
| Python/pip | Python 3.12.10 cài tại LocalAppData/Python/pythoncore-3.12-64; pip 25.0.1; venv tại workspace |
| Node/npm | Node 24.22.1 và npm 11.19.1 tại Program Files/nodejs |
| Git | 2.56.0.windows.3 tại Program Files/Git; repo main tại workspace |
| Docker | Desktop 4.96.3; Engine 29.9.2 Linux; Compose 5.6.1 |
| PostgreSQL | 17.11, kết nối TCP 127.0.0.1:5432 thành công |
| Role DB | API dùng doi_pin_runtime; migration dùng doi_pin_migrator; bootstrap dùng postgres |
| Migration | 0002_user_approval (head); empty DB và nâng cấp có dữ liệu đã kiểm tra |

Không cài lại công cụ hệ thống hoặc sửa PATH Windows. Docker CLI chưa trên PATH của phiên Codex: helper tìm đường dẫn cài thật và chỉ bổ sung PATH của tiến trình khi cần credential helper, sau đó khôi phục. Docker/localhost bị sandbox chặn được chạy bằng quyền đã cấp.

Người dùng đã đồng ý tạo container/volume và tải postgres:17 nếu thiếu. Trước đó Docker không có container/volume. Đã tạo doi-pin-dev-db-1, network doi-pin-dev_default, volume doi-pin-dev_postgres17_data; không xóa dữ liệu/volume nào. PostgreSQL bind loopback, không cài PostgreSQL native.

Git đã cấu hình **local repository** theo tên/email người dùng cung cấp. Commit nghiệm thu dùng thông điệp `feat: initialize project foundation and authentication`; lấy hash bằng `git log -1 --oneline`. Không thay cấu hình Git global hoặc push remote.

## P0-01/02/03

- **P0-01 Passed:** migration mới thêm APPROVED_FOR_SIMULATION_BY_USER và approval_evidence; seed giữ đúng thẩm quyền duyệt user và hash nguồn approved; không giả TEAM_CONFIRMED. Policy immutable, audit append-only.
- **P0-02 Passed:** OpenAPI validator, Draft 2020-12 approved config và pglast parse 278 SQL statements. Hash 5 file baseline và 74 file manifest vẫn khớp. Output ở docs, không ghi đè biên bản/tài liệu gốc.
- **P0-03 Passed:** 422/CONFIG_NOT_READY cho policy thiếu/không hợp lệ; 503 cho DB/service unavailable. Startup fail closed; health/login không tạo phiên nếu policy hết hợp lệ. Test trực tiếp case thiếu fee. Reserve/payment chưa triển khai.

QD01–QD09, FR01–FR19, UC01–UC17, BR01–BR12 giữ nguyên. Seed 3 tài khoản/3 vai trò, 2 trạm, 12 ngăn, 11 pin (gồm pin khách đang giữ), assignment Technician tại S01. Ngăn BLOCKED/cửa UNKNOWN, không giả telemetry hoặc bật khả dụng trước Phase 2/3.

## Sản phẩm Phase 1

- FastAPI factory, cấu hình approved fail closed, SQLAlchemy/PostgreSQL, structured errors đã loại thông tin nhạy cảm.
- Opaque bearer token chỉ hash trong DB, password Argon2id; 5 lần sai/15 phút bằng counters/locks trong PostgreSQL, username và IP kết nối; không tin X-Forwarded-For tùy ý.
- Login/logout/me; Admin list/create/update users và station assignments; kiểm role hiện hành mỗi request; thu hồi session khi khóa/đổi role; chặn thay role còn custody/assignment/active swap, chặn khóa quản trị viên cuối.
- Mutation idempotency với request hash, principal/route/key; 409 khi đổi body hoặc version cũ. State, response idempotency và audit commit trước khi gửi HTTP response.
- React/TypeScript/Vite có login, profile ba vai trò, admin account list/create/lock/unlock/change role; token chỉ trong bộ nhớ tab; Vite proxy API.
- Hai forward migrations, provisioning role/schema/grants và seed idempotent; không reset credential/custody hiện có. DDL đầy đủ là nền tảng schema, chưa có API nghiệp vụ Phase 2+.

## File tạo/chỉnh sửa

| Nhóm | File |
| --- | --- |
| Backend | services/backend/app/config.py, main.py, api/schemas.py, application/identity.py, domain/identity.py, infrastructure/db.py, seed.py và các __init__.py |
| Migration | services/backend/alembic.ini, alembic/env.py, versions/0001_baseline.py, 0002_user_approval.py |
| Frontend | apps/web/package.json, package-lock.json, index.html, tsconfig.json, vite.config.ts, src/main.tsx, src/styles.css |
| Config/dependency | .env.example, deploy/compose.yaml, requirements.in, requirements.lock.txt, pytest.ini; .gitignore hiện có được giữ và sử dụng |
| Tool | tools/provision_database.py, validate_contracts.py, dev.ps1; helper Phase 0 giữ nguyên |
| Test | tests/conftest.py, tests/test_phase1.py |
| Tài liệu | README.md, IMPLEMENTATION_DECISIONS.md, IMPLEMENTATION_PLAN.md cập nhật, IMPLEMENTATION_STATUS.md này |
| Bằng chứng | CONTRACT_VALIDATION.json, PHASE1_TEST_RESULTS.xml, TEST_ENVIRONMENT.json, HTTP_SMOKE_RESULTS.json, PHASE1_ENVIRONMENT.json |
| Local không commit | .env secret ngẫu nhiên, .venv, node_modules, dist, .cache, .pytest_cache, __pycache__ |

Tài liệu gốc doi-pin-giai-doan-2 và tài liệu riêng docs/CODEX_11_BUOC_MODEL_VA_PROMPT.md không bị chỉnh sửa hoặc đưa vào commit source của lượt này. Source hiện tham chiếu bộ hồ sơ gốc tại workspace; README ghi rõ phải giữ/khôi phục bundle khi lấy source từ Git. Không tạo bản sao DOCX/ảnh hoặc bản backup dự án.

## Kiểm thử và bằng chứng

| Kiểm tra | Kết quả | Phạm vi |
| --- | --- | --- |
| Pytest | **18 Passed, 0 Failed** | 8.70 giây lượt cuối; TC01/TC02 và foundation checks |
| TC01 | Passed | Ba role login/me; token hash; từ chối cross-role; giới hạn login kể cả 6 request đồng thời; spoof XFF không reset; expiry/logout/replay; validation không lộ password |
| TC02 | Passed | Create/retry/conflict; pagination; khóa thu hồi session và giữ lịch sử; đổi role/version; assignment atomic và scope; giữ active Admin; audit/runtime permissions |
| Migration | Passed | Từ schema sạch tới 0001, thêm marker dữ liệu, upgrade 0002, lặp upgrade head giữ marker |
| Seed | Passed | Chạy lại không đổi password/hash và bản ghi hiện có; đủ trạm/ngăn và trạng thái approved |
| OpenAPI/JSON Schema/SQL | Passed | Validator chuẩn + live OpenAPI 8 operations (gồm health) |
| Frontend build | Passed | tsc --noEmit và Vite production build; không có lỗi CSS còn lại |
| Dependency integrity | Passed | pip check: No broken requirements found |
| HTTP thật | **5 Passed** | HTML/proxy health; admin/customer/technician login → me → users 200/403 → logout/revoked; live OpenAPI |
| Browser | Passed giới hạn | Màn hình login được mở và kiểm tra bố cục qua in-app browser; không chạy toàn bộ form E2E trên browser |
| TC03–19, CT01–14 đầy đủ, NFR performance/restore | Not Run | Thuộc các phase chưa giao |

Pytest có 2 deprecation warnings: Starlette TestClient dùng httpx và openapi-spec-validator.validate_spec. Không làm test thất bại; nên chuyển API/dependency tương ứng khi cập nhật toolchain, không nâng cấp global trong lượt này.

Có một lượt test đầu bị dừng vì fixture lịch sử tạo FK qua kết nối thứ hai khi tài khoản đang bị test giữ khóa. Đã sửa thứ tự fixture và đặt statement_timeout 15s/lock_timeout 5s; các lượt đầy đủ sau Passed. Không có test ứng dụng quan trọng đang Failed.

Tests dùng schema phase1_test_* riêng, API bằng role runtime, per-test rollback. Bốn schema từ các lượt test được giữ trong volume, có tên trong PHASE1_ENVIRONMENT.json; không xóa dữ liệu để làm sạch kết quả. Bằng chứng JUnit chỉ giữ lượt nghiệm thu cuối, log chẩn đoán cục bộ trong .cache.

## Lệnh đã chạy

- Đọc AGENTS, status/plan, START_HERE, handoff, approved decisions/config, invariants, OpenAPI và DDL; kiểm PATH/đường dẫn cài thật.
- Python --version, pip --version, node --version, npm.cmd --version, git --version/config, wsl --version/list --verbose, Docker version/compose version/ps/volume ls.
- Python 3.12 `-m venv .venv`; ensurepip được hoàn tất trong venv sau lỗi quyền thư mục tạm sandbox. Không thay Python nền; dependency dùng cache/tmp trong workspace.
- `.venv/Scripts/python.exe -m pip install -r requirements.in` với cache local; `pip freeze --all` tạo lock; `pip check`.
- `npm.cmd --prefix apps/web install --ignore-scripts --no-audit --no-fund` với cache .cache/npm; `npm.cmd --prefix apps/web run build`.
- `docker compose --env-file .env -f deploy/compose.yaml config --quiet`, `up -d --wait db`; truy vấn SQL read-only xác nhận server/role/count/revision; Docker image inspect và du đo dung lượng.
- `python tools/provision_database.py roles`, `python -m alembic -c services/backend/alembic.ini upgrade head`, `python tools/provision_database.py grants`, `python -m app.seed` (PYTHONPATH=services/backend).
- `python tools/validate_contracts.py docs/CONTRACT_VALIDATION.json`.
- `python -m pytest -q --basetemp=.cache/pytest-tmp-commit --junitxml=docs/PHASE1_TEST_RESULTS.xml` (lượt cuối).
- `tools/dev.ps1 backend`, `tools/dev.ps1 frontend`; HTTP smoke bằng httpx, credential đọc từ env và không in ra log; mở browser login.
- `git init -b main`, cấu hình tên/email local, `git check-ignore`, stage chọn lọc, kiểm secret/artifacts trước commit. Không git add toàn workspace, không push.

## Khởi động và tài khoản

Xem [README.md](../README.md) để chuẩn bị lần đầu. Trong workspace hiện tại, DB và môi trường đã khởi tạo:

```powershell
.\tools\dev.ps1 database
.\tools\dev.ps1 backend
# Terminal khác:
.\tools\dev.ps1 frontend
```

Frontend http://127.0.0.1:5173; Backend http://127.0.0.1:8000; Swagger /docs; health /health. Hai server đang chạy ở cuối lượt; không khởi động thêm nếu port đang được dùng.

User admin/customer/technician; mật khẩu tương ứng trong biến DEMO_ADMIN_PASSWORD, DEMO_CUSTOMER_PASSWORD, DEMO_TECHNICIAN_PASSWORD của .env local. Không có mật khẩu mặc định trong source hoặc báo cáo. Reload tab yêu cầu login lại vì token không lưu persistent.

## Dung lượng và dọn an toàn

Số đo trong PHASE1_ENVIRONMENT.json; dung lượng thực trên đĩa có thể khác do filesystem/Docker VHDX.

| Thư mục/tài nguyên | Dung lượng gần đúng | Tác động nếu dọn |
| --- | --- | --- |
| .venv | 95,84 MiB | Cần cài lại từ requirements.lock.txt; không xóa khi server đang chạy |
| apps/web/node_modules | 56,39 MiB | Cần npm ci; không xóa khi Vite đang chạy |
| apps/web/dist | 0,22 MiB | Build lại bằng npm run build |
| .cache | 146,42 MiB | Có thể tái tạo; npm ~125,89 MiB, pip ~19,91 MiB; giữ log cần chẩn đoán trước khi dọn |
| PostgreSQL image | ~610,29 MiB | Docker quản lý; không tự xóa |
| PostgreSQL volume | ~69,85 MiB | Chứa DB demo và schemas test, cần bảo toàn |

Không dọn file hoặc volume trong lượt này. Chỉ cân nhắc cache/build rõ nguồn gốc trong workspace khi cần. Giữ source, migrations, lockfile, thiết kế gốc, docs bằng chứng, .env local và DB để khôi phục; không dùng docker down -v/prune volumes. Source/config/tài liệu mới nhỏ, không có bản sao dự án hoặc backup trùng lặp.
