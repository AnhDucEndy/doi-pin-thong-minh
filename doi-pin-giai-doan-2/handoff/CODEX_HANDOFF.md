# Bàn giao thiết kế Giai đoạn 2 cho Codex

Hệ thống quản lý mạng lưới tủ đổi pin tự động cho xe máy điện thông minh. Phiên bản thiết kế đề xuất 0.2, ngày 23/10/2026.

## Ranh giới thực hiện
Chỉ triển khai từng module khi nhóm giao việc sau khi xem xét thiết kế. Bộ hồ sơ này là thiết kế, không phải ứng dụng đã chạy. Giữ nguyên mã FR01–FR19, UC01–UC17, BR01–BR12 và phạm vi MVP trong baseline. Không thêm ví, gói thuê bao, đặt pin từ xa, định tuyến, AI hay thanh toán thật. Không tự ý đổi thu trước thành thu sau. Mọi QD01–QD09 còn chờ xác nhận; người triển khai không được coi giả định là phê duyệt.

## Thứ tự đọc và nguồn chuẩn
1. baseline/Phan-tich-thiet-ke-doi-pin-GD1.docx và bảng truy vết GĐ1 là chuẩn nghiệp vụ.
2. handoff/decisions.json: QD nào còn mở; contracts/demo-config.proposed.yaml là cấu hình đề xuất, chưa đủ để vận hành.
3. Tài liệu DOCX GĐ2, diagrams/*.puml và database/INVARIANTS.md.
4. contracts/openapi.yaml, contracts/state-enums.json, database/schema.sql và database/data-dictionary.json.
5. contracts/traceability.csv, handoff/ACCEPTANCE.md và validation/README.md.
Nếu có mâu thuẫn: dừng phần phụ thuộc, ưu tiên baseline, ghi câu hỏi/đề xuất sửa hợp đồng. Không âm thầm sửa FR, UC hoặc BR. Các ID AD, SM, ERD, ARCH, CT chỉ là ID thiết kế/kiểm thử bổ sung.

## Cấu trúc dự án đề xuất
```text
battery-swap/
  apps/web/src/{pages,features,api,auth,components}
  services/backend/app/
    api/{routes,schemas,dependencies}
    domain/{identity,assets,swaps,payments,telemetry,alerts}
    application/{commands,queries,policies}
    infrastructure/{db,repositories,device,payment,outbox}
    workers/
  services/backend/alembic/
  simulators/device/{ledger,scenarios,transport}
  simulators/payment/{ledger,callbacks,scenarios}
  contracts/{openapi.yaml,state-enums.json,demo-config.schema.json}
  tests/{unit,integration,contract,e2e,fault,performance}
  deploy/{compose,env.example}
  docs/{baseline,decisions,diagrams,runbooks}
```
Đây là cấu trúc dự kiến; chưa tạo mã ứng dụng. API và worker dùng cùng domain và PostgreSQL, chạy thành hai tiến trình. Thiết bị mô phỏng và payment mock là hai tiến trình độc lập. Không chia microservice nghiệp vụ trong MVP.

## Thứ tự triển khai và cổng kiểm tra

0. **Khóa baseline và hợp đồng — Cả nhóm.** Đối chiếu SHA256, QD01–09, FR01–19, UC01–17, BR01–12; ghi quyết định và cập nhật hợp đồng trước code.

1. **Nền tảng và định danh — TV3 chủ trì, TV2 hỗ trợ.** Cấu hình fail closed, migration, seed demo, token và phân quyền; TC01–02, không lộ hash hoặc khóa thiết bị.

2. **Trạm ngăn và pin — TV2 trạm/ngăn, TV4 pin/BMS.** TC03–08; vị trí pin duy nhất, ngăn chưa xác minh không khả dụng; kỹ thuật chỉ trạm được giao.

3. **Thiết bị và bằng chứng — TV5 chủ trì, TV3 hỗ trợ.** TC17, TC19; ledger bền vững, sự kiện lặp/đảo thứ tự, restart; ACK không thay thế cảm biến.

4. **Xác thực giữ chỗ và thu phí — TV3 QR/điều phối, TV4 thu phí.** TC09–10, TC14–15; QR một lần, race giữ pin, thanh toán UNKNOWN không thu lại.

5. **Trả pin nhận pin và khôi phục — TV3 chủ trì, TV4 và TV5 phối hợp.** TC11–12, TC16; kiểm tra pin sai, mất kết nối, đã trả chưa nhận, nhận pin chưa rõ, hoàn tiền đúng quyền.

6. **Giao diện lịch sử và cảnh báo — TV2, TV3, TV4 theo module; TV5 cảnh báo.** TC05, TC13, TC18–19; web theo trạng thái server, không suy đoán thành công từ timeout.

7. **Tích hợp và nghiệm thu — TV5 kiểm thử, TV1 bàn giao.** Chạy toàn bộ TC01–19, tiêu chí NFR GĐ1, restore backup, kiểm tra audit; đóng bằng chứng và biên bản demo.

TV1 chủ trì SRS, UML và bàn giao; TV2 chủ trì trạm và ngăn; TV3 chủ trì kiến trúc, tài khoản, QR/RFID và điều phối đổi; TV4 chủ trì pin/BMS và thanh toán; TV5 chủ trì IoT, cảnh báo và kiểm thử. Giữ nguyên mã và phân công W01–W12 của GĐ1; các người hỗ trợ module chỉ là đề xuất review kỹ thuật.

## Ánh xạ kế hoạch 10 tuần Giai đoạn 1
W01 tuần 1–2 và W02 tuần 2: phân tích/UML. W03 tuần 3: kiến trúc và hợp đồng dữ liệu (bộ hồ sơ này). W04–W05 tuần 4: tài khoản, trạm/ngăn. W06 tuần 4–5: pin/BMS. W07 tuần 5: QR/RFID. W08 tuần 5–8: IoT/cảnh báo. W10 tuần 5–7: thu phí mock. W09 tuần 6–7: điều phối đổi, phụ thuộc W06/W07/W08/W10. W11 tuần 4–9: tích hợp và kiểm thử liên tục. W12 tuần 9–10: hoàn thiện và bàn giao. Không mở thêm chu kỳ 10 tuần và không khẳng định công việc đã hoàn thành.

## Quy trình làm một module
Đọc FR/UC/BR liên quan → viết tiêu chí chấp nhận → thiết kế transaction và hợp đồng lỗi → triển khai thay đổi nhỏ → chạy test có ý nghĩa → cập nhật truy vết và bằng chứng → review. Không đưa dữ liệu thật, khóa thật hay thanh toán thật vào fixture. Không triển khai ra môi trường công khai tự động.

Migrations phải thuận tiến, không xóa lịch sử; thử trên PostgreSQL sạch và bản nâng cấp. SQL bàn giao là baseline DDL để chuyển thành migration đầu, không chạy đồng thời cả DDL và migration trùng lặp. Dùng role database riêng cho migration và runtime. Seed 2 trạm × 6 ngăn, tài khoản 3 vai trò, 1 dòng pin, phân công kỹ thuật và pin ban đầu; mật khẩu/khóa qua biến môi trường, không hard-code. Cấu hình phí và ngưỡng do nhóm chọn cho demo; không suy ra độ an toàn phần cứng thật.

## Điều kiện hoàn thành
Tất cả TC01–TC19 giữ nguyên ID và đạt với log; CT bổ sung đạt; mọi endpoint kiểm tra quyền và sở hữu; không còn lỗi mất pin/thu hai lần/phát hai lần; OpenAPI khớp response; migration và backup restore qua kiểm tra; README chạy demo tái lập; QD còn mở hiển thị rõ. Đạt test mô phỏng không đồng nghĩa đủ điều kiện triển khai tủ thật.
