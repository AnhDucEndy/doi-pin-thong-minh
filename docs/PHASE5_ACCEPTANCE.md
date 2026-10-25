# Nghiệm thu độc lập Phase 5 — QR/RFID & Reservation

> Báo cáo lịch sử trước sửa P5-A01. Bản sửa sau đó đã đạt 270 pytest Passed, gồm18 acceptance probes và25 ordering/concurrency tests; xem [PHASE5_P5_A01_FIX.md](PHASE5_P5_A01_FIX.md) để biết kết luận hiện hành. Giữ nguyên kết quả Failed bên dưới làm bằng chứng trước sửa.

Ngày 25/10/2026, Asia/Bangkok. Đối tượng: `8a29636 feat: implement QR RFID authentication and reservation`, trên `main`, trước khi nghiệm thu working tree sạch. Lượt tiếp tục xác minh HEAD vẫn là commit này, ahead origin/main 1 commit; không commit/push trong nghiệm thu.

**Kết luận: Phase 5 CHƯA đạt nghiệm thu, CHƯA đủ điều kiện chuyển Phase 6.** P5-A01 là Blocker: quan sát cửa cũ có sequence cao hơn ghi đè quan sát mới, khiến giữ tài nguyên thành công dựa trên trạng thái cửa sai. Không phải double booking; là sai điều kiện phục vụ dù transaction/unique constraints vẫn hoạt động.

## 1. Nguồn chuẩn và phạm vi

Đã đối chiếu AGENTS, README, IMPLEMENTATION_PLAN/STATUS, PHASE5_IMPLEMENTATION, PHASE4_IMPLEMENTATION/BMS_FIX, START_HERE/HANDOFF, baseline Truy-vet-yeu-cau/Test-case-du-kien, OpenAPI, schema.sql, INVARIANTS, AD-02a, SM-03a, approved config/decisions. Không đổi baseline hoặc mã yêu cầu.

- FR09/UC09/TC09, BR03: QR/RFID (F4 trong baseline, không nhầm với tên Phase 4 IoT).
- FR10/UC10/TC10, BR01/02/11: giữ pin mới, ngăn nhận, ngăn cấp nguyên tử.
- FR12/UC10: hủy/hết hạn trước thanh toán. **Không tuyên bố hoàn tất TC12 gốc** về mất mạng sau lệnh cấp/đối soát đầy đủ.
- FR13/UC11/TC13: đọc lịch sử đúng chủ; FR02/UC02/TC02: liên kết/thu hồi credential.
- CT01/02/09/10/11 và FR17/UC15/TC17, FR07/UC07/TC07: race, replay, thứ tự bằng chứng, scope và hồi quy BMS.
- QD05 QR một lần/RFID mô phỏng; QD06 quyền tách biệt; QD07 QR/verification/reservation TTL 120s, telemetry stale 15s, SOC≥80/SOH≥80/T≤40 là cấu hình mô phỏng. Không dùng phần cứng thật, thanh toán hoặc chuyển custody.

## 2. Bảo toàn trạng thái qua gián đoạn

Trước resume có `tools/run_phase5_acceptance.py`, `tests/test_phase5_acceptance.py`, `docs/PHASE5_ACCEPTANCE/PROBES.{xml,log}`, hai `STALE_DOOR_*.json`, CONTRACTS.json. Lượt PROBES trước hoàn tất **12 Passed, 2 Failed**; runner sau đó lỗi in Unicode trên console Windows, nhưng pytest/JUnit đã hoàn tất. Runner được sửa encoding trước gián đoạn; không sửa nghiệp vụ.

`REGRESSION.log` cũ dừng sau khoảng 63%, không có JUnit/kết quả cuối. Không dùng nó để tuyên bố 227 Passed. Phiên tiến trình cũ không còn. `docs/PHASE5_TEST_ENVIRONMENT.json` đã đổi schema từ `phase5_test_4ef3eb3cc2f5` sang `phase5_test_4f7250c654f8` trước resume. Giữ thay đổi này, không git restore. `docs/PHASE4_ACCEPTANCE/LATE_TELEMETRY_FINDING.json` là output do probe hồi quy cũ ghi; giữ nguyên.

