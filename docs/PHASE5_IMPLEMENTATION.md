# Phase 5 – QR/RFID Authentication & Reservation

Hoàn tất kiểm chứng 25/10/2026, Asia/Bangkok; bắt đầu 24/10. Base `main@a18e64f` (`fix: reject stale BMS telemetry despite higher sequence`), working tree ban đầu sạch; local khớp origin/main lúc bắt đầu. Kế thừa Phase1–4, không xây dựng lại. Chưa Phase6, chưa push.

## 1. Phạm vi và nguồn chuẩn

Đã đọc AGENTS, README, plan/status, PHASE3/4_IMPLEMENTATION, PHASE4_BMS_FIX, START_HERE, CODEX_HANDOFF/modules/tests, DOCX/CSV baseline, OpenAPI, ERD-02, AD-02a, SM-03a/b, invariants, DDL/data dictionary, approved config và QD01–09. Validator xác nhận hash baseline không đổi. Tên Phase5 theo yêu cầu không đổi mã module gốc: QR/RFID là F4 baseline, reservation là một phần F5 baseline.

| FR/UC/TC/BR | Kết quả trong lượt này |
| --- | --- |
| FR09 / UC09 / TC09, BR03 | QR opaque một lần, ràng buộc khách/trạm/hạn; RFID nhiều lần, thu hồi RFID, device authentication |
| FR02 / UC02 / TC02 (bổ sung credential) | Admin liên kết/thu hồi RFID cho Customer; không cấp role Technician cho Admin |
| FR10 / UC10 / TC10, BR01/02/11 | Giữ đúng pin cấp + hai ngăn nguyên tử; fee/policy/TTL từ approved snapshot; concurrency PostgreSQL |
| FR12 / UC10 | Chỉ hủy trước thanh toán/command và timeout an toàn; chưa full TC12 mất mạng sau lệnh cấp/recovery |
| FR13 / UC11 / TC13 | Đọc phiên/lịch sử scoped Admin/Customer để xem reservation; tài chính qua module sau, không trộn vào state |
| CT01/02/10/11, BR10/12 | Một active swap/khách, không double booking; ownership; idempotency; giữ lịch sử/audit |
| Phase4 BMS guard | Giữ cả 7 acceptance probes và 21 ordering tests; không hồi sinh P4-A01 |

Không consent/payment/outbox charge, không OPEN_RETURN/OPEN_SUPPLY từ reservation, không chuyển custody hoặc hoàn tất swap. State RESERVED là hook dữ liệu cho Phase6/7, không tự thực hiện các phase đó.

## 2. API mới – đúng hợp đồng gốc

| Method/path | Operation/status | Quyền |
| --- | --- | --- |
| POST /v1/users/{user_id}/credentials | createCredential, 201 CredentialView | Admin; target phải Customer ACTIVE |
| POST /v1/credentials/{credential_id}/revoke | revokeCredential, 200 CredentialView | Admin |
| POST /v1/qr-challenges | createQr, 201 QrResponse | Customer hiện hành |
| POST /v1/device/verifications | verifyAtDevice, 201 SwapTransactions | X-Device-Key; trạm suy từ device |
| GET /v1/swaps | listSwaps, 200 SwapTransactionsPage | Admin toàn mạng; Customer chỉ của mình |
| GET /v1/swaps/{swap_id} | getSwap, 200 SwapTransactions | Admin/Customer; khác chủ404 |
| POST /v1/swaps/{swap_id}/reserve | reserveSwap, 200 SwapTransactions | Customer đúng chủ; expected_version + Idempotency-Key |
| POST /v1/swaps/{swap_id}/cancel | cancelSwap, 200 SwapTransactions | Customer đúng chủ; expected_version/reason + key |

Mọi POST trên có Idempotency-Key UUID. CredentialRequest chỉ rfid_value (1..200); QrRequest chỉ station_id; VerificationRequest chỉ method QR/RFID và credential (1..512). Không nhận customer_id/station_id trong verification. Reserve chỉ expected_version≥1; cancel thêm reason không rỗng. Không có PATCH state/vị trí tùy ý hoặc endpoint tạo reservation chọn pin/ngăn theo client.

