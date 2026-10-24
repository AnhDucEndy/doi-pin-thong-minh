# Bảng model và prompt Codex — đồ án trạm đổi pin thông minh

> Tài liệu tham chiếu nhanh, tổng hợp từ cuộc trò chuyện ChatGPT. Hãy gửi **từng prompt** vào Codex theo đúng tiến độ, không gửi tất cả cùng lúc. Chỉ chọn model có trong danh sách Codex hiện tại; có thể thay Sol bằng model coding tương đương nếu tên/model không xuất hiện.
>
> Giả định repository chứa `AGENTS.md` tại thư mục gốc và bộ hồ sơ tại `doi-pin-giai-doan-2/`. Codex phải ưu tiên các tài liệu và quy tắc đã chốt trong bộ bàn giao. Không tự thay đổi FR01–FR19, UC01–UC17, BR01–BR12 và QD01–QD09.

## Bảng tra nhanh

| Bước | Phần việc | Model đề xuất | Trọng tâm nghiệm thu |
|---|---|---|---|
| 0 | Đọc tài liệu, rà soát môi trường | Sol Low | Xác minh hồ sơ, môi trường, kế hoạch |
| 1 | Khởi tạo dự án + DB + Authentication/RBAC | Sol Medium | Migration, seed, TC01–TC02 |
| 2 | Trạm và ngăn tủ (F2) | Sol Low | TC03–TC05 |
| 3 | Pin và BMS (F3) | Sol Medium | TC06–TC08; ngưỡng, dữ liệu cũ |
| 4 | IoT Simulator, telemetry (F7) | Sol Medium | TC17, TC19; ledger, ACK khác cảm biến |
| 5 | QR/RFID, giữ pin nguyên tử (F4, F5.1) | Sol Medium; Astra Low review | TC09–TC10; chống race condition |
| 6 | Thanh toán và đối soát mock (F6) | Astra Low | TC14–TC15; UNKNOWN, idempotency |
| 7 | Quy trình trả/cấp pin (F5) | Astra Medium | TC11–TC12; bằng chứng vật lý |
| 8 | Khôi phục, compensation/hoàn phí | Astra Low | TC16; REVIEW_REQUIRED |
| 9 | Giao diện ba vai trò | Sol Medium; Luna Medium chỉnh UI nhỏ | Dữ liệu từ API, trạng thái lỗi |
| 10 | Tích hợp, kiểm thử, demo | Sol Medium; Astra Low review nếu cần | TC01–TC19, README, demo |

*Bảng trên là khuyến nghị cân bằng chất lượng và hạn mức, không phải yêu cầu bắt buộc. Tên model và mức suy luận có thể khác tùy phiên bản Codex.*

## Quy tắc chung áp dụng cho mọi prompt

- Đọc `AGENTS.md`, `doi-pin-giai-doan-2/CODEX_START_HERE.md`, `handoff/CODEX_HANDOFF.md` và `docs/IMPLEMENTATION_STATUS.md` (nếu đã tạo) trước khi sửa code.
- Dùng tài liệu đã chốt làm nguồn chuẩn. Nếu hợp đồng API, schema và baseline xung đột thì báo rõ; không tự sửa nghiệp vụ.
- Chỉ sửa các module liên quan; chạy test thực tế, phân biệt **Passed / Failed / Not Run**.
- Không tự ý xóa source, migration, data, Docker volumes hoặc thay đổi hệ thống bên ngoài workspace.
- Cuối mỗi bước, nêu file tạo/sửa, lệnh đã chạy, kết quả test, blocker, cập nhật `docs/IMPLEMENTATION_STATUS.md`.
- Nên lưu commit Git sau mỗi bước đã nghiệm thu (không commit bí mật/`.env`).

---

## Bước 0 — Sol Low: Đọc và chuẩn bị triển khai

```text
Hãy bắt đầu Phase 0 của dự án hệ thống đổi pin thông minh.

Đọc AGENTS.md và CODEX_START_HERE.md trong doi-pin-giai-doan-2. Kiểm tra các quyết định QD01–QD09, FR01–FR19, UC01–UC17, BR01–BR12 và hợp đồng thiết kế.

Hãy kiểm tra môi trường Windows, Git, Python, Node.js và Docker; xác định công cụ nào đã cài, công cụ nào còn thiếu.

Tạo kế hoạch triển khai theo thứ tự trong CODEX_HANDOFF.md và file docs/IMPLEMENTATION_STATUS.md để theo dõi tiến độ.

Chưa lập trình các module nghiệp vụ, chưa cài đặt phần mềm toàn hệ thống khi chưa có sự đồng ý của tôi.

Báo cáo kết quả kiểm tra và những điều kiện cần chuẩn bị để bắt đầu Phase 1.
```