**Đính chính bằng chứng cũ:** trong cả STALE_DOOR_1/2, OPEN và CLOSED có observed_at bằng nhau do độ phân giải clock khi tạo hai packet liên tiếp. Hai test cũ vẫn Failed và được giữ nguyên; tên test không thay thế nội dung bằng chứng. Không gọi hai file cũ là chứng minh timestamp nhỏ hơn tuyệt đối. Resume bổ sung test riêng với CLOSED cũ hơn OPEN đúng 1s, không đổi assertion/fixture của test cũ để hợp thức hóa kết quả.

Docker Desktop tắt lúc resume. Lượt RESUME_NEW gặp **4 setup errors** trước khi chạy nghiệp vụ, giữ log/XML; không tính là bốn lỗi business. Đã được phép khởi động Docker Desktop hiện có; container `doi-pin-dev-db-1` PostgreSQL17 trở lại healthy, không tạo/reset volume. Lượt RESUME_NEW_RETRY: **2 Passed, 2 Failed**, 14 deselected. Hai Passed là ca tranh pin/ngăn nhận còn thiếu; hai Failed chứng minh timestamp nhỏ hơn tuyệt đối.

## 3. P5-A01 — Blocker: snapshot cửa cũ tạo reservation sai

### Tái hiện và kết quả

Hai probe gốc, giữ nguyên:

- `test_old_closed_snapshot_cannot_authorize_reservation[1]` — ngăn nhận.
- `test_old_closed_snapshot_cannot_authorize_reservation[2]` — ngăn cấp.

Hai probe resume xác nhận chặt hơn:

- `test_strictly_older_closed_snapshot_cannot_authorize_reservation[1]`.
- `test_strictly_older_closed_snapshot_cannot_authorize_reservation[2]`.

Quy trình fixture riêng:

1. Seed hai trạm/sáu ngăn; dùng Device-Key fixture, gửi snapshot đầy đủ + BMS qua `POST /v1/device/events` và worker thật trong process test. Trạng thái phục vụ fixture phù hợp để cô lập điều kiện cửa. Không trực tiếp đặt `accepted=true` cho packet lỗi.
2. Customer cấp QR `POST /v1/qr-challenges`, body `{ "station_id": "<S01 UUID>" }`, UserBearer + Idempotency-Key, 201. Device xác thực `POST /v1/device/verifications`, body `{ "method":"QR", "credential":"<QR local>" }`, X-Device-Key + Idempotency-Key, 201 VERIFIED.
3. Gửi SNAPSHOT cùng boot, seq2, observed_at=T, một cửa OPEN; worker chấp nhận và projection OPEN.
4. Gửi SNAPSHOT cùng boot, seq3, observed_at=T−1s, cửa đó CLOSED, các trường khác giống snapshot hợp lệ. Cả hai timestamp vẫn trong TTL15s. HTTP202/QUEUED là đúng semantics inbox; **sai ở worker accepted=true, processing_error=null**, projection thành CLOSED.
5. `POST /v1/swaps/{id}/reserve`, body `{ "expected_version":1 }`, Customer + key mới. Actual HTTP200, `state=RESERVED`; DB có ba holds unreleased (pin + hai ngăn). Command count truy vấn thực =0; chưa có thao tác vật lý.

Expected: không dùng quan sát đo cũ để thay projection mới hoặc gia hạn tính mới; trong fixture chỉ có bộ tài nguyên này thì không được RESERVED. Theo AD-02a, hết tài nguyên đủ điều kiện có thể trả200/CANCELLED/RESOURCE_UNAVAILABLE. Đề xuất event bị đánh dấu REJECTED/EVENT_OUT_OF_ORDER theo semantics hiện có; không đổi API inbox thành HTTP lỗi đồng bộ chỉ để sửa test.

Bằng chứng `STRICTLY_OLDER_DOOR_1/2.json` chứa đầy đủ payload không-secret, response, audit event, received_at/processed_at và ba holds. Schema `phase5_test_6dcbc630bfe8`; các row trong probe rollback sau khi chụp bằng chứng. Không giả định row vẫn tồn tại khi mở DB sau test. STALE_DOOR cũ có trường commands=0 do literal trong test; chỉ JSON STRICTLY_OLDER dùng count DB thật để xác minh không có command.

### Nguyên nhân gốc