Mã lỗi thực tế: 401 AUTH_REQUIRED/SESSION_INVALID/SESSION_REVOKED, DEVICE_AUTH_REQUIRED/DEVICE_KEY_INVALID, CREDENTIAL_INVALID; 403 FORBIDDEN/CUSTOMER_UNAVAILABLE/DEVICE_DISABLED/QR_STATION_FORBIDDEN; 404 RESOURCE_NOT_FOUND; 409 QR_ALREADY_USED/QR_EXPIRED/ACTIVE_TRANSACTION/STATE_CONFLICT/VERSION_CONFLICT/IDEMPOTENCY_CONFLICT/RECONCILIATION_REQUIRED/RESOURCE_CONFLICT/QR_DELIVERY_UNAVAILABLE; 422 VALIDATION_ERROR/CONFIG_NOT_READY/CUSTOMER_BATTERY_REQUIRED; 503 STATION_OFFLINE hoặc DATABASE_UNAVAILABLE. Không đưa token/hash/credential hoặc exception DB vào Error details.

## 3. QR một lần, nonce và bảo mật lưu trữ

QR là opaque value 256 bit, base64url, không là JWT hoặc payload ký mới. Tái sử dụng pattern secret delivery của createDevice: HMAC-SHA256 với DEVICE_KEY_DERIVATION_SECRET đã có, tách domain `createQr:v1:user_id:idempotency_key`. UUID key ngẫu nhiên do client tạo là nonce request; secret Backend khiến mã không thể suy ra chỉ từ UUID/khách. Không thêm secret Frontend. Giữ secret ổn định để retry trả đúng QR cũ; sai secret sau rotation bị QR_DELIVERY_UNAVAILABLE, không phát token khác cho cùng receipt.

DB chỉ lưu token_hash, customer, station, expires_at, consumed_at; audit/idempotency cache chỉ lưu public challenge metadata, không qr_token. API dựng lại đúng token khi replay; hash kiểm lại với challenge row trước trả. Hạn từ qr_ttl_seconds=120; retry cùng key không gia hạn hoặc phát QR mới. Khác body cùng key409.

Verification: lock station → user → QR row, kiểm user role/state, device enabled/online, QR đúng trạm/chưa consumed/chưa hết hạn; ghi VERIFIED và consumed_at cùng transaction. Row lock + unique qr_challenge_id + partial unique active swap/customer bảo vệ cả hai Backend process. Hai request khác key cùng QR: một201, một409; cùng key/nguyên body nhận cùng receipt201 và cùng swap_id. Receipt replay không phải tiêu thụ lần hai. Nếu insert/audit lỗi, cả swap và consumed_at rollback.

**Giới hạn contract về thu hồi QR:** schema không có revoked_at cho QR, cũng không có endpoint thu hồi từng QR. Không tự thêm cột/API/quy tắc “cấp QR mới hủy mọi QR cũ”. QR của tài khoản không còn ACTIVE/CUSTOMER bị từ chối; QR hết hạn/đã dùng/sai trạm bị từ chối. Thu hồi từng QR riêng là ngoài hợp đồng hiện có, chưa triển khai và không tuyên bố đã test.

## 4. RFID tái sử dụng

Admin tạo credential hash cho đúng Customer ACTIVE; raw RFID không lưu trong DB/audit/cache. UID chỉ là định danh mô phỏng; không coi là chống sao chép phần cứng. Admin thu hồi bằng revoked_at, không xóa lịch sử.

Thiết bị xác thực RFID ánh xạ đúng Customer từ hash, kiểm revoked_at và role/state. Một lần đọc hợp lệ tạo VERIFIED, **không tự reserve**. Khi khách đang có phiên active, đọc mới khác key409 ACTIVE_TRANSACTION; retry cùng key chỉ phát lại receipt. Sau khi phiên cũ CANCELLED/kết thúc, RFID vẫn dùng lại được cho phiên khác. RFID bị thu hồi/không tồn tại trả CREDENTIAL_INVALID; không cho browser đóng vai device bằng user bearer.

Adapter `python -m simulators.device.authenticate` nhận QR/RFID qua getpass trong terminal tương tác, không lấy credential qua argv. Key từ env riêng thiết bị, chỉ loopback, không đọc/đổi command ledger. Non-TTY bị từ chối để không fallback sang nhập có echo. Giao tiếp reader HTTP đã kiểm; nhập getpass tương tác bằng tay chưa chạy tự động.

