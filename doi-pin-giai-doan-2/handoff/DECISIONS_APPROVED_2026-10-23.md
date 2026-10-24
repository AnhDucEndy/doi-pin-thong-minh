# PHỤ LỤC CHỐT QD01–QD09 — ngày 23/10/2026

**Trạng thái:** người dùng đã đồng ý phương án thiết kế và yêu cầu chốt các quyết định để triển khai đồ án mô phỏng. **Không** tự suy ra toàn bộ thành viên/giảng viên đã ký duyệt. Phạm vi: simulation-only; không thay đổi baseline FR01–FR19, UC01–UC17, BR01–BR12 hay MVP.

## Quyết định

- **QD01:** Chốt 2 trạm, mỗi trạm 6 ngăn, một dòng pin, thiết bị mô phỏng.
- **QD02:** Pin thuộc mạng lưới; tạo seed trạng thái pin ban đầu do khách giữ; không hỗ trợ pin riêng.
- **QD03:** Thu trước bằng payment mock, phí cố định 9.000 VND/lượt; chưa áp dụng 20 lượt miễn phí.
- **QD04:** Pin trả sai loại/không nhận diện: không cấp pin mới; tạm giữ trạng thái, kỹ thuật xác minh và xử lý.
- **QD05:** QR dùng một lần và RFID mô phỏng; tài khoản cấp sẵn; không coi RFID UID là bảo mật của phần cứng thật.
- **QD06:** Admin và Technician độc lập, backend cưỡng chế RBAC/ownership.
- **QD07:** Phí 9.000 VND/lượt (giá V-Green tham khảo); ngưỡng phát pin SOC >=80%, SOH >=80%, T <=40°C là GIẢ ĐỊNH DEMO; TTL và timeout giữ theo GĐ2. Không coi mức T là tiêu chuẩn an toàn. Cảnh báo/lỗi BMS vẫn chặn phục vụ theo BR.
- **QD08:** Lập kế hoạch theo 5 thành viên, 8 giờ/người/tuần, 10 tuần, có thể điều chỉnh phân công tên thực tế.
- **QD09:** Người dùng đồng ý phương án thiết kế FR01–19, UC01–17, BR01–12 và MVP để chuyển sang triển khai từng module. Không thay cho phê duyệt chính thức của giảng viên hay biên bản của các thành viên khác.

## Cơ sở chọn QD07

- **9.000 VND/lượt:** giá dịch vụ đổi pin niêm yết trên trang chính thức V-Green (thông tin truy cập 23/10/2026). Với tiền VND dạng số nguyên trong schema, `fee_minor: 9000` tương ứng 9.000 VND (dù trường tên `_minor`). Không nhân 100.
- V-Green công bố ưu đãi 20 lượt miễn phí mỗi tháng cho khách đủ điều kiện đến 30/06/2028. **Không mô phỏng ưu đãi trong MVP**, vì baseline đã xác định thu phí cố định; nếu nhóm cần mô phỏng chính sách VinFast y hệt, phải nâng cấp thiết kế tính hạn mức theo tháng.
- **SOC cấp >=80%:** giả định mô phỏng để có tình huống đủ/thiếu dung lượng; không phải thông số bắt buộc được V-Green công bố cho pin cấp. VinFast có bài hướng dẫn sử dụng pin LFP/Gotion trong dải SOC 20–100%, nhưng đó không phải chuẩn cấp pin khi đổi.
- **SOH cấp >=80%:** giả định chất lượng pin cấp trong demo. V-Green công bố **SOH >70% cho pin nhận trả**, không phải ngưỡng SOH tối thiểu cho pin cấp. **Không áp dụng quy tắc 80% để tự động từ chối pin khách trả**; luồng pin trả tiếp tục theo BR05 và quy tắc BMS/thiết bị.
- **Nhiệt độ cấp <=40°C:** ngưỡng vận hành bảo thủ phục vụ logic cảnh báo/không cấp pin trong simulator. Trang VinFast Amio S khuyên không sạc khi nhiệt độ pin >45°C và không nhận sạc trên 50°C, **không phải quy chuẩn nhiệt độ cấp pin cho các mẫu xe đổi pin**. Không sử dụng 40°C làm ngưỡng chống cháy nổ ngoài thực tế; cần BMS, đặc tính thiết bị và kiểm thử an toàn chuyên ngành.
- Các TTL/timeout được giữ từ bản thiết kế GĐ2, chỉ là cấu hình thử nghiệm; không khẳng định là thông số ngành.

