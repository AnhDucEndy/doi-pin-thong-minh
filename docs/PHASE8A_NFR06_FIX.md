# R2-NFR06-01 — Recovery audit completeness fix

## Checkpoint quyết định mới — 15/11/2026

**PHASE 8A — CONDITIONAL ACCEPTANCE APPROVED BY USER.** Người dùng đã phê duyệt allocation R2-D01/NFR04, R2-D02/NFR07/CT14 và R2-D04/NFR08 sang final MVP integration acceptance. Các tests/gates này vẫn **NOT RUN / OPEN, bắt buộc trước full MVP acceptance/release**, không PASSED/WAIVED. Owner TV1–TV5 là đề xuất theo R3; nhóm chưa xác nhận cá nhân nhận việc. IA01/NFR06 Recovery findings FIXED/CLOSED technical scope; evidence603 Backend,21 audit actions,8 real runners và Browser/frontend được kế thừa theo R3, không chạy mới. Không full MVP PASS, không hoàn tất refund/compensation hoặc tự mở8B/8C.

[Biên bản quyết định](PHASE8A_CONDITIONAL_ACCEPTANCE.md) · [Release gates/criteria/owners](MVP_RELEASE_GATES.md) · [Đề xuất staging, không git add](PHASE8A_GIT_READINESS.md).

Các kết luận/pending tại những checkpoint bên dưới là **lịch sử trước approval này**, giữ nguyên, không sửa R1/R2/R3 thành PASS hồi tố. Không đổi production/baseline hoặc xóa dữ liệu/evidence.

Checkpoint cuối 15/11/2026. **R2-NFR06-01: FIX IMPLEMENTED & VERIFICATION PASSED trong phạm vi Recovery 8A; đề xuất đóng Major này.** Không Independent Acceptance Round3 hoặc nghiệm thu toàn Phase8A. D01/D02/D04 vẫn **PENDING APPROVAL**; D03 được người dùng giao thực hiện trong lượt này.

## Kết quả cuối 17:44 +07 — source audit cuối

| Gate chạy mới | Kết quả thực tế | Evidence |
|---|---|---|
| Targeted PostgreSQL/Recovery/P7 | **86 Passed, 0 Failed/Errors/Skipped, exit0**, 1498.71s | [JUnit](PHASE8A_TESTS/nfr06_regression_20261115_01/results.xml), [exit](PHASE8A_TESTS/nfr06_fix_20261115_01/nfr06_regression_20261115_01_exit.json) |
| Audit action coverage | **21/21**, không thiếu action; kiểm giá trị SQL, creation/consumption/version và protected facts | [Full coverage](PHASE8A_TESTS/nfr06_full_20261115_01/reports/PHASE8A_NFR06_AUDIT_COVERAGE.json) |
| Real-process A/B/CD/E/F/J/K/T | **8 runners exit0**, schemas/ledgers riêng, Backend OS processes/worker/simulator thật | [Exit metadata](PHASE8A_TESTS/nfr06_fix_20261115_01/), reports tại từng label `nfr06_real_*_20261115_01` |
| PostgreSQL persisted audit payload | **8/8 fixture Passed, read-only, exit0**, 63 Recovery audit rows đã commit | [Payload/transition validation](PHASE8A_TESTS/nfr06_fix_20261115_01/audit_all_03.json), [exit](PHASE8A_TESTS/nfr06_fix_20261115_01/audit_all_03_exit.json) |
| Browser Chromium affected | **3 Passed, 0 Failed/Errors/Skipped**, mỗi child/runner exit0: post workflow, successor, closure | [POST XML](PHASE8A_TESTS/nfr06_browser_post_20261115_02_browser/results.xml), [successor XML](PHASE8A_TESTS/nfr06_browser_successor_20261115_02_browser/results.xml), [closure XML](PHASE8A_TESTS/nfr06_browser_closure_20261115_02_browser/results.xml) |
| Frontend / build | **39 Passed**, TypeScript noEmit + Vite production exit0 | [Tests](PHASE8A_TESTS/nfr06_fix_20261115_01/frontend.log), [build](PHASE8A_TESTS/nfr06_fix_20261115_01/build.log), [exits](PHASE8A_TESTS/nfr06_fix_20261115_01/frontend_exits.json) |
| Full Backend, một suite trên source cuối | **603 Passed, 0 Failed/Errors/Skipped, exit0**, pytest3296.43s (**54:56.43**) | [Full log](PHASE8A_TESTS/nfr06_full_20261115_01/run.log), [JUnit](PHASE8A_TESTS/nfr06_full_20261115_01/results.xml), [exit/timestamps](PHASE8A_TESTS/nfr06_fix_20261115_01/full_exit.json) |
| Collection và SHA256 | Không mất **599** ca lịch sử, thêm đúng **4** audit tests; **179/179 hashes khớp**, delta0 | [Verification](PHASE8A_TESTS/nfr06_fix_20261115_01/full_verification.json), [before](PHASE8A_TESTS/nfr06_fix_20261115_01/source_final_before.json), [after](PHASE8A_TESTS/nfr06_fix_20261115_01/source_after_full.json) |

