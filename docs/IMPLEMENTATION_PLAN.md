# Kế hoạch triển khai hệ thống đổi pin thông minh

Ngày lập: 24/10/2026 (Asia/Bangkok). Phạm vi: MVP mô phỏng theo QD01–QD09 đã được người dùng duyệt ngày 23/10/2026. Phase 1 đã được giao và triển khai; kết quả nghiệm thu nằm trong IMPLEMENTATION_STATUS.md. Phase 2 – F2 được triển khai theo yêu cầu tiếp theo: chỉ trạm/thiết bị/ngăn (FR03–05, TC03–05). F3 pin/BMS trong cùng nhóm handoff vẫn chưa triển khai. Các phase sau vẫn là kế hoạch.

## Nguồn và thứ tự ưu tiên

- Đọc `../AGENTS.md` và `../doi-pin-giai-doan-2/CODEX_START_HERE.md` trước mỗi phase.
- QD và cấu hình: phụ lục `handoff/DECISIONS_APPROVED_2026-10-23.md`, `handoff/decisions.approved.json`, `contracts/demo-config.approved.yaml` trong bộ thiết kế là nguồn mới nhất.
- Nghiệp vụ: DOCX GĐ1, FR01–FR19, UC01–UC17, BR01–BR12 và bảng truy vết baseline.
- Chi tiết triển khai: `handoff/CODEX_HANDOFF.md`, DOCX GĐ2, `database/INVARIANTS.md`, DDL, OpenAPI, enum, từ điển dữ liệu, sơ đồ và ACCEPTANCE.
- Các dòng “chưa xác nhận” trong bản gốc cũ không thay thế quyết định approved mới. Giữ nguyên toàn bộ bộ hồ sơ gốc; ghi điều chỉnh triển khai trong docs/migration sau này và đối chiếu rõ nguồn.

## Phạm vi và kiến trúc đã chốt

2 trạm × 6 ngăn, một họ pin DEMO_FAMILY_A; pin thuộc mạng lưới, seed pin khách đang giữ. Tài khoản cấp sẵn; QR một lần và RFID mô phỏng. Admin, Customer và Technician độc lập; quyền và phạm vi trạm được Backend cưỡng chế.

Thu trước 9.000 VND/lượt qua payment mock sau khi khách chấp thuận; không áp dụng 20 lượt miễn phí. `fee_minor=9000` là 9.000 VND. Pin cấp lọc SOC ≥80%, SOH ≥80%, nhiệt độ ≤40°C cùng các guard lỗi/độ mới; các ngưỡng là giả định demo. Không áp ngưỡng SOH cấp để tự từ chối pin trả.

React + TypeScript + Vite; Python 3.12 + FastAPI; SQLAlchemy 2.x + Alembic; PostgreSQL 17. Backend modular monolith có Identity, Assets, Swaps, Payments, Telemetry và Alerts. API và worker dùng chung domain/database, chạy hai tiến trình. Device simulator và payment mock là hai tiến trình ngoài Backend, có ledger bền vững. REST/polling cho MVP; Docker Compose theo thiết kế khi môi trường sẵn sàng.

Luồng chuẩn: xác thực → giữ pin/ngăn → chấp thuận phí → xác minh thu → nhận đúng pin cũ và đóng cửa → kiểm tra lại điều kiện → cấp pin mới → xác nhận lấy pin và đóng cửa → hoàn tất. Cập nhật custody pin cũ ngay khi nhận đủ bằng chứng, không đợi đến cuối lượt.

## Tổ chức workspace dự kiến

```text
<workspace>/
  AGENTS.md
  .gitignore
  .venv/                         # Một môi trường Python tại gốc
  doi-pin-giai-doan-2/            # Hồ sơ gốc, giữ nguyên
  apps/web/src/{pages,features,api,auth,components}/
  services/backend/app/
    api/{routes,schemas,dependencies}/
    domain/{identity,assets,swaps,payments,telemetry,alerts}/
    application/{commands,queries,policies}/
    infrastructure/{db,repositories,device,payment,outbox}/
    workers/
  services/backend/alembic/
  simulators/device/{ledger,scenarios,transport}/
  simulators/payment/{ledger,callbacks,scenarios}/
  tests/{unit,integration,contract,e2e,fault,performance}/
  deploy/
  docs/
  tools/validate_design_phase0.py
```