## 5. Vòng đời reservation và quote

Một aggregate swap dùng các enum có sẵn: VERIFIED → RESERVED → CANCELLED trước thanh toán. Không thêm enum ACTIVE/EXPIRED cho reservation; released_at=null biểu thị hold độc quyền. Hết hạn tạo CANCELLED với review_reason=RESERVATION_EXPIRED hoặc VERIFICATION_EXPIRED, giữ tất cả lịch sử.

Verify TTL=120 từ verification_ttl_seconds; reservation TTL=120 từ reservation_ttl_seconds. created_at/expiry lấy giờ Backend và kiểm sau khi chờ lock; đúng deadline được coi hết hạn. Worker không dùng state in-memory nên restart vẫn hết hạn đúng từ DB. Job được tích hợp vào worker device hiện có, sau xử lý inbox/timeouts; không thêm broker/process hạ tầng.

Reserve không nhận pin/ngăn/giá do client chọn. Dùng policy_snapshot đã chốt lúc verify, xác định pin cũ đúng holder/family; chọn ngăn nhận trống ACTIVE/CLOSED/presence false/serial null/observation mới, không pin/reservation/alert/active swap liên quan; pin cấp qua đúng assets.eligible() Phase2/3, gồm accepted BMS/current boot/measurement order/TTL/SOC/SOH/T/lifecycle/location/không lỗi. IN_SERVICE riêng lẻ không đủ.

Giữ pin mới và cả ngăn nhận/ngăn cấp (ba resource_reservations), cập nhật old/new IDs, amount_minor=9000/currency=VND/expiry/version và audit cùng commit. Policy và mức tiền không lấy từ request hoặc hard-code lại trong logic.

**Kết quả không đủ tài nguyên:** AD-02a/SM-03a quy định đóng VERIFIED thành CANCELLED khi hết pin/ngăn. reserveSwap trả200 với đúng SwapTransactions.state=CANCELLED và review_reason=RESOURCE_UNAVAILABLE; không tạo hold hoặc quote giả. Giao diện chỉ báo thành công giữ tài nguyên nếu state=RESERVED, không chỉ dựa status200. Verification quá hạn khi reserve cũng trả CANCELLED/VERIFICATION_EXPIRED. Version/state sai vẫn409. Hai khách tranh đúng một bộ tài nguyên: một RESERVED, một CANCELLED; không coi cả hai HTTP200 là hai reservation thành công.

## 6. Transaction, concurrency và timeout an toàn

Khóa station advisory/row hiện có làm hàng rào chung với bảo trì, lifecycle, telemetry. Bên trong: user → swap → compartments theo UUID → batteries theo UUID. Backend recheck online/TTL/quality/held sau lock; không giữ lock trong lúc chờ khách hay mạng. Unique indexes active swap/customer, active battery reservation và active compartment reservation là lớp bảo vệ cuối tại PostgreSQL. Không có mutex in-memory.

Cancellation/expiry lock cùng station/user/swap; chỉ release rows có **đúng swap_id** và released_at null, tăng version và ghi closed_at/audit trong một transaction. Không release nếu đã consent, có bất kỳ payment, command, outbox của swap hoặc bằng chứng nhận/lấy pin. Không dựa expiry để cướp tài nguyên của giao dịch khác. Hủy/expiry đồng thời chỉ có một CANCEL_RESERVATION audit, job lặp không release lần hai. Job cũ không release booking mới sau khi tài nguyên được đặt lại.

Giữ nguyên Phase4: nếu lỗi/offline sau reserve làm phiên chuyển REVIEW_REQUIRED, giữ tài nguyên; không tự dùng timeout Phase5 để bypass điều kiện đối soát của Phase8. Payment UNKNOWN/CREATED, command pending/UNKNOWN hoặc state sau RESERVED không được force-cancel ở phase này. Chức năng recovery toàn diện chưa có.

Idempotency dùng utility Phase1, receipt commit cùng state/audit. Sau expiry, retry key reserve đã thành công trả receipt lịch sử RESERVED theo contract; **không tạo hold mới/không hồi sinh state**. Frontend luôn GET/poll state hiện tại sau mutation. Caller khác cũng phải đọc GET swap trước khi quyết định tiếp; không dùng receipt cũ làm bằng chứng trạng thái hiện tại hoặc physical effect.