Full bắt đầu16:46:41.325, kết thúc17:41:46.004 +07; wrapper55:04.679, khác thời gian pytest vì gồm startup/teardown. Bốn warnings: Starlette/httpx deprecation, OpenAPI `validate_spec` deprecation và hai cảnh báo `record_property`/xunit2 từ pause diagnostic; không có skipped/xfail hoặc thay assertion để đạt Passed. Không cộng86 targeted, các runner hoặc Browser vào603.

Engine29.9.2/PostgreSQL healthy, pg_isready/runtime SELECT1 đạt ba mẫu trước/sau; StartedAt không đổi trong full. Query power events trong cửa sổ full không có kết quả; không còn runner full/pytest sau kết thúc. [Readiness hậu kiểm](PHASE8A_TESTS/nfr06_fix_20261115_01/readiness_after_full_01.json), [resources](PHASE8A_TESTS/nfr06_fix_20261115_01/resources_after_full_01.json). Sự cố host power off trước full chỉ ngắt Browser post01, đã bảo toàn riêng; không gọi đó là failure production hay full regression.

### Facts của fixture đã commit

| Runner | Recovery audits đã commit | Kết quả state/custody/holds/payment |
|---|---:|---|
| A |6| Case v6/EVIDENCE_RECORDED, old settled=true/new NO;3 holds, SUCCEEDED; không suy giao pin mới |
| B |6| Case v6/EVIDENCE_RECORDED, old settled=true/new NO;3 holds, SUCCEEDED; restart/retry giữ một handover effect/một manual audit |
| CD |6| Nhánh C fail-closed khi thiếu delivery proof; D RESOLVED v6, custody pin cũ COMPARTMENT/pin cấp CUSTOMER,0 holds chỉ sau terminal guards; SUCCEEDED; một manual audit |
| E |12| Case v9, old settled=false/new UNKNOWN;3 holds/SUCCEEDED, custody không đổi; một foreign return effect và một settlement audit |
| F |7| Case v6, old settled=false/new UNKNOWN,3 holds/SUCCEEDED; offline/reboot không tạo completion giả |
| J |9| Case v7/OPEN, operation đóng no-effect;0 effect, một closure audit;3 holds/SUCCEEDED và custody giữ nguyên |
| K |14| Case v10, successor chain consumed đúng; một effect gốc/một foreign settlement audit, không effect thứ hai;3 holds/SUCCEEDED |
| T |3| Case v2/OPEN, old-boot refusals không tạo human proof/version/audit;0 effect,3 holds/SUCCEEDED |

Các báo cáo real-process kiểm demo fingerprint theo **8 bảng của runner**, không chứng nhận toàn Database. Audit verifier đọc lại metadata/states trực tiếp PostgreSQL bằng read-only transaction, không dùng report JSON thay DB, không UPDATE/backfill audit lịch sử. So before/after/case version và child creation/consumption dựa trên giá trị SQL; redaction không đưa payload/freeform note hay credentials vào snapshot.

### Rollback, replay, concurrency và khả năng tái hiện