Đây là cấu trúc tương lai; Phase 0 chỉ tạo docs và helper kiểm tra tĩnh. Không tạo một bản `battery-swap/` lồng thêm hoặc sao chép tài liệu vào docs/baseline. Hợp đồng gốc ở `doi-pin-giai-doan-2/contracts/`; client và kiểm thử sẽ tham chiếu đường dẫn này. Nếu cần hợp đồng triển khai khác baseline, lưu phần thay đổi có phiên bản và truy vết, không duy trì bản sao thủ công trùng lặp.

Frontend dùng npm và `apps/web/package-lock.json`; cài bằng `npm ci` khi đã có lockfile. Python pin dependencies sau khi kiểm chứng trong `.venv/`. Secret qua môi trường/.env bị ignore; chỉ commit mẫu không có secret. Không cài dependency vào runtime đóng gói của Codex.

## Thứ tự phase và cổng kiểm tra

| Phase | Phụ trách theo handoff | Nội dung và sản phẩm | Điều kiện qua cổng |
| --- | --- | --- | --- |
| 0 | Cả nhóm | Xác nhận baseline/QD/hợp đồng; kiểm tra Windows và công cụ; kế hoạch, trạng thái, bằng chứng | Hash/truy vết được đối chiếu; thiếu công cụ và điểm lệch hợp đồng được ghi rõ; không coi kiểm tra tĩnh là nghiệm thu ứng dụng |
| 1 | TV3 chủ trì, TV2 hỗ trợ | Cấu trúc dự án, config fail closed, migration đầu, seed demo, login/logout/me, quản lý tài khoản và RBAC/ownership; nền web/API/worker | TC01–02; khóa/đổi quyền thu hồi session; giới hạn 5 lần sai/15 phút ở server; không lộ hash/key; migration trên PostgreSQL sạch và lộ trình nâng cấp; official validators chạy |
| 2 | TV2 trạm/ngăn, TV4 pin/BMS | Trạm, danh tính thiết bị, ngăn, hồ sơ/vị trí pin, BMS và phục hồi theo assignment | TC03–08; vị trí pin duy nhất; ngăn chưa xác minh không khả dụng; lỗi/stale chặn; Admin không kế thừa Technician |
| 3 | TV5 chủ trì, TV3 hỗ trợ | Simulator thiết bị, transport HTTP, inbox/outbox, command ledger, snapshot/boot/seq và bằng chứng | TC17, TC19; event trùng/đảo thứ tự, replay, restart; ACK không thay cảm biến; không thực thi lại cơ khí khi chưa rõ |
| 4 | TV3 QR/điều phối, TV4 thu phí | QR/RFID chuẩn hóa một phiên, reserve nguyên tử, quote/policy snapshot, consent, payment mock độc lập, query/callback | TC09–10, TC14–15; QR một lần; tranh pin/ngăn chỉ một bên thắng; callback xác minh; UNKNOWN không thu lại |
| 5 | TV3 chủ trì, TV4/TV5 phối hợp | Trả/cấp pin, state machine, recovery evidence, xử lý pin cũ, refund và đóng bù trừ | TC11–12, TC16; sai pin dừng cấp; một OPEN_SUPPLY/phiên; không rõ bàn giao giữ review; Admin chỉ hoàn sau bằng chứng chưa giao; hoàn và custody đều phải giải quyết |
| 6 | TV2/TV3/TV4 theo module, TV5 cảnh báo | Hoàn thiện UI ba vai trò, lịch sử, dashboard, cảnh báo và thao tác khắc phục | TC05, TC13, TC18–19; UI theo server; quyền chéo bị chặn; stale hiển thị rõ; ACK cảnh báo không gỡ cách ly |
| 7 | TV5 kiểm thử, TV1 bàn giao | Tích hợp, đo NFR, backup/restore cả DB và ledger, audit, runbook và diễn tập | TC01–19, CT01–14 đạt có log; NFR đo trên máy demo; migration/restore tái lập; review và biên bản bàn giao |

Phase 1 tạo nền UI để tích hợp sớm; Phase 6 hoàn thiện luồng giao diện. Không đợi Phase 6 mới nối frontend/backend. Mỗi phase chỉ bắt đầu khi được giao; lượt hiện tại chỉ giao đến Phase 1. Dừng và báo cáo trước Phase 2.

