# Quyết định triển khai Phase 1

Ngày: 24/10/2026. Nguồn: QD01–QD09 approved và đề xuất đã được người dùng yêu cầu thực hiện. Tài liệu thiết kế GĐ1/GĐ2 được bảo toàn; không có thay đổi FR/UC/BR.

## P0-01 đã giải quyết

Migration `0001_baseline` đóng băng DDL gốc, đủ 24 bảng và 16 enum, không triển khai endpoint nghiệp vụ các phase sau. `0002_user_approval` mở rộng CHECK của `demo_policies.review_status` để nhận `APPROVED_FOR_SIMULATION_BY_USER`; không thay tên hoặc diễn giải lại TEAM_CONFIRMED.

Seed ghi revision 1 với parameters approved và approval_evidence chứa thẩm quyền user, ngày 23/10/2026, đường dẫn và SHA256 decisions.approved.json. Không tạo người xác nhận giả trong users. Policy revisions bất biến bằng trigger; thay đổi sau này cần revision mới và snapshot trên swap theo thiết kế.

Migration cũng bảo vệ audit append-only bằng trigger. Role runtime có SELECT, INSERT/UPDATE chỉ cho các bảng định danh cần ở Phase 1, INSERT audit, DELETE chỉ bảng phân công để thay tập assignment nguyên tử; không DELETE lịch sử/audit, không DDL hoặc cập nhật policy. Role migrator riêng, không superuser/CREATEDB/CREATEROLE.

Downgrade phá hủy bị từ chối bằng RuntimeError; chỉ có forward migrations. Không thực hiện DROP DATABASE/SCHEMA, TRUNCATE hoặc xóa Docker volume.

## P0-02 đã giải quyết

`tools/validate_contracts.py` dùng openapi-spec-validator, JSON Schema Draft 2020-12 và pglast. Input cấu hình là demo-config.approved.yaml. Kết quả mới ở docs/CONTRACT_VALIDATION.json; không chạy script gốc ghi đè structural-checks.json.

Kết quả: OpenAPI Passed, approved config Passed, 278 câu lệnh SQL parse Passed; manifest baseline/bàn giao vẫn khớp. Đây là kiểm tra tĩnh; migration và integration tests PostgreSQL có bằng chứng riêng.

## P0-03 đã giải quyết

Thống nhất theo OpenAPI máy: HTTP 422 với `CONFIG_NOT_READY` nếu policy thiếu/chưa approved/sai phạm vi đã chốt; HTTP 503 cho DB/dịch vụ chưa sẵn sàng. Startup thiếu policy từ chối khởi động; nếu file mất hiệu lực khi server đang chạy, health/login trả 422 và không tạo phiên. Không có default giá/ngưỡng thay thế.

Phase 1 chưa có reserve/payment endpoint, nên không giả lập các thao tác đó để kiểm thử. Guard tương ứng phải tiếp tục dùng khi các module được giao ở phase sau. Test P0-03 kiểm tra health/login fail closed.

## Hợp đồng Phase 1

Chỉ triển khai login/logout/me, list/create/update users và assign station. Generated OpenAPI lọc đúng các operation đã có từ hợp đồng gốc, giữ operationId, x-fr/x-uc/x-roles, schema, mã lỗi và security; thêm /health cho vận hành. Không đưa endpoint credentials/QR, CRUD trạm/pin, swap, payment hoặc telemetry vào Phase 1.

Bearer opaque được sinh ngẫu nhiên, chỉ hash lưu DB; không JWT, không token chứa quyền cố định. Mỗi request đọc tài khoản/role hiện hành. Password Argon2id; khóa/đổi vai trò thu hồi toàn bộ session của tài khoản. Admin và Technician không kế thừa nhau; guard trạm kiểm assignment.

Login failure counters theo username và IP thật từ kết nối, PostgreSQL advisory transaction lock, 5 lần sai/900 giây; không tin X-Forwarded-For tùy ý. Deployment hiện chỉ loopback, uvicorn mặc định không đọc proxy headers (xem lệnh chạy). Mutation dùng UUID Idempotency-Key + principal + route + canonical request hash, phản hồi và audit commit nguyên tử. Giữ key tối thiểu 72 giờ, hiện chưa có cleanup tự động.

## Hạ tầng và dữ liệu được cho phép

Người dùng đồng ý tạo PostgreSQL container/volume và tải postgres:17 nếu thiếu trong lượt này. Project Compose doi-pin-dev; volume doi-pin-dev_postgres17_data. Không tìm thấy container/volume trước khi tạo; không xóa hoặc thay thế tài nguyên khác.

`.env` chứa secret ngẫu nhiên tạo local, không được commit. Seed thêm bản ghi thiếu theo UUID ổn định, không reset mật khẩu/key hoặc ghi đè custody/policy có sẵn. Ngăn BLOCKED, cửa UNKNOWN; không giả telemetry hoặc phục hồi pin ở Phase 1.

Tests tạo schema phase1_test_* mới trong DB doi_pin, kiểm empty migration → có bản ghi → upgrade → repeat head, sau đó chạy API bằng role runtime và rollback giao dịch riêng mỗi test. Các schema test được giữ để truy vết; không tự xóa. Một lượt test đã bị dừng khi fixture lịch sử chờ khóa; fixture được sửa và lượt đầy đủ được chạy lại, bằng chứng cuối là lượt Passed.