- Test mới `test_audit_after_write_failure_rolls_back_and_retry_is_single` gây lỗi **sau INSERT audit thật**: attestation/case version/audit/idempotency không commit; retry cùng key thành công đúng một lần, replay không tăng audit. Các tests settlement/handover/POST/IA01 hiện có tiếp tục kiểm audit error rollback, refusal và guards nguyên vẹn.
- Observer SQL chạy trên workflows thật, gồm các ca concurrent PostgreSQL của suite; real B/CD/E/K có hai Backend OS process, replay/version serialization chỉ tạo một success audit. Không gọi hai TestClient là hai OS process; không tuyên bố đã chạy mới toàn bộ17 final-decision races lịch sử.
- B replay qua simulator restart và K successor sau expiry/reboot chứng minh lịch sử/ledger/fence bền vững; J đóng no-effect không release holds. Không thêm fault hook production hoặc lặp lại physical effect để kiểm audit.
- Tái hiện targeted: đặt `TEST_REPORT_ROOT=PHASE8A_TESTS`, chạy `.venv/Scripts/python.exe tools/run_phase6_fix.py LABEL_MOI pytest tests/test_phase8a_audit.py tests/test_phase8a_authorization.py tests/test_phase8a_post_confirmations.py tests/test_phase8a_staged_settlement.py tests/test_phase8a_expired_recovery.py`. Full: cùng runner với `pytest` không bộ lọc; dùng label mới, chạy tuần tự. Runner giữ schema/ledger/log; không chạy migration demo.
- Real E/K/J: dùng `tools/smoke_phase8a.py --branch E --operator-check` qua runner, `P8_OPERATOR_MODE=E/K/J` tương ứng; xem JSON và exit từng label. Read-only verifier tái hiện bằng `tools/phase8a_audit_verify.py --report REPORT_JSON --output OUTPUT_MOI` (có thể lặp `--report`); chỉ nhận fixture `phase5_test_*`, không ghi đè output hoặc đọc schema demo.

### Phạm vi source và kết luận

So với freeze IA01175 files, đổi **9 production files**: recovery.py, recovery_authorization.py, recovery_handover.py, recovery_inspection.py, recovery_settlement.py, recovery_reconciliation.py, recovery_closure.py, swaps.py, payments.py; thêm recovery_audit.py. Tests đổi conftest.py, thêm recovery_audit_checks.py và test_phase8a_audit.py; thêm read-only tooling phase8a_audit_verify.py. **10 files đổi +4 mới =14 source/test/tooling files**, không tính docs/evidence. [Manifest delta chuẩn hóa paths](PHASE8A_TESTS/nfr06_fix_20261115_01/source_scope_delta_02.json). File `source_scope_delta.json` ban đầu so khác separator Windows nên không hợp lệ; giữ nguyên làm evidence diagnostic, không dùng làm kết luận source.

**Đề xuất đóng R2-NFR06-01 trong technical scope Recovery8A đã kiểm chứng.** Không có regression Major tái hiện trong gates trên; không tuyên bố audit các module khác toàn MVP đã hoàn tất, không đóng các gate NFR04/NFR07/NFR08 còn thiếu hoặc phê duyệt D01/D02/D04. Toàn Phase8A tiếp tục **PARTIAL/chờ quyết định nghiệm thu**. Không Round3, không8B/8C, không stage/commit/push hoặc xóa dữ liệu/evidence. Các checkpoint ban đầu dưới đây là lịch sử.

### Git và bảo toàn

Checkpoint17:48:35 +07: HEAD vẫn `e4fb9f540195d4cbd10c97b03cd4dccc959c3a9d`, `main...origin/main`, **17 tracked modifications tích lũy,1042 untracked files,0 staged**. `git diff --check` và `git diff --cached --check` exit0; source179 vẫn delta0. [Danh sách file và kiểm tra cuối](PHASE8A_TESTS/nfr06_fix_20261115_01/final_workspace_state_02.json). Secret heuristic trên14 source/test/tooling files của increment +4 reports không flag literal credential; không phải chứng nhận toàn1042 artifacts hoặc lý do stage hàng loạt.