## 7. Database, migration, seed và tích hợp

PostgreSQL17.11 kết nối thành công. Schema đã có credentials/qr_challenges/swaps/resource_reservations/idempotency/audit, constraints và indexes: **không migration cấu trúc mới**, head0002_user_approval. Không chạy schema.sql lại. tools/provision_database.py thêm INSERT/UPDATE cho bốn bảng Phase5, giữ runtime/migrator tách biệt, audit INSERT-only, không DELETE lịch sử. Grants đã được áp dụng trên demo sau khi tests đạt; không sửa các row demo hoặc credential hiện có.

Seed không thay đổi, không gán RFID cố định hoặc tạo reservation vào demo tự động. Ba tài khoản, hai trạm×sáu ngăn, một dòng pin vẫn giữ. E2E tạo schema mới, seed idempotent riêng; các pin/ngăn test chỉ được activate/restore sau snapshot/BMS thật từ simulator đã qua worker. Các race tests dùng fixture PostgreSQL rõ ràng, không thay seed chính để làm Passed.

P4-A01 source guard được giữ nguyên; 7 acceptance +21 ordering tests vẫn chạy và Passed. Không cập nhật service_state chỉ do cửa đổi, không xem ACK là delivery. Không payment/outbox/device_command hoặc custody được tạo từ reservation.

Rate limiting: cơ chế login Phase1 với approved login_max_failures/login_window_seconds và counters DB giữ nguyên, đã regression. Hợp đồng/QD không chốt quota riêng cho issuing QR hoặc failed device-verification; không tự đặt quota mới từ số tùy ý và không tuyên bố đã có limiter riêng hai endpoint này. Device endpoints bắt buộc key còn enabled và không dùng user bearer.

## 8. Frontend và các trạng thái

Menu **QR/RFID và giữ tài nguyên** cho Customer/Admin; Technician không có quyền lịch sử khách nên không có menu này. React dùng API client/auth hiện có, token chỉ bộ nhớ tab, không Device-Key trong bundle/localStorage.

Customer: chọn trạm, **Cấp QR một lần**, hình QR thực sự bằng qrcode@1.5.4, countdown/hết hạn; có **Sao chép mã cho bộ đọc mô phỏng**. QR được ẩn khi có phiên active. Xem VERIFIED/RESERVED/CANCELLED/REVIEW_REQUIRED, quote/IDs/TTL, nút **Giữ pin và hai ngăn**, **Hủy trước thanh toán** khi phù hợp. Đồng hồ client chỉ giúp hiển thị; hết hạn/kết quả luôn từ Backend.

Admin: **Liên kết RFID**, **Thu hồi RFID**, danh sách credential của thao tác trong phiên UI và đọc lịch sử toàn mạng. Không có endpoint list credentials trong contract, nên UI không tự invent một endpoint để tải lịch sử RFID; có thể nhập ID credential đã lưu để revoke. Raw RFID form bị xóa sau thành công, không trả lại trong list.

Có loading/error/empty, lỗi role/scope từ Backend, QR expired và reservation đến hạn/chờ Backend xác nhận. Không có nút consent/thu phí hoặc mở cửa Phase6/7. Dependency npm thêm qrcode1.5.4 và @types/qrcode1.5.6 (local workspace), không dependency Python/hạ tầng mới. npm audit hiện0 vulnerabilities; không tự approve lại install scripts toàn hệ thống.

## 9. Kiểm thử thực tế

| Nhóm | Kết quả cuối | Bằng chứng |
| --- | --- | --- |
| Phase1 | 18 Passed | PHASE5_REGRESSION.xml |
| Phase2 | 37 Passed | cùng JUnit |
| Phase3 | 48 Passed | cùng JUnit |
| Phase4 | 44 +7 acceptance +21 ordering =72 Passed | cùng JUnit, PHASE5_BMS_GUARD_RESULTS.json |
| Phase5 | 52 Passed | cùng JUnit và PHASE5_TEST_RESULTS.xml |
| Tổng regression cuối | **227 Passed, 0 Failed, 0 Skipped** | PHASE5_REGRESSION.xml / VERIFICATION_SUMMARY |
| HTTP Phase5 trên test API | **28 Passed** | PHASE5_HTTP_SMOKE_RESULTS.json |
| E2E Phase5 tiến trình thật | **8 checks Passed** | PHASE5_E2E_RESULTS.json |
| E2E IoT hồi quy với code Phase5 | **8 checks Passed** | PHASE5_IOT_REGRESSION_RESULTS.json |
| OpenAPI/approved schema/SQL/hash baseline | Passed,278 statements parse | PHASE5_CONTRACT_VALIDATION.json |
| TypeScript/Vite | Passed,81 modules, JS283.09kB/gzip90.09kB | lệnh build cuối |
| npm audit/pip check | Passed,0 npm vulnerabilities/no broken Python requirements | tool output |
| Browser phần mô tả dưới | Passed, có DB confirmation | PHASE5_BROWSER_RESULTS.json + ảnh/text |

