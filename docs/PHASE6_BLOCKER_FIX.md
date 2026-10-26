# Sửa P6-A01 và P6-A02 — Phase6

Ngày26/10/2026 (Asia/Bangkok), base `81a8acd`. Chưa commit/push; không Phase7. Bản nghiệm thu trước sửa ở PHASE6_ACCEPTANCE.md được giữ nguyên. Bằng chứng sau sửa chỉ ở `docs/PHASE6_FIX/`; không thay report lỗi cũ bằng kết quả mới.

## 1. Nguồn và quyết định kiểm thử

Kế thừa AGENTS, START_HERE/HANDOFF, QD01–09 approved, OpenAPI, schema/invariants, SM-03a/SM-04, FR14/UC12/TC14 và FR15/UC13/TC15, BR02/07 cùng guard ordering Phase4–5. Không thay baseline hoặc TTL. Source/provider/worker/reservation và các probe nghiệm thu được đọc trước sửa. HEAD đúng81a8acd, tài liệu tiến độ đã có thay đổi và61file untracked được bảo toàn.

Có một lỗi trong **assertion cuối của probe P6-A02 lịch sử**: test gửi callback sai, tiếp theo callback SUCCEEDED hợp lệ, rồi yêu cầu Payment không SUCCEEDED ở cuối. Điều này trái yêu cầu callback hợp lệ phía sau phải được xử lý. Người dùng đã xác nhận: **giữ probe gốc, thêm test đúng hai thời điểm**. Vì vậy không sửa/xóa/xfail assertion cũ; phải báo Failed của nó riêng nếu callback hợp lệ đã settle đúng. Đây không phải lý do đổi nghiệp vụ để cố làm toàn bộ test xanh.

## 2. P6-A01 — kiểm freshness tại điểm quyết định

Nguyên nhân: `resources_valid()` dùng mốc now truyền từ trước các thao tác đọc/khóa; locks giữ dữ liệu ổn định nhưng không ngăn15sTTL trôi qua. Consent chỉ kiểm lại reservation120s. Settlement có thể ghi SUCCEEDED/AWAITING_RETURN khi cửa/BMS đã hết freshness.

Sửa duy nhất source `services/backend/app/application/payments.py`:

- Giữ toàn bộ guard station/device/service, pin+hai ngăn, location/holder, alert, current_observation và quality.
- Khi guard ban đầu hợp lệ, đọc cặp timestamps của mẫu BMS mới nhất dưới cùng station/resource locks. **Sau lần đọc DB cuối của bước đánh giá**, lấy `decision_at=utcnow()` mới.
- Dùng cùng decision_at kiểm heartbeat, receipt cửa ngăn nhận/cấp, BMS received_at và measured_at. Không thêm query hoặc HTTP trong phần kiểm thời gian cuối này.
- Consent fail closed409 RESOURCE_UNAVAILABLE trước tạo intent/outbox; transaction rollback không có AWAITING_PAYMENT một phần.
- Settlement đã có provider success vẫn giữ Payment SUCCEEDED; evidence hết hạn khiến nhánh hiện có REVIEW_REQUIRED/holds3, không lệnh thiết bị, không refund/cancel/release.

`compartments.observed_at` vẫn là receipt time; DeviceEvent.observed_at/BMS.measured_at vẫn là thời điểm vật lý, received_at là tiếp nhận, processed_at là xử lý. Không có trường accepted_at mới. Guard P4/P5 và boot/seq không đổi. Điểm quyết định là sau khi tập hợp evidence dưới lock; không tuyên bố bảo đảm clock ngừng trôi đến fsync/commit hoặc đến thao tác vật lý Phase7. Phase7 vẫn phải recheck trước tác động.

Trước khi sửa P6-A02, đã chạy hai failing probes A01 nguyên bản và18ca biên mới: **20Passed** (`A01_READY`). Ngăn nhận/cấp được recheck cùng nhau. Test mới phân biệt chỉ door, chỉ BMS, cả hai; tại TTL−1µs/TTL/TTL+1µs, cho consent và settlement. TTL bằng biên vẫn fresh theo helper khoảng đóng hiện có, không tự đổi hợp đồng. Hai probe gốc dùng delay thật16s, không thay clock/evidence để né lỗi. Các ca mới dùng clock điều khiển và timestamp fixture nhất quán, không sửa accepted flag.

Lượt A01_REPRO đầu có2setupErrors do Docker Desktop chưa chạy/PG timeout; chưa chạy nghiệp vụ. Đã mở Docker Desktop có sẵn; container cũ healthy, không tạo/reset volume. Giữ log lỗi môi trường, không tính vào kết quả Passed.

## 3. P6-A02 — receipt ownership, savepoint và xử lý bền vững

Nguyên nhân: ingress chỉ so receipt với Payment hiện tại, không biết receipt đã thuộc Payment khác. Worker UPDATE vấp UNIQUE, rollback cả apply, processed_at vẫnnull; lỗi thoát lên vòng inbox trước outbox, restart lặp lại và callback hợp lệ phía sau bị chặn.

Trong cùng `payments.py`:

1. `apply_result()` trở thành boundary dùng chung callback và response/query outbox. Receipt hợp lệ về dạng nhận transaction advisory lock theo receipt, **không giới hạn theo station**, rồi kiểm ownership hiện có. Không giữ lock qua HTTP.
2. Receipt thuộc Payment khác: `reject_receipt()` không gán receipt sai. Nonterminal chuyển UNKNOWN/REVIEW_REQUIRED qua State Machine cũ; giữ3holds, không thu lại. Terminal đã xác minh giữ nguyên.
3. Ghi audit append-only `PAYMENT_RESULT_REJECTED`, code PAYMENT_RESULT_MISMATCH, reason PROVIDER_REFERENCE_CONFLICT, eventID/reference/result để đối chiếu inbox. Không log key/secret.
4. Apply bình thường nằm trong SQLAlchemy savepoint. Nếu writer cũ không tuân receipt lock vẫn gây **đúng** UniqueViolation `payments_provider_reference_key`, savepoint rollback trước khi ghi rejection. Không bỏ constraint và không bắt rồi bỏ qua mọi IntegrityError.
5. Caller worker cũ commit rejection/UNKNOWN/audit cùng `payment_events.processed_at`. Payload/hash inbox còn nguyên; processed nghĩa đã xử lý thành công hoặc xử lý thành từ chối bền vững, không tự chứng minh PaymentSUCCEEDED. Audit phân biệt hai outcome. Không cần enum/cột mới.
6. Sự kiện vĩnh viễn sai không còn nằm trong nhóm unprocessed. Worker tiếp tục tới sự kiện hợp lệ và outbox; restart không crash lại. Callback mới hợp lệ có thể giải UNKNOWN thành SUCCEEDED đúng một lần, cùng provider key. Replay cùng event ID/body vẫn receipt cũ; sửa body cùng ID vẫn409, không ghi đè bằng chứng cũ.

Không thay ingressHTTP202: đó là tiếp nhận bất đồng bộ theo contract. Không sửa claim/outbox/provider ledger hoặc callback auth. Không tự tạo receipt khác; receipt hợp lệ đến sau là kết quả riêng của đúng intent do provider xác nhận. Lỗi DB không liên quan constraint này vẫn được raise, không bị ack thành công để che lỗi vận hành.

Không migration/dependency mới. Giữ UNIQUE payments.swap_id/provider_key/provider_reference, inbox.provider_event_id và outbox.dedup_key. Transaction order cũ station→user→swap/payment/resources được giữ; thêm receipt advisory lock không khóa hàng của Payment khác, tránh tạo vòng lock xuyên station.

## 4. Test bổ sung và bảo toàn probe

`tests/test_phase6_blocker_fix.py` có23case:

-18 freshness boundary cases đã mô tả.
- `test_conflicting_then_valid_callback_two_distinct_decisions`: sai→UNKNOWN/REVIEW_REQUIRED/holds, replay không audit thêm; hợp lệ→SUCCEEDED đúng1audit; A không đổi receipt; inbox đều processed.
- `test_two_workers_continue_past_conflict_and_restart`: PG connections độc lập, hai worker, hai subprocess restart exit0; reject1 và success1.
- `test_actual_unique_violation_rolls_back_savepoint_before_rejection`: fault injection gây **UNIQUE thật trên PostgreSQL sau precheck**; rollback write trong savepoint, session dùng được, audit reject; callback hợp lệ sau đó thành công. Đây không thay thế stress writer legacy nhiều process.
- `test_rejection_and_inbox_ack_rollback_together`: audit rejection lỗi thì rollback cả UNKNOWN/review/ack; retry đúng.
- `test_query_receipt_conflict_keeps_same_key_until_valid_result`: response xung đột→UNKNOWN, query cùng key giải quyết, không POST charge lần hai.

Probe gốc `tests/test_phase6_acceptance.py` không sửa byte nào. A02_TARGETED:15Passed/1Failed/20deselected; Failed duy nhất ở assertion lịch sử `payment != SUCCEEDED` sau valid callback, **không còn IntegrityError**, hai process exit0. Bộ nguyên bản còn được chạy trong full pytest, không âm thầm loại bỏ.

## 5. E2E tiến trình thật

`tools/smoke_phase6_fix.py` mới tái sử dụng fixture/HTTP helpers hiện có. Hai Backend8010/8011, provider8012, payment workers và callback sender riêng; schemaPG/ledger riêng, fingerprint demo trước/sau.

Receipt E2E **5checksPassed**:

- A được provider xác nhận FAILED, sau đó restart provider với cùng ledger để xử lý B thành công; hai receipt khác nhau, mỗi intent một charge.
- Nguồn callback xác thực gửi receipt A cho B; worker ghi UNKNOWN/review và audit reject. Hai process restart exit0, giữ3holds/0command.
- Callback sender thật gửi valid B phía sau; hai worker settle đúng1lần, inbox được xử lý hết.
- Replay/callback sender restart và outbox terminal không charge lại; ledger2intent/2charge,2receipt, không command.
- Fingerprint demo tài chính/assets/evidence không đổi.

Fixture chỉ hoãn `next_attempt_at` của outbox B để quan sát riêng bước reject trước khi query tự động có thể giải quyết; sau valid callback cho outbox đến hạn và kiểm terminal acknowledgement. Không sửa nguồn nghiệp vụ hoặc giả kết quả trong ledger; provider HTTP đã ghi B SUCCEEDED trước callback. Không dùng lịch test này trên DB demo.

E2E Payment cũ chạy lại riêng để kiểm success/failure/lost-response/restart và evidence stale sau timeout30s: kết quả cuối ghi bên dưới. Không gọi API tests là Browser E2E.

## 6. Lệnh, bằng chứng và tài nguyên

