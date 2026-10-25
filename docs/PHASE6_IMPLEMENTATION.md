# Phase 6 — Mock Payment & Payment Management

Ngày 25/10/2026, Asia/Bangkok. Base `29f4352` đã có trên main/origin lúc bắt đầu. Báo cáo triển khai mô phỏng F6; không có thanh toán thật hoặc workflow đổi pin Phase7. Các kết quả cuối và commit được ghi ở cuối báo cáo sau khi hoàn tất kiểm chứng.

## 1. Truy vết và API

Nguồn: AGENTS, START_HERE, CODEX_HANDOFF, approved decisions/config QD01–09, baseline DOCX/các CSV truy vết/test case, INVARIANTS, ERD-02/03/04, AD-02a/04a/04b, SM-03a/03b/04 và OpenAPI nguyên bản. Không sửa baseline. F6 chính thức: **FR14/UC12/TC14** thu phí; **FR15/UC13/TC15** đối soát. Tích hợp FR10/UC10 reservation, FR13/UC11 đọc đúng chủ. BR07 bắt buộc UNKNOWN/query cùng intent; BR01/02/10/11 giữ eligibility và tài nguyên; BR06 ACK không là bằng chứng. BR08/09 refund/custody review đầy đủ thuộc phase sau.

| Method/path | Quyền và hành vi |
| --- | --- |
| POST /v1/swaps/{swap_id}/consent |Customer sở hữu; Idempotency-Key UUID; body expected_version, quoted_amount_minor, currency=VND, accept=true;202 SwapTransactions |
| GET /v1/swaps/{swap_id}/payment |Customer đúng chủ hoặc Admin;200 Payments,404 nếu chưa có/khác chủ; Technician403 |
| POST /v1/payments/{payment_id}/reconcile |Admin; key UUID; ReasonAction expected_version của Payment và reason;202 Payments, chỉ schedule query cùng provider_key |
| POST /v1/payment-events |X-Payment-Key riêng, không UserBearer; PaymentCallback;202 accepted/duplicate; chưa có nghĩa đã apply |
| POST /mock/v1/charges |Tiến trình provider riêng; X-Service-Key + Idempotency-Key=provider_key;202 ProviderResult |
| GET /mock/v1/charges/{provider_key} |X-Service-Key;200 ProviderResult, bao gồm NOT_FOUND chưa phải FAILED |

Không thêm endpoint chọn outcome công khai. Không triển khai refund API. Body/response lấy nguyên schema OpenAPI. API lỗi dùng Error chuẩn; validation422, chưa xác thực401, trái role403, khác chủ/không tồn tại404, state/version/key/quote conflict409. Các mã triển khai: VALIDATION_ERROR, AUTH_REQUIRED, FORBIDDEN, RESOURCE_NOT_FOUND, VERSION_CONFLICT, STATE_CONFLICT, IDEMPOTENCY_CONFLICT, QUOTE_MISMATCH, RESERVATION_EXPIRED, RESOURCE_UNAVAILABLE, PAYMENT_RESULT_MISMATCH, EVENT_ID_CONFLICT. Retry receipt lịch sử không chứng minh trạng thái hiện tại; luôn GET swap/payment.

## 2. Fee, consent và transaction

Phí đọc từ policy_snapshot bất biến đã tạo từ approved config: fee_minor9000/currencyVND (không nhân100). Amount client chỉ là xác nhận bằng quote. Backend kiểm quote/policy, customer ACTIVE, TTL120s và pin+hai ngăn còn hợp lệ. Kiểm ba holds, station online, service_state, BMS đã xác minh/fresh và guard door evidence P5-A01 cho cả hai ngăn; không xem IN_SERVICE tự đủ điều kiện.

