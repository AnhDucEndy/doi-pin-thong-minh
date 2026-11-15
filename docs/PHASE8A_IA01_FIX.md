# P8A-IA01 fix — checkpoint 14/11/2026

## Final full regression 15/11/2026 — COMPLETE, exit 0

**FULL BACKEND REGRESSION GATE PASSED trên source IA01 cuối.** P8A-IA01 đã đủ các verification gates sửa lỗi trong phạm vi đã kiểm chứng: final targeted 6 Passed, real-process T/E/K exit 0, Browser affected 6 Passed và full Backend mới **599 Passed, 0 Failed, 0 Errors, 0 Skipped, exit 0**. Đây không phải Independent Acceptance lần hai và không chuyển kết luận lịch sử hoặc toàn Phase 8A thành Acceptance PASS.

### Hai lượt full được ghi riêng

| Lượt | Kết quả | Bằng chứng |
|---|---|---|
| `ia01_full_20261115_01` | **Interrupted**; không có JUnit/exit cuối. Không suy số Passed từ progress | [Log cũ giữ nguyên](PHASE8A_TESTS/ia01_full_20261115_01/run.log); shutdown User32 1074 lúc 01:16:25 đã ghi trong checkpoint bên dưới |
| `ia01_full_20261115_02` | **599 Passed / 0 Failed / 0 Errors / 0 Skipped; exit 0** | [Full log](PHASE8A_TESTS/ia01_full_20261115_02/run.log), [JUnit 599 testcase](PHASE8A_TESTS/ia01_full_20261115_02/results.xml), [exit/timestamps](PHASE8A_TESTS/ia01_full_preflight_20261115_02/exit.json), [đối chiếu](PHASE8A_TESTS/ia01_full_preflight_20261115_02/verification.json) |

Run 02 bắt đầu **11:20:51.047 +07**, kết thúc **12:10:06.452 +07** ngày 15/11/2026. Pytest báo **2947.95 giây (49:07.95)**; JUnit time 2947.936 giây. Wall time của wrapper khoảng **49:15.405**, gồm khởi tạo/thoát interpreter. Chạy một full suite qua PowerShell độc lập ẩn với log/exit bền vững, không `--lf`, không deselect/skip/xfail để ép kết quả. Người dùng đã xác nhận giữ máy hoạt động 60–75 phút. Wrapper dùng execution-state tạm thời của thread; không thay power plan/registry/Update/driver và không bảo vệ được explicit shutdown.

### Collection và source freeze

- Đối chiếu toàn bộ testcase JUnit với [collection 599](PHASE8A_TESTS/ia01_collection_20261115_01/run.log) bằng multiset node IDs, chỉ chuẩn hóa UUID ngẫu nhiên của tham số: **missing=0, unexpected=0**.
- So collection 587 lịch sử: **missing=0, added=12** (6 IA01 + 6 operator). Danh sách delta nằm trong verification JSON; không cộng các lượt targeted/E2E/Browser vào 599.
- 175 file trong freeze đã khớp checkpoint `ia01_environment_20261115_01/source_after.json` trước chạy, và **delta=0** sau chạy. [Before](PHASE8A_TESTS/ia01_full_preflight_20261115_02/source_before.json) / [After](PHASE8A_TESTS/ia01_full_preflight_20261115_02/source_after.json) có cùng SHA256 manifest: `1CEFEA6171294602071648C055B32211088B047AD3B093D6F4FE649308FC5A9D`.
- Không sửa production, test assertions, migrations hoặc overlays trong lượt này. Không chạy lại T/E/K, final targeted hoặc 6 Browser scenarios vì source liên quan không đổi và checkpoints exit 0 còn hợp lệ.

### Môi trường, warnings và dữ liệu

Preflight có ba mẫu Engine **29.9.2**, PostgreSQL healthy, cùng StartedAt `2026-11-15T04:16:10.917567377Z`, RestartCount 0, `pg_isready` và runtime `SELECT 1=1`: [readiness](PHASE8A_TESTS/ia01_full_preflight_20261115_02/readiness.json). RAM trống ban đầu khoảng 1.0–1.4 GiB, còn khoảng 4.8 GiB commit headroom và hơn 184 GB ổ C; không tự dừng ứng dụng người dùng. Khi chạy RAM khả dụng tăng; pytest process đo khoảng 257 MB. Query scheduled tasks không thấy lịch shutdown/restart cụ thể trong các task matching đã đọc; không coi đây là bảo đảm chống shutdown.

