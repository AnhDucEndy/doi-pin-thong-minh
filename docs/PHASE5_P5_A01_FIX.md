# Sửa P5-A01 — ordering quan sát cửa và reservation

Ngày 25/10/2026, Asia/Bangkok. Base `main@8a29636`, ahead origin/main1. **Không commit/push, không Phase6.** Bản sửa ở working tree, cần restart Backend/worker khi người dùng duyệt áp dụng; không tự restart dịch vụ demo chính.

## 1. Nguyên nhân và hợp đồng

FR10/UC10/TC10, BR01/02/11 yêu cầu giữ đúng pin và hai ngăn dựa trên điều kiện hiện hành; FR17/UC15/TC17 và CT09 yêu cầu event cũ không làm mới projection/heartbeat. INVARIANTS, AD-02a, SM-03a và approved QD không cho sequence thay thế bằng chứng thời gian vật lý. Không đổi baseline, OpenAPI, trạng thái, API hoặc QD.

Cả bốn failing probes có cùng nguyên nhân: worker đã kiểm boot/seq/TTL nhưng chỉ nhánh TELEMETRY có watermark thời điểm đo từ bản sửa BMS Phase4. Nhánh SNAPSHOT gọi observation để cập nhật cửa/presence/serial vô điều kiện; slot.observed_at lưu thời gian **nhận**. Snapshot CLOSED cũ nhưng seq tăng vì thế làm cửa từ OPEN thành CLOSED, lại có vẻ fresh, và reserve giữ3tài nguyên.

Hai probe gốc đã ghi nhận timestamp bằng nhau; hai probe strictly_older ghi timestamp giảm đúng1s. Trong lượt sửa, chạy lại nguyên bốn probe trước khi sửa: **4 Failed**, BEFORE.xml/log. Sau sửa không đổi assertion/expected result hoặc fixture của `tests/test_phase5_acceptance.py`.

| Trường | Ngữ nghĩa được giữ nguyên |
| --- | --- |
| device_events.observed_at | Thời điểm quan sát tại thiết bị; dùng ordering vật lý |
| battery_telemetry.measured_at | Thời điểm đo BMS, vẫn lấy từ TELEMETRY observed_at; guard Phase4 không đổi |
| received_at | Thời điểm Backend nhận, vẫn dùng freshness/TTL theo hợp đồng |
| compartments.observed_at | Projection hiện tại lưu receipt time, không đổi nghĩa thành measurement time |
| processed_at | Thời điểm worker xử lý; không làm mốc thay quan sát |
| boot_id + seq | Thứ tự transport trong boot, không chứng minh thời điểm quan sát tăng |

## 2. Thay đổi source

### app/application/assets.py

- `observations()` lấy evidence accepted+processed của đúng device/ngăn: SNAPSHOT có ngăn trong slots, hoặc DOOR/PRESENCE có compartment_id. Không lấy HEARTBEAT/ACK/telemetry/seed unverified/rejected làm mốc cửa.
- `latest_observation()` chọn observed_at lớn nhất **qua các boot**, sau đó received_at/id để truy vấn xác định. Đây không phải chính sách cho phép ghi đè khi timestamp bằng nhau.
- UUID trong JSON snapshot được so không phân biệt hoa/thường bằng PostgreSQL jsonpath (cast JSONPATH rõ ràng); không để một UUID hợp lệ viết hoa né guard.
- `current_observation()` bảo vệ dữ liệu lịch sử đã bị phiên bản cũ ghi sai: projection phải khớp payload của evidence tại mốc mới nhất, đúng boot hiện tại, receipt time khớp projection; các evidence có cùng timestamp không được mâu thuẫn door/presence/serial. Không fallback sang chứng cứ tốt cũ hoặc sửa/xóa lịch sử.
- `eligible()` dùng guard này cho ngăn cấp, thống nhất với BR02 availability.

### app/workers/device.py

