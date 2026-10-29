# P7-A01 — kiểm deadline tại quyết định custody

Ngày 28/10/2026. HEAD nền `81ade593182bb2830b87d2059707da05a2717149`. Không commit/push. Báo cáo nghiệm thu gốc `PHASE7_ACCEPTANCE.md`, hai probe gốc và các log trước sửa được giữ nguyên.

## Nguyên nhân và phạm vi sửa

AD-02b, SM-03a/03b, INVARIANTS §4–6: FR11/UC10/TC11, BR04/05/06 và nhánh timeout FR12/TC12. Hợp đồng thời gian đã được người dùng duyệt: ACK trong 15 giây; sau ACK hợp lệ, physical deadline 60 giây **từ command.created_at**; evidence freshness tối đa 15 giây. Đúng deadline là hết hạn. Ba điều kiện độc lập.

`workers/device.py::command_event` kiểm deadline trước khi xác nhận chuỗi evidence. Sau đó `application/swaps.py::advance` còn đọc DB, kiểm custody/BMS/cửa và cập nhật pin. `proof`/`physical_context` kiểm lại freshness nhưng trước sửa không kiểm physical deadline. Khóa bảo vệ trạng thái, không ngăn đồng hồ trôi. Vì vậy command được chấp nhận ở bước trước nhưng custody có thể quyết định sau hạn khi evidence vẫn mới.

Bản sửa nghiệp vụ chỉ trong `services/backend/app/application/swaps.py`:

- `physical_context` dùng cùng một clock sample UTC sau toàn bộ lượt đọc DB để kiểm cả freshness và `now < command.created_at + policy_snapshot.physical_step_timeout_seconds`.
- Cả return và pickup dùng guard này ở cuối điều kiện, ngay trước cập nhật custody. Đọc closing event phục vụ transition được chuyển lên trước guard; không còn đọc evidence sau khi đã ghi pin.
- Guard chạy dưới khóa station → user → swap → compartments → batteries hiện có. Không có HTTP, chờ khách hoặc provider sau guard. Các SQL write custody/state/audit/release vẫn nằm trong một transaction; lỗi rollback toàn bộ.
- Quá hạn đi nhánh `SWAP_RETURN_EVIDENCE`/`SWAP_PICKUP_EVIDENCE` → `REVIEW_REQUIRED` hiện có. Giữ ba holds, Payment SUCCEEDED, last-known custody, accepted inbox/command evidence; không ghi audit RETURN_ACCEPTED/COMPLETED giả, không tạo lệnh tiếp theo.
- Evidence có thể đã accepted và command OBSERVED nhưng **không đủ điều kiện chuyển custody tại thời điểm quyết định**. Không sửa bằng chứng thành chưa quan sát và không tự hoàn tiền/đối soát.

Không thay ACK handling, ordering/boot/sequence, TTL, BMS, PostgreSQL lock timeout/retry, API hoặc enum. Return dùng deadline OPEN_RETURN; pickup dùng OPEN_SUPPLY, không cộng lại từ ACK/retry/restart. Không migration/dependency/seed/demo change. Clock production là UTC hiện tại (`identity.utcnow`), không phải PostgreSQL transaction-start `now()`. Đây là kiểm tra tại điểm quyết định dưới khóa, không cam kết thời điểm commit hệ điều hành tuyệt đối trước deadline.

## Bằng chứng gốc

`tests/test_phase7_acceptance.py::test_physical_deadline_rechecked_at_custody[return/pickup]` không sửa expected result, không skip/xfail.

- Trước sửa: `PHASE7_TESTS/independent_deadline_02`: 18 Passed, 2 Failed. Return đổi CUSTOMER→COMPARTMENT/RETURN_ACCEPTED; pickup đổi COMPARTMENT→CUSTOMER/COMPLETED khi service clock đã ở created+61 giây.
- Lượt mới `p7a01_original_01`: 1 Passed, 19 setup Errors vì sandbox từ chối kết nối 127.0.0.1:5432; không phải kết quả nghiệp vụ.
- Chạy lại ngoài sandbox `p7a01_original_02`: 20 Passed, 0 Failed (2 probe nguyên bản +18 Phase7).

## Regression mới

`tests/test_phase7_deadline.py` có 20 ca tham số hóa trên PostgreSQL cô lập:

| Test | Ca | Bảo vệ |
|---|---:|---|
| `test_custody_deadline_boundary_and_replay` |8|Return/pickup tại 59.999999 /60 /60.000001 /61 giây; inbox accepted, command OBSERVED; custody/holds/audit/Payment và replay|
| `test_freshness_still_required_inside_physical_window` |2|Evidence >15 giây bị từ chối dù command chưa 60 giây|
| `test_deadline_crossed_during_final_evidence_read` |2|Clock tăng từ 59 lên60 trong lúc đọc observation; guard đầu hàm không đủ|
| `test_review_failure_rolls_back_inbox_then_retry_after_deadline` |2|Lỗi audit review rollback inbox/projection/custody; retry giữ an toàn|
| `test_persisted_observed_command_resumed_after_deadline` |2|Resume transaction từ evidence bền vững không kéo dài command deadline|
| `test_two_event_workers_at_expired_custody_decision` |2|Hai kết nối PG cạnh tranh cùng closing event; chỉ một review audit, không custody/release|
| `test_timeout_worker_races_closing_evidence` |2|Timeout và evidence cạnh tranh trên shared station lock; cả hai thứ tự đều không bàn giao sai|

`p7a01_boundary_01`: 16 Passed ở lần đầu, trước khi thêm 4 ca đọc-trễ và race timeout. `p7a01_targeted_02`: 40 Passed/0 Failed =20 ca mới +2 probes gốc +18 Phase7. Không cộng các lượt targeted vào full suite.

## E2E thời gian thực

Runner mới `tools/smoke_phase7_deadline.py`: API và child evidence worker là tiến trình riêng, PostgreSQL schema riêng, HTTP xác thực, thời gian thật. Command không bị sửa created_at/expires_at; policy60/15 giữ nguyên. Script gửi snapshot/BMS mô phỏng hợp lệ để giữ evidence mới, đợi command gần hạn rồi tiêm một lượt đọc evidence chậm **chỉ trong child worker kiểm thử**. Không patch clock hoặc logic expected result. Sau sleep guard thật quyết định. Script dừng đúng các process do mình tạo, giữ schema/log.

`p7a01_realtime_return_01`: Passed; elapsed60.349633s, evidence age tối đa7.152419s. PostgreSQL+HTTP xác nhận REVIEW_REQUIRED, custody không đổi,3holds, Payment không đổi, không success audit/lệnh thêm, replay an toàn. Fingerprint demo không đổi.

Giới hạn: runner deadline dùng transport mock đã xác minh cho bước Payment setup và emitter HTTP fixture, không tự nhận đây là E2E provider/simulator đầy đủ. E2E Phase7 hiện có là kiểm tra tích hợp bổ sung riêng. Các ca cạnh tranh mới dùng kết nối PostgreSQL độc lập trong threads; không gọi chúng là hai Backend OS process.

## Kiểm chứng cuối — tiếp tục sau gián đoạn

Kiểm tra đầu lượt: không còn process Python/pytest; `p7a01_full_01/run.log` dừng giữa suite, chưa có results.xml. Không coi là Passed. Giữ nguyên bằng chứng bị ngắt và chạy lại với label mới. HEAD vẫn81ade59, source/test không sửa thêm trong lượt tiếp tục.

| Lượt | Passed | Failed | Errors | Skipped | Exit | Thời gian |
|---|---:|---:|---:|---:|---:|---|
| p7a01_full_01 |Chưa có kết quả cuối|—|—|—|Không thu được|Bị ngắt, thiếu XML|
| p7a01_full_02 |24|0|391|0|1|180.38s; Docker chưa chạy, lỗi setup PG|
| p7a01_full_03 |415|0|0|0|0|910.56s (JUnit910.566s)|

Full cuối: `docs/PHASE7_TESTS/p7a01_full_03/run.log` và `results.xml`, đã đối chiếu cả summary và thuộc tính JUnit. 415 =393 regression hiện có +2 probe gốc +20 deadline tests. Không cộng targeted40 hoặc các lượt chạy lỗi vào tổng này. Bao gồm P6-A01/A02/A03, BMS/door ordering và Phase1–7. Hai warnings là deprecation của thư viện, không skip/xfail. Docker Desktop hiện có được mở lại; giữ container/volume, không cài mới/reset.

