# Sửa và nghiệm thu P4-A01 – BMS telemetry đến muộn

Ngày 24/10/2026 (Asia/Bangkok). Base `main@a8a1d48`. Bản sửa ở working tree, chưa stage/commit/push. Lượt tiếp tục sau usage limit chỉ đọc lại source và chạy kiểm thử; không viết lại source, test hoặc fixture đã hoàn thành.

**Kết quả: hai probe tái hiện lỗi đã Passed; toàn bộ bảy probe nghiệm thu Passed.** Mẫu SOC90 đo cũ hơn bị worker từ chối với EVENT_OUT_OF_ORDER, không thay mẫu SOC10 mới hơn, availability giữ false. Toàn bộ regression sau sửa trước gián đoạn có 175 Passed; lượt tiếp tục chạy lại 2 probe mục tiêu, 7 probe nghiệm thu, 21 ca timestamp và 8 checks E2E thật, tất cả Passed.

## 1. Trạng thái Git và bốn file đã kiểm tra lại

Lúc tiếp tục, Git HEAD vẫn là a8a1d48. `git diff` có ba file tracked: hai source bên dưới và IMPLEMENTATION_STATUS.md (ghi nhận blocker từ lượt nghiệm thu). Các báo cáo/nghiệm thu/test mới vẫn untracked; không giả định tất cả untracked đều phát sinh trong lượt sửa này.

| File trực tiếp liên quan đã rà soát | Thay đổi thực tế đã lưu trước gián đoạn |
| --- | --- |
| services/backend/app/workers/device.py | Thêm 5 dòng kiểm mốc thời điểm đo trước khi insert telemetry |
| services/backend/app/application/assets.py | Thêm helper đọc max thời điểm đo accepted và guard availability cho dữ liệu lịch sử sai thứ tự; thêm func import |
| tests/test_phase4_bms_ordering.py | File kiểm thử mới: 21 ca timestamp/sequence/boot/atomic evidence/legacy availability |
| tests/test_phase4_acceptance.py | Giữ nguyên cả bảy probe và assertions từ nghiệm thu; không sửa để làm Passed |

Đã đọc lại AGENTS, START_HERE, HANDOFF, approved decisions/config, PHASE4_IMPLEMENTATION, PHASE4_ACCEPTANCE, IMPLEMENTATION_STATUS, OpenAPI/schema/invariants, SM-01/02, worker/availability và tests Phase 3–4. Không chỉnh baseline/hợp đồng. Trong baseline nhóm IoT là F7 (FR17/UC15/TC17); cách gọi Phase 4 theo yêu cầu người dùng không đổi mã baseline. Liên quan FR07/UC07/TC07, CT09, BR02/BR10/BR11.

RESUME_INPUT_HASHES.json ghi hash bốn file trên và bản lỗi gốc. Đối chiếu cuối nghiệm thu khớp, chứng minh lượt tiếp tục không sửa source/test/fixture hoặc bằng chứng lỗi.

## 2. Nguyên nhân gốc và ngữ nghĩa thời gian

| Trường | Nghĩa theo hợp đồng/implementation |
| --- | --- |
| DeviceEvent.observed_at | Timestamp tại thiết bị; với TELEMETRY là thời điểm đo BMS được gửi trong envelope |
| battery_telemetry.measured_at | Thời gian đo, được chép từ TELEMETRY observed_at; payload không có measurement timestamp thứ hai |
| device_events.received_at / battery_telemetry.received_at | Thời gian Backend nhận event; là cơ sở TTL tiếp nhận, không chứng minh phép đo mới hơn |
| device_events.processed_at | Thời gian worker xử lý; không dùng thay thời gian đo |
| boot_id + seq | Thứ tự event trong một boot; seq cao hơn không chứng minh đo BMS muộn hơn |