Một link `PHASE4_ACCEPTANCE.md` đã thiếu ngay trong HEAD được phát hiện khi kiểm docs; giữ nguyên vì ngoài scope. `final_workspace_state.json` có assertion fail do link lịch sử này, không phải product regression; kết quả02 tách rõ preexisting/introduced, không có broken link mới. Không xóa hoặc sửa evidence kiểm tra đầu. Các reports/runners/source tests cần giữ; JUnit/log/source manifests là bằng chứng mới cục bộ. Private credentials, `.local` command/service/payment ledgers, schemas và toàn evidence lịch sử được giữ nguyên, không đưa vào staging. `apps/web/dist`, `.pytest_cache`, `__pycache__` là output có thể tái tạo trong lượt dọn riêng; **không dọn trong lượt này** và không coi `.cache` runtime/evidence hoặc ledger là rác có thể xóa tùy ý.

## Checkpoint 16:46 — full suite đang chạy

Targeted rộng đã hoàn tất **86 Passed, exit0,1498.71s**, SQL observer đủ **21/21 actions**, không missing. Real-process **A/B/CD/E/F/J/K/T:8 runners exit0**, không gọi chúng là102 checks mới. SELECT read-only E/K/J mới đạt; E có12 audits gồm case-created, activation5→6, settlement8→9;3 holds/Payment SUCCEEDED và custody đúng. Các branch khác cũng được chạy lại vì dùng chung audit helper.

Frontend mới **39 Passed**, TypeScript/Vite exit0. Browser affected **post/successor/closure:3 Passed**, mỗi scenario XML/exit0 trên labels `_20261115_02`. Browser post01 **Interrupted**, không final XML/exit: Windows User32/StartMenuExperienceHost khởi tạo power off16:16:16, boot16:16:45. Không quy nguyên nhân cho source; không có bugcheck event trong cửa sổ đã đọc. Mở Docker Desktop bình thường một lần, không reset; PG automatic recovery rồi readiness3 mẫu healthy/pg_isready/runtime SELECT1 đạt. [Events](PHASE8A_TESTS/nfr06_fix_20261115_01/interruption_events_01.json), [readiness](PHASE8A_TESTS/nfr06_fix_20261115_01/readiness_after_reboot_01.json). Old fixture/ledger của post01 giữ nguyên, không tái dùng để ép happy path.

Collection mới **603 tests**, không mất599 cũ, thêm4 audit tests. Source production/tests178 file không đổi trong các gate; thêm read-only verifier vào final manifest thành **179 file**, delta0. [Pre-full validation](PHASE8A_TESTS/nfr06_fix_20261115_01/pre_full_validation.json).

Full `nfr06_full_20261115_01` bắt đầu **16:46:41 +07** qua PowerShell độc lập PID24488, không suite khác chạy; [started](PHASE8A_TESTS/nfr06_fix_20261115_01/full_started.json), [run.log](PHASE8A_TESTS/nfr06_full_20261115_01/run.log). Nguồn điều kiện giữ máy: yêu cầu full hiện tại và xác nhận60–75 phút đã có trong hội thoại; không coi câu hỏi nhắc lại chưa trả lời là approval mới. Thread execution-state không thay power plan/registry và không ngăn explicit power off. **Chưa có final JUnit/exit thì chưa đóng Major hoặc dùng dots suy Passed.** Các bảng checkpoint ban đầu dưới đây giữ lịch sử; kết quả cuối cần cập nhật sau full.

## Root cause và phạm vi

`recovery.audit` trước sửa chỉ ghi action references trong after_data. `change_case` và các mutation child records không có snapshot trước/sau; audit append-only không tự điền dữ liệu này. R2 SELECT read-only đã xác nhận11 audit fixture E có after_data, không có before_data. Không backfill hoặc chỉnh những records lịch sử đó.

Bản sửa chỉ phục vụ audit Phase8A. Không đổi protocol/schema/API/UI, migration/grants, state transition guards, ACK15/physical60/freshness15, custody/payment/holds hoặc simulator effect. `change_case` vẫn là primitive cập nhật như trước; call sites phải capture BEFORE rõ ràng, không dùng Session.info/global cache/rollback hook để đoán trạng thái cũ.

## Representation và transaction