E2E cấp pin chạy mới `p7a01_realtime_pickup_01`: **Passed, exit0**. Command thực tế tên `OPEN_SUPPLY` (không có enum OPEN_PICKUP). Quyết định sau60.428641s, evidence age tối đa7.228998s. API/PG: REVIEW_REQUIRED, không COMPLETED/closed_at, pin cấp vẫn ở ngăn, pin trả đã nhận trước đó được giữ,3holds, Payment SUCCEEDED không đổi, không audit hoàn tất/lệnh thêm. Replay và gọi lại service không gia hạn deadline. Fingerprint demo không đổi. Log/timing ở `.cache/p7-deadline-a668030786`, báo cáo JSON riêng dưới thư mục lượt chạy. E2E trả pin `p7a01_realtime_return_01` Passed được kế thừa từ lượt sửa trước, không chạy lại hoặc ghi đè.

OpenAPI/approved JSON Schema/SQL278 statements/baseline hashes: Passed (`p7a01_VALIDATION.json`), `pip check` và TypeScript `tsc --noEmit` + Vite build Passed: kết quả lượt sửa trước đã kiểm tra lại bằng chứng/ngữ cảnh, không tuyên bố chạy mới ở lượt tiếp tục. Browser mới: **Not Run**. E2E đầy đủ provider + hai simulator sau sửa: **Not Run**; không dùng E2E triển khai trước sửa để thay thế. E2E deadline đã chạy API + child evidence worker riêng với transport Payment/emitter fixture như mô tả trên.

Sau guard cuối chỉ còn các SQL write dưới khóa; không thêm external I/O. Guard xác định tính hợp lệ tại điểm quyết định, không bảo đảm transaction commit trước60s: scheduling hoặc DB writes vẫn có thể kéo commit qua mốc. Đó là giới hạn được nêu rõ, không gia hạn điều kiện hoặc coi thời gian nhận evidence là thời gian quyết định. Lỗi write rollback giữ tính nguyên tử; nếu phát hiện yêu cầu commit-before-deadline tuyệt đối cần đối chiếu hợp đồng riêng trước khi đổi policy.

**P7-A01 đạt kiểm chứng bản sửa và đủ điều kiện TIẾP TỤC nghiệm thu độc lập.** Chưa có blocker mới được xác nhận trong các kiểm tra này; không kết luận toàn bộ Phase7 đạt nghiệm thu. Ma trận độc lập còn thiếu Browser, review/integration và các crash/process cases rộng hơn vẫn theo báo cáo nghiệm thu gốc. Không commit/push/Phase8.

Lệnh lượt tiếp tục: `git status -sb`, `git diff`, `git diff --check`, kiểm tra process/log/JUnit; runner `TEST_REPORT_ROOT=PHASE7_TESTS python tools/run_phase6_fix.py p7a01_full_03 pytest tests`; `... p7a01_realtime_pickup_01 script tools/smoke_phase7_deadline.py --step pickup`. Không thay script hoặc fixture để làm Passed.

## File và tài nguyên

- Giữ source sửa `application/swaps.py`, regression mới `tests/test_phase7_deadline.py`, runner `tools/smoke_phase7_deadline.py`, báo cáo này và cập nhật tiến độ.
- Giữ nguyên `tests/test_phase7_acceptance.py`, `PHASE7_ACCEPTANCE.md`, `independent_deadline_01/02` và mọi log/XML trước sửa.
- `docs/PHASE7_TESTS/p7a01_*`: bằng chứng chạy mới, giữ đến nghiệm thu. `.cache/p7-deadline-*` chứa process logs/timing; chưa tự dọn. Những cache cũ có thể chứa credentials fixture nên không commit hàng loạt.
- `.local`, provider/command ledgers, PostgreSQL schemas/volume, `.vs`, `.env` và mọi untracked cũ được giữ. Không có lệnh reset/clean/drop/delete. Cache/build chỉ là ứng viên dọn sau khi người dùng duyệt, không tự xóa bằng chứng.

Chưa kết luận Phase7 đã nghiệm thu toàn bộ. Sau khi kiểm chứng bản sửa sẽ bàn giao để tiếp tục cuộc nghiệm thu độc lập còn thiếu; không triển khai Phase8.