## Bước 1 — Sol Medium: Database, Authentication và RBAC

```text
Tiếp tục Phase 1: Project Foundation và Authentication.

Tuân thủ AGENTS.md, GĐ1/GĐ2 và trạng thái hiện tại của repository.

Hãy trực tiếp triển khai:
1. Khởi tạo Backend FastAPI và Frontend React + TypeScript + Vite.
2. Cấu hình PostgreSQL 17 và Docker Compose.
3. Chuyển database/schema.sql thành Alembic migration phù hợp, không áp dụng DDL và migration trùng lặp.
4. Tạo seed data theo bộ thiết kế.
5. Xây dựng đăng nhập, quản lý phiên và phân quyền Admin, Customer, Technician.
6. Thực thi bảo mật và giới hạn đăng nhập sai tại Backend.
7. Viết và chạy kiểm thử TC01–TC02.

Không tự sửa các tài liệu baseline. Không hard-code secret.

Kết thúc bằng kết quả chạy thử, các file đã tạo và cập nhật IMPLEMENTATION_STATUS.md. Nếu Docker hoặc PostgreSQL chưa hoạt động, nêu rõ blocker thay vì tuyên bố hoàn thành.
```

## Bước 2 — Sol Low: Quản lý trạm và ngăn (F2)

```text
Tiếp tục triển khai module F2 – Station & Compartment Management.

Đọc AGENTS.md, IMPLEMENTATION_STATUS.md và các yêu cầu FR03–FR05, UC03–UC05, cùng các phần thiết kế liên quan.

Triển khai API quản lý trạm, thiết bị và ngăn tủ theo OpenAPI hiện có. Hỗ trợ hai trạm mô phỏng, mỗi trạm sáu ngăn, mỗi ngăn có trạng thái phục vụ và trạng thái cửa độc lập.

Thực thi phân quyền theo trạm. Không cho phép bảo trì hoặc ngừng sử dụng ngăn khi thao tác đó phá vỡ trạng thái giao dịch đang hoạt động.

Viết và chạy các bài kiểm thử TC03–TC05 liên quan.

Không triển khai quy trình đổi pin trong bước này. Cập nhật tiến độ, kết quả kiểm thử và các lỗi chưa giải quyết.
```

## Bước 3 — Sol Medium: Pin và BMS (F3)

```text
Triển khai module F3 – Battery & BMS dựa trên FR06–FR08, UC06–UC08 và thiết kế GĐ2.

Xây dựng quản lý mã pin, vị trí pin, dữ liệu BMS gồm SOC, SOH, nhiệt độ, trạng thái lỗi và thời điểm đo.

Áp dụng cấu hình demo đã duyệt: SOC tối thiểu 80%, SOH tối thiểu 80%, nhiệt độ tối đa 40°C để cấp pin. Không diễn giải đây là tiêu chuẩn an toàn phần cứng.

Pin thiếu dữ liệu, dữ liệu quá cũ, không rõ vị trí hoặc bị cách ly phải không khả dụng. Chỉ cho phục hồi theo đúng phân quyền kỹ thuật viên và bằng chứng hợp lệ.

Đảm bảo một pin không tồn tại ở hai vị trí đồng thời.

Viết và chạy TC06–TC08 và test boundary cho các ngưỡng BMS. Báo cáo file, kết quả test và cập nhật trạng thái triển khai.
```

## Bước 4 — Sol Medium: IoT Simulator (F7)