- `before_data.recovery_snapshot` là giá trị thực đọc trong transaction đang giữ station/user/resource locks, trước mutation và trước final time guards của các quyết định có guard đó. `after_data.recovery_snapshot` được đọc qua cùng session sau writes. Các metadata/action references hiện có vẫn nằm ở top-level after_data.
- Allowlist trong `recovery_audit.py` chỉ lấy case state/version/flags, operations lifecycle/context hash, proof provenance/hash/reference, authorization/ACK/activation/closure metadata và protected swap/battery/payment/hold/command facts. Không copy row/context/payload toàn bộ; không log password/token/Device-Key/raw QR/headers/freeform notes. Freeform notes bị loại vì có thể chứa dữ liệu nhạy cảm; trạng thái vận hành và references vẫn được giữ.
- Tạo child mới: trước snapshot không có child ID đó, sau mới có; không dựng before-object giả. Tạo Recovery case mới: before snapshot là **JSON null**, after là case thực với default DB, không suy một trạng thái trước chưa tồn tại.
- Để không bỏ sót đầu vào Recovery, hai handoff `swaps.review`/`payments.review` dùng chính INSERT ON CONFLICT cũ cộng RETURNING; chỉ khi tạo case thực sự mới ghi `RECOVERY_CASE_CREATED` (SYSTEM device-worker/payment-worker). Không đổi outcome hoặc action cũ; case tồn tại không tạo creation audit nữa.
- Audit/mutation/idempotency vẫn cùng transaction. Helper không commit, không thêm khóa, không gọi provider/device. Failure rollback không giữ snapshot cache hoặc audit thành công; retry lấy state mới. Không UPDATE/DELETE audit hoặc sửa append-only policy.
- `RECOVERY_RESUMED_COMPLETED` ghi before/after của **Recovery case closure** sau automatic custody writes trong cùng transaction. Nó không giả nhận snapshot đó là trước physical pickup; Phase7 custody audit và correlation cùng swap vẫn giữ nguyên. Đây là scope Recovery8A, chưa là chứng nhận NFR06 toàn bộ các module MVP.

## Coverage matrix cuối — 21/21 actions Passed

| Action | BEFORE → AFTER bắt buộc | Evidence status |
|---|---|---|
| RECOVERY_CASE_CREATED | Không có case → case OPEN/default DB, không fake before-object | Targeted86/full603 Passed; real8 fixtures |
| RECOVERY_EVIDENCE_RECORDED | Case version/state/evidence ref trước → +1/ref mới; không lộ raw note | Targeted86/full603 Passed |
| RECOVERY_OPERATION_CREATED | Child ID vắng → operation/context/lifecycle thực; case +1/current operation | Targeted86/full603 Passed; real8 fixtures |
| RECOVERY_OPERATION_ATTACHED | Ref/version trước → current operation/ref thật và +1 | Targeted86/full603 Passed |
| RECOVERY_OPERATION_SUPERSEDED | cancelled_at null → timestamp thật; version case không tự tăng | Targeted86/full603 Passed |
| RECOVERY_ATTESTATION_RECORDED | Source proof chưa có → immutable proof/provenance/hash, case +1 | Targeted86/full603 Passed; real A/B/CD/F |
| RECOVERY_INSPECTION_RECORDED | Simulator PRE receipt chưa có → accepted metadata; case version giữ nguyên | Targeted86/full603 Passed; real E/J/K/T |
| RECOVERY_PRE_ACTION_CONFIRMED | Human source chưa có → proof/ref CONFIRM/REJECT; case +1, protected facts giữ | Targeted86/full603 Passed; real E/J/K |
| RECOVERY_AUTHORIZATION_INTENT_CREATED | Permit chưa có → intent row/hash/expiry; case +1 | Targeted86 Passed |
| RECOVERY_AUTHORIZATION_ACKNOWLEDGED | ACK chưa có → durable ACK id/device/boot/seq/hash; case giữ version | Targeted86 Passed |
| RECOVERY_ACTION_ACTIVATED | Activation chưa có → activation/hash/permit/ACK refs; case +1 | Targeted86 Passed |
| RECOVERY_POST_ACTION_RECEIPT_STORED | POST receipt chưa có → immutable actual receipt metadata; version giữ | Targeted86 Passed |
| RECOVERY_POST_ACTION_CONFIRMED | Human POST chưa có → source/stage/ref đúng; case +1 | Targeted86 Passed |
| FOREIGN_OBJECT_RETURN_SETTLED | Operation(s) chưa consumed → consumed và case +1; custody/payment/holds không đổi | Targeted86/full603 Passed; real E/K |
| RECOVERY_REINSPECTION_REQUESTED | Successor chưa có → read-only successor/current ref; case +1 | Targeted86/full603 Passed; real K |
| RECOVERY_REINSPECTION_RECORDED | Current successor receipt chưa có → accepted metadata; version giữ | Targeted86/full603 Passed; real K |
| RECOVERY_REINSPECTION_ATTESTED | Human successor proof chưa có → stage/ref đúng; case +1 | Targeted86/full603 Passed; real K |
| RECOVERY_NO_EFFECT_CLOSURE_REQUESTED | Intent chưa có → durable closure intent; case +1 | Targeted86/full603 Passed; real J |
| RECOVERY_NO_EFFECT_CLOSED | Receipt chưa có/op mở → receipt mới/op cancelled/case +1; protected facts giữ | Targeted86/full603 Passed; real J |
| MANUAL_RECOVERY_SETTLED | Case/op/custody/holds/commands thực trước → state có guard và +1, consumption/custody/release đúng từng nhánh | Targeted86 Passed |
| RECOVERY_RESUMED_COMPLETED | Case chưa RESOLVED → RESOLVED/old settled/new YES/+1; nguồn command/evidence giữ | Targeted86 Passed |