| Thành phần | Kết luận review source |
| --- | --- |
| `workers/device.py:115` apply | Kiểm TTL/future timestamp và boot/seq; seq tăng không chứng minh observed_at tăng |
| `workers/device.py:134` SNAPSHOT | Kiểm đủ sáu ngăn rồi gọi observation, không so mốc quan sát đã chấp nhận của từng ngăn |
| `workers/device.py:63` observation | Ghi door/presence/serial và `compartments.observed_at = event.received_at`, không có guard thứ tự thời điểm đo |
| `workers/device.py:152` TELEMETRY | Có guard latest_accepted_measurement riêng cho pin từ bản sửa Phase4; guard này không bảo vệ cửa/snapshot |
| `application/reservations.py:205` và `application/assets.py:174` | Ngăn nhận/ngăn cấp kiểm CLOSED và fresh trên projection. Projection sai nhưng vừa received nên lọt guard |

`device_events.observed_at` là thời điểm quan sát từ thiết bị; `battery_telemetry.measured_at` chỉ áp dụng BMS và lấy từ observed_at. `received_at` là lúc Backend nhận; `processed_at` là lúc xử lý. `compartments.observed_at` hiện lưu thời gian nhận cho freshness, không thể dùng nó như timestamp đo để so trực tiếp. `boot_id+seq` là thứ tự luồng event trong boot. Hai kiểm tra thứ tự transport và thứ tự quan sát phải độc lập.

Không cần race mới tái hiện được: các request chạy tuần tự cũng sai. Station advisory lock, row locks và transaction làm ba holds nguyên tử, nhưng không sửa được ý nghĩa dữ liệu đầu vào đã sai. Race với snapshot cũ vẫn có nguy cơ tương tự khi worker commit trước reserve. Không có bằng chứng đã mất pin hoặc mở cửa thật; tác động đã chứng minh là reservation sai điều kiện.

INVARIANTS yêu cầu “Event cũ vẫn giữ bằng chứng nhưng không làm mới projection/heartbeat”, và reserve phải kiểm lại door/presence/quality trong transaction. Lỗi cùng dạng với BMS Phase4 nhưng ở projection cửa; không phải bản sửa BMS đã bị hoàn tác.

### Đề xuất sửa — chưa thực hiện

1. Đặt guard thứ tự quan sát vật lý tại đường dùng chung cho SNAPSHOT/DOOR/PRESENCE, theo đúng ngăn/thiết bị và accepted+processed evidence. So event.observed_at với mốc quan sát hợp lệ trước đó, không dùng seq/received_at thay timestamp đo. Xét qua reboot để snapshot cũ boot mới không hồi sinh khả dụng.
2. Chọn cách lưu/đọc mốc từ event history hiện có; đánh giá index/chi phí trước quyết định có cần migration. Không đổi nghĩa cột compartments.observed_at hoặc TTL bằng sửa tên ngầm.
3. Giữ xử lý snapshot toàn phần nguyên tử: một quan sát không hợp lệ không được để một số ngăn/heartbeat/ledger đã đổi. Rollback projection rồi ghi rejected event và audit; retry không thực hiện lại side effect.
4. Timestamp bằng nhau nhưng payload mâu thuẫn cần quyết định rõ. Không coi seq cao là chứng cứ vật lý mới; lựa chọn fail-closed phù hợp tiền lệ BMS phải được ghi nhận, không tự sửa baseline. Duplicate nguyên event ID/body vẫn nhận receipt cũ.
5. Bảo vệ read/eligibility cho dữ liệu lịch sử đã được phiên bản lỗi chấp nhận; không xóa lịch sử hoặc reset demo để vượt test. Giữ source BMS guard hiện tại.
6. Chạy lại bốn failing probes, thêm cross-boot, DOOR/PRESENCE và lỗi giữa snapshot, rồi regression/concurrency/E2E. Không chỉ sửa điều kiện reserve để che projection sai.

## 4. Kết quả probe độc lập và transaction review