52 ca Phase5 bao phủ TC09/10 và phần cancel/read: QR unknown/tampered/used/wrong station/expiry boundary/user locked/role changed/disabled device; schema nghiêm; idempotent delivery/consume; RFID reuse/revoke/active swap; reserve quote/ba holds; mọi eligibility fail, rollback audit failure; TTL−1µs/đúng hạn/+1µs; không release payment/outbox/command; quyền/ownership; timeout cũ không giải phóng reservation mới; BMS ordering được áp lại khi chọn pin.

Race tests có schema riêng từng ca và kết nối commit thật: cùng QR hai key chỉ một consume; cùng key cùng swap; hai khách tranh một pin; reserve với bảo trì/quarantine/telemetry; cancel với expiration. **test_CT02_double_booking_across_two_backend_processes** khởi hai Uvicorn process trên8005/8006, hai Customer reserve đồng thời, xác nhận chỉ ba hold. Không chỉ chạy hai thread với mutex ứng dụng. Các process test được dừng trong finally, schema giữ lại.

Lỗi tìm thấy và sửa trong lượt triển khai: wrong-station QR bị kiểm online trước scope trả503, đã chuyển scope trước online và giữ expectation403. Full regression ban đầu phát hiện ba assertion mới giả định list UUID đầu là phiên mới/lịch sử trống, trong khi test cũ giữ một row lịch sử: sửa kiểm đúng ID/membership và so nguyên lịch sử trước/sau rollback, không xóa fixture hay đổi quy tắc thành công. Các lượt đầu 41/42, rồi225/227,226/227; lượt cuối227/227 đạt. Hai warnings deprecation Starlette/httpx và validate_spec hiện hữu, không nâng library để che cảnh báo.

## 10. E2E/Browser và giới hạn bằng chứng

E2E schema **phase5_e2e_4ffedbef8c**: hai API8003/8004, worker và hai simulator, một pin được Technician activate cùng hai ngăn restore bằng evidence. QR race qua hai Backend, retry reserve qua process khác, đúng ba holds/không payment-outbox-command; worker restart trong lúc giữ và chờ **TTL thật120s** tới CANCELLED/release; RFID dùng hai phiên liên tiếp, revoke rồi bị từ chối; fingerprints tám bảng demo chính trước/sau khớp. Hồi quy IoT dùng schema **phase4_e2e_a4228faac4**, kiểm lại ACK/NACK/timeout/offline/reboot/hot không auto-restore.

Browser dùng Vite5174 với DEV_API_TARGET trỏ API8003, không phải demo chính: đăng nhập Customer, cấp QR và thấy hình QR, adapter xác thực thành VERIFIED, bấm giữ thành RESERVED, bấm hủy thành CANCELLED. Admin liên kết rồi revoke RFID; Technician không có menu truy cập lịch sử. DB xác nhận ba hold được release, RFID revoked,0 payment/outbox/command. Đã logout ba vai trò. Ảnh chỉ chụp sau khi QR đã được tiêu thụ/ẩn, không chụp token/QR đang còn hiệu lực. Các server Browser/E2E đã dừng; data/ledger giữ lại.

**Not Run/giới hạn:** cầu clipboard CUA trả chuỗi rỗng dù UI copy promise thành công; adapter test dùng đúng idempotent replay của challenge do Browser tạo để nhận token rồi verify. Không tuyên bố kiểm chứng clipboard hệ điều hành hoặc decode camera. Camera/RFID thật, nhập getpass terminal tương tác, toàn bộ Browser negative/concurrency scenarios, per-QR revocation không có trong contract, payment/custody/recovery đầy đủ chưa chạy/ngoài phạm vi. Browser UI có Passed phần cụ thể trên, không tuyên bố mọi E2E giao diện Passed.