## Truy vết yêu cầu theo module

| Module | FR | UC | TC gốc | Phase chính |
| --- | --- | --- | --- | --- |
| F1 Tài khoản/quyền | FR01–02 | UC01–02 | TC01–02 | 1 |
| F2 Trạm/ngăn/khả dụng | FR03–05 | UC03–05 | TC03–05 | 2, 6 |
| F3 Pin/BMS/cách ly | FR06–08 | UC06–08 | TC06–08 | 2 |
| F4 QR/RFID | FR09 | UC09 | TC09 | 4 |
| F5 Điều phối/khôi phục/lịch sử | FR10–13 | UC10–11 | TC10–13 | 4, 5, 6 |
| F6 Thu/đối soát/hoàn | FR14–16 | UC12–14 | TC14–16 | 4, 5 |
| F7 IoT/giám sát/cảnh báo | FR17–19 | UC15–17 | TC17–19 | 3, 6 |

| Quy tắc | Bằng chứng/ràng buộc cần thực hiện | Phase và kiểm tra |
| --- | --- | --- |
| BR01 | Một active swap/khách; reserve pin và hai ngăn nguyên tử, unique dưới DB lock | 4; TC10, CT01–02 |
| BR02 | Đúng family; BMS đầy đủ/mới, SOC/SOH/nhiệt theo policy; không lỗi/cách ly; đúng trạng thái ngăn/cửa/presence | 2, 4, 5; TC05/07, CT09/12 |
| BR03 | QR gắn khách/trạm/nonce/hạn và tiêu thụ nguyên tử; RFID credential còn hiệu lực | 4; TC09 |
| BR04 | Chấp thuận và thu đã xác minh trước trả/cấp; giá snapshot bất biến | 4, 5; TC11/14 |
| BR05 | Đối chiếu serial/family/holder pin trả; pin lạ giữ observed_serial và case, không nhập kho sai | 5; TC11–12, CT05 |
| BR06 | Một command_id qua retry; ledger ghi trước tác động; ACK không là bằng chứng giao pin | 3, 5; TC11/17, CT04/06 |
| BR07 | Payment timeout là UNKNOWN; query cùng provider_key; callback đúng intent/tiền/currency | 4; TC14–15, CT03 |
| BR08 | Admin hoàn toàn bộ khi đã thu/chắc chắn chưa giao; một intent; pin cũ có xử lý riêng | 5; TC16, CT07/13 |
| BR09 | Chưa rõ pickup: giữ reservation/review, không tự hoàn hoặc cấp thêm | 5; TC12/16, CT08 |
| BR10 | Cảnh báo chặn; ACK chỉ đã đọc; Technician đúng trạm phục hồi có bằng chứng | 2, 3, 6; TC08/19 |
| BR11 | Online và dữ liệu mới trước phiên mới; mất mạng dừng lệnh mới; boot mới cần đối soát | 3, 4, 5; TC12/18, CT06/09 |
| BR12 | Không xóa cứng lịch sử/tài sản có tham chiếu; audit append-only; không endpoint sửa state tùy ý | 1–7; TC02/06/13, CT14 |

Ma trận trên là kế hoạch kiểm chứng, chưa là kết quả test. Các ID CT bổ sung giữ nguyên trong ACCEPTANCE, không thay TC gốc.

## Lịch và nguồn lực

Giữ W01–W12 của GĐ1 và tổng 10 tuần tương đối, không mở thêm 10 tuần từ 24/10/2026. Chưa có ngày khởi đầu dự án hoặc tên thật, tiếp tục dùng TV1–TV5.

- W01–02 tuần 1–2: nghiệp vụ/UML; W03 tuần 3: kiến trúc và hợp đồng, gồm rà soát Phase 0.
- W04–05 tuần 4: nền tảng/tài khoản/trạm; W06 tuần 4–5: pin/BMS.
- W07 tuần 5: QR/RFID; W08 tuần 5–8: IoT/cảnh báo; W10 tuần 5–7: payment mock.
- W09 tuần 6–7: điều phối, phụ thuộc W06/W07/W08/W10; Phase 4–5 tích hợp các phần này.
- W11 tuần 4–9: tích hợp và kiểm thử liên tục; W12 tuần 9–10: bàn giao.