| Probe thực tế | Kết quả đã hoàn tất | DB/assertion |
| --- | --- | --- |
| old_closed_snapshot… [1,2] | 2 Failed, trước resume | OPEN→CLOSED cùng timestamp, RESERVED,3 holds |
| strictly_older_closed_snapshot… [1,2] | 2 Failed, resume | OPEN→CLOSED timestamp−1s, RESERVED,3 holds,0 commands |
| qr_consumed_at_verification_even_when_reservation_has_no_resources | Passed trước resume | QR consumed cùng VERIFIED; reserve CANCELLED không hoàn lại QR; replay409 QR_ALREADY_USED |
| failure_on_second_hold_insert_rolls_back_first_hold | Passed trước resume | Inject lỗi tại INSERT hold thứ hai; rollback hold đầu, VERIFIED còn nguyên, retry thành công |
| two_expiration_workers_close_and_audit_once | Passed trước resume | Hai connection/worker đồng thời, chỉ một close/audit, cả3holds release |
| rfid_concurrent_reads_no_implicit_reservation [False,True] | 2 Passed trước resume | Khác key201/409 ACTIVE_TRANSACTION; cùng key201/201 cùng swap;0holds |
| rfid_revocation_competes_with_verify | Passed trước resume | Verify thắng trước revoke hoặc401 nếu revoke thắng; lần đọc sau luôn401 CREDENTIAL_INVALID |
| revoke_user_session_then_retry_cannot_read_historical_receipt | Passed trước resume | Logout rồi replay key reserve trả401 SESSION_REVOKED; không trả receipt vượt auth |
| user_locked_while_reserved_can_still_expire | Passed trước resume | User bị khóa không hủy qua session cũ; SYSTEM expiry vẫn release an toàn |
| expiration_respects_handoff_evidence [consent,return,pickup] | 3 Passed trước resume | Fixture evidence khiến cancel409 RECONCILIATION_REQUIRED; expiry không đổi holds |
| rfid_identity_cannot_be_reassigned_to_another_customer | Passed trước resume | Trùng hash409 RESOURCE_CONFLICT; giữ nguyên chủ thẻ |
| competing_customers_single_pin_or_single_return_slot [False,True] | 2 Passed resume | Barrier hai connection, một RESERVED/một CANCELLED, đúng3holds; pin cuối hoặc ngăn trả cuối với2pin cấp |

Tổng probe độc lập phân biệt: **18 =14 Passed +4 Failed**; không cộng lại lượt setup error vào tổng nghiệp vụ. Đây là kết quả kết hợp hai lượt, không tuyên bố vừa chạy lại toàn bộ18.

QR tiêu thụ tại VERIFIED theo INVARIANTS §1/AD-02a, không đợi RESERVED. Idempotency là receipt của cùng principal+route+key+body, không tiêu thụ lần hai; reserve receipt lịch sử có thể vẫn RESERVED sau cancel/expire, caller phải GET current state. RFID đã xác thực tạo VERIFIED; không tự giữ tài nguyên. Thu hồi RFID được kiểm tại verify. Việc revoke thẻ sau khi đã VERIFIED có phải hủy phiên đã xác thực hay không chưa được baseline quy định; không tự đặt expected mới hoặc tuyên bố lỗi nếu reserve vẫn dùng phiên hợp lệ.

Lock review: PostgreSQL transaction-scoped advisory station lock + user/swap/resource row locks; compartments và batteries theo UUID. Ba holds/quote/state/audit/idempotency cùng commit. Partial unique indexes một active swap/customer, một active battery hold, một active compartment hold là lớp cuối; không dùng mutex memory. Expiry/cancel chỉ release đúng swap_id và unreleased; chặn consent/payments/outbox/commands/evidence. Isolation không được override trong engine, dùng mặc định server; không tuyên bố SERIALIZABLE. Lỗi P5-A01 tồn tại ngay cả khi serialize đúng.

## 5. Regression, API, Frontend và giới hạn

Kết quả cuối của regression/E2E bổ sung được ghi ở phần cập nhật cuối báo cáo này. Build TypeScript/Vite trước gián đoạn đã chạy thành công (81 modules); lần sandbox đầu bị Access denied, lần escalated Passed. CONTRACTS.json: OpenAPI/approved JSON Schema/278 SQL statements/baseline hashes Passed. Không sửa Frontend/source sau build đó.

Tám endpoint F5 đối chiếu OpenAPI:

| Method/path | Role | Thành công / lỗi quan trọng |
| --- | --- | --- |
| POST /v1/users/{user_id}/credentials | Admin | 201; trùng409 RESOURCE_CONFLICT |
| POST /v1/credentials/{id}/revoke | Admin | 200; Technician403 FORBIDDEN |
| POST /v1/qr-challenges | Customer | 201; Admin/Tech403 |
| POST /v1/device/verifications | X-Device-Key | 201; thiếu key401; QR sai trạm403 QR_STATION_FORBIDDEN; expired409 QR_EXPIRED; replay409 QR_ALREADY_USED; revoked RFID401 CREDENTIAL_INVALID |
| GET /v1/swaps | Admin/Customer | 200 scoped; Tech403 |
| GET /v1/swaps/{id} | Admin/owner Customer | 200; khác chủ404 RESOURCE_NOT_FOUND |
| POST /v1/swaps/{id}/reserve | owner Customer | expected_version, key;200 RESERVED hoặc CANCELLED, version409 |
| POST /v1/swaps/{id}/cancel | owner Customer | expected_version,reason,key;200 CANCELLED; unsafe409 RECONCILIATION_REQUIRED |

POST yêu cầu Idempotency-Key UUID; verification chỉ method+credential, không cho client tự khai station_id/device_id. Trạm suy từ key. QR/RFID raw không được lưu trong audit/receipt; QR response cần token cho caller hợp lệ, không in vào báo cáo. Không có per-QR revoke endpoint/column trong baseline. Không có quota approved riêng cho QR/verify; limiter login giữ nguyên. Không coi RFID UID mô phỏng là xác thực phần cứng chống sao chép.

Các giới hạn chưa kiểm chứng toàn bộ: full Browser negative/concurrency, camera/clipboard/getpass tương tác, RFID thật; cưỡng bức TCP mất response tại từng mốc (retry sau commit đã được kiểm nhưng không tương đương mọi kiểu network failure); full workflow Phase6–8/TC12; restart đúng thời điểm deadline của Backend đồng thời multiworker; stress/load dài hạn và mọi lịch xen kẽ thread. Các mục này là Not Run hoặc phụ thuộc phase sau, không làm giảm mức Blocker đã tái hiện.

## 6. Hướng dẫn kiểm tra UI an toàn

Menu đúng: **QR/RFID và giữ tài nguyên**. Tài khoản demo `customer`, `admin`, `technician`; dùng mật khẩu local hiện có, không đưa vào report/chat. Backend/worker/frontend khởi qua `tools/dev.ps1 backend`, `worker`, `frontend` ở terminal riêng; tránh chạy trùng port. Để kiểm thử ghi/lỗi, dùng `tools/smoke_phase5.py --serve` và Vite DEV_API_TARGET trỏ test API8003, port5174, không sử dụng demo API8000.

1. Customer: mở menu, chọn trạm → **Cấp QR một lần**. QR có hình/countdown; đừng chụp ảnh QR còn hiệu lực. Bộ đọc local đúng trạm xác thực; xem VERIFIED. **Giữ pin và hai ngăn** chỉ được coi thành công khi Backend trả RESERVED, chưa thu phí/giao pin. **Hủy trước thanh toán** → CANCELLED; GET API kiểm release.
2. Admin: cùng menu, **Liên kết RFID**, chọn Customer, nhập giá trị thử chỉ trong fixture; giữ ID response, **Thu hồi RFID**. Device verify thẻ đã thu hồi phải401. Không có API liệt kê credential nên danh sách UI chỉ các thao tác trong phiên.
3. Technician: không có menu QR/lịch sử Customer; Swagger GET /v1/swaps với bearer Technician phải403. Không dùng Device-Key trong Frontend.
4. Swagger `/docs`: Authorize bằng session local, POST QR/verify/reserve/cancel đúng bảng trên. Không chia sẻ token; không nhập key S01 để giả station S02. Gửi thêm station_id vào verification phải422; QR của S02 qua key S01 phải403.
5. **Không tái hiện snapshot lỗi trên demo chính.** Chạy probe PostgreSQL riêng bên dưới; UI reservation chỉ phản ánh response, không phải một phép kiểm độc lập chứng minh cửa vật lý đúng.

## 7. Tái chạy và bảo toàn file