`tests/recovery_audit_checks.py` dùng SQL đọc actual rows tại capture, kiểm snapshot detached, đúng values/version delta, creation absence, consumption/cancellation, provenance và protected facts. Nó không gọi helper để tự tính expected bằng chính helper đó, không thay clock/lock/observation, không tạo mock audit thay source. Đây là assertion bổ sung trên workflows cũ của Phase8A; coverage counts là số lần assertions chạy, kể cả attempt sau đó rollback, **không phải số audit đã commit hoặc số effect**.

## Tests và evidence checkpoint

| Lượt | Kết quả | Scope |
|---|---|---|
| nfr06_targeted_20261115_01 |9 Passed, exit0,49.13s | Smoke audit/IA01 trước khi bổ sung creation/coverage cuối; không dùng làm full source cuối |
| nfr06_targeted_20261115_02 |14 Passed, exit0,56.75s | SQL-backed assertions, actual before/after, audit-after-write rollback/retry/replay, legacy receipt/attach/supersede, IA01; trước freeze thêm review_reason field |
| nfr06_regression_20261115_01 | **86 Passed, exit0,1498.71s** | SQL-backed assertions đủ21/21 actions, gồm P7 deadline, rollback/replay/concurrency và ER01/02 |
| Real-process A/B/CD/E/F/J/K/T | **8 runners exit0** | Không cộng assertions độc lập vào603; SQL verifier8 fixtures đạt |
| Browser affected | **3 Passed** | POST/successor/closure trên source audit mới; post01 Interrupted giữ riêng |
| Full Backend mới | **603 Passed, exit0** | Không mất599 cũ; thêm4 audit tests,179 SHA256 không đổi |

[Source freeze178 file](PHASE8A_TESTS/nfr06_fix_20261115_01/source_before.json). Batch hidden PowerShell bắt đầu15:30:06 +07, PID17764; labels/schema/ledger riêng, ports8070/8071 và5190. [Batch metadata](PHASE8A_TESTS/nfr06_fix_20261115_01/batch_process.json). Không chạy các suite dùng chung DB song song. Nếu process bị ngắt, cần thu hồi log/XML/exit trước khi khởi chạy lại; không suy Passed từ dots.

## Files và điểm dừng

Source: helper `recovery_audit.py` mới; audit call sites trong recovery.py/authorization/handover/inspection/settlement/reconciliation/closure; handoff creation audit trong swaps.py/payments.py. Tests: conftest load observer, `recovery_audit_checks.py`, `test_phase8a_audit.py` mới. Không đổi migrations/frontend/contracts/dependencies.

Chỉ đề xuất đóng Major sau coverage21 actions, targeted/real-process/full source cuối đạt, before/after chính xác và không hồi quy invariants. Toàn8A vẫn PARTIAL, không Independent Acceptance Round3 hoặc8B/8C. Không stage/commit/push, không xóa fixture/schema/ledger/evidence.