Hậu kiểm **12:11:11 +07**: healthy cùng StartedAt, runtime SELECT 1 đạt, không còn runner của lượt này, không có power events 1074/41/42/506/507/12/13 từ các provider đã query trong cửa sổ chạy; host boot vẫn 07:39:28.5. RAM trống khoảng 3.1 GiB, commit headroom khoảng 6.2 GiB. [Host hậu kiểm](PHASE8A_TESTS/ia01_full_preflight_20261115_02/host_after.json). Root cause hai bugcheck lịch sử vẫn Unknown; lượt thành công này không được dùng để tuyên bố đã chữa lỗi host.

Full run có **4 warnings**, không có unhandled-thread warning: Starlette TestClient/httpx deprecation (1), OpenAPI `validate_spec` deprecation (1), `record_property` không tương thích JUnit xunit2 ở hai diagnostic tests (2). Các testcase và counts vẫn có trong XML; diagnostic properties không được coi là evidence duy nhất. Không cài dependency để né warning.

Fixture chính dùng schema mới `phase5_test_5ffc7f268122`, PostgreSQL **17.11**; migration empty/upgrade lặp lại đạt, schema được giữ: [test environment](PHASE8A_TESTS/ia01_full_20261115_02/reports/PHASE5_TEST_ENVIRONMENT.json). Các fixture concurrency tiếp tục dùng schema cô lập theo runner hiện có. Không migration vào demo, không reset/delete schema, volume, `.local`, ledger hoặc evidence. Không đo lại demo fingerprint trong lượt full này, không thay bằng khẳng định fingerprint mới.

### Bàn giao

Lượt này chỉ thêm wrapper/verification tooling cục bộ dưới `.cache`, artifacts của label mới và cập nhật ba báo cáo. Source IA01, failing evidence/probe gốc và các lượt interrupted giữ nguyên. Git working tree vẫn dirty tích lũy, không stage/commit/push. **IA01 fix verification COMPLETE trong phạm vi này; toàn Phase 8A vẫn PARTIAL/chờ người dùng quyết định bước nghiệm thu tiếp theo**, gồm các giới hạn/NFR trong báo cáo độc lập gốc. Dừng tại đây, không Independent Acceptance lần hai hoặc Phase 8B/8C.

Git cuối lúc12:13:17: `main...origin/main`, HEAD `e4fb9f5`, ahead/behind0/0, **15 tracked modifications, 912 untracked files, staged0**; `git diff --check` exit0. [Git snapshot đã hiệu chỉnh bộ đếm](PHASE8A_TESTS/ia01_full_preflight_20261115_02/git_final_corrected.json). Snapshot sơ bộ `git_final.json` đã đếm nhầm do wildcard `??` của PowerShell; chỉ số phân loại file ở đó được thay thế bằng snapshot này, giữ bản sơ bộ để truy vết. Lỗi bộ đếm không liên quan pytest, JUnit, collection hoặc hash validation. Không tự dọn `.cache`, build outputs, logs, schemas, ledger hay evidence; việc dọn chỉ xét ở lượt riêng sau khi người dùng phê duyệt.

## Resume 15/11/2026 — K/Browser đạt, full regression Interrupted

**Implementation vẫn IMPLEMENTED; verification PARTIAL / ENVIRONMENT BLOCKED.** Không Independent Acceptance lần hai hoặc đóng Major từ targeted. Source production IA01 giữ nguyên; 175 file freeze được đối chiếu trước và sau lượt, delta=0 theo freeze mới của lượt này. So checkpoint 14/11, chỉ mở rộng test tooling (operator REBOOT và Browser old-boot), không đổi Backend/migrations/contracts/deadlines. T/E exit0 trước đó giữ nguyên theo production snapshot và đường dispatch tương ứng; không chạy lại chúng.

### A–F: chẩn đoán có căn cứ