`tools/run_phase6_fix.py` chạy pytest/script hiện có, redirect mọi report ghi qua Path.write_text/write_bytes dưới docs sang `docs/PHASE6_FIX/<LABEL>/reports/`, cùng JUnit/log riêng. LABEL không được tồn tại trước đó. Không sửa test expected hoặc ghi đè67file bằng chứng cũ. Không chạy trực tiếp probe gốc nếu chưa có cơ chế này, vì nó viết findingJSON tên cố định.

```powershell
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A01_READY pytest tests/test_phase6_acceptance.py tests/test_phase6_blocker_fix.py -k 'freshness_rechecked or freshness_decision'
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A02_TARGETED pytest tests/test_phase6_blocker_fix.py tests/test_phase6_acceptance.py -k 'not freshness'
.\.venv\Scripts\python.exe tools/run_phase6_fix.py FULL_REGRESSION pytest
.\.venv\Scripts\python.exe tools/run_phase6_fix.py RECEIPT_E2E script tools/smoke_phase6_fix.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py PAYMENT_E2E script tools/smoke_phase6.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py HTTP_REGRESSION script tools/smoke_phase5.py --http-smoke
.\.venv\Scripts\python.exe tools/validate_contracts.py docs/PHASE6_FIX/CONTRACTS.json
npm.cmd --prefix apps/web run build
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix apps/web ls --depth=0
```

Đây là labels đã dùng; khi chạy lại chọn label mới. Giữ source/test/runner/report và bằng chứng trước/sau để regression. Log setup PG timeout và các output trung gian có thể cân nhắc dọn sau nghiệm thu, chưa tự dọn. `.cache/p6-fix-*`, `.cache/phase6_fix_e2e_*` chứa test runtime/log; `.local` chứa ledger bền vững không phải cache. DB/schema/volume, .env, baseline và ledger đều phải giữ. Dist có thể tạo lại; không xóa.

## 7. Kết quả cuối và giới hạn

Kết quả đã đối chiếu JUnit/log khi tiếp tục sau usage limit; không chạy lại các suite đã có bằng chứng đầy đủ và source không đổi:

| Nhóm | Kết quả | Nguồn/lượt |
| --- | --- | --- |
| P6-A01, hai probe gốc + 18 biên TTL | 20 Passed | Kế thừa `A01_READY` |
| P6-A02 và probe không freshness | 15 Passed, 1 Failed, 20 deselected | Kế thừa `A02_TARGETED`; assertion lịch sử |
| Full pytest Phase 1–6 + acceptance + bản sửa | **367 Passed, 1 Failed, 0 Errors, 0 Skipped** | Kế thừa `FULL_REGRESSION/results.xml`, 368 ca, 440,25s |
| Regression Phase 1–6 đã có | 332 Passed | Phân nhóm từ cùng full run; không cộng thêm |
| Acceptance Phase 6 gốc | 12 Passed, 1 Failed | Phân nhóm từ cùng full run |
| Regression bản sửa mới | 23 Passed | Phân nhóm từ cùng full run: 18 freshness + 5 receipt/rollback |
| BMS ordering / door ordering / acceptance Phase 5 | 21 / 25 / 18 Passed | Các tập con của 332, không cộng trùng |
| Suite riêng loại assertion lịch sử | Not Run | Không tự lọc/skip/xfail probe gốc |
| Payment E2E | 12 Passed | Kế thừa `PAYMENT_E2E` |
| Receipt-conflict E2E | 5 Passed | Kế thừa `RECEIPT_E2E` |
| Phase 5 E2E tuần tự | **8 Passed** | `HTTP_SERIAL_RETRY`; đã hoàn tất trước resume, kiểm chứng log/JSON trong resume |
| IoT E2E | **8 Passed** | Chạy mới `IOT_SERIAL_RESUME`, schema `phase4_e2e_9ade47cd5b`, exit 0 |
| HTTP smoke trên schema riêng | **28 Passed** | Cùng `HTTP_SERIAL_RETRY`, không sửa demo |
| Validators/hash | Passed | Kế thừa `CONTRACTS.json`: OpenAPI, JSON Schema, 278 SQL, baseline |
| Dependency checks và TypeScript/Vite | Passed | Kế thừa lệnh đã chạy ở lượt sửa trước |
| Browser | Not Run | Không lấy API/build làm Browser Passed |

Failed duy nhất: `test_duplicate_provider_reference_cannot_poison_worker`, assertion cuối yêu cầu không SUCCEEDED dù callback hợp lệ phía sau đã settle. Worker đã exit 0, không còn IntegrityError; test mới kiểm riêng hai thời điểm đạt. Theo quyết định của người dùng, test gốc vẫn nguyên vẹn trong suite; **không gọi full pytest Passed hoặc 368 Passed**. Không đề xuất thay đổi nghiệp vụ để thỏa assertion này.

### Tranh chấp advisory lock và kiểm thử tuần tự

Lượt `HTTP_REGRESSION` chạy chồng full regression đã Failed tại expiration, chưa đạt 28 HTTP checks. Log `.cache/phase5_e2e_2820b2a91a/worker-restarted.log` ghi `LockNotAvailable` ở `pg_advisory_xact_lock`; DB cấu hình `lock_timeout=5000`. `assets.station_lock` dùng khóa `assets:station:<UUID>` và `db.advisory_lock` hash key không có namespace schema. Seed tạo cùng station UUID giữa các schema trong cùng database. Probe A01 giữ transaction/khóa trong lúc delay thật 16s, vượt timeout worker 5s. Các schema riêng cách ly dữ liệu nhưng không cách ly advisory locks.

