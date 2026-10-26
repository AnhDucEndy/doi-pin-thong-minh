# Nghiệm thu độc lập Phase 6 — Mock Payment

Bắt đầu 25/10/2026; hoàn tất báo cáo tiếp tục ngày 26/10/2026 (Asia/Bangkok). Đối tượng: `81a8acd feat: implement mock payment management`, `main` ahead `origin/main` một commit. Lượt này chỉ review, thêm probe và báo cáo; không sửa source nghiệp vụ, baseline, commit, push hoặc Phase 7.

**Kết luận: Phase 6 CHƯA đạt nghiệm thu, CHƯA đủ điều kiện chuyển Phase 7.** Phát hiện P6-A01 và P6-A02 (hai Blocker nghiệm thu độc lập). Bộ regression cũ vẫn Passed không phủ định các lỗi mới.

## 1. Nguồn chuẩn và phạm vi

Đối chiếu AGENTS, README, IMPLEMENTATION_PLAN/STATUS, PHASE6_IMPLEMENTATION, PHASE5_IMPLEMENTATION/ACCEPTANCE/P5_A01_FIX, PHASE4_IMPLEMENTATION/BMS_FIX; START_HERE, CODEX_HANDOFF, baseline DOCX/CSV, approved QD/config, OpenAPI, SM-03a/SM-04, AD-04a/04b, ERD-02/03, schema.sql, INVARIANTS và handoff/tests.json. `docs/PHASE4_ACCEPTANCE.md` không còn trên đĩa; không khôi phục hoặc giả định đã đọc file không tồn tại. Bằng chứng lịch sử Phase4 còn trong BMS_FIX và test đã commit.

- F6 chính thức: **FR14 / UC12 / TC14**, thu sau consent; **FR15 / UC13 / TC15**, đối soát UNKNOWN, callback trùng không thu lại.
- BR07: timeout/mâu thuẫn không phải FAILED; query cùng provider key. BR02/10/11 và FR10/UC10: điều kiện tài nguyên/cửa/BMS còn hợp lệ. BR06: ACK không là bàn giao vật lý. BR04/08/09: tách thanh toán với bàn giao/khôi phục; refund và full swap không được triển khai trong lượt này.
- CT01/02/03/09/10/11: cạnh tranh, callback/retry, ordering và quyền. Không tự gán TC mới cho probe bổ sung.
- QD03/07: phí 9.000 VND, telemetry stale 15 giây, payment timeout 30 giây, reservation TTL 120 giây; ngưỡng SOC/SOH ≥80%, T≤40°C là giả định mô phỏng.

## 2. Kết quả chạy mới, tách khỏi lịch sử

| Bộ kiểm tra | Kết quả mới | Bằng chứng |
| --- | --- | --- |
| Regression đã có Phase1–6 | **332 Passed, 0 Failed**, 251,40 giây | `PHASE6_ACCEPTANCE/REGRESSION.xml` và log |
| Probe độc lập cuối | **10 Passed, 3 Failed**, 53,28 giây | `PHASE6_ACCEPTANCE/PROBES_FINAL.xml` và log |
| OpenAPI / approved JSON Schema / SQL / baseline hashes | Passed; 278 SQL statements | `PHASE6_ACCEPTANCE/CONTRACTS.json` |
| TypeScript `tsc --noEmit` / Vite build | Passed; 82 modules, JS285,66kB/gzip90,92kB | Lệnh `npm.cmd --prefix apps/web run build` đã chạy |
| Payment real-process E2E | **12 Passed** | `PHASE6_ACCEPTANCE/E2E_RESULTS.json` và `REAL_PAYMENT_E2E.log` |
| Browser mới trong lượt này | **Not Run** | Không lấy ba nhóm Browser Passed lịch sử làm kết quả mới |

332 regression gồm: Phase1 18, Phase2 37, Phase3 48, Phase4 44, P4 acceptance7, BMS ordering21, Phase5 52, P5 acceptance18, door ordering25, Phase6 62. Tổng các **test pytest khác nhau** trong hai lượt cuối: **342 Passed / 3 Failed**, không phải một invocation 345 test, không cộng lại các lần chạy probe.

Lượt `INDEPENDENT_PROBES` đầu có **11 setup Errors** do sandbox chặn localhost5432 (Permission denied), chưa chạy nghiệp vụ. Sau khi chạy ngoài sandbox, `INDEPENDENT_PROBES_RETRY` có8Passed/3Failed; bổ sung hai race test rồi chạy `PROBES_FINAL` có10Passed/3Failed. Giữ cả log lỗi môi trường; không tính setup errors thành lỗi Payment hoặc cộng các lượt vào số Passed cuối.

## 3. P6-A01 — Blocker: dùng mốc kiểm tra độ mới đã cũ trong transaction

### Điều kiện và cách tái hiện

Hai test giữ nguyên expected theo BR02 và SM-03a:

- `test_freshness_rechecked_after_slow_resource_read[consent]`
- `test_freshness_rechecked_after_slow_resource_read[settlement]`

