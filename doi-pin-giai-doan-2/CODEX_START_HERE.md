# CODEX — ĐỌC FILE NÀY TRƯỚC

Người dùng đã đồng ý các QD01–QD09 và chọn ngưỡng/giá mô phỏng trong ngày 23/10/2026. Đây là bổ sung mới **sau** khi tạo hồ sơ GD2 0.2. Không coi dòng trạng thái "chưa xác nhận" ở DOCX hoặc handoff cũ là quyết định cuối cùng.

**Thứ tự ưu tiên (chỉ với QD và cấu hình):**
1. `handoff/DECISIONS_APPROVED_2026-10-23.md` và `handoff/decisions.approved.json`.
2. `contracts/demo-config.approved.yaml` (khi chạy simulator; không dùng `demo-config.proposed.yaml` chứa null).
3. `handoff/CODEX_HANDOFF.md` và tài liệu GĐ1/GĐ2 để triển khai các module. Bản gốc giữ nguyên để đối chiếu.

Chỉ làm mô phỏng và thực hiện từng module; đừng tự mở rộng trả miễn phí 20 lượt như VinFast vì MVP đang thu phí cố định 9.000 VND/lượt. Ngưỡng SOC/SOH/nhiệt độ là giả định demo, không phải thông số vận hành thực.

Kiểm tra `demo-config.approved.yaml` khớp schema; thực hiện giai đoạn 0 trong handoff (xác nhận baseline) rồi giai đoạn 1 (nền tảng). Ghi rõ chạy test nào và kết quả; chưa có chạy runtime nào được thực hiện ở bộ hồ sơ này.