Bằng chứng chạy lại tuần tự, không tăng timeout hoặc sửa source/test: `HTTP_SERIAL_RETRY` đạt expiration thật 120s sau worker restart, release một lần, 8 E2E và 28 HTTP checks. Fingerprint demo không đổi. Đây là bằng chứng lỗi điều phối giữa suite trong lần chạy song song; không phải bằng chứng double charge hoặc sai dữ liệu Payment.

**Giới hạn production cần ghi nhận:** `app.workers.device.main` không bắt OperationalError quanh tick; contention thật kéo dài hơn timeout cũng có thể làm worker thoát và cần khởi động lại. Chưa kiểm thử retry tự động/supervisor trong production, không khẳng định mọi contention production an toàn. Lượt này không thay worker, timeout hoặc lock key. Chạy các suite dùng cùng database/seed tuần tự; muốn chạy song song cần thiết kế cách ly database/namespace test được review riêng.

### Resume hiện tại

Chỉ đọc lại bằng chứng, kiểm tra process/cổng và tiếp tục IoT E2E tuần tự; không sửa thêm source nghiệp vụ hoặc expected result. Khi kiểm tra đầu lượt không có Python test chạy; Docker Desktop đã tắt, mở lại bản cài sẵn qua phê duyệt công cụ, container PostgreSQL cũ trở lại. Không tạo/reset volume hoặc dừng tiến trình demo.
 ValidatorsOpenAPI/JSONSchema/278SQL/baselinehash Passed; pip check/npm dependencies Passed; TypeScript/Vite Passed82modules,JS285,66kB/gzip90,92kB. Không tải dependency/image mới.

Browser E2E mới **Not Run**; không thay đổi Frontend trong bản sửa này và không lấy BrowserPassed lịch sử làm kết quả mới. Chưa stress dài hạn, chưa backup/restore toàn hệ thống, chưa kill process ở mọi instruction boundary. Chưa có phần cứng thật, refund/recovery đầy đủ hoặc Phase7. Bất thường dữ liệu demo lịch sử không tự sửa.

Source nghiệp vụ sửa: **chỉ `services/backend/app/application/payments.py`**. File mới: test_phase6_blocker_fix.py, run_phase6_fix.py, smoke_phase6_fix.py, tài liệu này và bằng chứng PHASE6_FIX. IMPLEMENTATION_STATUS được cập nhật với kết quả sau sửa và giữ lịch sử trước sửa. Không commit/push.

## 8. Bàn giao sau resume

IoT E2E chạy mới đạt 8 checks, Backend/worker/hai simulator thật, ACK khác physical evidence, NACK, retry/ledger/restart và offline theo cấu hình. Báo cáo `PHASE6_FIX/IOT_SERIAL_RESUME/reports/PHASE4_E2E_RESULTS.json`; giữ schema và ledger. Các script dừng các child process do chính chúng tạo trong finally. Không chạy lại full regression/Payment E2E vì source không đổi và bằng chứng đã đầy đủ.

**P6-A01 và P6-A02 đã được khắc phục về hành vi trong phạm vi các probe, rollback và E2E đã thực hiện; sẵn sàng nghiệm thu lại bản sửa. Phase 6 chưa được tuyên bố đạt nghiệm thu toàn bộ và chưa chuyển Phase 7:** full suite vẫn 1 Failed lịch sử, Browser Not Run và giới hạn vận hành worker khi lock timeout nêu trên. Không có bằng chứng mới về double charge hoặc sai tài nguyên trong lượt này. Nếu muốn sửa expected/tách archival probe lịch sử khỏi suite cần người dùng phê duyệt riêng; hiện giữ nguyên quyết định giữ probe. Chưa commit/push.

### File và tài nguyên

- Source bản sửa cần giữ: `services/backend/app/application/payments.py` (không sửa thêm trong resume).
- Regression/runner cần giữ: `tests/test_phase6_blocker_fix.py`, `tools/run_phase6_fix.py`, `tools/smoke_phase6_fix.py`. Giữ cả `tests/test_phase6_acceptance.py` và `tools/phase6_acceptance_e2e.py` có sẵn từ nghiệm thu.
- Tài liệu cần giữ: báo cáo này, `IMPLEMENTATION_STATUS.md`; `PHASE6_ACCEPTANCE.md` giữ nguyên làm kết luận trước sửa.
- Resume chỉ cập nhật hai tài liệu trên, thêm `PHASE6_FIX/IOT_SERIAL_RESUME/` và `RESUME_FINAL_VERIFICATION.json`. Các report/log từ lượt sửa trước được giữ nguyên.
- Có thể cân nhắc dọn sau khi người dùng nghiệm thu: log runtime `.cache`, build `apps/web/dist` (tạo lại bằng build). JUnit, finding JSON, báo cáo thất bại và snapshot hash cần giữ làm bằng chứng; chưa tự dọn file nào.
- `.local` chứa ledger bền vững, không phải cache; PostgreSQL/test schemas/volume và `.env` giữ nguyên. Không xóa để tiết kiệm dung lượng. Tổng kích thước thư mục đo tại resume, không phải dung lượng tăng thêm: `.cache` khoảng 151,53 MiB, `.local` khoảng 44,63 MiB, `dist` 0,28 MiB, `docs/PHASE6_FIX` khoảng 0,1 MiB; không đo DB/VHDX.
- HEAD vẫn `81a8acd`, main ahead origin/main 1; working tree chưa sạch do bản sửa và bằng chứng có chủ đích. Không có staged file, không tạo commit. `git diff --check` đạt; Git có cảnh báo chuẩn hóa CRLF, không phải lỗi whitespace.

