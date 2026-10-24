# Tiêu chí kiểm thử bổ sung

Các CT bổ sung không thay TC01–TC19 Giai đoạn 1. Đây là tiêu chí chưa chạy trên ứng dụng.

## CT01 — Hai yêu cầu cùng khách đồng thời
Một swap active; yêu cầu còn lại 409; không thu hai lần.

## CT02 — Hai khách tranh pin hoặc ngăn trả cuối
Chỉ một reservation thành công; rollback không để tài nguyên mồ côi.

## CT03 — Mất response thu tiền và callback đến muộn
Payment UNKNOWN; query cùng provider key; đúng một charge; callback trùng không đổi kết quả.

## CT04 — ACK mở cửa nhưng cảm biến không đổi
Không xác nhận nhận/trả pin; chuyển review khi hết hạn.

## CT05 — Sai serial hoặc pin không biết nguồn
Không phát pin mới; lưu bằng chứng, khóa tài nguyên và mở case.

## CT06 — Mất điện sau tác động cơ khí rồi restart
Ledger command bền vững; không tác động lần hai; snapshot và đối soát trước tiếp tục.

## CT07 — Đã trả pin nhưng chưa nhận pin mới
Custody pin cũ cập nhật theo bằng chứng; hoàn phí và trả/quyết toán pin cũ là hai bước riêng.

## CT08 — Không rõ khách đã lấy pin mới
Không tự hoàn tiền hay phát pin khác; giữ review và reservation đến đối soát.

## CT09 — Telemetry trùng đảo thứ tự hoặc quá hạn
Không làm mới dữ liệu bằng timestamp cũ; không biến pin nguy hiểm thành khả dụng.

## CT10 — Truy cập chéo khách hoặc sai trạm kỹ thuật
403 hoặc 404 nhất quán; không lộ lịch sử, tiền hoặc khóa.

## CT11 — Retry cùng key khác body hoặc version cũ
409; không tạo side effect mới; cùng key cùng body nhận lại kết quả.

## CT12 — Phí hoặc ngưỡng bắt buộc còn null
Không reserve; lỗi CONFIG_NOT_READY; không tự dùng ngưỡng mặc định.

## CT13 — Hoàn tiền timeout rồi retry
Một refund intent, cùng key; UNKNOWN giữ đối soát; không hoàn hai lần.

## CT14 — Sao lưu rồi khôi phục database và simulator
Giữ audit, idempotency và command ledger; không mở lại lệnh đã thực thi.

NFR kế thừa: QR 120 giây; khóa thử sai 5 lần/15 phút; telemetry 5 giây và stale sau 15 giây; đọc p95 ≤ 2 giây với 20 phiên đồng thời, 1000 request. Ghi phần cứng, dataset, thời lượng, percentiles và tỷ lệ lỗi khi đo. Các timeout kỹ thuật khác là đề xuất cần chốt.