Fixture PostgreSQL riêng tạo QR, xác thực, reserve bằng snapshot/BMS được worker chấp nhận thật. Không sửa timestamp, không tạo accepted evidence giả. Probe chỉ chèn **độ trễ thực 16 giây** trước lần đọc compartment đầu tiên trong `resources_valid`, mô phỏng thread/I/O bị chậm sau khi đã lấy mốc `now`. Clock hệ thống chạy thật; reservation120s vẫn còn hạn, nhưng BMS/cửa15s đã hết độ mới. Đây là fault injection latency trong cùng process, chưa phải diễn tập OS suspend toàn máy.

Consent: `POST /v1/swaps/{swap_id}/consent`, Customer đúng chủ, Idempotency-Key UUID mới; body:

```json
{"expected_version": 2, "quoted_amount_minor": 9000, "currency": "VND", "accept": true}
```

`expected_version` thực tế lấy từ GET/reserve, không hard-code2 trong thao tác thủ công.

| Nhánh | Expected | Actual PostgreSQL/API |
| --- | --- | --- |
| Consent chậm | 409/RESOURCE_UNAVAILABLE; không intent/outbox mới | **202**, swap AWAITING_PAYMENT; payments1/outbox1/holds3; elapsed≈16,05s |
| Callback success, settlement chậm | Payment SUCCEEDED; swap REVIEW_REQUIRED, giữ3holds, không command | Payment SUCCEEDED nhưng **swap AWAITING_RETURN**, review_reason=null, holds3, command0; elapsed≈16,06s |

Callback settlement dùng `POST /v1/payment-events`, X-Payment-Key của fixture, payment/key/amount/currency/reference đúng, result=SUCCEEDED. HTTP202 chỉ xác nhận inbox; worker sau đó ghi trạng thái sai. Giá trị chi tiết theo lượt cuối trong `SLOW_READ_CONSENT.json`, `SLOW_READ_SETTLEMENT.json` (không chứa credential).

### Nguyên nhân và tác động

`services/backend/app/application/payments.py`:

- `consent()` dòng80 lấy `now` trước `resources_valid()`; sau đó chỉ đọc lại clock để kiểm **reservation TTL**, không kiểm lại TTL cửa/BMS.
- `resources_valid()` dòng38–72 dùng cùng tham số `now` cho online, slot freshness và `assets.quality()` sau các thao tác đọc/khóa.
- `apply_result()` dòng134/168–173 cũng sử dụng mốc do worker truyền từ trước khi đánh giá tài nguyên. Worker `process_events()` dòng46 truyền `utcnow()` trước các đọc này.

Station/row locks ngăn ghi cạnh tranh, **không ngăn thời gian trôi qua**. `assets.fresh()`/quality vốn kiểm đúng với mốc được truyền; lỗi nằm ở việc giữ mốc đó quá lâu. Bản sửa BMS/door ordering Phase4–5 vẫn hoạt động: đây không phải snapshot cũ ghi đè, mà là bằng chứng hết hạn được coi còn mới ở thời điểm quyết định.

Blocker vì phiên được cho qua guard `AWAITING_PAYMENT→AWAITING_RETURN [điều kiện vẫn hợp lệ]` bằng chứng đã stale. Không khẳng định đã có mở cửa/giao pin: các probe xác nhận **0 device commands**, chưa có Phase7. Không phát hiện double charge trong ca này.

### Đề xuất sửa nhỏ nhất (chưa thực hiện)

Tập hợp/khóa dữ liệu cần thiết trước, lấy lại thời gian sát điểm đánh giá/transition, kiểm toàn bộ online/door/BMS freshness trên cùng trạng thái được khóa; bảo đảm chậm trong chuỗi đọc không dùng lại clock trước khi chậm. Consent phải fail closed trước tạo intent/outbox; settlement sau thu vẫn giữ SUCCEEDED và REVIEW_REQUIRED/holds khi quá hạn. Kiểm lại cả ngăn nhận/cấp, không chỉ TTL120s. Giữ hai failing probes và thêm kiểm tra sát biên TTL sau khi sửa. Không cần đổi baseline hay tăng TTL để né lỗi.

## 4. P6-A02 — Blocker: callback có receipt trùng làm worker lỗi lặp và chặn kết quả hợp lệ

Probe: `test_duplicate_provider_reference_cannot_poison_worker`.

1. Phiên A được reserve/consent bình thường; provider trả FAILED cuối cùng có receipt R. A FAILED/CANCELLED, release đúng tài nguyên.
2. Cùng Customer tạo phiên B hợp lệ, reserve/consent mới. Không sửa các bản ghi tài chính trực tiếp để tạo lỗi.
3. Callback nguồn đã xác thực cho B, payment_id/provider_key/amount/currency đúng B nhưng provider_reference=R của A, result=SUCCEEDED.
4. Backend trả **202**, ghi inbox. Gửi tiếp callback hợp lệ cho B với receipt riêng cũng202.
5. Chạy `worker.process_events()` hai lần: cả hai lần đều `IntegrityError`. Hai inbox vẫn chưa processed.