## 11. Khởi động và demo

Từ root, terminal riêng, giữ .env và ledger hiện có. Grants Phase5 đã áp dụng; khi lấy source mới dùng `tools/dev.ps1 migrate` chỉ upgrade head+grants hiện có, không DDL reset. Sau npm lockfile thay đổi, cài frontend dependencies bằng npm ci trong workspace nếu máy chưa có qrcode; không cần làm lại venv.

```powershell
.\tools\dev.ps1 database
.\tools\dev.ps1 migrate
.\tools\dev.ps1 backend
.\tools\dev.ps1 worker
.\tools\dev.ps1 frontend
# Chỉ chủ động bật nguồn quan sát mô phỏng khi muốn demo và hiểu dữ liệu sẽ đổi:
.\tools\dev.ps1 simulator
```

Nếu Backend/worker đang chạy bản Phase4 từ trước, Ctrl+C đúng terminal rồi chạy lại để đọc code Phase5; không chạy trùng port8000/5173. Không tự kill tiến trình người dùng trong lượt triển khai.

Demo Customer: admin/customer/technician dùng password .env local, không có password công khai. Customer → **QR/RFID và giữ tài nguyên** → chọn S01 → **Cấp QR một lần**. Tại terminal tương tác local, bộ đọc đúng trạm nhập token sao chép (không dán vào chat/log):

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'services/backend'
.\.venv\Scripts\python.exe -m simulators.device.authenticate --station S01 --method QR
# RFID đã được Admin liên kết:
.\.venv\Scripts\python.exe -m simulators.device.authenticate --station S01 --method RFID
# Mất response: lặp đúng credential + --request-id <UUID đã in trước đó>
```

Sau VERIFIED, web tự thấy phiên, bấm **Giữ pin và hai ngăn**. Demo seed mặc định vẫn chưa phục vụ: muốn giữ được phải có snapshot/BMS mới và Technician activate/restore theo Phase3; không bật toàn bộ pin bằng seed. Không đủ điều kiện sẽ CANCELLED thay vì reservation giả. RESERVED hiển thị9.000VND và thời hạn; bấm **Hủy trước thanh toán** hoặc chờ worker hết hạn. Đây chưa thanh toán hoặc đổi pin.

Admin dùng cùng menu để nhập giá trị RFID mô phỏng cho Customer, giữ ID credential được trả, revoke bằng ID khi cần. Frontend không nhận Device-Key; việc đọc RFID thực hiện qua adapter device bên trên. Không cấp quyền Technician đọc lịch sử Customer.

Tái kiểm an toàn, chỉ dùng schema test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=.cache/phase5-recheck --junitxml=docs/PHASE5_REGRESSION.xml
npm.cmd --prefix apps/web run build
.\.venv\Scripts\python.exe tools/validate_contracts.py docs/PHASE5_CONTRACT_VALIDATION.json
.\.venv\Scripts\python.exe tools/smoke_phase5.py
# Giữ môi trường tách biệt cho Browser/HTTP:
.\.venv\Scripts\python.exe tools/smoke_phase5.py --serve
# Dùng đúng đường dẫn fixture được lần chạy đó tạo (không phải .env/demo):
.\.venv\Scripts\python.exe tools/smoke_phase5.py --http-fixture .cache/phase5_e2e_<id>/connection.json
```

Helper E2E cần8003/8004 rảnh; pytest two-process test dùng8005/8006. Browser dùng `$env:DEV_API_TARGET='http://127.0.0.1:8003'` rồi npm dev -- --port5174; biến DEV_API_TARGET chỉ ở Vite server, không public secret. --serve dừng bằng file STOP trong thư mục .cache của chính fixture. Không gửi thêm request tranh seq vào simulator demo chính để thử lỗi.

Lưu ý probe Phase4 cũ ghi docs/PHASE4_ACCEPTANCE/LATE_TELEMETRY_FINDING.json; nếu người dùng đã dọn thư mục thì tạo parent trước khi chạy hoặc dùng wrapper tương tự lượt này. Không thay source probe. Trong lượt triển khai đã lưu kết quả mới thành PHASE5_BMS_GUARD_RESULTS.json và bảo toàn report cũ nếu có; không giả artifact trước đây vẫn tồn tại.