| Nhóm | Bằng chứng / kết luận |
|---|---|
| A Engine | Đầu lượt và sau interruption: không có pipe dockerDesktopLinuxEngine, không có Docker backend; WSL docker-desktop Stopped ở preflight. Đây là trạng thái quan sát, không suy thành lỗi source |
| B Container/PG | Mở Docker Desktop per-user bình thường, không reset: container cũ tự start/recovery, healthy; StartedAt=14/11 17:42:55Z và RestartCount0 trong ba samples. RestartCount0 không phủ nhận việc container start lại khi Engine/máy khởi động lại |
| C Execution session | Không còn runner K/full cũ tại preflight và sau interruption. Không có bằng chứng một execution-session-only failure trong khi host/Engine vẫn bình thường để giải thích các lần mất process |
| D Host / power | 14/11 Kernel-General12/Kernel-Power41/WER1001 xác nhận hai bugcheck 0x3b và 0x13a, boot21:56:54 và22:06:12. Lần sau trùng K03. Chưa xác định driver/hardware/cause gốc. Không mở/upload dump; chỉ metadata |
| D lần full mới | Full log cuối01:16:24.617; User32 1074 lúc01:16:25 ghi StartMenuExperienceHost yêu cầu power off; EventLog6006 lúc01:16:37, Kernel-General13 lúc01:16:43. Boot tiếp07:39:28. Đây là shutdown có event điều phối, **khác hai bugcheck cũ**. Modern Standby09:00:52→10:13:34 xảy ra sau full đã bị ngắt, không dùng nó giải thích lần ngắt full |
| E Connection | K02 ConnectionTimeout và FATAL starting-up phù hợp PG chưa phục hồi/Engine mất pipe; không có bằng chứng độc lập lỗi LAN/firewall riêng |
| F Unknown | Root cause hai bugcheck vẫn Unknown. Docker safe-tail còn hoạt động đến22:05:49 trước host boot22:06; không có chứng cứ quy Docker/Codex/WSL là thủ phạm. RAM/disk hiện tại không chứng minh pressure lúc crash |

Preflight đo khoảng16GB RAM tổng,5GB available/56% commit, ổC trống188GB; không thấy Resource Exhaustion2004 trong cửa sổ đã query. Đã đọc safe Docker log tail/index, System/Application events và WSL list, không đọc/copy nội dung memory dump. Không reset Docker/WSL/PG/volumes, không đổi power plan hoặc driver. Wrapper test dùng thread execution-state tạm thời rồi restore; không thể ngăn explicit power off.

[Windows events cũ](PHASE8A_TESTS/ia01_environment_20261115_01/windows_events.json), [bugcheck/resource reports](PHASE8A_TESTS/ia01_environment_20261115_01/crash_resource_events.json), [events sau full](PHASE8A_TESTS/ia01_environment_20261115_01/windows_events_after_full.json), [safe Docker tail](PHASE8A_TESTS/ia01_environment_20261115_01/docker_safe_tail.json). Raw event logs có machine/user metadata nên chỉ giữ local, không bulk commit; không có dump trong repo.

### Readiness và gates mới

Sau normal start, ba bounded samples00:46:59/00:47:11/00:47:22 đều Engine29.9.2 + container healthy cùng StartedAt + pg_isready + runtime SELECT1=1. Không runner cũ, có disk/RAM, source freeze khớp. [Readiness JSON](PHASE8A_TESTS/ia01_environment_20261115_01/readiness.json). Đây là evidence readiness trong cửa sổ đo, không tuyên bố đã chữa kernel crash.

| Gate mới trên source IA01 | Kết quả | Evidence |
|---|---|---|
| real-process K label ia01_real_K_20261115_01 | **exit0**,00:52:45 | Hai Backend OS processes, worker/operator thật; successor current proof/chain/replay; một service effect, một foreign settlement audit; protected custody/Payment/3holds giữ nguyên. Native runner JSON/log/exit, không giả tạo pytest XML cho script |
| Browser post | **1 Passed / exit0** | PRE Tech/Customer, intent/ACK/activation, HANDOVER, POST, settle/replay |
| Browser successor | **1 Passed / exit0** | Real TTL rồi successor current inspection; không physical effect thứ hai |
| Browser old-boot | **1 Passed / exit0** | Test IPC thực sự dựng Simulator boot mới trên durable ledger cũ. Accepted receipt boot cũ vẫn trong15s; Customer UNAVAILABLE/disabled, Technician click thật bị409, version/attestations không đổi |
| Browser pre-reject | **1 Passed / exit0** | REJECT giữ review, không authorization/physical effect |
| Browser revoked | **1 Passed / exit0** | Revoked session bị chặn, không confirmation POST |
| Browser stale-expired | **1 Passed / exit0** | Chờ15s/TTL thật, unavailable/expired và mutation disabled |
| Local tooling + TS | **25 Passed**, TypeScript exit0 | SQLite operator/fence/closure + typecheck riêng Playwright; không tính là PG/full/Browser |
| Collection mới | **599 tests, exit0**, removed0 | So 587 lịch sử: thêm6 IA01 (probe1+regression5) và6 operator tests được tạo sau full lịch sử; normalize riêng UUID params để so tên |
| Full ia01_full_20261115_01 | **Interrupted** | Không results.xml, không exit/batch_final; không còn process. Log qua48% rồi13 dots, chỉ progress, không là final Passed count |