Payload đã che định danh:

```json
{"provider_event_id":"<new-event>","payment_id":"<B>","provider_key":"<B-key>",
 "provider_reference":"<receipt-already-owned-by-A>","result":"SUCCEEDED",
 "amount_minor":9000,"currency":"VND"}
```

Expected: từ chối mismatch ở ingress, hoặc lưu sự kiện để đối soát nhưng xử lý an toàn, không đánh dấu B thành công và không làm worker chết/chặn các kết quả hợp lệ. Không bỏ unique constraint để cho trùng receipt.

Actual `REFERENCE_COLLISION.json`: A FAILED; B CREATED/AWAITING_PAYMENT; payments2/outbox2/holds3, inbox2/unprocessed2, command0; worker_errors=`IntegrityError` hai lần. Unique `payments.provider_reference` đã bảo vệ DB khỏi ghi sai; transaction rollback không tạo partial success. **Không có double charge được chứng minh**. Receipt lỗi là input của nguồn callback đã xác thực, không phải bypass X-Payment-Key hay tấn công từ Customer.

Nguyên nhân:

- `payments.receive()` dòng124–130 chỉ so receipt với receipt hiện có của **chính** Payment B (đang null), không kiểm thuộc Payment khác.
- `apply_result()` dòng160–163 gán receipt R và chạm UNIQUE của PostgreSQL.
- `workers/payment.py:process_events()` không cô lập lỗi này; `tick()` xử lý inbox trước toàn bộ outbox, `main()` không có boundary bắt lỗi. Từ source, CLI worker thoát khi gặp lỗi; restart đọc lại cùng unprocessed event. Probe thực tế xác nhận hai lần gọi worker đều lỗi và callback hợp lệ phía sau bị chặn. **Đã xác minh tiếp bằng hai subprocess worker `--once` riêng: cả hai exit1, UniqueViolation `payments_provider_reference_key`; sau restart inbox vẫn2unprocessed.** Xem POISON_PROCESS_CONFIRMATION.xml và POISON_WORKER_0/1.log. Lượt xác minh này dùng schema riêng, mỗi HTTP request commit thật; không dựa vào outer rollback transaction hoặc timestamp inbox bằng nhau.

Ledger provider trong probe này không được tạo: adapter test trả kết quả xác định cho A, sau đó fault input qua HTTP callback. Không tuyên bố provider SQLite tự sinh receipt trùng; UUID receipt của provider bình thường không tạo ca này. Các kiểm tra ledger bền vững ở regression/E2E là nhóm riêng.

Đề xuất: kiểm ràng buộc ownership của provider_reference và bảo vệ race hai payment/khác station (global receipt guard hoặc xử lý unique violation trong savepoint); callback mâu thuẫn không trở thành poison pill. Ghi bằng chứng/audit/đối soát theo hợp đồng, giữ trạng thái fail closed, worker tiếp tục xử lý các aggregate không liên quan. Giữ unique constraint; không tự sửa/loại bỏ inbox lỗi hoặc giải phóng holds. Cần kiểm tương tự nhánh query/direct response. Chưa sửa source.

## 5. Các probe độc lập còn lại

| Tên test / tham số | Kết quả | Bằng chứng kiểm tra |
| --- | --- | --- |
| `test_new_bad_evidence_and_old_good_replay_after_consent[bms]` | Passed | SOC mới10, SOC cũ90 seq cao bị EVENT_OUT_OF_ORDER; success→REVIEW_REQUIRED,3holds,0command |
| Cùng test `[return_door]`, `[supply_door]` | 2 Passed | OPEN mới, CLOSED cũ hơn1s bị từ chối cả hai ngăn; callback replay không đổi state/holds |
| `test_inbox_duplicate_payload_conflict_before_processing` | Passed | Cùng ID/body trảduplicate; đổi result cùng ID409 EVENT_ID_CONFLICT; trước workerPaymentCREATED, sau applySUCCEEDED đúng1event |
| `test_two_callback_consumers_apply_one_terminal_transition` | Passed | Hai HTTP thread/two PG connections, hai worker consumers; một inbox, đúng1audit PAYMENT_SUCCEEDED,3holds/0command |
| `test_callback_queued_before_dispatch_is_not_a_second_charge[PENDING/SUCCEEDED/FAILED]` | 3 Passed | Callback trước dispatch; nếu gọi provider thì chỉ query; đúng1intent/0command |
| `test_callback_waits_for_committing_bad_device_evidence[door/bms]` | 2 Passed | Device transaction giữ stationlock trước; settlement thật sự chờ; commit dữ liệu xấu rồi PaymentSUCCEEDED/REVIEW_REQUIRED,3holds/0command |