```text
Triển khai IoT Device Simulator và phần đồng bộ dữ liệu theo F7, UC15–UC17 và hợp đồng GĐ2.

Xây dựng simulator Python qua HTTP cho hai trạm, mỗi trạm sáu ngăn.

Simulator phải có dữ liệu trạng thái pin, cảm biến hiện diện, cửa, khóa và telemetry BMS. Hỗ trợ nhận lệnh có command_id, phản hồi ACK và bằng chứng thao tác riêng biệt.

Lưu ledger đủ bền vững để kiểm tra các tình huống gửi lặp, sự kiện sai thứ tự, mất kết nối và khởi động lại.

Backend phải kiểm tra danh tính thiết bị, xử lý trùng event_id và phát hiện dữ liệu stale.

Viết kiểm thử TC17, TC19 và fault tests liên quan. Chỉ mô phỏng khóa và cảm biến, không điều khiển phần cứng thật.

Chạy test thực tế và cập nhật IMPLEMENTATION_STATUS.md.
```

## Bước 5 — Sol Medium, Astra Low review: QR/RFID và giữ chỗ nguyên tử

```text
Triển khai F4 – QR/RFID Authentication và F5.1 – kiểm tra điều kiện, giữ pin/ngăn.

Bám sát UC09, UC10, BR01–BR03 và các hợp đồng API/Database đã bàn giao.

Xây dựng QR dùng một lần, có thời hạn và gắn với khách hàng, trạm. Triển khai RFID mô phỏng ánh xạ định danh sang tài khoản hợp lệ.

Sau xác thực, cho phép Backend kiểm tra điều kiện và giữ nguyên tử một pin đủ điều kiện cùng một ngăn nhận phù hợp.

Sử dụng transaction và cơ chế khóa cần thiết của PostgreSQL để ngăn hai khách cùng giữ một pin. Kiểm thử các yêu cầu đồng thời và credential hết hạn hoặc dùng lại.

Chưa thực hiện mở ngăn hoặc cấp pin ở bước này.

Chạy TC09–TC10, báo cáo bằng chứng test và cập nhật tiến độ.
```

## Bước 6 — Astra Low: Payment Mock (F6)

```text
Triển khai module F6 – Payment theo FR14–FR16, UC12–UC14, BR04, BR07–BR09 và State Machine SM04.

Xây dựng Payment Simulator độc lập, sử dụng phí 9.000 VND/lượt theo cấu hình đã duyệt và quy trình thu trước.

Mỗi khoản thu phải có idempotency key, trạng thái rõ ràng và ledger lưu bền vững. Xử lý callback lặp, thanh toán thất bại, timeout UNKNOWN, truy vấn đối soát và hoàn tiền có kiểm soát.

Không thu lại khi kết quả cũ chưa rõ; không hoàn quá số tiền đã thu. Không coi thanh toán thành công là bằng chứng đã giao pin.

Triển khai các API theo OpenAPI, viết và chạy TC14–TC15 cùng những kiểm thử ngoại lệ quan trọng.

Đối chiếu với State Machine và Database Invariants. Báo cáo kết quả thực tế và cập nhật trạng thái triển khai.
```

## Bước 7 — Astra Medium: Quy trình đổi pin hoàn chỉnh (F5)

```text
Triển khai nghiệp vụ trung tâm F5 – Battery Swap Workflow theo Use Case UC10, Activity AD02a/AD02b, State Machine SM03a/SM03b và BR01–BR12.

Tích hợp các module Authentication, Battery, BMS, IoT và Payment đã hoàn thành.

Thực hiện đúng chuỗi nghiệp vụ đã chốt: xác thực → giữ pin/ngăn → chấp thuận phí → xác minh thanh toán → tiếp nhận pin cũ → cấp pin mới → xác minh bàn giao → hoàn tất.

Mỗi chuyển trạng thái phải có guard, quyền, bằng chứng và transaction phù hợp. Không coi ACK mở cửa là bằng chứng người dùng đã trả hoặc nhận pin.

Triển khai trước luồng giao dịch thành công, không mở rộng sang các tính năng ngoài MVP.

Viết và chạy các kiểm thử TC11–TC12, đặc biệt xác minh không cấp nhầm pin, không hoàn tất giao dịch khi thiếu bằng chứng và không làm sai vị trí pin.

Báo cáo code, test, các trạng thái đã triển khai và cập nhật tiến độ.
```

## Bước 8 — Astra Low: Khôi phục giao dịch và hoàn phí