```powershell
# Dùng label mới để không ghi đè bằng chứng runner cũ.
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py CHECK_STRICT tests/test_phase5_acceptance.py -k strictly_older
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py CHECK_RACES tests/test_phase5_acceptance.py -k competing_customers
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py CHECK_REGRESSION --ignore=tests/test_phase5_acceptance.py
```

Probe finding JSON hiện dùng tên cố định; trước khi tái chạy failing probes ở lượt sửa, lưu bản bằng chứng hiện tại riêng và không xóa. Runner giữ các report cũ mà helper/conftest tự ghi; dùng schema mới, per-test rollback hoặc schema race độc lập, không DROP/TRUNCATE/reset. Migrations empty/upgrade/repeated upgrade chạy trong fixture, head0002_user_approval. Không cần migration để nghiệm thu.

Nên giữ làm regression: `tests/test_phase5_acceptance.py` (cả failing probes), runner `tools/run_phase5_acceptance.py`. Giữ báo cáo này và XML/log/JSON trong `docs/PHASE5_ACCEPTANCE/` làm bằng chứng trước sửa. File gốc STALE_DOOR/PROBES/REGRESSION.log bị ngắt vẫn giữ.

File tracked đã thay đổi trước resume: `docs/PHASE5_TEST_ENVIRONMENT.json` (chỉ schema test). File phát sinh `docs/PHASE4_ACCEPTANCE/LATE_TELEMETRY_FINDING.json` cũng giữ. Không tự phục hồi report về HEAD để làm working tree sạch. Không sửa source nghiệp vụ/Frontend/baseline, không commit/push.

`.cache/p5-acceptance-*` là thư mục tạm pytest/log có thể cân nhắc dọn sau lưu bằng chứng; dist/__pycache__/.pytest_cache tái tạo được. Không tự dọn. DB schemas test, `.local` ledger, Docker volume, `.env`, `.git` phải bảo toàn. Không cài dependency/hạ tầng mới.

## 8. Kết quả hồi quy mới sau resume

`RESUME_REGRESSION.xml/log`: **227 Passed, 0 Failed, 0 Errors, 0 Skipped**, 132.90s. Bao gồm Phase1:18; Phase2:37; Phase3:48; Phase4:44; Phase4 acceptance:7; BMS ordering:21; Phase5:52. Không cộng các lần chạy lại cùng test thành test mới. `REGRESSION.log` cũ chưa hoàn tất chỉ giữ làm lịch sử gián đoạn.

Trong52 Phase5 có các test `test_CT01_concurrent_qr_exactly_one_consumption`, `test_CT02_double_booking_across_two_backend_processes` (hai Uvicorn thật8005/8006), `test_reservation_race_with_asset_changes` (maintenance/quarantine/telemetry), `test_cancel_and_expire_release_once`, `test_old_expiry_job_cannot_release_a_new_booking`, `test_verification_transaction_rollback_keeps_qr_unused`, các TTL boundary ±1µs/đúng hạn, eligibility/RBAC/schema/idempotency. BMS21 và acceptance7 vẫn Passed; event BMS cũ bị EVENT_OUT_OF_ORDER, không nâng availability. Đây là kết quả mới, không trích con số227 từ bàn giao.

Tổng pytest phân biệt của cuộc nghiệm thu (gộp kết quả hoàn tất trước/sau resume): **245 =241 Passed +4 Failed**. Bốn Failed là bốn biểu hiện của cùng P5-A01, không phải bốn blocker. Bốn setup errors của RESUME_NEW là lượt môi trường thất bại, đã retry đúng bốn ca; không đếm thành lỗi nghiệp vụ hoặc bỏ log. Hai deprecation warnings Starlette/httpx và validate_spec giữ nguyên.