- Guard nằm đầu `observation()`, đường chung SNAPSHOT/DOOR/PRESENCE: event mới phải có observed_at **lớn hơn** watermark; `<=` bị EVENT_OUT_OF_ORDER.
- Vẫn giữ kiểm key/device/scope/schema/TTL/future, sequence và boot replay hiện có. Boot mới bắt buộc SNAPSHOT; không reset watermark vật lý chỉ vì restart. Timestamp cao nhưng seq thấp vẫn bị reject. Event mới sau reboot phải vượt mốc trước reboot; không tự chỉnh clock hoặc tạo timestamp giả.
- Retry nguyên event ID/body vẫn receipt cũ, không chạy lại observation. ID/body hoặc boot/seq conflict vẫn409 ở inbox. HTTP đầu tiên vẫn202/QUEUED; worker ghi processed_at/accepted=false/processing_error và audit khi reject, retry202/REJECTED/duplicate=true.

### app/application/reservations.py

- Ngăn nhận cũng gọi `current_observation()` trong transaction giữ tài nguyên. Cả ngăn nhận/cấp được kiểm thống nhất; không chỉ sửa một nhánh hoặc chỉ ẩn nút UI.
- Không đổi QR/RFID, payment, fee/policy, TTL, trạng thái reservation hoặc các API.

**Timestamp bằng nhau:** baseline không có quy tắc tie-break cho hai event khác ID nhưng cùng thời điểm vật lý. Bản sửa áp dụng fail-closed giống lựa chọn đã ghi ở PHASE4_BMS_FIX: không chứng minh là quan sát mới nên không thay projection hoặc gia hạn freshness, kể cả cùng payload. Event ID/body trùng vẫn idempotent. Đây là cách xử lý bảo thủ của bản sửa, không tuyên bố baseline đã định nghĩa tie-break chi tiết hơn thực tế. Không dùng seq làm bằng chứng mới cho payload mâu thuẫn. Nếu phần cứng tương lai có clock độ phân giải thấp/reset phải duyệt hợp đồng tích hợp riêng.

## 3. Transaction, concurrency và dữ liệu cũ

Không thêm mutex/in-memory guard, không thay isolation hoặc thứ tự lock. Worker và reserve dùng cùng transaction-scoped station advisory lock, user/swap/resources row locks; watermark đọc trong lock. Guard write của từng ngăn nằm trong savepoint hiện có của apply; lỗi ở ngăn cuối rollback các ngăn trước, alert/command/heartbeat/boot/seq nghiệp vụ trong event. Sau rollback, transaction vẫn lưu rejection/audit theo hợp đồng.

Kiểm thử deterministic với hai kết nối PostgreSQL và gate trong test:

- Worker OPEN giữ lock trước: reserve chờ rồi đọc OPEN, không RESERVED/không hold.
- Reserve giữ lock trước và quyết định trên CLOSED hợp lệ: reserve commit3holds, sau đó worker cập nhật OPEN. Đây là thứ tự serial hợp lệ; không phát minh việc tự release tài nguyên sau một quan sát đến sau. Các phase sau phải kiểm lại điều kiện trước tác động; bản sửa không giao pin/thanh toán.
- CLOSED cũ đến sau OPEN và sau booking đều bị reject; không hồi sinh khả dụng, không đổi holds/phiên/audit ngoài rejection.
- Hai Backend cạnh tranh cùng tài nguyên vẫn được test cũ bảo vệ bằng DB unique constraints/locks.

Dữ liệu lịch sử: không cập nhật demo hay xóa accepted events cũ. Guard đọc từ chối dùng projection sai để giữ mới. Chỉ snapshot mới hợp lệ theo pipeline hiện có mới làm projection nhất quán trở lại, không tự restore service_state/lifecycle hoặc resolve alert. Reservation đã được tạo sai bởi phiên bản cũ không bị âm thầm hủy/release; cần kiểm tra/đối soát trước tiếp tục workflow. Không tuyên bố đã sửa mọi row lịch sử của demo. Trường hợp evidence accepted nhưng handler terminal không cập nhật projection có thể làm read guard fail-closed cho tới snapshot mới; không dùng ACK hay ignored event để khẳng định khả dụng.