Station advisory lock và thứ tự user→swap→ngăn UUID→pin UUID dùng lại Phase5. Consent lock rồi kiểm version/state/TTL; tạo **một** payments và **một** CHARGE outbox, consented_at/AWAITING_PAYMENT, audit và HTTP idempotency cùng transaction. TTL lấy sau lock, kiểm lại trước commit. Unique payments.swap_id, provider_key, outbox.dedup_key và locks bảo vệ khác key/hai process. Rollback không để Payment/outbox/consent/audit/idempotency một phần.

## 3. Provider/ledger và worker

`simulators/payment/main.py` chạy riêng ở127.0.0.1:8001. SQLite ledger dưới `.local/payment/ledger.sqlite3`, WAL, BEGIN IMMEDIATE, unique provider_key/payment_id/swap_id; body hash cùng key khác body409. Ghi receipt trước response, giữ nguyên qua restart. Tình huống chọn lúc khởi động: success, failure, timeout, lost-response (đã ghi SUCCEEDED nhưng trả503), delayed (PENDING rồi query SUCCEEDED). Đây là dữ liệu mô phỏng, không bằng chứng thiết bị hay tiền thật.

`app.workers.payment` đọc callback inbox và outbox. Claim trong transaction: CREATED→PENDING, attempts/next_attempt_at tăng; **commit trước HTTP**. Gọi provider ngoài DB lock. Worker sau crash hoặc lần tiếp theo chỉ GET cùng key, không phát POST charge lần thứ hai. Trường hợp crash sau claim nhưng trước dispatch có thể mãi NOT_FOUND/UNKNOWN; bảo thủ giữ tài nguyên, không tự suy ra thất bại hoặc tạo intent khác. Query/timeout theo approved30s, HTTP timeout5s là giới hạn truyền thông cục bộ. HTTP lỗi/JSON/schema sai/không khớp key/amount/currency không được ghi success.

Callback sender tùy chọn `simulators.payment.callbacks` đọc ledger đã commit, gửi terminal result qua HTTP loopback với X-Payment-Key. UUID event xác định từ key+result; chỉ đánh dấu delivered trong bảng callback_deliveries sau202 accepted. Mất response: retry đúng event; restart không gửi effect mới. Không giữ khóa SQLite hay PostgreSQL qua HTTP. Backend xác thực nguồn/mã/tiền/currency/reference trước inbox, cùng ID khác hash409; worker apply+processed_at+audit nguyên tử. Browser không có key này. Provider/Backend key riêng, không có API đổi kết quả dành người dùng.

## 4. State và Reservation

Payment SM-04: CREATED→PENDING hoặc UNKNOWN; PENDING→SUCCEEDED/FAILED/UNKNOWN; UNKNOWN chỉ được giải bằng kết quả cuối xác minh SUCCEEDED/FAILED. Callback có thể thắng response; record bước PENDING cùng transaction trước kết quả cuối. Late PENDING không phục hồi UNKNOWN hoặc ghi đè terminal. Callback trùng không cập nhật lại version/thu thêm. Kết quả terminal mâu thuẫn giữ kết quả terminal đã ghi, audit và mở recovery case tối thiểu; không tạo charge khác.

| Kết quả | Swap/tài nguyên |
| --- | --- |
| CREATED/PENDING |AWAITING_PAYMENT, giữ3holds; cancel trước thu không còn hợp lệ |
| UNKNOWN |REVIEW_REQUIRED, giữ3holds; Admin query cùng key, NOT_FOUND không giải phóng |
| SUCCEEDED, evidence còn hợp lệ/chưa physical |AWAITING_RETURN; **không tạo OPEN_RETURN/OPEN_SUPPLY** |
| SUCCEEDED, cửa/BMS/service/evidence đổi/cũ |Payment SUCCEEDED; REVIEW_REQUIRED, giữholds; mở case tối thiểu |
| FAILED xác định, không command/return/pickup |CANCELLED, release đúng holds của phiên, closed_at/audit nguyên tử |
| FAILED nhưng đã có khả năng tác động |REVIEW_REQUIRED, giữholds |