Sáu Browser XML đều0 Failed/Errors/Skipped, child exit0, không cộng chung với Browser15 trước sửa Backend. [Tổng hợp Browser/DB](PHASE8A_TESTS/ia01_environment_20261115_01/browser_verified.json), [K operator summary](PHASE8A_TESTS/ia01_environment_20261115_01/K_operator_summary.json). Parent reports trong `ia01_real_K_20261115_01/reports/PHASE8A_E2E_E.json` và `ia01_browser_<scenario>_20261115_01/reports/...`; Browser XML/safe-http/screenshots/exit tại các thư mục tương ứng thêm `_browser`. Custody/Payment/holds/effects/audit lấy từ actual runner DB/ledger assertions, không SQL UPDATE proof/custody. Fingerprint demo vẫn chỉ phạm vi tám bảng của runner, không toàn Database.

Full bắt đầu file log01:07:09.525, ghi cuối01:16:24.617, không hoàn tất. Passed/Failed/Errors/Skipped **cuối cùng và exit code: Unknown**, không báo0 Failed hay301 Passed từ dots. Không dùng --lf, không skip lịch sử hoặc probe IA01. [Collection delta và12 node mới](PHASE8A_TESTS/ia01_environment_20261115_01/collection_delta.json), [collection log/XML](PHASE8A_TESTS/ia01_collection_20261115_01/run.log), [full log giữ nguyên](PHASE8A_TESTS/ia01_full_20261115_01/run.log), [final checkpoint](PHASE8A_TESTS/ia01_environment_20261115_01/final_verification.json). Một full suite hoàn chỉnh vẫn là gate bắt buộc còn thiếu.

### Thay đổi / điểm dừng

Không sửa production trong lượt resume. Test-only `tools/phase8a_manual_operator.py` thêm REBOOT IPC và `apps/web/e2e/staged.spec.ts` thêm old-boot assertions; không thêm API/enum domain hoặc công cụ Computer Use. Mọi source prod/migration/overlay khớp IA01 checkpoint; freeze mới tính cả tooling mở rộng. [Before](PHASE8A_TESTS/ia01_environment_20261115_01/source_before.json)/[after](PHASE8A_TESTS/ia01_environment_20261115_01/source_after.json) khớp175 file. Windows/context diagnostics và cache orchestration scripts được lưu; không mất K01/K02/K03/evidence trước.

Scan91 text artifacts mới không thấy password fixture/JWT; credentials/private.json và ledgers vẫn local ignored, raw traces/HAR không bật. [Scan](PHASE8A_TESTS/ia01_environment_20261115_01/security_scan.json). Working/staged diff --check đạt; HEAD e4fb9f5/index trống, [Git inventory](PHASE8A_TESTS/ia01_environment_20261115_01/git_status.txt). Không stage/commit/push, không xóa cache/schema/ledger. Các cache/build có thể tái tạo chỉ được dọn trong lượt riêng; không xóa .cache tổng.

**ENVIRONMENT BLOCKED tại checkpoint cuối**: host đã power off giữa full, hiện Engine pipe mất; không runner full cũ đang chạy, không tự retry suite tiếp. Cần một cửa sổ máy hoạt động liên tục và Docker/PG stable khoảng50–60phút. Sau bounded readiness/source check, chạy một full mới bằng label/schema mới (ví dụ ia01_full_20261115_02), không dùng --lf và không ghi đè lượt01. Collection599/K/Browser có thể kế thừa nếu source liên quan không đổi; không cần chạy lại T/E/K/Browser chỉ để lặp bằng chứng. Nếu source đổi phải xác định scope lại.

Chưa đóng P8A-IA01 hoàn toàn, chưa sửa Independent Acceptance thành PASS, không 8B/8C. Dừng sau ghi nhận interruption và báo cáo.

Status cuối lượt: **IMPLEMENTED / VERIFICATION PARTIAL-BLOCKED (environment)**; chưa kết luận P8A-IA01 FIXED hoàn toàn hoặc acceptance.