**Không cần migration** cho bản sửa này: dùng inbox JSONB/history/received_at hiện có, head0002_user_approval. Query kiểm mốc cần được đo/tối ưu khi quy mô event lớn; MVP hiện tại không tự thêm migration/index hoặc hạ tầng.

## 4. Công việc trước/sau gián đoạn

Trước usage limit: tái hiện4Failed; thêm guard ở ba source trên, sửa runner để output sang PHASE5_P5_A01_FIX và bảo toàn finding JSON cũ. TARGETED.xml hoàn tất **18Passed** trước gián đoạn; resume đã đọc file/kết quả, không giả định tiến trình còn chạy.

Sau resume: rà soát diff, giữ phần đã đúng; thêm `tests/test_phase5_door_ordering.py` và hỗ trợ UUID khác letter-case. Lượt ORDERING đầu **24Passed**. Khi thêm jsonpath, regression phát hiện tham số PostgreSQL thiếu cast JSONPATH, nhiều ca trả lỗiDB; dừng lượt đó, giữ REGRESSION.log chưa hoàn tất. Sửa cast tại source, không đổi test/fixture/expected. ORDERING_FINAL **43Passed =25 ordering+18 acceptance**. Không tính log regression lỗi bị ngắt là Passed hoặc bịa tổng số failure cuối.

Runner tái sử dụng `tools/run_phase5_acceptance.py`: chọn output trong workspace bằng P5_EVIDENCE_DIR, giữ output acceptance gốc byte khi lượt hoàn tất, lưu các kết quả mới bằng prefix lượt chạy. Không tạo bản sao repository. `tools/smoke_phase5.py` chỉ thêm cờ `--http-smoke` để chạy lại28 HTTP checks đã có ngay trên fixture E2E đang hoạt động trước cleanup; không đổi assertions E2E, không tạo API mới.

## 5. Kiểm thử mới và bằng chứng

Các bằng chứng trong `docs/PHASE5_P5_A01_FIX/`; đây là kết quả của lượt sửa, không dùng số227/8 của nghiệm thu để tuyên bố đã chạy lại.

| Lượt | Kết quả |
| --- | --- |
| BEFORE: bốn probe gốc |4Failed,14deselected |
| TARGETED: toàn bộ independent probes trước gián đoạn |18Passed |
| ORDERING: ca mới đầu tiên sau resume |24Passed |
| ORDERING_FINAL: toàn bộ ordering + acceptance sau cast |43Passed,0Failed |
| REGRESSION_FINAL: toàn bộ pytest Phase1–5 và probes |270 Passed,0 Failed,188.41s; 227 cũ +18 acceptance +25 ordering |
| E2E_PHASE5: hai Backend + worker + hai simulator |8 Passed; schema phase5_e2e_cbf41b2520, TTL thật120s và worker restart |
| HTTP trong fixture E2E_PHASE5 |28 Passed; QR/replay/reserve/cancel/RFID/role/logout |
| E2E_IOT: Backend + worker + hai simulator |8 Passed; schema phase4_e2e_b3978d4561; ACK/NACK/timeout/offline/restart |
| CONTRACTS |OpenAPI/approved JSON Schema/278SQL/hash baseline Passed |
| TypeScript/Vite build mới |Passed,81modules; không sửa web |

25 ca ordering thực tế bao phủ: timestamp tăng1µs; giảm/tie cùng/khác payload; seq thấp; boot mới cũ/tie và boot replay; duplicate nguyên event/ID conflict/seq conflict; timestamp missing/null/invalid/naive/quá hạn/future; sai trạm; UUID hoa/thường; DOOR và PRESENCE không bypass snapshot; snapshot lỗi ngăn cuối rollback cả projection; legacy corrupt evidence cho ngăn nhận/cấp và tie/older; reserve/OPEN hai thứ tự khóa PostgreSQL.