Cancel/expiration Phase5 chỉ release VERIFIED/RESERVED chưa payment/outbox/consent. Consent cạnh tranh cancel/expiry cùng station/user/swap locks: hoặc cancel/expire thắng với0payment/0holds, hoặc consent thắng với1payment/3holds. Sau consent, reservation TTL cũ không được tự release tài nguyên, kể cả Payment timeout hoặc worker restart. Settlement cạnh tranh cancel/expiry không tạo trạng thái mâu thuẫn. Phiên bản/row locks/unique constraints dùng PostgreSQL, không mutex in-memory.

Recovery case chỉ là hook OPEN/UNKNOWN theo bảng đã có; không giải quyết custody, refund, đóng bù trừ hoặc workflow Phase8. Kết quả mâu thuẫn sau CANCELLED không tự hồi sinh state ngoài SM; giữ terminal và mở case để người có quyền xử lý sau. Không sửa/hủy reservation lịch sử từ P5-A01 trong demo.

## 5. Database, cấu hình và Frontend

Không migration cấu trúc mới; head0002_user_approval. Không chạy schema.sql lại. Bổ sung grants INSERT/UPDATE payments/payment_events/outbox_messages và INSERT recovery_cases; không cấp DELETE/audit UPDATE. Test migration từ rỗng/upgrade lặp và seed idempotent dùng fixture cũ. Không thay seed, không chèn Payment vào demo. Ledger callback_deliveries là cấu trúc local provider, CREATE IF NOT EXISTS bảo toàn charges cũ.

Không thêm dependency. Dùng httpx/sqlite3/FastAPI/SQLAlchemy đã có. `tools/init_payment_env.py` chỉ append trường thiếu trong .env, không ghi đè; đã bổ sung5 trường Payment trước gián đoạn. .env tiếp tục ignore. PAYMENT_CALLBACK_URL có mặc định loopback hoặc cấu hình mẫu. Không thay PATH/cài hệ thống/image.

Trong menu **QR/RFID và giữ tài nguyên**, mỗi phiên RESERVED có phần **Thanh toán mô phỏng · không dùng tiền thật**. Customer xác nhận giá Backend bằng nút **Đồng ý phí và thanh toán mô phỏng**. Nút disable khi gửi, retry giữ cùng key/body trong tab; sau response/poll hiển thị Payment ID/state/receipt. Loading/error/FAILED/UNKNOWN/SUCCEEDED và phí rõ ràng; Admin có **Đối soát cùng khoản thu** khi PENDING/UNKNOWN. Technician không được truy cập dữ liệu Payment của khách. Token/key không vào bundle. UI hiển thị SUCCEEDED chưa đồng nghĩa giao pin/COMPLETED.

## 6. Công việc qua gián đoạn và bằng chứng

Trước gián đoạn: consent/intent/outbox/verified result, provider ledger, worker, UI,51 F6 tests và regression321 Passed; validators/build/pip check Passed. Lượt TARGETED đầu5Failed/37Passed do mock trả422 cho request không key trước khi auth; đã sửa dependency xác thực tại source, không đổi expected. Sau đó TARGETED_FINAL51Passed. Sau regression321 bổ sung explicit boolean consent/null refund validation, hai ca key non-ASCII và kiểm callback/recovery bổ sung: **không suy ra số cuối từ321**.

E2E đầu lỗi import `simulators`: Python chạy file tools chỉ có tools/ trên sys.path; sửa chính script bằng ROOT+services/backend+tests, giữ cwd=ROOT/PYTHONPATH ở child. REAL_E2E_RETRY sau đó8Passed (ba kịch bản và fingerprint demo). Sau resume, PostgreSQL timeout vì Docker Desktop tắt; khởi động Docker Desktop hiện có, container cũ trở lại, không reset/create volume. Lượt callback E2E gặp listener đóng chậm giữa kịch bản trên Windows; thêm chờ cổng tối đa15s, không kill tiến trình lạ. Giữ mọi log lỗi phát triển trong docs/PHASE6_TESTS (log bị ignore); chúng không được tính Passed.