Root cause: record gọi recovery_authorization.human cho Technician PRE mà không kiểm current boot; Customer confirmation có guard riêng. Chuyển current-boot/provenance validation vào shared human PRE sau exact actor auth-session lock wait, dưới station mutex/user/resource locks đã có. Re-read enabled device/boot và accepted processed SNAPSHOT provenance/hash/context/actual serial; recheck operation/token expiry trước write. Không thêm device lock ordering mới hoặc HTTP dưới DB lock. POST trả về handler riêng trước guard PRE; successor dùng current() hiện có; legacy0.1 không gọi shared staged handler. Không đổi authorization guards/quiet/deadlines/custody/Payment/holds/migrations/contracts.

Source sửa: services/backend/app/application/recovery.py và recovery_authorization.py. Tests mới test_phase8a_ia01_fix.py; probe test_phase8a_independent_acceptance.py giữ assertion business. Operator driver thêm mode T cho real reboot + hai Backend OS requests từ chối PRE old-boot.

Probe gốc nguyên vẹn đã lưu `docs/PHASE8A_TESTS/ia01_fix_20261114_01/original_probe.py`. Chạy nguyên probe sau sửa (`ia01_original_after_20261114_01`) trả cả hai request409 nhưng Failed tại equality correlation_id. Error handler hiện có sinh correlation UUID từng request; idempotency chỉ cache success. Người dùng đã chấp thuận sửa riêng comparison envelope để bỏ correlation_id, vẫn so status/code/message/details, thêm case-version/attestation invariants. Không sửa production error semantics/idempotency để làm probe Passed; lịch sử failure giữ nguyên. Không skip/xfail probe.

Targeted đang chạy tại `PHASE8A_TESTS/ia01_targeted_20261114_01`; chưa có kết quả cuối. Full pytest/real-process/Browser source mới chưa chạy tại checkpoint này. Kế hoạch: chốt targeted, freeze source, real-process T/E/K, Browser post/successor/negative, full Backend pytest tuần tự. Không sử dụng số 587 lịch sử làm kết quả mới.

Không Independent Acceptance lần hai, không 8B/8C, không stage/commit/push hoặc xóa DB/schema/ledger/evidence.

## Kết quả thực tế cuối lượt

| Lượt | Kết quả | Phạm vi / evidence |
|---|---|---|
| ia01_original_after_20261114_01 | 1 Failed, exit1 | Trước chuẩn hóa envelope theo chấp thuận; cả request/retry đã409, chỉ correlation_id khác; giữ nguyên log/XML |
| ia01_targeted_20261114_01 | **42 Passed**, exit0, 1250.26s | POST, Customer projection, successor/staged settlement, P7 deadline và tests fix load trước bước dời final-time check; không gọi là toàn source cuối |
| ia01_final_targeted_20261114_01 | **6 Passed**, exit0, 39.92s | Source cuối: probe gốc với envelope correction được duyệt, same-boot CONFIRM/REJECT, audit rollback, hai app/PG connections tranh một Technician proof, simulated delayed decision freshness/expiry; không sửa observation timestamps |
| ia01_real_T_20261114_01 | **exit0** | Hai Backend OS process + worker + simulator reboot thật: current projection UNAVAILABLE; cả hai Technician requests409 và Customer409; case/version/facts không đổi, 0 service effect/confirmation audit |
| ia01_real_E_20261114_01 | **exit0** | Actual INSPECT→PRE Tech/Customer→intent/ACK→activation→handover→POST→settlement/replay. Một effect/success audit, custody/Payment/holds đúng |
| ia01_real_K_20261114_01 | Interrupted | Mất execution session, không có final exit; không tính Passed |
| ia01_real_K_20261114_02 | exit1, environment blocked | PostgreSQL ConnectionTimeout trước workflow; Docker pipe mất. Không phải successor assertion failure |
| ia01_real_K_20261114_03 | Interrupted / blocked | Sau khôi phục Docker bình thường, orchestration hidden chạy nhưng lại mất process và Engine; chỉ setup output, không final exit |
| Browser post/successor/pre-reject/revoked source mới | **Not Run** | Batch dừng ở K trước khi tới Browser; không dùng Browser15 lịch sử thay thế |
| Full Backend pytest source mới | **Not Run** | Chưa khởi chạy, không suy số test vẫn587 hoặc cộng các nhóm targeted |

