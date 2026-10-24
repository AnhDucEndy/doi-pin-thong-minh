# Ràng buộc ngoài DDL và trách nhiệm triển khai

DDL là thiết kế nền, không tự đảm bảo toàn bộ nghiệp vụ. Không cho client/role ứng dụng chạy UPDATE trạng thái tùy ý.

## Giao dịch và khóa
1. UC09: khóa user, kiểm tra role/state và active swap; khóa QR (nếu dùng), kiểm tra hash/trạm/hạn; tạo VERIFIED và consumed_at cùng commit. Unique index một active swap là lớp bảo vệ cuối. VERIFIED hết verification_ttl và chưa giữ tài nguyên có thể CANCELLED.
2. Reserve: khóa theo thứ tự cố định user → swap → compartments sắp UUID → batteries sắp UUID. Kiểm tra lại online/quality/family/SOC/door/presence/lifecycle/location và policy đầy đủ trong transaction. Ghi old/new IDs, hai ngăn cùng trạm, amount và resource_reservations (pin mới + hai ngăn; pin cũ bảo vệ bởi active swap của khách). Rollback toàn bộ nếu xung đột. Không khóa DB trong lúc chờ khách/HTTP.
3. Thanh toán: sau consent, lock swap; tạo payments một lần, AWAITING_PAYMENT và outbox cùng commit. Worker retry cùng provider_key. CREATED mà chưa rõ đã dispatch không được tự cancel hoặc giải phóng giữ chỗ.
4. Nhận pin cũ: event phải cùng device/trạm/swap/command, đủ chuỗi sự kiện và cửa đóng; đối chiếu serial, family và holder. Ghi location về ngăn, bỏ holder, return_observed_at và RETURN_ACCEPTED nguyên tử. Không cập nhật vị trí theo mọi telemetry đơn lẻ.
5. Cấp pin: check lại BR02/BR11, payment SUCCEEDED và returned evidence; một lệnh OPEN_SUPPLY/phiên. Khi pin mới đã lấy và cửa đóng: chuyển location cho khách (đã không giữ pin cũ), COMPLETED, closed_at, release các reservation và audit trong một transaction.
6. Lỗi/timeout: giữ reservation; REVIEW_REQUIRED. Không tự mở ngăn khác. Hoàn tiền không tự trả lại pin cũ. REPLAY/ACK không là bằng chứng cấp pin.
7. Hoàn: khóa swap → payment → refund; kiểm tra Admin, payment SUCCEEDED, recovery.new_pin_delivered=NO dựa thiết bị đã đối soát và không còn lệnh có thể thực thi. Amount phải bằng payment và tổng hoàn không vượt thu. Unique refund/payment chống tạo nhiều khoản hoàn. Refund FAILED retry cùng intent chỉ khi provider xác nhận không hoàn trước đó; UNKNOWN chỉ query.
8. Kết thúc bù trừ: CLOSED_COMPENSATED chỉ khi refund SUCCEEDED và pin cũ đã giải quyết có chứng cứ. Nếu chưa từng nhận pin cũ, xác minh khách vẫn giữ đúng pin mới đặt old_pin_settled=true. Nếu thu FAILED và chưa có tác động vật lý, CANCELLED, không dùng CLOSED_COMPENSATED.

## Guard bắt buộc ở Backend vì CHECK không kiểm tra được bảng khác
- battery holder phải là CUSTOMER; assignment phải TECHNICIAN; compartment/device/event phải cùng trạm phiên; old/new battery đúng họ cấu hình.
- Không xóa/đổi trạm của device/compartment có lịch sử. API PATCH không cho đổi các FK này. User khóa/đổi quyền phải revoke session; mỗi request đọc quyền hiện hành.
- Retirement pin: không có reservation, active swap hay khách giữ. Initial placement chỉ khi REGISTERED chưa có lịch sử; không có endpoint sửa trực tiếp vị trí pin IN_SERVICE.
- Không đổi compartment sang MAINTENANCE/RETIRED khi phiên active; RETIRED phải trống. Mở khóa chỉ qua UC10, không API người dùng mở tùy ý.
- Phục hồi chỉ TECHNICIAN đúng trạm, quality còn mới, không lỗi/alert chưa giải quyết liên quan. Backend hỗ trợ phục hồi + resolve cảnh báo liên quan trong cùng transaction để tránh vòng phụ thuộc. Không tự phục hồi sau telemetry bình thường.
- Policy snapshot bất biến trên swap; đổi config chỉ tạo revision mới. Giá do Backend quyết định, amount client là xác nhận khớp quote, không là nguồn tính giá.
- Audit append-only ở service và DB grant của tài khoản chạy; migration dùng tài khoản riêng. Chưa triển khai grants/trigger tự động trong schema.sql.

## Mất mạng và thứ tự
Event ID toàn cục UUID, unique(device,boot,seq), hash nội dung. Trùng nguyên vẹn trả kết quả cũ; cùng ID khác hash trả 409. Event cũ vẫn giữ bằng chứng nhưng không làm mới projection/heartbeat. Phải xử lý event sau commit inbox bằng worker, mark processed cùng commit nghiệp vụ.
Boot mới cần SNAPSHOT và ledger lệnh bền vững để đối soát; không reset khả dụng chỉ vì reconnect. Thiết bị ghi command_id xuống đĩa trước khi tác động; sau crash không thực hiện lại nếu kết quả chưa rõ, trả UNKNOWN và snapshot.
Heartbeat mới không làm mới BMS/cửa. Độ mới BR02 được kiểm tra riêng theo received_at của quan sát hợp lệ; timestamp đo/seq còn phải hợp lệ. Timeout job tạo stale alert/REVIEW_REQUIRED ngay cả khi không có event mới.
Một sự kiện bắt được pin sai không được gán nhầm mã pin vào kho; giữ observed_serial, BLOCKED và recovery case. Không ghi đè last-known custody nếu chưa đối soát.

## Lưu ý ERD
Các quan hệ 'pin cũ / mới' và 'ngăn nhận / cấp' trong ERD-02 là cách vẽ gộp hai FK cùng kiểu để dễ đọc; schema.sql chứa đủ từng FK. Resource reservation dùng XOR pin hoặc ngăn. Số lượng 0..1 của battery tại một ngăn/khách là nhờ partial unique index, không chỉ nhờ FK.
ERD-04 có bảng độc lập kỹ thuật: login_limits, idempotency, outbox, audit. aggregate_id là tham chiếu đa hình ở service, không FK SQL. Data dictionary đầy đủ có trong data-dictionary.json, không lược cột khỏi schema SQL.