Lệnh chạy mới: `.\.venv\Scripts\python.exe tools/run_phase6_fix.py IOT_SERIAL_RESUME script tools/smoke_phase4.py`. Các lệnh `git status -sb`, `git diff --stat`, `git diff --check`, `git rev-parse HEAD`, kiểm tra process/cổng/container và đối chiếu SHA256/JUnit được chạy lại. Không cài dependency hoặc migration mới.

## 9. Nghiệm thu bổ sung sau khi người dùng cho phép chỉnh regression

Mục này cập nhật trạng thái mới nhất; các số 367 Passed/1 Failed và quyết định giữ nguyên test ở mục trước là lịch sử, không bị sửa hoặc xóa.

### Assertion P6-A02 và căn cứ điều chỉnh

Yêu cầu mới cho phép điều chỉnh regression khi xác minh assertion mâu thuẫn. SM-04 quy định UNKNOWN → SUCCEEDED khi đối soát thành công, callback lặp không đổi tác động, terminal SUCCEEDED không bị kết quả lỗi muộn ghi đè. Test cũ gửi callback có receipt của khoản thu A cho B, rồi gửi callback hợp lệ B trước khi worker xử lý, nhưng cuối cùng lại yêu cầu B không SUCCEEDED. Điều này gộp hai thời điểm khác nhau và trái transition được duyệt.

Đã lưu **nguyên byte** `tests/test_phase6_acceptance.py` cũ tại `PHASE6_FIX/HISTORICAL_P6_A02/test_phase6_acceptance.py.txt`, kèm manifest SHA256; hash khớp manifest trước sửa. Toàn bộ log/JUnit/finding gốc giữ nguyên. Bản archive không nằm trong đường dẫn test discovery vì là bằng chứng, không phải một regression thứ hai; không xóa/skip/xfail ca test hiện hành.

Chỉnh chính `test_duplicate_provider_reference_cannot_poison_worker`:

1. Gửi callback receipt xung đột, xử lý inbox trước khi gửi callback hợp lệ; xác nhận UNKNOWN, REVIEW_REQUIRED, 3 holds, 0 commands.
2. Gửi callback SUCCEEDED hợp lệ, giữ các lần xử lý/restart cũ; xác nhận SUCCEEDED, inbox hết pending, vẫn 3 holds/0 commands và đúng một audit PAYMENT_SUCCEEDED.
3. Giữ regression độc lập `test_conflicting_then_valid_callback_two_distinct_decisions` kiểm replay và receipt A không bị đổi.

Không thay baseline, cấu hình, fixture để né lỗi hoặc source nghiệp vụ. Targeted mới `A02_CORRECTED_TARGETED`: **16 Passed, 20 deselected**, 29,74s. Không cộng targeted này vào full run.

### P6-A03 — Major: worker thoát sau advisory-lock timeout, chưa có tự phục hồi

Đây là kết quả phân tích/kiểm chứng mới, tách biệt với P6-A01/A02 đã sửa. Hai ca `test_lock_timeout_preserves_inbox_but_requires_worker_restart[payment/device]` dùng PostgreSQL thật: holder giữ station lock **cùng schema/cùng station** với worker subprocess, không chạy một suite khác. Không thay timeout 5s. Có callback hợp lệ pending cho Payment CREATED, session AWAITING_PAYMENT và 3 holds trước contention.

Cả Payment worker và Device worker đều exit **1**, stderr có `LockNotAvailable`. Payment chưa đổi thành công, callback chưa processed, 3 holds và 0 commands được bảo toàn. Khi thả lock và khởi chạy Payment worker thủ công, process exit0, Payment SUCCEEDED và audit thành công đúng một lần. Với nhánh device, bước phục hồi này chỉ xác minh xử lý Payment sau lock, chưa tuyên bố Device tự phục hồi.

Bằng chứng `LOCK_TIMEOUT_CHARACTERIZATION/reports/PHASE6_FIX/LOCK_TIMEOUT_payment.json` và `LOCK_TIMEOUT_device.json`; targeted **2 Passed, 23 deselected**, 21,82s. Đây là **characterization probes** xác nhận lỗi đang tồn tại và rollback/restart thủ công an toàn, không phải tiêu chí tự phục hồi Passed. Full pytest có thể xanh nhưng không đóng finding này.

Nguyên nhân: `Database` đặt lock_timeout=5000; `payment.main` và `device.main` gọi tick không catch OperationalError. `tools/dev.ps1` chạy trực tiếp worker, không có restart loop; restart policy trong Compose chỉ áp dụng container hiện có, không tự giám sát Python worker chạy ngoài. Một contention kéo dài hợp lệ có thể làm tiến trình ngừng hẳn, bỏ pending inbox/outbox cho đến can thiệp. Khóa riêng schema không giải quyết contention cùng trạm trong thực tế.

**Phân loại:** Major về khả dụng/recovery, **chặn đề xuất nghiệm thu đầy đủ Phase 6** trong cấu hình chạy hiện tại. Chưa có bằng chứng double charge, sai Payment–Reservation hoặc mất inbox (không xếp Blocker dữ liệu). Việc chạy tuần tự xử lý orchestration của test trước, không sửa lỗi vận hành này.