| Nhóm nghiệm thu | FR/UC/TC/CT | Backend/API và DB | Frontend | Trạng thái nhóm |
| --- | --- | --- | --- | --- |
| 1 QR một lần/replay/rollback | FR09/UC09/TC09,CT01/11 | Unique challenge/active swap;201/409; rollback consumed_at; retry cùng receipt; hết tài nguyên không phục hồi QR | Xem hướng dẫn mục6; không suy ra toàn bộ UI từ API | Passed phần API/DB |
| 2 RFID/revoke/Device-Key | FR09/UC09/TC09,FR02,CT10 | Hash không đổi chủ; race revoke/verify; đọc lặp không tạo hold; key suy đúng trạm; thẻ revoked401 | Chức năng UI có sẵn, nhập thẻ thật ngoài phạm vi | Passed phần API/DB |
| 3 Độc quyền/atomicity | FR10/UC10/TC10,CT02 | Hai khách tranh pin/ngăn; hai Backend; fail INSERT thứ2 rollback; chỉ3holds cho người thắng | UI chỉ lấy kết quả server | Passed về độc quyền; **không đồng nghĩa reserve đúng mọi eligibility** |
| 4 Door/BMS/maintenance eligibility | FR10,FR07,FR17,BR02/11,CT09 | Maintenance/BMS races Passed; snapshot cửa cũ lọt và tạo RESERVED/3holds | Hiển thị RESERVED sai từ Backend, chưa kiểm lỗi bằng Browser | **Failed — Blocker P5-A01** |
| 5 TTL/cancel/expiration | FR12 phần trước thu,SM-03a,CT11 | TTL120, boundary, cancel/expiry, hai worker chỉ1audit; không release booking khác/evidence workflow | Hạn hiển thị không thay quyền quyết định của Backend | Passed các test nêu trên; full TC12 Not Run |
| 6 Auth/RBAC/scope | FR01/02/13,UC01/02/11,TC01/02/13,CT10 | Customer cross-owner404, Technician403; revoked session401 kể cả retry; worker vẫn expire user locked | Kiểm ba vai trò theo phần Browser cuối báo cáo | Passed phần API/DB |
| 7 Hồi quy IoT/BMS/invariants | FR03–08/17/19,CT04/06/09 | 175 regression trước Phase5 Passed, BMS fix còn nguyên; ACK không custody; snapshotordering còn lỗi | Không suy ra phần cứng thật | **Failed tích hợp ordering cửa**, phần hồi quy có sẵn Passed |
| 8 Contract/build/UI/bảo mật | OpenAPI/Schema/QD | Validator Passed,278SQL; không có per-QR revoke/quota mới ngoài contract | TypeScript/Vite Passed trước resume; Browser tách báo cáo dưới | Passed static/build; các giới hạn Not Run nêu rõ |

Không phát hiện thêm Blocker/Major độc lập trong những ca đã chạy. Không kết luận đã loại trừ mọi race, mọi lỗ hổng hoặc mọi đường đời của module tương lai. Trạng thái tổng thể vẫn **Blocked chuyển Phase6** bởi P5-A01.

## 9. Hoàn tất E2E, Browser và kiểm tra file

E2E mới trong lượt resume: **8 checks Passed**, `RESUME_E2E_PHASE5_E2E_RESULTS.json` và `RESUME_E2E.log`, schema `phase5_e2e_161c5f9b7c`. Hai Backend8003/8004, worker và hai simulator thật, bằng chứng đi qua inbox. Kiểm QR cạnh tranh một token qua hai process; retry reserve qua process khác giữ đúng3holds,0payments/outbox/commands; chờ **TTL120s thật** sau worker restart, release một lần; receipt lịch sử không hồi sinh phiên; RFID dùng lại sau kết thúc rồi revoke bị từ chối; fingerprints asset/evidence/reservation của demo chính trước/sau khớp. Không thay thế blocker snapshot bằng luồng E2E happy-path này.

Browser test: Vite5174 trỏ fixture8003, không demo. Đã mở trang/login Customer; UI trả “Đã vượt giới hạn đăng nhập. Vui lòng thử lại sau 15 phút.” Đọc DB fixture thấy hai login buckets có failed_count=5 và locked_until=2026-10-25 04:20:39.064897+00:00. Không xóa counters/đổi password/seed lại để làm Passed. Chưa xác định chắc chắn nguồn của các lần thử sai, vì vậy không quy lỗi này cho nghiệp vụ auth hoặc kết luận ba vai trò đã Passed qua Browser. Đã xóa nội dung hai ô trên form, lưu `BROWSER_BLOCKED.png`, đóng tab và bỏ credentials khỏi biến làm việc.

**Browser ba vai trò và các thao tác UI: Blocked tại login**, cần chạy lại trong lượt sửa/nghiệm thu sau. Frontend build/static vẫn Passed như trước gián đoạn; không đồng nhất build với E2E. Không lấy ảnh/UI Passed của lần triển khai làm bằng chứng của lượt nghiệm thu độc lập này.