Các race mới dùng schema PG riêng và các connection độc lập, không SQLite thay DB nghiệp vụ. Gate test chỉ kiểm soát lịch thread, không thay expected/state của service. Hai Backend process cùng consent được kiểm qua E2E riêng, không gọi test thread là hai Backend process.

## 6. Review transaction, crash window và bảo mật

- Consent: ownership trước mutation, idempotency lock ở PostgreSQL, station→user→swap/resources; intent+AWAITING_PAYMENT+outbox+audit+idempotency cùng commit. Unique swap_id/provider_key/dedup_key là lớp cuối. Các rollback/idempotency/version test cũ đã chạy lại.
- Outbox claim commit trước HTTP; không giữ PG lock qua provider. Khi chưa rõ đã dispatch, chỉ query cùng key. Crash sau claim **trước** gửi HTTP có thể mắc NOT_FOUND/UNKNOWN lâu dài; hạn chế đã ghi từ triển khai, an toàn chống thu lại, chưa có tự động giải phóng/khôi phục Phase8.
- Callback ingress commit inbox,202 không phải Payment success. Apply+processed_at+audit cùng transaction. Exact duplicate không tạo effect mới; cùng ID khác body409. Trước inbox commit/crash có thể retry; sau commit trước apply có thể worker tiếp nhận lại. Rollback tại apply được regression kiểm. P6-A02 là lỗ hổng về khả năng tiến triển khi một event không xử lý được.
- Provider SQLite WAL/BEGIN IMMEDIATE; unique key/payment/swap; kết quả lưu trước response; khác body409. Response loss/restart dùng lại key, không thu lại. Chỉ provider dùng SQLite, Backend vẫn PostgreSQL17.11.
- Payment terminal không bị late PENDING/FAILED ghi đè. Terminal mâu thuẫn mở recovery hook, không tự refund hoặc giao pin. UNKNOWN giữ tài nguyên; cancellation/expiration pre-payment không được giải phóng phiên đã consent.
- X-Payment-Key và X-Service-Key riêng; constant-time compare; user Bearer không thay device/provider credential. Callback không có chữ ký riêng vì hợp đồng dùng key riêng; không tự yêu cầu một cơ chế ký ngoài baseline.
- Fee/currency do policy snapshot quyết định; client chỉ xác nhận quote. Strict JSON number/bool guards, extra field rejection; Customer khác chủ404, Technician403, session bị thu hồi401. Các test tương ứng của62F6 đã chạy lại.
- Không có rate limit Payment riêng được thiết kế; không coi login rate limit là rate limit callback. Cần đánh giá chống abuse riêng nếu đưa ra ngoài loopback, không suy diễn có bảo vệ chưa triển khai.
- Source Frontend chỉ gửi user API, không có Device/Payment key; outcome không do button quyết định. Không chứng nhận tuyệt đối mọi log hay dependency không có secret chỉ từ review source.

## 7. Bảng nghiệm thu theo nhóm

| Nhóm / truy vết | API, DB và ledger | UI mới | Trạng thái nghiệm thu |
| --- | --- | --- | --- |
| Consent/intent — FR14/TC14/CT11 | Idempotency/atomicity/race cũ Passed; **P6-A01 consent stale** | Not Run | **Failed** |
| Provider/chống double charge — TC14/15/CT03 | Regression durable ledger/retry/2workers Passed; E2E riêng bên dưới | Not Run | Passed trong các kịch bản đã chạy, không phải proof mọi crash window |
| Callback/auth/replay — TC14/15/CT10 | Auth/money/idempotency Passed; **P6-A02 poison receipt** | Không có UI callback công khai | **Failed** |
| UNKNOWN/outbox/restart — BR07/CT03 | Query same key/holds/rollback Passed; poison inbox có thể chặn outbox | Not Run | **Failed do P6-A02**, luồng UNKNOWN thông thường Passed |
| Payment–Cancel–Expiration — FR10/14 | Existing concurrency Passed; hai race evidence mới Passed | Not Run | Passed phạm vi test đã chạy |
| SUCCEEDED/REVIEW_REQUIRED — SM03a/BR02 | Dữ liệu xấu đến trước callback được chặn; **P6-A01 expiry trong lúc đọc** | Not Run | **Failed** |
| Amount/RBAC — FR01/02/14, CT10 | Strict fields/quote/role/owner/session Passed trong regression | Not Run | API Passed; Browser chưa nghiệm thu mới |
| Kế thừa Phase1–5/hợp đồng/build | 270 regression cũ Passed; BMS21+door25+P5acceptance18 giữ nguyên | Build Passed | Passed nhóm này; không bù cho blocker Payment |

## 8. Những phần chưa kiểm chứng

Không có Browser E2E mới: **Not Run**, không phải Blocked bởi login. Không đăng nhập demo, không reset counter; ưu tiên tái hiện hai lỗi Backend trước việc nghiệm thu tương tác UI. Ba nhóm tương tác còn Not Run: Customer bấm consent→kết quả; UI FAILED/UNKNOWN và retry; Admin bấm reconcile. Ba nhóm đọc/role lịch sử không được tính Passed mới.