`assert_rejected` so nguyên devices/compartments/batteries/BMS/swaps/holds/commands/alerts trước-sau, kiểm error/audit đúng một lần và retry không thay đổi dữ liệu. Legacy fixture ghi giả trạng thái của phiên bản lỗi chỉ trong transaction test riêng, để kiểm read guard; không thay fixture bốn failing probes hay dữ liệu demo.

Browser không tuyên bố Passed: lượt nghiệm thu trước Blocked login429; lượt sửa không reset counters/password để vượt khóa. Phần UI không đổi, test build không thay thế Browser E2E. Camera/RFID/phần cứng thật và full workflow Phase6–8 ngoài phạm vi.

REGRESSION_FINAL bao gồm kiểm thử BMS ordering Phase4, Authentication/RBAC, station/compartment, battery, IoT và QR/RFID/reservation. Hai warning là deprecation của FastAPI TestClient/httpx và openapi-spec-validator, không phải failure; không cài/nâng dependency trong bản sửa.

## 6. Tái chạy, file và dung lượng

```powershell
$env:P5_EVIDENCE_DIR='docs/PHASE5_P5_A01_FIX'
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_PROBES tests/test_phase5_acceptance.py
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_ORDERING tests/test_phase5_door_ordering.py
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_ALL
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_E2E --script tools/smoke_phase5.py --http-smoke
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_IOT --script tools/smoke_phase4.py
```

Dùng label mới để giữ mọi lượt bằng chứng. Không chạy các runner cùng lúc vì helper cũ ghi chung một số report trung gian. PostgreSQL phải healthy. Simulator/E2E chỉ dùng schema/ledger test riêng, không bật simulator demo.

Giữ source ba file, test ordering mới, test acceptance nguyên vẹn, runner/helper và tài liệu/bằng chứng BEFORE/AFTER làm regression. Bảo toàn thay đổi/tài liệu uncommitted có từ nghiệm thu, bao gồm PHASE5_TEST_ENVIRONMENT và PHASE4_ACCEPTANCE output. Không git restore/reset/clean. Cache/build/log có thể cân nhắc dọn sau lưu bằng chứng; không tự xóa. `.local`, DB schema/volume, `.env`, `.git` không phải cache; test connection.json có secrets nằm trong .cache và không commit/chia sẻ.

Danh sách file của bản sửa:

| File | Mục đích / xử lý |
| --- | --- |
| services/backend/app/application/assets.py | Guard evidence/eligibility; giữ source |
| services/backend/app/application/reservations.py | Guard ngăn nhận; giữ source |
| services/backend/app/workers/device.py | Reject ordering trước cập nhật projection; giữ source |
| tests/test_phase5_door_ordering.py |25 regression mới; giữ |
| tools/run_phase5_acceptance.py |Runner có từ nghiệm thu, bổ sung output/bảo toàn bằng chứng; giữ |
| tools/smoke_phase5.py |Chạy HTTP checks sẵn có trước khi đóng fixture; giữ |
| docs/PHASE5_P5_A01_FIX.md và docs/IMPLEMENTATION_STATUS.md |Báo cáo/kết luận sửa lỗi; giữ |
| docs/PHASE5_P5_A01_FIX/ |XML/log/JSON bằng chứng mới; giữ đến khi nghiệm thu xong |

`tests/test_phase5_acceptance.py`, `docs/PHASE5_ACCEPTANCE.md`, thư mục bằng chứng nghiệm thu, `docs/PHASE4_ACCEPTANCE/` và thay đổi sẵn có của `docs/PHASE5_TEST_ENVIRONMENT.json` được bảo toàn; không coi tất cả untracked là file do bản sửa mới tạo. Log `REGRESSION.log` là lượt lỗi phát triển bị ngắt, có thể lưu trữ riêng sau nghiệm thu; không thay thế REGRESSION_FINAL.xml/log.