## Tài liệu tham khảo công khai

1. [V-Green: chính sách và tủ đổi pin](https://vgreen.net/san-pham-dich-vu?tab=xemay)
2. [V-Green: hướng dẫn đổi pin và ưu đãi](https://vgreen.net/vi/huong-dan-doi-pin-tai-tu-doi-pin-v-green-trong-3-buoc)
3. [VinFast: hướng dẫn dùng LFP/Gotion](https://vinfastauto.com/vn_vi/luu-y-su-dung-doi-voi-pin-cell-lfp-gotion)
4. [VinFast Amio S: lưu ý nhiệt độ khi sạc](https://vinfastauto.com/vn_vi/xe-may-dien-vinfast-amio-s)

## Cấu hình đã thống nhất

| Mục | Giá trị | Loại |
| --- | --- | --- |
| phí đổi pin | 9.000 VND/lượt | Giá tham khảo V-Green + chọn chính sách phí cố định demo |
| SOC tối thiểu cho pin cấp | 80% | Giả định demo |
| SOH tối thiểu cho pin cấp | 80% | Giả định demo (tùy chọn trong schema cũ) |
| nhiệt độ tối đa cho pin cấp | 40°C | Giả định demo, không phải chuẩn an toàn thực |
| QR hết hạn | 120 giây | Giữ thiết kế GĐ1/GĐ2 |
| thời gian telemetry | 5 giây | Giữ thiết kế GĐ1/GĐ2 |
| stale/offline | 15 giây | Giữ thiết kế GĐ1/GĐ2 |
| giữ chỗ | 120 giây | Giữ thiết kế GĐ2 |
| chờ thao tác vật lý | 60 giây | Giữ thiết kế GĐ2 |
| hạn lệnh | 15 giây | Giữ thiết kế GĐ2 |
| thời gian query payment | 30 giây | Giữ thiết kế GĐ2 |
| thời hạn verification | 120 giây | Giữ thiết kế GĐ2 |
| phiên web | 3.600 giây | Giữ thiết kế GĐ2 |
| poll UI | 3 giây | Giữ thiết kế GĐ2 |
| giới hạn đăng nhập | 5 lần sai/15 phút | Giữ thiết kế GĐ1/GĐ2 |

## Ưu tiên và bảo toàn bản gốc

1. `baseline/*` và tài liệu GD1/GD2 được giữ **nguyên trạng** để có lịch sử thiết kế và SHA256 cũ vẫn có ý nghĩa.
2. Phụ lục này cùng `handoff/decisions.approved.json` và `contracts/demo-config.approved.yaml` là **quyết định mới nhất**, được ưu tiên hơn các dòng "chưa xác nhận" trong bản DOCX 0.2 và `handoff/decisions.json` nguyên bản.
3. Việc xác nhận này **không ủy quyền sửa FR/UC/BR**, thêm tính năng mới, hoặc triển khai ra trạm thật.
4. Trước khi lập trình nghiệp vụ, Codex cần đánh giá phần phụ thuộc QD07, ghi nhận cấu hình policy theo revision/snapshot để giao dịch cũ không bị tính lại giá; không lược các guard lỗi/stale/UNKNOWN.
5. Nhóm nên thông báo cho giảng viên về các chính sách mô phỏng, đặc biệt về quyền sở hữu pin, thu phí trước và ngưỡng dữ liệu giả định.

**Kiểm tra thực hiện khi đóng gói:** cấu hình .approved.yaml đã được kiểm tra với JSON Schema gốc; không có DB/API/UI được chạy.