QD08 cho tổng 400 giờ-người; baseline dự kiến 320 giờ kế hoạch + 80 giờ dự phòng. Vai trò TV là phân công của nhóm, không phải lệnh tạo subagent.

## Các điều kiện đã xử lý trong Phase 1

P0-01/02/03 đã được xử lý theo IMPLEMENTATION_DECISIONS.md. PostgreSQL 17.11, migration, seed và runtime role đã được chạy kiểm tra. Phần dưới giữ lại cơ sở kế hoạch; trạng thái hiện hành theo IMPLEMENTATION_STATUS.md.

1. **P0-01 — trạng thái duyệt policy:** DDL cũ chỉ nhận PROPOSED/TEAM_CONFIRMED, trong khi approved ghi APPROVED_FOR_SIMULATION_BY_USER. Phương án migration đề xuất: bổ sung trạng thái duyệt mô phỏng bởi người dùng, giữ revision/snapshot và liên kết bằng chứng approved; không gán TEAM_CONFIRMED hoặc bịa người xác nhận. Giữ nguyên DDL gốc. Chốt phần thay đổi kỹ thuật trong hồ sơ migration trước seed policy.
2. **P0-02 — validator:** tạo `.venv/` và cài thư viện validator theo dependency khai báo của dự án sau khi được giao Phase 1. Chạy JSON Schema Draft 2020-12 trên file approved, OpenAPI 3.1 validator và parser PostgreSQL. Helper Phase 0 chỉ kiểm tra các ràng buộc đang dùng, không thay thế các validator này. Không chạy nguyên script gốc vì nó kiểm tra proposed và ghi đè `validation/structural-checks.json`; dùng đường dẫn output ngoài bộ gốc.
3. **P0-03 — mã lỗi thiếu cấu hình:** DOCX mô tả 503 cho config chưa đủ, OpenAPI mô tả 422 cho thiếu cấu hình demo và có cả 503 cho dịch vụ chưa sẵn sàng. Đề xuất bám hợp đồng máy: 422/CONFIG_NOT_READY cho thiếu policy bắt buộc, 503 cho offline/chưa sẵn sàng; ghi rõ quyết định kỹ thuật trước contract tests. Dù mã HTTP nào, vẫn phải fail closed và không reserve/thu tiền.
4. Chuẩn bị Python thực dùng được để tạo `.venv/`, Node kèm npm và PostgreSQL 17. Nếu dùng Compose theo thiết kế thì cần Docker Engine/Compose chạy được, thường kèm WSL2 trên máy này; mọi cài đặt hệ thống phải được người dùng đồng ý riêng. Python/Git/Node runtime Codex hiện có chỉ là khả năng của phiên làm việc.
5. Khởi tạo Git tại workspace khi bước nền tảng được giao; không clone hay tạo worktree thừa. `.gitignore` đã tồn tại. Chưa cấu hình remote hoặc tạo commit trong Phase 0.

## Quy trình nghiệm thu và dung lượng

Mỗi module: đọc FR/UC/BR → tiêu chí chấp nhận → transaction/guard/lỗi → thay đổi nhỏ → test phù hợp → bằng chứng và truy vết → review. Không chạy DDL gốc song song với migration đầu. Tách role DB migration/runtime; bảo vệ audit và lịch sử bằng grant/trigger được kiểm chứng. Seed từ env, không hard-code password/key.

Sau từng phase cập nhật `IMPLEMENTATION_STATUS.md`: file đổi, lệnh chạy, Passed/Failed/Not Run, vấn đề còn mở và dung lượng thư mục mới. Theo dõi `.venv/`, `apps/web/node_modules/`, cache/build, bằng chứng UI, dữ liệu DB và ledger. Không tạo backup lặp không cần thiết.

Chỉ dọn cache/build có thể sinh lại sau khi xác định chính xác. `.venv/` và node_modules có thể tạo lại khi giữ dependency/lockfile và hướng dẫn; xóa chúng cần cài lại. DB, ledger, migrations, source, tài liệu gốc và bằng chứng kiểm thử phải được bảo toàn. Không dùng `docker compose down -v` hay prune volumes để tiết kiệm dung lượng.