Chưa diễn tập kill worker đúng instruction sau provider commit nhưng trước DB settlement; chưa kill callback process đúng instruction sau inbox commit trước ack. Các test response loss, rollback, durable restart đã chạy không được gọi là bao phủ mọi điểm kill. Poison event đã tái hiện cả hai lần gọi worker và hai subprocess restart exit1; chưa kiểm riêng race receipt trùng xuyên trạm. Chưa stress dài hạn/cross-station receipt collision đồng thời, backup/restore đồng bộ DB+ledger, hay full Phase7/8 recovery/refund/custody. Không chỉnh reservation demo lịch sử P5-A01; read guards và regression lịch sử test riêng Passed.

HTTP28 của Phase5 và IoT/Phase5 real-process E2E8/8 lịch sử không tự mang sang lượt này. Kết quả chạy mới chỉ lấy artifact của thư mục PHASE6_ACCEPTANCE.

## 9. Hướng dẫn người dùng tự kiểm tra an toàn

Chỉ đọc demo: khởi động bằng README (Backend, payment, payment-worker, frontend; callback sender tùy chọn), đăng nhập tài khoản `customer`, `admin`, `technician` với password local, không gửi password/key vào báo cáo. Mở **QR/RFID và giữ tài nguyên** → **Thanh toán mô phỏng · không dùng tiền thật**. Xem phí9.000VND, Payment ID/state/Receipt; SUCCEEDED không là cửa mở/Swap COMPLETED. Admin chỉ có **Đối soát cùng khoản thu** khi PENDING/UNKNOWN; Technician không có quyền Payment.

Thao tác ghi như **Đồng ý phí và thanh toán mô phỏng**, **Gửi lại xác nhận với cùng mã yêu cầu**, **Đối soát cùng khoản thu** chỉ thử trên fixture riêng. Do blocker chưa sửa, không dùng việc UI báo thành công để kết luận eligibility còn đúng. Không bật kịch bản lỗi provider trên DB demo.

Swagger Backend `/docs`: Customer GET `/v1/swaps/{id}/payment` là chỉ đọc; POST `/v1/swaps/{id}/consent` có body và Idempotency-Key như mục3 là thao tác ghi. Admin POST `/v1/payments/{id}/reconcile`: `{ "expected_version": <Payment.version>, "reason": "Kiểm tra cùng intent mô phỏng" }`, UUID idempotency;202 chỉ schedule query. Callback `/v1/payment-events` dành adapter private, không nhập key vào Frontend. Dùng các test bên dưới để tái hiện lỗi, không tạo receipt collision bằng tài khoản demo.

```powershell
$env:P5_EVIDENCE_DIR='docs/PHASE6_ACCEPTANCE'
# Dùng label mới mỗi lần để giữ bằng chứng cũ:
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_PROBES tests/test_phase6_acceptance.py
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_REGRESSION --ignore=tests/test_phase6_acceptance.py
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_E2E --script tools/phase6_acceptance_e2e.py
.\.venv\Scripts\python.exe tools/validate_contracts.py docs/PHASE6_ACCEPTANCE/RECHECK_CONTRACTS.json
npm.cmd --prefix apps/web run build
```

Không chạy các runner đồng thời: helper cũ ghi một số report trung gian dùng chung rồi giữ bản mới vào thư mục nghiệm thu và trả lại đúng bytes report trước đó. E2E wrapper mới chuyển output cuối sang PHASE6_ACCEPTANCE, không ghi đè report E2E Phase6 đã commit. Đầu ra finding JSON của probe dùng tên cố định; lưu bản bằng chứng trước khi tự chạy lại nếu cần giữ từng lượt.

## 10. File và dữ liệu cần giữ

- `tests/test_phase6_acceptance.py`:13probe độc lập; **giữ làm regression**, đặc biệt ba failing cases, không đổi expected để thành Passed.
- `tools/phase6_acceptance_e2e.py`: wrapper test nhỏ tái sử dụng E2E thật, chỉ redirect report; giữ nếu tiếp tục nghiệm thu. Không tạo bản sao business runner.
- `docs/PHASE6_ACCEPTANCE.md`: báo cáo này.
- `docs/PHASE6_ACCEPTANCE/`: JUnit/log các lượt,3findingJSON, contract result, E2E result và bản report testenvironment/ordering tách riêng. Giữ PROBES_FINAL,REGRESSION,3finding và E2E làm bằng chứng; log setup sandbox/lượt probe trước là bằng chứng trung gian, có thể dọn sau khi người dùng quyết định.
- `.cache/p5-acceptance-*`, `.cache/phase6_e2e_*`, `.local/phase6_e2e_*`: test runtime/log/ledger; không commit, không tự xóa. `.local` và PostgreSQL schema/volume cần bảo toàn. Build `apps/web/dist` có thể tạo lại; không tự dọn.
- Không sửa .env, không thêm dependency/migration, không sửa tài liệu baseline/source/backend/frontend hoặc expected của test cũ. Các file untracked cũ được giữ nguyên; không reset/clean/restore.