Hướng sửa tối thiểu đề xuất cho lượt được giao sửa: rollback transaction đã lỗi, bắt riêng lỗi DB transient phù hợp (ví dụ SQLSTATE 55P03) ở ranh giới vòng worker, retry có backoff và log không secret; giữ inbox/outbox chưa ack để retry, không giữ lock qua sleep/HTTP và không đổi provider key. Không bắt mọi exception để che lỗi vĩnh viễn. Có thể bổ sung supervisor, nhưng phải kiểm thử recovery tự động thực tế. Probe nghiệm thu cần giữ process sống hoặc tự restart sau lock release và chứng minh settle đúng một lần, không dispatch charge lặp. Chưa triển khai thay đổi worker trong lượt review này.

### Phạm vi thay đổi và bằng chứng mới

- Chỉnh `tests/test_phase6_acceptance.py` theo hai thời điểm (user đã cho phép), `tests/test_phase6_blocker_fix.py` thêm hai characterization probes và mô tả bảo toàn archive.
- Cập nhật báo cáo này và `IMPLEMENTATION_STATUS.md`; tạo archive/manifest, logs/JUnit/finding trong `A02_CORRECTED_TARGETED`, `LOCK_TIMEOUT_CHARACTERIZATION`, `FINAL_REACCEPTANCE`.
- Source bản sửa payments.py giữ nguyên như trước lượt này, không migration/dependency/Frontend mới. Build/validators/E2E vẫn là bằng chứng lịch sử đã đối chiếu, không gọi là chạy mới.
- Full pytest mới đã hoàn tất; kết quả cuối ghi bên dưới. Browser Not Run. Không commit/push hoặc Phase7. Không xóa schema, volume, ledger, file untracked hoặc bằng chứng.

### Kết quả chạy mới cuối cùng

| Nhóm | Kết quả mới | Bằng chứng |
| --- | --- | --- |
| P6-A02 và nhóm không freshness | 16 Passed, 20 deselected | A02_CORRECTED_TARGETED/results.xml |
| Probe cùng-schema lock timeout | 2 Passed, 23 deselected | LOCK_TIMEOUT_CHARACTERIZATION/results.xml; xác nhận lỗi còn tồn tại |
| **Full pytest** | **370 Passed, 0 Failed, 0 Errors, 0 Skipped**, 318,97s | FINAL_REACCEPTANCE/results.xml và run.log |
| Regression Phase 1–6 cũ | 332 Passed | Tập con full run |
| Acceptance Phase 6 sau chỉnh assertion | 13 Passed | Tập con full run |
| Regression P6-A01/A02 | 23 Passed | Tập con full run |
| Characterization P6-A03 | 2 Passed | Tập con full run, không phải tiêu chí auto-recovery đạt |
| E2E Payment/receipt/Phase5/IoT và HTTP | 12/5/8/8 và 28 Passed lịch sử | Không chạy lại trong lượt này; source nghiệp vụ không đổi |
| Validators/baseline/build/dependency | Passed lịch sử | Không chạy lại vì chỉ chỉnh test/tài liệu |
| Browser / auto-recovery sau lock timeout | Not Run / **chưa đáp ứng** | Không suy ra từ pytest xanh |

Không cộng targeted vào full hoặc cộng các tập con lần nữa. Bằng chứng full cũ 367/1 giữ nguyên. Archive test gốc khớp SHA256 trước chỉnh; 66 file bảo vệ khác không thay đổi.

**Kết luận mới nhất: P6-A01/P6-A02 đạt kiểm chứng bản sửa; chưa đề xuất nghiệm thu đầy đủ Phase6 do P6-A03 (Major) chưa được xử lý.** Không phát hiện double charge hoặc hỏng tài nguyên trong probe timeout, nhưng pending work có thể bị bỏ lại đến khi operator restart. Cần bản sửa phục hồi transient lock timeout và kiểm thử tiến trình tự tiếp tục/restart an toàn; Browser tương tác vẫn chưa kiểm chứng. Không commit/push/Phase7.

## 10. Sửa P6-A03 — phục hồi có giới hạn ở vòng worker

Theo yêu cầu tiếp theo của người dùng, sửa đúng ranh giới chạy worker, không thay State Machine/QR/Payment/provider hoặc timeout nghiệp vụ. Các kết luận P6-A03 chưa sửa ở mục9 và bằng chứng cũ vẫn được giữ nguyên.

### Nguyên nhân và phạm vi lỗi

`tick()` dùng transaction context nhưng `main()` không bắt lỗi OperationalError; 55P03 từ advisory lock làm context rollback/đóng session rồi thoát process. Đây là lỗi transient khi khóa đang do một transaction khác giữ. Không thể xem mọi OperationalError là transient: sai SQL/schema/quyền, lỗi kết nối, statement cancellation hoặc lỗi lập trình cần được báo rõ, không tự retry chung trong bản sửa này.

### Giải pháp

Thêm `services/backend/app/workers/retry.py`, dùng chung trong vòng chính của `payment.py` và `device.py`:

- Chỉ bắt SQLAlchemy OperationalError với PostgreSQL SQLSTATE **55P03**; phù hợp cả lock timeout và lock-not-available. Các lỗi khác propagate ngay.
- Tối đa **3 lần thực thi tick**, backoff **1s rồi 2s**, không busy-loop. Đây là chính sách retry kỹ thuật nội bộ, không thay approved payment/telemetry/reservation TTL hoặc DB lock_timeout5s.
- Retry nằm ngoài toàn bộ tick/session context: transaction đang lỗi đã rollback và session đóng trước sleep. Mỗi lần đọc lại công việc bền vững bằng session mới; không tự gọi lại một câu SQL trên session đã abort. Những transaction trước đó đã commit được giữ, không giả định toàn bộ tick nguyên tử.
- Log `worker_lock_retry`, `worker_lock_recovered`, `worker_lock_exhausted` gồm worker/attempt/sqlstate/delay; không log exception payload, token hoặc SQL parameters ở helper. Lỗi DB khác có `worker_db_fatal` và được raise. Không thay cơ chế traceback fatal hiện có.
- Hết budget vẫn raise và dừng có báo lỗi, bảo toàn inbox/outbox. Không có retry vô hạn hoặc supervisor tự restart mới. Khóa giải phóng trong cửa sổ retry được xử lý trong cùng process, không cần operator restart; contention kéo dài vượt budget vẫn cần xử lý vận hành.

### Bảo vệ thanh toán

Nếu timeout sau HTTP provider, claim PENDING/attempt/next_attempt_at đã commit trước HTTP. Retry tick không tạo claim/POST mới: giữ cùng payment/provider_key, chờ deadline rồi query. Settlement rollback không ghi thành công/audit một phần. Callback được processed cùng commit như trước; event đã xử lý không lặp tác động. Không giữ DB lock qua HTTP hoặc backoff. Không đổi charge intent, giải phóng tài nguyên hoặc coi timeout là FAILED.

### Regression và bằng chứng lịch sử

Archive nguyên byte `tests/test_phase6_blocker_fix.py` trước sửa ở `PHASE6_FIX/HISTORICAL_P6_A03/`, kèm SHA256. Giữ tất cả JSON/JUnit P6-A03 trước sửa. Hai characterization cũ được chuyển thành regression **persistent timeout exhausts budget**: giữ khóa đến hết budget, kiểm hai log retry, exhausted/exit1, inbox/3holds nguyên vẹn rồi phục hồi thủ công. Đây là kiểm tiêu chí dừng có giới hạn, không thay thế ca auto-recovery.

Thêm `tests/test_phase6_worker_recovery.py`:

1. Lỗi QueryCanceled/UndefinedTable không được retry (2 cases).
2. Budget đúng3 lần, sleep1/2s; helper log không lộ payload/SQL.
3. Hai subprocess Payment/Device **đồng thời cùng schema** bị holder khóa station; đợi cả hai log timeout rồi thả khóa. Không restart; cả hai exit0/recovered, callback SUCCEEDED đúng một audit, heartbeat accepted/processed, holds3/command0; replay callback không nhân side effect. Dùng --once để chứng minh cùng process hoàn tất một tick sau retry.
4. Timeout PostgreSQL thật sau provider response bằng transport fixture: claim còn PENDING, settlement/audit chưa commit; backoff xảy ra sau unwind, thả khóa; lần tiếp theo đến deadline chỉ GET cùng key. Transport fixture chỉ kiểm dispatch/query decision, không được mô tả là provider ledger E2E thật.

Targeted mới `A03_TARGETED`: **12 Passed, 18 deselected**,75,85s, bao gồm recovery tests và P6-A02/non-freshness regression. Full regression chạy tuần tự, kết quả cuối ghi sau khi hoàn tất. Chưa chạy Browser; không thay Frontend/dependency/migration/baseline. E2E lịch sử không được gọi là chạy mới.

File source thay đổi lượt này: hai worker, helper retry mới. Test: blocker_fix và worker_recovery mới. Tài liệu: báo cáo này và IMPLEMENTATION_STATUS. Source payments.py của P6-A01/A02 giữ nguyên. Không commit/push/Phase7, không xóa DB/ledger/bằng chứng.

### Kiểm chứng cuối sau P6-A03 (26/10/2026)

Full regression đã kết thúc, không phải suy ra từ tiến độ 76%: **375 Passed / 0 Failed / 0 Errors / 0 Skipped**,404,20s (`A03_FULL_REGRESSION/results.xml`). 332 ca Phase1–6 cũ +13 acceptance Phase6 hiện hành +25 blocker-fix +5 worker-recovery. Hai ca persistent contention hiện kiểm budget/exhaustion đúng yêu cầu, không còn là characterization crash ngay lần đầu. Targeted12 là một lượt riêng, không cộng lại.

Probe P6-A02 mâu thuẫn đã được người dùng cho phép điều chỉnh trước lượt P6-A03: nguyên bản vẫn ở HISTORICAL_P6_A02 với SHA256, các log367/1 không đổi. Suite hiện hành kiểm hai thời điểm, không skip/xfail test. Không được lấy full375 để viết lại kết quả lịch sử.

Payment E2E chạy mới `A03_PAYMENT_E2E`: **12 Passed**, provider/Backend/worker/callback sender thật, bao phủ timeout30s/lost-response/restart/UNKNOWN/query cùng key và freshness review. Receipt E2E chạy mới `A03_RECEIPT_E2E`: **5 Passed**, ledger bền vững, conflict reject rồi valid settle, không thu lặp. Recovery lock thực với hai worker cùng schema được kiểm trong targeted/full; E2E provider dùng scenario hiện có, không tuyên bố đã crash tại mọi instruction boundary.

Validators chạy mới `A03_CONTRACTS.json`: OpenAPI/approved JSON Schema/278 SQL statements/baseline hashes Passed. `pip check`, `npm ls --depth=0`, TypeScript/Vite build chạy lại Passed (82 modules). Không dependency mới. Browser không chạy trong lượt này; chưa thay frontend. Các kết quả IoT/Phase5/HTTP mới được bổ sung khi từng tiến trình kết thúc.