Trước sửa, worker kiểm đúng schema, freshness/future và seq lớn hơn last_seq, nhưng không so thời điểm đo với mẫu đã chấp nhận của pin. Mẫu cũ vẫn trong TTL và seq cao đi qua tất cả guard. API chọn mẫu theo received_at mới nhất nên mẫu đo cũ đến sau trở thành mẫu đánh giá, gây SOC10→SOC90 và false→true sai quy tắc.

Không sửa định nghĩa trường, không đổi thứ tự lịch sử API, không thay received_at bằng measured_at để tính TTL. Thay đổi là thêm điều kiện thứ tự đo độc lập với điều kiện thứ tự event.

## 3. Cách sửa

`latest_accepted_measurement()` lấy max measured_at của đúng battery_id, chỉ từ TELEMETRY có event accepted=true và processed_at khác null. Không lọc quality_ok: một mẫu mới thiếu/lỗi vẫn phải ngăn mẫu cũ tốt quay lại. Không lấy seed chưa xác minh, event bị reject hoặc chưa xử lý làm mốc. Mốc đo dùng xuyên boot vì timestamp đo là thời gian tuyệt đối; reconnect không làm mất lịch sử đo của pin.

Worker giữ các guard seq/freshness/boot/scope trước đó. Trong transaction đang có station/pin locks, trước khi ghi battery_telemetry:

- observed_at > mốc đo: có thể tiếp tục các kiểm tra BMS hiện có.
- observed_at <= mốc đo: DomainError EVENT_OUT_OF_ORDER, không ghi mẫu BMS/projection.
- Cùng event ID và nguyên body: idempotent receipt cũ, không qua insert/worker một lần nữa.
- ID cũ/body khác hoặc ID khác/cùng boot-seq: các 409 EVENT_ID_CONFLICT/EVENT_SEQUENCE_CONFLICT cũ vẫn giữ.
- Sequence thấp dù timestamp mới: vẫn EVENT_OUT_OF_ORDER theo guard transport hiện có.

**Điểm hợp đồng chưa nêu rõ:** tie-break giữa hai event ID khác nhau có timestamp đo bằng nhau. Bản sửa không coi seq tăng là bằng chứng của phép đo mới: event mới có cùng thời điểm đo bị reject, không thay mẫu hoặc gia hạn freshness. Hai representation timezone khác nhau nhưng cùng instant cũng bằng nhau. Retry nguyên event vẫn trả receipt cũ. Đây là lựa chọn bảo thủ được ghi rõ, không sửa baseline hoặc tự thêm trường timestamp/role/state.

Khi reject, savepoint rollback cập nhật nghiệp vụ rồi transaction ghi processed_at, accepted=false, processing_error và audit DEVICE_EVENT_PROCESSED. HTTP đầu tiên vẫn202/QUEUED theo hợp đồng inbox; gửi lại nguyên body nhận202/REJECTED/duplicate=true. EVENT_OUT_OF_ORDER là reason trong DB/audit, không tự đổi API bất đồng bộ thành HTTP422 tại thời điểm worker xử lý.

Guard đọc `quality()` còn kiểm mẫu được chọn theo received_at không cũ hơn mốc đo accepted. Điều này chặn dữ liệu lịch sử từng bị phiên bản cũ chấp nhận sai. Không xóa/sửa lịch sử, không fallback sang mẫu tốt cũ, không nâng quality của seed, không tự phục hồi lifecycle. Một mẫu đo mới thực sự vẫn được đánh giá qua toàn bộ quy tắc Phase 3.

## 4. Trước/sau sửa và bằng chứng

Các artifact trong `docs/PHASE4_BMS_FIX/`:

| Lượt chạy | Kết quả | Bằng chứng |
| --- | --- | --- |
| BEFORE, trước thay source | 2 Failed, 5 deselected; lỗi được tái hiện lại | BEFORE.xml/log, BEFORE_LATE_TELEMETRY_FINDING.json |
| TARGETED sau sửa, trước gián đoạn | 2 Passed | TARGETED.xml |
| ACCEPTANCE sau sửa, trước gián đoạn | 7 Passed | ACCEPTANCE.xml |
| BOUNDARIES trước gián đoạn | 21 Passed | BOUNDARIES.xml |
| Toàn bộ regression sau sửa, trước gián đoạn | **175 Passed, 0 Failed/Skipped**, 67.55s | REGRESSION.xml/log |
| RESUME_TARGETED lúc tiếp tục | **2 Passed**, 5 deselected | RESUME_TARGETED.xml |
| RESUME_ACCEPTANCE lúc tiếp tục | **7 Passed** | RESUME_ACCEPTANCE.xml |
| RESUME_BOUNDARIES lúc tiếp tục | **21 Passed** | RESUME_BOUNDARIES.xml |
| E2E sau sửa, hoàn tất lúc tiếp tục | **8 checks Passed** | RESUME_E2E_PHASE4_E2E_RESULTS.json/log |
| OpenAPI/approved JSON Schema/SQL/hash baseline | Passed trước gián đoạn; 278 statements parse | CONTRACTS.json |
| pip check | Passed trước gián đoạn, không broken requirements | Tool output của lượt sửa |
| TypeScript + Vite | Passed trước gián đoạn, 31 modules, JS250.26kB | Tool output của lượt sửa; không đổi Frontend |
| Browser/real hardware/full swap | Not Run trong lượt sửa/tiếp tục; ngoài tác động bản sửa Backend | Không lấy ảnh nghiệm thu cũ làm chứng cứ mới |

175 ca phân biệt = 18 Phase1 + 37 Phase2 + 48 Phase3 + 44 Phase4 + 7 acceptance + 21 ordering. Các lần chạy mục tiêu là tập con, không cộng lặp vào tổng 175. Regression toàn bộ/build không chạy lại lần nữa sau resume vì hash source/test giữ nguyên; báo cáo rõ chúng đã thực sự hoàn tất trước gián đoạn.

Hai probe gốc không thay đổi:

- `test_acceptance_late_telemetry_never_replaces_newer_measurement[older_measurement]`.
- `test_acceptance_older_good_soc_cannot_override_newer_low_soc`.

RESUME_ACCEPTANCE_LATE_TELEMETRY_FINDING.json: seq5 SOC10 có observed_at mới hơn; seq6 SOC90 đo cũ hơn bị accepted=false, processing_error=EVENT_OUT_OF_ORDER; latest_api_reading vẫn SOC10, before_available=false, after_available=false. Dữ liệu fixture rollback sau test, không kỳ vọng các row đó tồn tại khi truy vấn schema sau test.

21 ca bổ sung kiểm: seq cao/thời gian thấp; seq thấp/thời gian cao; thời gian bằng nhau với số đo giống/khác; mới hơn1µs; TTL đúng15s/±1µs và future1µs; timestamp thiếu/null/invalid/naive/sai kiểu; UTC và UTC+7 cùng instant; mốc đo qua restart; tách từng pin và heartbeat; quality_ok=false vẫn tạo mốc; seed chưa xác minh không tạo mốc; historical accepted row sai thứ tự không làm pin khả dụng. Ca atomic so sánh nguyên các row devices/batteries/compartments và danh sách telemetry trước/sau reject; audit đúng một lần cả khi retry.

E2E giữ nguyên helper `tools/smoke_phase4.py`: hai simulator thật, HTTP API và worker độc lập trong `phase4_e2e_b7484a3d8d`; ACK không mở cửa/custody, NACK, command timeout, heartbeat timeout15s thực, reboot/ledger, hot→quarantine và good không tự restore. Fingerprint tám bảng demo chính trước/sau khớp. Không khởi simulator trên doi_pin, không reset volume. E2E này kiểm hồi quy tích hợp; tình huống P4-A01 cụ thể được kiểm qua FastAPI/TestClient + worker + PostgreSQL trong probe, không tuyên bố đã có HTTP socket E2E riêng cho mọi biến thể timestamp.