Kết quả hoàn tất và kiểm tra file cuối ở mục11. **Bất kể happy-path E2E Passed, Phase6 vẫn CHƯA đạt cho đến khi P6-A01 và P6-A02 được sửa và failing probes được kiểm chứng lại.**


## 11. E2E và bàn giao cuối

`REAL_PAYMENT_E2E` exit0: **12 checks Passed** với hai Backend8010/8011, provider8012, payment worker và callback sender riêng. Đây là chạy lại E2E thực, không suy ra từ pytest. Provider ledger SQLite đúng một charge trong mỗi schema:

| Kịch bản | PostgreSQL cuối | Ledger/HTTP |
| --- | --- | --- |
| failure | Payment FAILED / Swap CANCELLED /0holds | Một charge; callback xử lý; retry không charge khác |
| lost-response | UNKNOWN rồi query cùng key → Payment SUCCEEDED / REVIEW_REQUIRED /3holds | Worker restart, provider đã lưu receipt; không charge thứ hai; evidence thật đã cũ nên review đúng |
| success | SUCCEEDED / AWAITING_RETURN /3holds | Callback xác thực apply trước query, outbox attempts1; hai Backend cạnh tranh chỉ1intent |

Tất cả không tạo device command, không hoàn tất swap. Fingerprint demo tài chính/assets/evidence không đổi trong E2E. Fixture F6 chuẩn bị device evidence qua inbox/worker nhưng không chạy hai simulator liên tục trong F6 E2E; không gọi đây là IoT E2E8 mới. Source helper dừng đúng subprocess tự tạo trong finally; không còn listener test8010/8011/8012 sau lượt chạy. PostgreSQL schema và ledger test được giữ.

`POISON_PROCESS_CONFIRMATION`: **1 Failed,12 deselected**, là chạy xác minh sâu hơn của **cùng** failing probe P6-A02, không cộng thành test lỗi thứ tư. Fixture chuyển sang schema riêng với commit từng HTTP request để worker process nhìn thấy dữ liệu. Không đổi expected, không sửa source hoặc nới test. Hai worker process khởi động liên tiếp đều exit1. Đây là bằng chứng restart không tự vượt được poison inbox.

Tổng kết cuối: 342 test pytest khác nhau Passed,3Failed;12E2EchecksPassed;validators/buildPassed. **0 final setup errors/0 skipped** trong regression và bộ13probe cuối;11setupErrors ban đầu được ghi riêng. Browser3nhóm tương tác NotRun; HTTP28/Phase5E2E8/IoTE2E8 riêng NotRun trong lượt này. Các crash/stress/restore chưa chạy được nêu tại mục8, không gộp thành Passed hoặc tự gán một số lượng test không có test case.

Rà soát cuối: `git diff --check` Passed; không có tracked source/baseline diff, index không được stage; HEAD vẫn81a8acd. Report E2E implementation đã commit không thay đổi. File mới chỉ là test, wrapper và báo cáo/bằng chứng nghiệm thu;36file untracked cũ được giữ. Không tạo commit/push.

Quét exact các secret trong `.env` với artifact mới và JS bundle không có match (SUMMARY.json). Đây là kiểm tra bổ sung có phạm vi cụ thể, không chứng nhận mọi log hoặc mọi dạng secret. Các error log poison có mock receipt UUID để đối chiếu, không có key/password; SQL parameters được ẩn. Không đưa test credentials vào report.

**Kết luận dứt khoát: Phase 6 CHƯA đủ điều kiện chuyển Phase 7. Cần sửa P6-A01 và P6-A02, chạy lại ba failing probes và regression trước khi nghiệm thu lại.**


## 12. Hoàn tất sau gián đoạn — 26/10/2026

Lượt tiếp tục chỉ kiểm tra file/source/hợp đồng, đọc JUnit/log/JSON đã có và hoàn thiện tài liệu. **Không chạy pytest/E2E/build lại, không tạo fixture mới, không sửa probe hoặc source.** Kết quả tại mục2/11 đều là kết quả thực chạy trước gián đoạn; không phải các lần chạy mới ngày26. `RESUME_VERIFICATION_2026_10_26.json` xác nhận HEAD, số test trong XML và SHA256 của probe/runner/bằng chứng cùng đủ36file untracked cũ. SUMMARY.json là snapshot kiểm tra trước lượt xác minh process sâu hơn, được giữ nguyên thay vì ghi đè.

### P6-A01: các đường đọc evidence và điểm quyết định