### Bảng bàn giao cuối P6-A01/P6-A02/P6-A03

Tất cả các lượt dưới đây chạy **sau bản sửa P6-A03**, tuần tự giữa các suite DB:

| Nhóm | Passed | Failed/Errors/Skipped | Bằng chứng |
| --- | ---: | --- | --- |
| Targeted P6-A03 và non-freshness | 12 | 0;18 deselected | A03_TARGETED/results.xml |
| Full pytest Phase1–6 | **375** | **0/0/0** | A03_FULL_REGRESSION/results.xml |
| Payment E2E tiến trình thật | 12 | 0 | A03_PAYMENT_E2E |
| Receipt-conflict E2E | 5 | 0 | A03_RECEIPT_E2E |
| IoT E2E | 8 | 0 | A03_IOT_E2E; phase4_e2e_dca8098e37 |
| Phase5 E2E | 8 | 0 | A03_PHASE5_HTTP; phase5_e2e_e59f9ce795 |
| HTTP smoke | 28 | 0 | A03_PHASE5_HTTP/reports/PHASE5_HTTP_SMOKE_RESULTS.json |
| Validators + baseline hashes | Passed | 0 | A03_CONTRACTS.json |
| pip check/npm dependencies/TypeScript/Vite | Passed | 0 | Lệnh chạy mới trong lượt bàn giao |
| Browser E2E | Not Run | — | Không lấy kết quả API thay Browser |

Không cộng các lượt targeted/E2E vào375. E2E dùng schema/ledger riêng, fingerprint demo trước/sau theo script không đổi; child processes test được dừng bởi finally. Không kill dịch vụ demo. 375 không bao gồm archive historical test như một test thứ hai; ca P6-A02 hiện hành đã chỉnh theo phê duyệt, không bỏ hoặc xfail ca đó.

**Kết luận:** P6-A01, P6-A02 và P6-A03 đã được khắc phục và đạt kiểm chứng kỹ thuật trong phạm vi mô phỏng đã giao. Không còn blocker nghiệp vụ được xác nhận qua các kiểm thử này. Đề xuất người dùng nghiệm thu bản sửa Phase6; không tuyên bố toàn bộ Browser/độ bền production đã Passed và không tự chuyển Phase7. Contention vượt3 lần hoặc lỗi DB không55P03 vẫn dừng có log, cần operator xử lý/restart; đây là giới hạn fail-closed đã chủ động thiết kế/kiểm thử, không retry vô hạn. Chưa thử tải dài hạn, supervisor production, mọi crash boundary hoặc phần cứng thật.

### Lệnh chạy mới và file bàn giao

```powershell
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_TARGETED pytest tests/test_phase6_worker_recovery.py tests/test_phase6_blocker_fix.py -k 'not freshness'
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_FULL_REGRESSION pytest
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_PAYMENT_E2E script tools/smoke_phase6.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_RECEIPT_E2E script tools/smoke_phase6_fix.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_IOT_E2E script tools/smoke_phase4.py
.\.venv\Scripts\python.exe tools/run_phase6_fix.py A03_PHASE5_HTTP script tools/smoke_phase5.py --http-smoke
.\.venv\Scripts\python.exe tools/validate_contracts.py docs/PHASE6_FIX/A03_CONTRACTS.json
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix apps/web ls --depth=0
npm.cmd --prefix apps/web run build
```

Các label trên đã tồn tại; khi chạy lại dùng label mới để không ghi đè bằng chứng.

Giữ làm regression: `tests/test_phase6_worker_recovery.py`, `test_phase6_blocker_fix.py`, acceptance hai thời điểm và các runner cần thiết. Giữ source `workers/retry.py`, hai worker đã tích hợp, payments.py bản sửa trước; giữ báo cáo/tiến độ. Không migration/dependency/API/State Machine mới. Archive `HISTORICAL_P6_A03` chứa bản test trước sửa và manifest; các kết quả FAILED trước đây không bị thay bằng kết quả mới.

Dung lượng tổng đo cuối lượt: docs/PHASE6_FIX khoảng0,24MiB, .cache152,58MiB, .local50,91MiB, apps/web/dist0,28MiB (không phải dung lượng tăng riêng lượt này; DB/VHDX chưa đo). Cache/build có thể tạo lại; chỉ cân nhắc dọn sau nghiệm thu. Không tự xóa log/JUnit/evidence, `.local`/provider ledger, schemas, volume, .env hoặc source.

Git HEAD81a8acd, main ahead origin/main1. Working tree chưa sạch có source/test/docs/bằng chứng đã biết; không staged/commit/push. `git diff --check` Passed, chỉ cảnh báo CRLF của Git. Cần người dùng duyệt trước commit.

## 11. Chốt nghiệm thu và chọn commit

Người dùng đã đồng ý nghiệm thu phạm vi kỹ thuật đã kiểm chứng và yêu cầu commit `fix: harden payment evidence callbacks and worker retries`. Xem `PHASE6_FIX/COMMIT_EVIDENCE.md` để đối chiếu375 ca, SHA256 artifact cuối, archive probe gốc và danh sách bằng chứng cần giữ. Không sửa source/test trong bước chuẩn bị commit; không chạy lại các suite đã có bằng chứng đầy đủ. Browser vẫn NotRun. Các câu chưa được phép commit ở trên là lịch sử trước phê duyệt mới. Commit chỉ chọn source, regression/runner, báo cáo và bằng chứng gốc tối thiểu; raw logs/XML/report trùng vẫn giữ local, không tự xóa.