## 5. Database, trạng thái triển khai và giới hạn

**Không cần migration**: dùng cột/index hiện có, Alembic head vẫn0002_user_approval. Các test tạo schema mới và kiểm empty/upgrade/repeated upgrade/seed, không chạy lại DDL gốc trên demo. Không update hoặc dọn dữ liệu demo để xử lý row lịch sử; guard đọc từ chối đánh giá khả dụng khi phát hiện mẫu lịch sử đến muộn.

Giới hạn còn lại:

- Timestamp bằng nhau ở event mới bị từ chối; nếu sau này nguồn phần cứng có độ phân giải timestamp thấp/clock reset cần quy định tích hợp riêng. MVP hiện tại dùng UTC của simulator; không giả clock synchronization phần cứng thật.
- Bản sửa chỉ ở working tree. Backend/worker đã chạy từ trước có thể vẫn giữ code cũ trong RAM; test tạo process/app mới đã dùng code sửa. Chưa tự restart tiến trình demo chính. Khi người dùng duyệt chạy bản sửa, khởi động lại Backend và worker hiện có.
- Còn warnings deprecation Starlette/httpx và validate_spec; không ảnh hưởng kết quả, không nâng dependency trong bản sửa này.
- Chưa kiểm Browser lại, phần cứng thật, hoàn tất custody/full swap; không suy ra từ pytest/E2E module.

P4-A01 đã được khắc phục trong phạm vi kiểm thử nêu trên. Chờ người dùng xem xét/duyệt bản sửa và quyết định commit; chưa thực hiện Phase5.

## 6. File và tài nguyên giữ lại

Source sửa: chỉ application/assets.py và workers/device.py. Test bổ sung: test_phase4_bms_ordering.py. Bảy acceptance probes giữ nguyên. Báo cáo mới này, cập nhật IMPLEMENTATION_STATUS.md và bằng chứng trong PHASE4_BMS_FIX/ ghi tiến độ; PHASE4_ACCEPTANCE.md cùng JSON lỗi gốc vẫn giữ như lịch sử trước sửa.

Runner `.cache/run_phase4_bms_fix.py` là tiện ích local đã tạo ở lượt sửa, không source nghiệp vụ: ghi kết quả riêng rồi phục hồi byte các report cũ mà helper gốc tự ghi. Chạy lại bằng:

```powershell
.\.venv\Scripts\python.exe .cache/run_phase4_bms_fix.py RECHECK_TARGETED tests/test_phase4_acceptance.py -k 'older_measurement or older_good_soc'
.\.venv\Scripts\python.exe .cache/run_phase4_bms_fix.py RECHECK_ACCEPTANCE tests/test_phase4_acceptance.py
.\.venv\Scripts\python.exe .cache/run_phase4_bms_fix.py RECHECK_BOUNDARIES tests/test_phase4_bms_ordering.py
.\.venv\Scripts\python.exe .cache/run_phase4_bms_fix.py RECHECK_ALL
.\.venv\Scripts\python.exe .cache/run_phase4_bms_fix.py RECHECK_E2E --e2e
```

Mỗi lần dùng label mới nếu muốn giữ toàn bộ bằng chứng. Không chạy song song các runner vì helper hiện tại ghi cùng report trung gian. Lệnh E2E cần port8002 rảnh, tự dừng những process nó tạo khi xong.

Nên giữ test, JUnit/log/finding và report trước/sau. `.cache/bms-fix-*` là temp kiểm thử, có ledger test; chỉ cân nhắc dọn khi đã lưu bằng chứng và người dùng đồng ý. `.local/phase4_e2e_b7484a3d8d/` là command ledger, giữ cùng schema E2E; không xóa `.local`, schema hay volume. Không tải dependency/image mới, không tạo bản sao dự án. Dung lượng đo cuối ghi ở PHASE4_BMS_FIX/DISK_USAGE.json.