| Đường đọc trong phạm vi tích hợp | Điều kiện/thời gian | Kết luận phạm vi |
| --- | --- | --- |
| Payment `resources_valid()` → `online()` | Heartbeat last_received_at fresh và có accepted snapshot đúng boot | Cùng mốc now đầu hàm bị giữ qua các đọc sau |
| Payment → hai compartment | ACTIVE, CLOSED, observed_at(receipt) trongTTL, `current_observation()` khớp accepted physical watermark/payload/boot | Độ mới được kiểm cho cả ngăn nhận/cấp; ordering guard không tự cập nhật clock |
| Payment → `quality()` | newest received sample, verified event/boot/location, received_at **và** measured_at fresh; SOC/SOH/T/fault/lifecycle | Mẫu không đổi vẫn hết hạn theo thời gian; không phải stale event ghi đè |
| `consent()` → resources_valid | Trong API transaction: ownership/idempotency/station/user/swap/resources; tạo intent/outbox/consent/audit cùng commit | Phải kiểm eligibility bằng thời gian hiện hành sát quyết định tạo intent; recheck reservation120s không thay evidence15s |
| Callback `process_events()` → apply_result → resources_valid | Inbox đã commit; Payment/swap/evidence locks rồi atomic settlement+processed_at+audit | Thu đã xác minh phải giữ SUCCEEDED, nhưng **không** sang AWAITING_RETURN nếu freshness đã hết; REVIEW_REQUIRED/holds |
| Outbox HTTP/query response → apply_result → resources_valid | Sau HTTP reacquire payment/station locks, cùng hàm settlement | Cùng lỗi về việc giữ mốc now có thể áp dụng; latency probe trực tiếp đã chạy nhánh callback, chưa fault-inject độ trễ riêng nhánh query |
| Reservation `reserve()`, asset availability/eligible, restore và device worker | Dùng chung fresh/quality/current_observation; Phase4–5 có guard riêng và regression | Chưa xác nhận lỗi mới ở mọi call site này; không mở rộng kết luận P6-A01 sang tất cả module chỉ vì dùng chung helper |

`assets.fresh(value,now,policy)` dùng khoảng đóng `now−15s ≤ value ≤ now`; `compartments.observed_at` là receipt time. BMS còn phải kiểm measured_at và watermark xuyên boot. Clock không bị mock trong hai failing probes; chỉ có một delay16s tại đọc ngăn. Snapshot/BMS đã bị **thay đổi** trong transaction khác được stationlock bảo vệ (hai race mới Passed); snapshot/BMS **không đổi nhưng quá hạn** không được lock bảo vệ. Device timeout worker cũng phải chờ stationlock, nên không thể dựa vào việc worker khác chắc chắn đưa phiên vào review trước Payment commit.

File sửa tối thiểu dự kiến: `services/backend/app/application/payments.py` (thời điểm đánh giá/freshness và transition), rà soát call site ở `services/backend/app/workers/payment.py`. `application/assets.py` cung cấp primitive đúng và guard ordering cần bảo toàn; không mặc định phải sửa helper dùng chung. Không đổi TTL/config hoặc meaning received_at để làm probe Passed.

### P6-A02: 202, xác minh, inbox và acknowledgement là các bước khác nhau

OpenAPI `/v1/payment-events` cho phép **202 CallbackReceipt**, yêu cầu xác minh key/mã/tiền/currency trước inbox và409 khi cùng eventID khác hash. Không có quy định riêng bắt buộc HTTP status nào cho cross-Payment receipt collision. Vì vậy **không kết luận 202 tự nó vi phạm hợp đồng**. Có thể reject sớm bằng lỗi conflict đã có, nhưng vẫn phải có phòng vệ durable ở worker vì collision/race có thể chỉ phát hiện lúc apply.

1. API xác thực X-Payment-Key; `receive()` giữ event advisory lock, kiểm payload hash và identity/amount/currency/receipt hiện tại của chính Payment.
2. INSERT inbox nằm trong request transaction; commit xong trả202. Đây là nhận bền vững, chưa là SUCCEEDED hoặc audit settlement.
3. Worker chọn100event chưa processed **toàn schema**, theo created_at. Không có claim lease hoặc SKIP LOCKED; station/payment/event row locks và recheck processed_at bảo vệ xử lý lặp bình thường.
4. `payments` có UNIQUE swap_id, provider_key, provider_reference; `payment_events.provider_event_id` UNIQUE. Receipt đã thuộc A chỉ bị DB unique bắt khi worker UPDATE B.
5. IntegrityError rollback toàn transaction apply: Payment B vẫnCREATED, swapAWAITING_PAYMENT,3holds, processed_at vẫnnull; audit trong transaction cũng rollback. Inbox payload trước đó vẫn bền vững, không mất bằng chứng. **Không có business error code trả ngược cho HTTP202 đã hoàn tất**; lỗi thực là psycopg UniqueViolation/SQLAlchemy IntegrityError.
6. Không có durable processing-error/rejection handler trong Payment inbox; schema chỉ có payload/hash/processed_at, khác Device inbox có accepted/processing_error. Sau restart cùng oldest event vẫn được chọn, worker lại exit1. Provider callback sender có thể đã ghi delivered sau202, nên không được trông cậy vào sender gửi lại để sửa settlement.
7. `tick()` gọi process_events trước outbox. Nếu poison event làm throw, chưa tới query/charge outbox. Trong cùng batch, callback hợp lệ sau poison không tiến triển. **Đã chứng minh** với hai event của B và hai worker subprocess restart. **Suy ra từ source**, callback của Payment khác nằm sau poison và outbox/query UNKNOWN cũng bị chặn tại vòng này; chưa tạo thêm một multi-Payment queue stress probe. Hai worker không tự giải quyết: cả hai có thể lần lượt lock rồi rollback cùng event, không có durable disposition để bỏ qua event đã được xử lý là lỗi.

