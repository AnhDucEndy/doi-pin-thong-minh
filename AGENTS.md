# Quy ước Codex – Đồ án hệ thống đổi pin thông minh

## Nguồn yêu cầu và phạm vi
- Trước khi thay đổi code, đọc `doi-pin-giai-doan-2/CODEX_START_HERE.md`, `doi-pin-giai-doan-2/handoff/CODEX_HANDOFF.md`, các quyết định đã duyệt, OpenAPI và các invariants liên quan. Nếu workspace được mở trực tiếp trong `doi-pin-giai-doan-2/`, bỏ tiền tố thư mục này khi tìm file.
- Tuân thủ FR01–FR19, UC01–UC17, BR01–BR12 và QD01–QD09 đã chốt cho MVP mô phỏng. Không tự ý đổi thứ tự thu phí/đổi pin, thêm nghiệp vụ ngoài MVP, thanh toán thật hoặc điều khiển phần cứng thật.
- Sử dụng `contracts/demo-config.approved.yaml` và `handoff/decisions.approved.json` cho các QD đã chốt; nếu mâu thuẫn với baseline cũ, nêu rõ và yêu cầu xác nhận trước khi thay đổi bản chất nghiệp vụ.

## Cách làm việc
- Thực hiện theo từng phase/module của `handoff/CODEX_HANDOFF.md`; đọc code hiện có trước khi sửa và giữ các thay đổi trong phạm vi phase được giao.
- Dùng React + TypeScript + Vite; Python + FastAPI + SQLAlchemy + Alembic; PostgreSQL; simulator và payment mock tách biệt theo thiết kế.
- Luôn kiểm tra xác thực, phân quyền, idempotency, ràng buộc nhất quán và trạng thái không xác định ở Backend. Không coi ACK/timeout là bằng chứng bàn giao pin thành công.
- Sau mỗi phase, báo cáo file thay đổi, lệnh đã chạy, kết quả kiểm thử Passed/Failed/Not Run và những vấn đề còn mở. Không khẳng định test đã chạy khi chưa chạy.

## File, dung lượng và môi trường Windows
- Giữ mã nguồn, tài liệu sinh ra và cấu hình ứng dụng trong workspace; không tạo bản sao dự án không cần thiết.
- Ưu tiên môi trường Python `.venv/` trong dự án; tạo `.gitignore` cho `.venv/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`, log, file tạm và file `.env` có secret.
- Không tự ý cài công cụ toàn hệ thống, xóa dữ liệu, dọn thư mục bên ngoài workspace hoặc xóa Docker volumes. Hỏi trước các thao tác phá hủy hoặc có nguy cơ mất dữ liệu.
- Cache và artifacts chỉ được dọn khi chắc chắn có thể tạo lại; không xóa source, migrations, tài liệu thiết kế, `.git/`, dữ liệu DB hay tệp chứa bằng chứng kiểm thử.
- Sau từng phase, nêu những thư mục cache/build có thể dọn và tác động của việc xóa. Không cần tự dọn ngay nếu chưa được yêu cầu.