Lượt sau resume RELEASE_REGRESSION330Passed, rồi rà soát kiểu JSON phát hiện chuỗi/bool có thể bị ép thành số. Đã thêm validator tại source và hai test giữ đúng integer JSON (không chấp nhận string/bool, vẫn cho số nguyên biểu diễn dạng số). **FINAL_REGRESSION332Passed** là lượt cuối dùng nghiệm thu, không cộng các lượt321/330/332. Browser không được suy ra từ API/build.

## 7. Chạy và demo

Tại workspace, giữ .env và DB/ledger:

```powershell
.\.venv\Scripts\python.exe tools/init_payment_env.py
.\tools\dev.ps1 migrate
# Mỗi tiến trình một terminal:
.\tools\dev.ps1 backend
.\tools\dev.ps1 worker
.\tools\dev.ps1 payment
.\tools\dev.ps1 payment-worker
.\tools\dev.ps1 payment-callbacks   # tùy chọn, callback HTTP thật
.\tools\dev.ps1 frontend
```

Không bật simulator demo chỉ để thử lỗi. Nếu demo đã có đủ evidence mô phỏng hợp lệ, Customer tạo QR, adapter thiết bị xác thực, giữ pin+hai ngăn, xem quote và xác nhận phí. GET Payment/poll để xem state. Admin đối soát UNKNOWN/PENDING. Không dùng dữ liệu BMS seed chưa xác minh để ép reserve. Các tài khoản demo admin/customer/technician; mật khẩu chỉ lấy từ .env local, không ghi trong báo cáo.

Các kịch bản success/failure/lost-response/timeout nên chạy **trong schema test**:

```powershell
$env:P5_EVIDENCE_DIR='docs/PHASE6_TESTS'
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_F6 tests/test_phase6.py
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_ALL
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_E2E --script tools/smoke_phase6.py
.\.venv\Scripts\python.exe tools/validate_contracts.py docs/PHASE6_TESTS/RECHECK_CONTRACTS.json
npm.cmd --prefix apps/web run build
```

Chọn label mới, không chạy nhiều runner cùng lúc do helper chung ghi report trung gian. E2E kiểm cổng8010/8011/8012, chỉ dừng các process tự tạo; `--serve` giữ fixture success cho Browser, dừng bằng file STOP trong thư mục .cache được log chỉ rõ. Không reset login counters demo. Provider query ledger bền vững chứng minh một charge; callback ledger chứng minh một delivery identity. Success/failure/UNKNOWN và retry trong F6 tests dùng PostgreSQL riêng, không SQLite thay thế Backend DB.

## 8. File và giới hạn

Source mới: app/api/payments.py, application/payments.py, workers/payment.py; simulators/payment/{__init__,main,callbacks}.py; apps/web/src/Payment.tsx. Tích hợp: main.py, Reservations.tsx, provision_database.py, dev.ps1, .env.example. Test/tool mới: tests/test_phase6.py, tools/smoke_phase6.py, tools/init_payment_env.py. test_phase1.py chỉ mở allowlist endpoint F6 đã triển khai, vẫn đối chiếu role/operation/schema theo baseline; không nới guard nghiệp vụ cũ.

Giữ source/test/runner/docs cùng bằng chứng cuối. docs/PHASE6_TESTS chứa cả lượt đầu lỗi và output trung gian; chưa tự dọn. PHASE4_ACCEPTANCE output do regression cũ tạo, PHASE5_TEST_ENVIRONMENT và bốn finding P5 được runner bảo toàn byte sau mỗi lượt. Cache .cache có connection.json chứa secret test: không commit/chia sẻ. `.local` chứa ledger bền vững, phải bảo toàn cùng DB/volume; không coi là cache.