Do bằng chứng hai subprocess exit1 và phạm vi hàng đợi dùng chung, phân loại P6-A02 được nâng từ **Major trong bản nháp ban đầu lên Blocker nghiệm thu**. Nó khác P6-A01 về nguyên nhân: thiếu xử lý durable khi vi phạm receipt uniqueness, không liên quan freshness. Unique constraint vẫn bảo vệ dữ liệu; chưa phát hiện double charge/mất ledger. Hậu quả là settlement và đối soát không tiến triển, tài nguyên giữ kéo dài, không phải đã thu tiền hai lần.

File sửa dự kiến: `application/payments.py` (`receive`, `apply_result`, xử lý conflict/audit); `workers/payment.py` (cô lập event lỗi, durable acknowledgement, tiếp tục aggregate khác). Không sửa provider ledger để chấp nhận receipt trùng. Không bắt Exception rồi bỏ qua/mark success tùy tiện. Phương án phải giữ payload và audit lý do, phân biệt outcome rejected với applied; dùng savepoint/transaction để tránh partial write, giữ DB uniqueness làm lớp cuối. Nếu muốn thêm cột trạng thái lỗi mới thay vì biểu diễn bằng cấu trúc audit hiện có, cần đề xuất migration và semantics rõ, không sửa baseline âm thầm. Không tự tạo chính sách cancel/refund/release khi receipt mâu thuẫn.

### Tái hiện riêng và kiểm thử cần giữ sau sửa

Các lệnh dưới đây dành lượt sửa/kiểm chứng tiếp theo; **không chạy lại trong lượt tiếp tục này**. Trước khi chạy phải bảo toàn ba finding JSON có tên cố định vì test sẽ viết snapshot kết quả mới. Giữ nguyên expected và artifact trước sửa; label XML/log mới không tự bảo vệ các finding tên cố định.

```powershell
$env:P5_EVIDENCE_DIR='docs/PHASE6_ACCEPTANCE'
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_P6_A01 tests/test_phase6_acceptance.py -k freshness_rechecked_after_slow_resource_read
.\.venv\Scripts\python.exe tools/run_phase5_acceptance.py RECHECK_P6_A02 tests/test_phase6_acceptance.py -k duplicate_provider_reference_cannot_poison_worker
```

Sau sửa P6-A01: hai nhánh consent/settlement, biên15s, query/direct response, cả hai ngăn, BMS, transaction latency, race evidence commit trước/sau settlement; giữ P4 ordering21 và P5 door25/acceptance18. Sau sửa P6-A02: duplicate receipt cùng/khác Payment/station, callback/query race, hai worker, restart, legitimate event phía sau, rollback audit/ack, same-event replay, cùngID khácpayload, terminal conflict, UNKNOWN query và outbox vẫn tiến triển. Không tự thay expected của callback202 thành409 nếu chọn kiến trúc inbox bất đồng bộ; test quan trọng là fail closed và queue tiến triển bền vững.

**Thứ tự đề nghị:** sửa P6-A01 trước để ngăn quyết định tiến workflow bằng evidence hết hạn; tiếp theo P6-A02 để worker/đối soát không bị mắc kẹt. Không đưa bản sửa trở lại demo như phiên bản đã nghiệm thu khi mới giải quyết một lỗi. Hai lỗi độc lập, có thể review thành hai phần thay đổi riêng nhưng phải kiểm cả hai trước chuyển Phase7.

### File và tài nguyên của lượt tiếp tục

Chỉ chỉnh `docs/PHASE6_ACCEPTANCE.md`, `docs/IMPLEMENTATION_STATUS.md`; tạo `docs/PHASE6_ACCEPTANCE/RESUME_VERIFICATION_2026_10_26.json`. Không đổi test/runner hay evidence cũ. Bằng chứng nghiệm thu trước resume khoảng115KiB;3ledger E2E mới trước đó mỗi32KiB, log process tương ứng khoảng606byte/thư mục. Không đo tăng trưởng Docker/VHDX và không dọn schema/volume. Các con số không phải tổng dung lượng toàn dự án. Test/cache/ledger vẫn giữ tại workspace và PostgreSQL test; không có tiến trình test mới trong lượt tiếp tục.

**PHASE 6 CHƯA ĐẠT NGHIỆM THU, CHƯA ĐỦ ĐIỀU KIỆN CHUYỂN PHASE 7. P6-A01 và P6-A02 chưa được sửa.**