| Phép kiểm | Kết quả của cuộc nghiệm thu độc lập |
| --- | --- |
| Regression hiện hữu chạy mới sau resume | 227 Passed /0 Failed /0 Errors /0 Skipped |
| Probe độc lập đã hoàn tất trước resume | 12 Passed /2 Failed |
| Bốn probe bổ sung sau Docker healthy | 2 Passed /2 Failed |
| Tổng pytest phân biệt | **241 Passed /4 Failed** |
| Lượt setup khi Docker còn tắt | 4 Errors môi trường, đã retry; giữ log riêng |
| E2E Phase5 socket/process thật chạy mới | **8 Passed** |
| Validator OpenAPI/JSON Schema/SQL/baseline | Passed trước gián đoạn, artifact còn nguyên |
| TypeScript/Vite | Passed trước gián đoạn, không đổi source web sau đó |
| Secret scan artifact/bundle | Passed:0 matches với secret local/fixture,25files, không in secret |
| Browser ba vai trò | **1 nhóm Blocked** tại login429; các flow phía sau Not Run |
| Bộ HTTP smoke28 riêng | **Not Run** trong nghiệm thu này; E2E8 có HTTP thật nhưng không tính thay28 |
| Bộ E2E IoT8 riêng | **Not Run** trong nghiệm thu này; pytest Phase4/ordering đã chạy |
| Full Phase6–8/TC12, phần cứng, TCP fault mọi mốc/stress | **Not Run**, không lấy kết quả phase trước cộng vào |

Not Run đếm theo nhóm công việc, không bịa số test chưa được tạo/chưa collect. Các bước chưa chạy không ảnh hưởng kết luận từ blocker đã có bằng chứng; sau sửa phải hoàn tất các cổng nghiệm thu cần thiết, đặc biệt Browser và ordering trên các loại evidence khác.

Lệnh thực tế quan trọng: git status/diff/log; runner PROBES trước gián đoạn; runner RESUME_NEW và RESUME_NEW_RETRY với `-k "strictly_older or competing_customers"`; runner RESUME_REGRESSION `--ignore=tests/test_phase5_acceptance.py`; runner RESUME_E2E `--script tools/smoke_phase5.py --serve`; npm Vite dev5174; trước gián đoạn npm build và validate_contracts. Đã dừng fixture E2E bằng STOP của chính schema, helper finally dừng các process nó tạo; Vite test dừng Ctrl+C. Không tắt Docker/DB người dùng; không đụng ledger demo.

File mới/tiếp tục: báo cáo này, `tests/test_phase5_acceptance.py` (resume chỉ append hai ca strictly-older), `tools/run_phase5_acceptance.py` giữ nguyên khi resume, mọi artifact liệt kê trong `docs/PHASE5_ACCEPTANCE/`. `docs/IMPLEMENTATION_STATUS.md` thêm thông báo nghiệm thu mới ở đầu, không xóa báo cáo lịch sử. `docs/PHASE5_TEST_ENVIRONMENT.json` và output Phase4 đang untracked/thay đổi từ trước được giữ nguyên byte khi runner hoàn tất. Không sửa bất kỳ file services/backend, apps/web, simulators, migration hoặc baseline nào.

Dung lượng đo: artifact nghiệm thu khoảng131KiB trước bổ sung văn bản cuối;6 thư mục `.cache/p5-acceptance-*` khoảng298KiB; cache E2E mới khoảng4.7KiB; ledger E2E mới khoảng8.25MiB. Không tải thư viện/image mới. `.cache/phase5_e2e_161c5f9b7c/connection.json` chứa **test credentials**, bị Git ignore, không chia sẻ/commit. Giữ `.local/phase5_e2e_161c5f9b7c` cùng DB schema làm bằng chứng. Các con số là dung lượng file, không phải mức tăng VHDX Docker.

**Quyết định nghiệm thu cuối: CHƯA ĐẠT. Không chuyển Phase6 cho đến khi P5-A01 được sửa và kiểm chứng lại.** Lượt này chỉ điều tra, test và báo cáo; không tự sửa nghiệp vụ, không commit, không push.