Giới hạn: chưa refund/full recovery/physical swap; chưa stress diện rộng hay bảo đảm phần cứng thật. Claim đã commit nhưng request chưa gửi là trạng thái UNKNOWN cần đối soát, không tự thu lại. NOT_FOUND không có bằng chứng phủ định cuối. Clock/timestamp guards Phase4/5 giữ nguyên. Case OPEN chỉ chuẩn bị cho Phase8, không tự ra quyết định tài sản. Điều khiển outcome chỉ qua tiến trình mock/fixture test, không API công khai.

## 9. Kết quả cuối và bảng nghiệm thu sơ bộ

JUnit `docs/PHASE6_TESTS/FINAL_REGRESSION.xml`: **332 Passed,0 Failed,0 Errors,0 Skipped**,275.89s. Hai warning deprecation TestClient/httpx và openapi validator, không thay dependency để che warning.

| File/nhóm pytest | Passed |
| --- | ---: |
| test_phase1.py |18 |
| test_phase2.py |37 |
| test_phase3.py |48 |
| test_phase4.py |44 |
| test_phase4_acceptance.py |7 |
| test_phase4_bms_ordering.py |21 |
| test_phase5.py |52 |
| test_phase5_acceptance.py |18 |
| test_phase5_door_ordering.py |25 |
| test_phase6.py |62 |

F6 cases bao phủ consent/quote/TTL±1µs, accept phải boolean true, từ chối số dưới dạng string/bool, extra/null fields, khóa quyền/session/khác chủ, invalid resources/evidence, callback sai nguồn/mã/tiền/reference và refund ngoài phạm vi;10callback trùng; late terminal conflict; UNKNOWN/NOT_FOUND không thu lại; ledger restart/lost response; callback response loss; rollback/audit/inbox; hai request consent/worker và payment cạnh tranh cancel/expiration trên PostgreSQL thật. Test snapshot/BMS cũ giữ nguyên các expected result đã phát hiện blocker.

| Cổng nghiệm thu | Bằng chứng / kết quả |
| --- | --- |
| TC14 thu phí sau consent, callback xác minh |Passed qua test_TC14_* và E2E |
| TC15/CT03 UNKNOWN/query/10duplicate |Passed qua test_TC15_*, uncertain_query, pending_timeout, callback_delivery và E2E |
| PostgreSQL chống double intent/charge |Passed: khác/cùng key, hai Backend process trong E2E, unique constraints và ledger một charge |
| Payment–Cancel–Expiration / rollback |Passed: tests cạnh tranh, rollback giữ consent/Payment/audit/inbox nguyên tử |
| Kế thừa Phase1–5 |270/270 Passed trong332, không dùng số cũ thay regression |
| Migration/seed |Passed trong fixture migration rỗng/upgrade lặp/seed regression; không migration mới/downgrade demo |
| OpenAPI/JSON Schema/SQL/baseline |Passed, RELEASE_CONTRACTS.json;278SQLstatements, baseline hash giữ nguyên |
| TypeScript/Vite/pip/npm |Passed;82modules, bundle285.66kB/gzip90.92kB; pip check không lỗi, npm ls đủ dependency |
| Browser phần đọc/role |3 nhóm Passed: Customer thấy9.000VND/SUCCEEDED/receipt; Admin xem cùng intent, không thu lại; Technician không có menu Payment |
| Browser thao tác đầy đủ |3 nhóm Not Run: bấm consent→success, UI FAILED/UNKNOWN, Admin bấm reconcile; không gọi toàn bộ Browser E2E Passed |

Browser dùng schema `phase5_test_` riêng của E2E, Vite5174→Backend8010, không dùng tài khoản demo. Bằng chứng BROWSER_RESULTS.json và ba PNG; đã logout/đóng tab/dừng Vite test, E2E chỉ dừng các process tự tạo. Không reset counters. Browser nhìn thấy offline sau khi fixture evidence cũ là đúng; UI không tuyên bố đã mở cửa hoặc hoàn tất đổi pin.

Các kết quả E2E/HTTP cuối được cập nhật bên dưới sau khi tiến trình hoàn tất. Commit chỉ stage source/test/config mẫu/docs và bằng chứng cuối được chọn; `.env`, .cache, .local, thư viện, dist và report trung gian không stage. Không push/Phase7.