Dung lượng cuối lượt (tổng thư mục hiện tại, không phải toàn bộ là phát sinh mới): bằng chứng sửa lỗi0.11MiB, `.cache`148.78MiB, `.local`27.72MiB, `apps/web/dist`0.28MiB, `.pytest_cache`0.02MiB. Build và pytest cache có thể tạo lại. `.cache` chứa cả log/bằng chứng và connection.json kiểm thử có secret: chỉ cân nhắc dọn từng thư mục sau khi lưu bằng chứng và dừng tiến trình; không commit. Giữ nguyên `.local`/ledger và các schema test để đối chiếu; chưa đo dung lượng PostgreSQL/volume, không xóa tài nguyên. Không thêm dependency/image/phần mềm hệ thống.

## 7. Nghiệm thu bản sửa

Chuẩn bị commit riêng theo yêu cầu người dùng: giữ ba source, hai file test (18+25 ca), runner, helper HTTP/E2E, báo cáo sửa lỗi, báo cáo nghiệm thu lịch sử và tiến độ. `PHASE5_IMPLEMENTATION.md` đã được theo dõi, không thay đổi. Chọn commit bốn finding gốc `STALE_DOOR_1/2.json`, `STRICTLY_OLDER_DOOR_1/2.json`; JUnit `BEFORE.xml`, `REGRESSION_FINAL.xml`, `ORDERING_FINAL.xml`; `CONTRACTS.json` và ba JSON kết quả E2E/HTTP cuối trong thư mục sửa lỗi. Các file này là bằng chứng kiểm thử được giữ có chủ đích, không phải dữ liệu DB/credential.

Không stage `PHASE5_TEST_ENVIRONMENT.json` (chỉ đổi tên schema cục bộ), output `PHASE4_ACCEPTANCE/`, screenshot Browser, XML/JSON trung gian/lặp và các bản sao finding khác. Giữ nguyên trên đĩa để người dùng quyết định lưu trữ/dọn sau nghiệm thu. Không xóa file nào. `.env`, `.cache`, `.local`, thư viện và build tiếp tục bị ignore; log lỗi phát triển được giữ cục bộ. Kết quả270/8/8/28 là lượt kiểm chứng bản sửa trước bước chuẩn bị commit này; không tuyên bố đã chạy lại trong bước Git.

| Hạng mục | Kết luận mới |
| --- | --- |
| Bốn reproductions P5-A01 |4/4 Passed, nằm trong18 probes và270 regression; trước sửa4Failed |
| Snapshot ordering, restart, duplicate, scope |25/25 ca mới Passed; bao gồm cả ngăn nhận/cấp |
| Projection/rejection/audit/rollback |Passed; event lỗi không làm đổi current state/eligibility hoặc giữ tài nguyên sai |
| Reservation cạnh tranh OPEN / hai Backend |Passed qua tests PG và E2E; giữ thứ tự serial, không double booking |
| Toàn bộ pytest Phase1–5 |270 Passed,0 Failed sau sửa cuối; không cộng lại các lượt chạy trùng |
| Tiến trình thật và HTTP |8 Phase5 +8 IoT +28 HTTP Passed; fingerprint demo không đổi |
| Hợp đồng/build |Passed; baseline hash giữ nguyên, git diff --check không có lỗi whitespace |
| Browser |Not Run lượt sửa; lần nghiệm thu trước Blocked429, không reset counters |

**P5-A01 đã được khắc phục và đạt kiểm chứng kỹ thuật trong phạm vi bản sửa. Không phát hiện blocker mới qua các phép kiểm đã chạy. Phase5 đủ điều kiện kỹ thuật để người dùng nghiệm thu bản sửa và quyết định chuyển Phase6; chưa triển khai Phase6, chưa commit/push.** Kết luận không bao gồm chứng nhận phần cứng, mọi Browser flow hoặc đối soát mọi reservation lịch sử của demo. Trước chạy workflow trên dữ liệu đã bị phiên bản lỗi tác động, cần đối soát các reservation đó; bản sửa chỉ chặn việc dùng evidence sai và không tự chỉnh dữ liệu chính. Source Backend/worker đang chạy lâu dài cần được restart khi áp dụng bản sửa đã duyệt.