```text
Tiếp tục hoàn thiện phần xử lý ngoại lệ của F5 và F6, dựa trên SM03b, AD04b, BR06–BR11 và các thiết kế khôi phục giao dịch.

Không viết lại luồng đổi pin thành công nếu không cần thiết.

Triển khai xử lý khi thiết bị mất kết nối, cửa không mở, không xác nhận được pin trả, đã nhận pin cũ nhưng chưa cấp pin mới, thanh toán UNKNOWN hoặc kết quả cấp pin không rõ.

Đảm bảo giao dịch chuyển REVIEW_REQUIRED đúng lúc, không tự mở ngăn khác, không cấp thêm pin và không tự hoàn phí nếu chưa chứng minh được trạng thái vật lý.

Triển khai cơ chế đối soát, compensation và phục hồi sau restart theo hợp đồng hiện có.

Chạy TC16 và các fault tests liên quan. Báo cáo rõ kết quả, các invariant còn rủi ro và cập nhật tiến độ.
```

## Bước 9 — Sol Medium, Luna Medium cho sửa UI nhỏ: Frontend ba vai trò

```text
Triển khai Frontend React + TypeScript + Vite cho MVP dựa trên các API và phân quyền đã hoàn thành.

Thiết kế giao diện rõ ràng, hiện đại, nhất quán và phù hợp demo đồ án đại học.

Ưu tiên Customer UI trước: đăng nhập, xem trạm, xem pin khả dụng, xác thực đổi pin, chấp thuận phí, theo dõi giao dịch và lịch sử.

Sau đó triển khai Admin Dashboard cho trạm, ngăn, pin, BMS, giao dịch, thanh toán và cảnh báo; cuối cùng là giao diện Technician theo quyền.

Sử dụng dữ liệu từ Backend và OpenAPI, không hard-code kết quả nghiệp vụ. Phải thể hiện loading, lỗi, timeout và trạng thái REVIEW_REQUIRED.

Chia triển khai thành từng nhóm màn hình có thể kiểm thử được, tránh sửa toàn bộ Frontend trong một lần.

Chạy test phù hợp và cập nhật trạng thái triển khai sau mỗi nhóm màn hình.
```

## Bước 10 — Sol Medium, Astra Low review nếu cần: Kiểm thử/demo

```text
Thực hiện giai đoạn kiểm thử và hoàn thiện MVP của hệ thống trạm đổi pin thông minh.

Đọc IMPLEMENTATION_STATUS.md, CODEX_HANDOFF.md, ACCEPTANCE.md và các tiêu chí kiểm thử đã bàn giao.

Kiểm tra toàn bộ ứng dụng với Docker Compose, Frontend, Backend, PostgreSQL, IoT Simulator và Payment Mock.

Chạy các Test Case TC01–TC19, unit tests, integration tests, API contract tests và E2E tests khi môi trường hỗ trợ.

Đặc biệt kiểm tra: hai người tranh cùng pin, mất mạng, telemetry cũ, callback thanh toán trùng, restart ứng dụng, phân quyền sai và giao dịch REVIEW_REQUIRED.

Sửa các lỗi được phát hiện mà không tự thay đổi nghiệp vụ đã chốt.

Tạo README hướng dẫn cài đặt và chạy demo, dữ liệu mẫu, kịch bản demo thành công/thất bại và báo cáo kết quả kiểm thử.

Phân biệt Passed, Failed và Not Run. Không tuyên bố hoàn thành nếu chưa có bằng chứng chạy thực tế.

Cuối cùng, báo cáo mức độ đáp ứng FR01–FR19 và các vấn đề còn tồn tại.
```

---

## Prompt tiếp tục sau một bước

```text
Hãy kiểm tra repository và docs/IMPLEMENTATION_STATUS.md, đối chiếu tiêu chí nghiệm thu của bước vừa thực hiện. Chỉ khi bước trước đạt thì tiếp tục bước kế tiếp trong tài liệu CODEX_11_BUOC_MODEL_VA_PROMPT.md. Không lặp lại phần đã đạt. Nếu blocker, liệt kê rõ và đề xuất cách giải quyết; phân biệt test đã chạy và chưa chạy.
```

## Lưu trữ đề xuất trên Windows

Đặt tài liệu này trong:

`C:\Users\admin\Documents\ChatGPT\KTPM Hệ thống đổi pin thông minh\docs\CODEX_11_BUOC_MODEL_VA_PROMPT.md`

File chỉ để người dùng tra cứu; **không** yêu cầu Codex tự động thực hiện mọi prompt trong file. Hãy giao từng bước bằng tin nhắn.