| Kiểm thử tiến trình thật cuối | Kết quả |
| --- | --- |
| FINAL_PAYMENT_E2E / E2E_FINAL_RESULTS.json |**12 Passed**, hai API8010/8011, provider8012, worker và callback sender riêng; success do callback trước query, failure, mất response→UNKNOWN→restart/query cùng key, SUCCEEDED nhưng evidence cũ→REVIEW_REQUIRED; SQL giữ đúng holds/outbox/inbox, SQLite đúng1charge |
| REGRESSION_E2E_PHASE5 |**8 Passed**, QR race hai API, reservation retry, TTL thật120s và worker restart |
| HTTP trong fixture Phase5 |**28 Passed**; phân biệt với các API F6 kiểm trực tiếp qua12 nhóm E2E ở trên, không gọi28check này là28check Payment |
| REGRESSION_IOT |**8 Passed**, hai simulator, heartbeat/offline, ACK/NACK/timeout, restart ledger; ACK không đổi cửa/custody |

Tất cả E2E kiểm fingerprint demo không đổi; schema/ledger test giữ lại. F6 success scenario provider trảPENDING rồi callback xác thực qua HTTP làm Payment SUCCEEDED trước query đầu tiên, attempts outbox vẫn1. Các callback trùng/restart không tạo event/charge mới. Tiến trình test đã dừng qua finally/STOP do chính helper quản lý; Docker/DB của người dùng vẫn chạy. Không đánh dấu các lượt lỗi import, Docker timeout hoặc port occupied ban đầu là Passed.

Dung lượng toàn thư mục đo cuối (không phải toàn bộ phát sinh mới): `.cache`150.47MiB, `.local`34.07MiB, `.venv`95.84MiB, `apps/web/node_modules`60.77MiB, dist0.28MiB, bằng chứng F6 khoảng0.31MiB. Không tải dependency/image mới. Dung lượng PostgreSQL/VHDX chưa đo; các schema test đều được giữ, không reset hoặc prune.

Commit chọn giữ FINAL_REGRESSION.xml, E2E_FINAL_RESULTS.json, RELEASE_CONTRACTS.json, BROWSER_RESULTS.json và JSON hồi quy E2E/HTTP cuối. Log/XML/JSON trung gian và ba PNG Browser để ngoài commit, giữ trên đĩa cho người dùng quyết định sau nghiệm thu. Có thể dọn dist/pytest cache sau; với .cache chỉ dọn thư mục test xác định rõ sau khi lưu bằng chứng/dừng tiến trình. Không dọn `.local`, DB, .env hoặc hồ sơ thiết kế.

**Kết luận sơ bộ: F6 đủ điều kiện kỹ thuật để nghiệm thu độc lập.** Không còn blocker được phát hiện trong các phép kiểm đã chạy. Browser chỉ Passed phần đọc/role, ba nhóm tương tác còn Not Run; refund/đối soát custody đầy đủ và đổi pin vật lý chưa triển khai. Bản bàn giao dùng commit `feat: implement mock payment management`; hash được báo sau khi Git tạo commit. Dừng sau Phase6, không push/Phase7.

| Nghiệm thu sơ bộ F6 | Trạng thái cuối |
| --- | --- |
| Thu phí/consent/Payment State Machine |Passed |
| Callback/query/idempotency/chống double charge |Passed |
| PostgreSQL atomicity và Payment–Reservation concurrency |Passed |
| Unit/integration+regression |332Passed/0Failed/0Errors/0Skipped |
| Payment E2E / Phase5 E2E / IoT E2E / HTTP smoke |12 /8 /8 /28Passed, không cộng với pytest |
| Validators/build/dependencies |Passed |
| Browser |3 nhóm đọc/role Passed;3 nhóm thao tác Not Run |
| Điều kiện bàn giao |Đủ để nghiệm thu độc lập; chưa triển khai Phase7 |