Mỗi pytest có run.log/results.xml trong PHASE8A_TESTS/<label>; child exit checkpoints/console tại PHASE8A_TESTS/ia01_fix_20261114_01. Real-process JSON trong <label>/reports/PHASE8A_E2E_E.json, field operator phân biệt T/E; không cộng setup checks vào số tests. Hai app/PG connections trong targeted không gọi là hai OS processes; nhánh T là evidence OS-process riêng.

Lệnh điều phối đầu sau final targeted gặp lỗi PowerShell gom progress string vào return value nên dừng dù child exit0; đã sửa riêng orchestration, không chạy lại 6 tests. T/E sau đó exit0. Không xem outer PowerShell status là kết quả pytest.

## Lock / decision boundary

record và confirmation đều vào lock_context: station mutex → participants/users/resources theo thứ tự hiện có → actor auth_session row trong human. Guard PRE đọc current device/source snapshot **sau** session wait; device worker cũng phải station mutex nên boot không thể commit xen giữa guard và write. Không thêm thứ tự khóa device sau session hoặc network wait. Cuối các provenance reads: utcnow mới, open_operation, expiry token, freshness rồi insert/change_case/audit trong cùng transaction. Từ chối raise DomainError trước write; idempotency không tạo successful cache record. POST dispatch handler riêng trước guard này; successor dùng current() và không chạy PRE boot check; compatibility0.1 không đi qua handler0.2.

Một số targeted delay cases mock decision clock để chứng minh đọc lại thời gian, không sửa dữ liệu hoặc kéo dài deadline; không gọi chúng là real-time lock race. Các ordering probes cũ là evidence lịch sử, full source mới chưa được hồi quy đủ do environment.

## Environment / preservation

Execution session ID mất và sau đó không thấy các process batch cũ. K02 xác nhận ConnectionTimeout + mất dockerDesktopLinuxEngine pipe. Tìm bản cài Docker qua CLI root per-user; mở Docker Desktop bình thường (không reset). Engine29.9.2 trở lại, container cũ tự start và recovery; pg_isready accepting, configured runtime SELECT1=1, healthy. Tiếp tục K03 bằng schema mới/hidden owned process; sau đó process lại biến mất và Engine pipe lại mất. **Chưa xác định nguyên nhân các tiến trình bị dừng**, không quy chắc cho cập nhật tool, user hoặc source nghiệp vụ. Dừng retry sau lần lặp này, không sửa business để vượt lỗi môi trường.

Không có full pytest đang chạy cần thu hồi ở checkpoint cuối. Giữ K01/K02/K03, schemas, ledgers và .cache scripts. Không dùng kết quả fingerprint của K interrupted để tuyên bố demo unchanged; T/E có fingerprint và facts theo scope runner tám bảng. Không chạy demo migration, không reset Database/volume, không xóa dữ liệu.

## File và bàn giao

Production: recovery.py, recovery_authorization.py. Tests: test_phase8a_independent_acceptance.py (chỉ envelope correction + invariant asserts theo chấp thuận), test_phase8a_ia01_fix.py. Test runner: phase8a_operator_verify.py thêm modeT. Docs fix/implementation/status; original independent acceptance không sửa thành PASS. Bản probe gốc original_probe.py và toàn bộ failed evidence được giữ. Script awake/orchestration chỉ trong .cache, không commit cache/credentials/SQLite/runtime/artifacts.

[Freeze hashes trước](PHASE8A_TESTS/ia01_fix_20261114_01/source_final_before.json), [sau](PHASE8A_TESTS/ia01_fix_20261114_01/source_final_after.json), [checkpoint](PHASE8A_TESTS/ia01_fix_20261114_01/final_checkpoint.json), [Git inventory](PHASE8A_TESTS/ia01_fix_20261114_01/git_status.txt). Diff --check/staged check đạt, index trống. Không thay contracts/migration/Frontend/P6/P7 guards. 587/full,102E2E,15Browser cũ không được ghi thành regression mới của source fix.

Để tiếp tục: cần Docker/PostgreSQL và các process test ổn định; kiểm tra process/checkpoints trước, không chạy suite trùng. Chạy K trên label/schema mới, Browser affected flows, rồi full pytest (runner tạo schema riêng, lưu collection/XML/log/exit thực tế). T/E và final targeted đã có evidence hợp lệ nếu source tương ứng không đổi. Chỉ sau các gate còn thiếu đạt mới xem xét đóng Major trong scope kỹ thuật; không Independent Acceptance lần hai hoặc tự chuyển 8B/8C.