## 12. File, bảo mật và dung lượng

Source mới: application/reservations.py, api/reservations.py, apps/web/src/Reservations.tsx, simulators/device/authenticate.py, tests/test_phase5.py, tools/smoke_phase5.py. Source/config sửa: app/main.py, workers/device.py (hook expiry), tools/provision_database.py, tools/dev.ps1, tests/conftest.py (schema/report Phase5), test_phase1.py (chỉ thêm tám endpoint approved), web/main.tsx/vite.config.ts/package.json/package-lock.json; README/plan/status. Không sửa các test Phase2/3/4, acceptance hoặc BMS ordering cũ, migration, seed, Compose hoặc baseline.

Bằng chứng nên giữ: PHASE5_REGRESSION.xml, TEST_RESULTS.xml, TEST_ENVIRONMENT.json, BMS_GUARD_RESULTS.json, E2E_RESULTS.json, IOT_REGRESSION_RESULTS.json, HTTP_SMOKE_RESULTS.json, CONTRACT_VALIDATION.json, VERIFICATION_SUMMARY.json, DISK_USAGE.json, BROWSER_RESULTS.json và các ảnh/text Browser. Nội dung không có password/token/key thật; ảnh QR còn hiệu lực không được lưu/commit.

Local không commit: .cache/phase5_e2e_4ffedbef8c chứa logs và connection.json có **test credentials**, browser-read.json là đầu vào adapter local; không chia sẻ/commit chúng. .local/phase5_e2e_4ffedbef8c và .local/phase4_e2e_a4228faac4 là ledger bền vững, giữ cùng schema DB. Mỗi race/full test có schema phase5_test_* riêng; không DROP để làm test đạt. PHASE5_TEST_ENVIRONMENT ghi schema test cuối được tạo, không có nghĩa toàn bộ lượt chỉ dùng một schema.

Lúc đo: .venv95.84MiB (không đổi), node_modules60.77MiB (~tăng4.38MiB do QR và types), dist0.28MiB, .cache148.20MiB, .local13.47MiB, docs0.92MiB trước báo cáo cuối. PostgreSQL data241MiB theo du (không phải VHDX), gồm nhiều schema/bằng chứng kiểm thử được giữ và ledger tăng do simulator chạy trong quá trình Browser. Không tải image/cài phần mềm hệ thống mới. Không tự dọn.

dist/__pycache__/.pytest_cache và npm/pip cache tái tạo được; logs/temp .cache chỉ cân nhắc dọn sau lưu bằng chứng. **Không coi .local, DB/volume/schema hoặc .git là cache.** .env/secret local giữ ngoài Git. Mục tiêu commit chỉ source/tests/config mẫu/tài liệu tiến độ và bằng chứng an toàn; không push.

## Bảng nghiệm thu sơ bộ Phase5

| Hạng mục | Trạng thái |
| --- | --- |
| QR entropy, một lần, replay/TTL/scope, consume+VERIFIED atomic | Passed |
| RFID reuse/revoke, active swap ngăn đọc lặp tạo thêm phiên | Passed |
| Reservation ba tài nguyên, quote, eligibility BMS, không double booking | Passed |
| Races với maintenance/BMS/state, cancel/expiry, hai Backend process | Passed |
| TTL120s thật và worker restart; retry không hồi sinh reservation | Passed |
| 175 regression cũ +52 Phase5, HTTP28, E2E8+IoT8, build/contracts | Passed |
| Browser QR/VERIFIED/reserve/cancel, Admin RFID, Technician menu | Passed phần mô tả |
| Clipboard OS/camera/RFID thật, full Browser scenarios, per-QR revoke | Not Run / không thuộc contract đã triển khai |
| Payment, bàn giao custody/full swap/recovery | Chưa triển khai; Phase6–8 |

Không còn blocker bắt buộc trong phạm vi API/BR Phase5 đã triển khai và kiểm chứng. Commit dự kiến `feat: implement QR RFID authentication and reservation` sau rà soát diff/secret; hash xem git log khi tạo. Dừng sau Phase5, không tự push hoặc làm Phase6.
