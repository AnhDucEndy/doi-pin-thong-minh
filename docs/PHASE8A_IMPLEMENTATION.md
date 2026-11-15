# Phase 8A — Recovery Evidence & Settlement (đang triển khai)

## Checkpoint quyết định mới — 15/11/2026

**PHASE 8A — CONDITIONAL ACCEPTANCE APPROVED BY USER.** Người dùng đã phê duyệt allocation R2-D01/NFR04, R2-D02/NFR07/CT14 và R2-D04/NFR08 sang final MVP integration acceptance. Các tests/gates này vẫn **NOT RUN / OPEN, bắt buộc trước full MVP acceptance/release**, không PASSED/WAIVED. Owner TV1–TV5 là đề xuất theo R3; nhóm chưa xác nhận cá nhân nhận việc. IA01/NFR06 Recovery findings FIXED/CLOSED technical scope; evidence603 Backend,21 audit actions,8 real runners và Browser/frontend được kế thừa theo R3, không chạy mới. Không full MVP PASS, không hoàn tất refund/compensation hoặc tự mở8B/8C.

[Biên bản quyết định](PHASE8A_CONDITIONAL_ACCEPTANCE.md) · [Release gates/criteria/owners](MVP_RELEASE_GATES.md) · [Đề xuất staging, không git add](PHASE8A_GIT_READINESS.md).

Các kết luận/pending tại những checkpoint bên dưới là **lịch sử trước approval này**, giữ nguyên, không sửa R1/R2/R3 thành PASS hồi tố. Không đổi production/baseline hoặc xóa dữ liệu/evidence.

## R2-NFR06-01 final verification — 15/11/2026

**FIX IMPLEMENTED & VERIFICATION PASSED trong Recovery8A; đề xuất đóng riêng Major audit completeness.** `recovery.audit` trước đây chỉ có after refs; nay capture actual BEFORE dưới context locks trước mutation và AFTER cùng transaction, allowlist an toàn, giữ action/actor/device/correlation/IDs. Creation case có before-object null; child creation có absence đúng; không backfill audit lịch sử, không đổi append-only policy, API/protocol/migrations/UI/guards/deadlines hoặc custody/Payment/holds/effects.

Kết quả mới trên source cuối: **targeted86 Passed; coverage21/21 actions; real-process A/B/CD/E/F/J/K/T:8 runners exit0; SQL read-only8 fixtures/63 audit rows Passed; Browser affected3 Passed; frontend39 Passed; TypeScript/Vite exit0. Full Backend mới603 Passed,0Failed/Errors/Skipped,exit0**, pytest3296.43s/54:56.43; 16:46:41–17:41:46 +07. JUnit/node multiset giữ đủ599 lịch sử +4 audit tests; **179 source hashes trước/sau khớp, delta0**. Bốn warnings được lưu, không skip/xfail/đổi assertions. Không cộng các gate độc lập vào603.

Rollback sau actual audit INSERT, retry/replay, concurrent PostgreSQL và two-process settlement bảo toàn audit/mutation atomicity và không double effect/success audit. E/K foreign settlement giữ old_pin_settled=false,3 holds/SUCCEEDED/custody; J0effect/3holds; CD chỉ release0holds sau terminal completion hợp lệ. Resume case closure audit được capture trước/sau Recovery closure, không giả làm before-physical-pickup của Phase7. Demo fingerprint chỉ8 bảng runner. Browser post01 bị power off trước full, giữ Interrupted; full mới có kết quả hoàn chỉnh và PG healthy trước/sau, không restart trong suite.

Đổi9 production files hiện có +1 helper audit mới, conftest +2 test helpers/tests mới và1 read-only verifier; không đổi Frontend/contracts/migrations. [Root cause, coverage matrix21 actions, commands, XML/exits, exact file delta và source hashes](PHASE8A_NFR06_FIX.md). [Full verification](PHASE8A_TESTS/nfr06_fix_20261115_01/full_verification.json).

**Toàn Phase8A vẫn PARTIAL/chờ quyết định nghiệm thu**, không Independent Acceptance Round3. R2-D01/D02/D04 vẫn **PENDING APPROVAL**; không xác nhận NFR04/full coordinated restore/NFR08 hoặc NFR06 các module ngoài scope đã đạt. R2 gốc giữ nguyên và chỉ bổ sung checkpoint sửa. Không stage/commit/push, không8B/8C hoặc xóa dữ liệu/evidence. Các checkpoint tiến độ sau đây là lịch sử.

Git cuối17:48: HEAD e4fb9f5/main,17 tracked modifications tích lũy,1042 untracked,0 staged; diff/cached diff --check exit0, source179 delta0. Secret heuristic trong increment không flag, không quét/chứng nhận toàn bộ artifacts. Giữ credentials/DB/ledgers/evidence. Link Phase4 report thiếu đã có trong HEAD, không sửa ngoài scope; report kiểm tra đầu có assertion fail vì link lịch sử, lần02 phân loại đúng. [Final workspace state](PHASE8A_TESTS/nfr06_fix_20261115_01/final_workspace_state_02.json).

## R2-NFR06-01 fix — 15/11/2026, verification đang chạy

Checkpoint16:46: targeted rộng **86 Passed**, coverage SQL21/21; A/B/CD/E/F/J/K/T8 runners exit0, read-only audit E/K/J đạt. Frontend39/TS/Vite exit0; Browser affected3 Passed ở runs02. Browser post01 bị host power off ngắt, không Passed. Docker/PG được mở lại bình thường và3 readiness đạt; không reset. Collection**603**, retained599+4, source freeze179 khớp. Full mới bắt đầu16:46:41 qua runner độc lập, **đang chạy**, chưa đóng finding. D01/D02/D04 vẫn Pending. [Checkpoint và artifacts](PHASE8A_NFR06_FIX.md).

Đã bổ sung snapshot before/after allowlist cho Recovery mutations, giữ metadata/action cũ, atomicity/locks/idempotency và append-only. Hai handoff chỉ ghi thêm RECOVERY_CASE_CREATED khi INSERT thực sự tạo case; before-object null đúng creation, không đổi Payment/custody/outcome. Không migration, API/protocol/UI/deadline changes hoặc backfill lịch sử. Smoke đầu9 Passed, nhóm sau14 Passed; source freeze178, broad coverage/real E/K/J đang chạy tuần tự, full Backend trên source mới chưa chạy. **Finding chưa đóng**, không dùng599 lịch sử thay kết quả source mới. D01/D02/D04 vẫn PENDING APPROVAL, D03 đã được giao sửa; không Round3/stage/commit/push/8B/8C. [Root cause, coverage21 actions, tests và checkpoint](PHASE8A_NFR06_FIX.md).

## IA01 final full regression 15/11/2026 — COMPLETE

**Full Backend trên source IA01 cuối: 599 Passed, 0 Failed, 0 Errors, 0 Skipped, exit 0.** Label `ia01_full_20261115_02`, chạy 11:20:51–12:10:06 +07; pytest 2947.95 giây (49:07.95), wall wrapper 49:15.405. JUnit xác nhận đủ 599 testcase, không mất 587 ca lịch sử, thêm đúng 12 ca (6 IA01 + 6 operator); multiset node IDs không missing/unexpected. 175 source hashes khớp freeze trước/sau, delta=0. Bốn warnings chỉ gồm TestClient/httpx và OpenAPI deprecations, cùng hai `record_property`/xunit2 warnings; chi tiết trong full log.

Preflight ba mẫu Engine29.9.2/PG healthy/pg_isready/runtime SELECT1 đạt. Hậu kiểm healthy cùng StartedAt, không runner còn lại hoặc power event trong cửa sổ query. Fixture chính schema `phase5_test_5ffc7f268122` trên PostgreSQL17.11, migration/grants theo runner cô lập; không đụng demo/volume/ledger. Không sửa production, tests, migrations/contracts hoặc chạy lại các gate đã đủ evidence: final targeted6, T/E/K exit0 và Browser affected6 Passed. Không cộng các kết quả đó vào full599.

Run `ia01_full_20261115_01` vẫn **Interrupted**, thiếu XML/exit cuối, giữ nguyên evidence; không suy Passed từ dots. Nguyên nhân gốc bugcheck host lịch sử vẫn chưa xác định. Lượt mới dùng PowerShell độc lập có exit/log bền vững, không thay power plan/registry/driver và không tuyên bố ngăn shutdown.

[Log full mới](PHASE8A_TESTS/ia01_full_20261115_02/run.log) · [JUnit](PHASE8A_TESTS/ia01_full_20261115_02/results.xml) · [exit/timestamps](PHASE8A_TESTS/ia01_full_preflight_20261115_02/exit.json) · [collection/hash verification](PHASE8A_TESTS/ia01_full_preflight_20261115_02/verification.json) · [báo cáo sửa IA01 đầy đủ](PHASE8A_IA01_FIX.md).

**IA01 fix verification đã hoàn tất trong phạm vi kỹ thuật được giao; toàn Phase 8A vẫn PARTIAL, không tự sửa kết luận Independent Acceptance gốc thành PASS.** Chưa thực hiện Independent Acceptance lần hai hoặc giải quyết các NFR còn thiếu trong báo cáo đó. Không stage/commit/push, không triển khai 8B/8C; dừng sau full regression. Các checkpoint dưới đây là lịch sử, được giữ nguyên.

## IA01 resume 15/11/2026 — K và Browser đạt, full Interrupted

Không sửa lại production IA01. Freeze175 file trước/sau lượt mới khớp; chỉ bổ sung test-only Browser reboot/old-boot. Read-only diagnostics xác nhận hai bugcheck host14/11 (0x3b/0x13a), chưa xác định driver/cause. Khôi phục Docker bình thường; ba samples readiness đạt, rồi real-process K mới exit0 và **sáu affected Browser tests Passed/exit0**: post, successor, old-boot, pre-reject, revoked, stale-expired. T/E exit0 trước đó được giữ theo source production/đường dispatch tương ứng, không chạy lại.

Collection mới **599**, không mất587 lịch sử, thêm12 (6IA01+6operator). Full đã chạy một lượt trên schema mới, không --lf; **Interrupted**, thiếu XML/exit cuối. Log cuối01:16:24, Windows User321074 ghi power off01:16:25, shutdown6006/13 sau đó; boot07:39:28. Modern Standby09:00→10:13 xảy ra sau, không phải bằng chứng nguyên nhân ngắt full. Hiện Engine pipe mất/không còn runner; dừng không retry. Không suy all-green từ48% progress hoặc 587 lịch sử. **Implementation IMPLEMENTED; verification PARTIAL / ENVIRONMENT BLOCKED**, chưa đóng Major/nghiệm thu. [Diagnostic, XML/JSON/exit, source hashes và resume plan](PHASE8A_IA01_FIX.md).

## P8A-IA01 fix — 14/11/2026, verification PARTIAL/BLOCKED

Shared PRE human handler đã kiểm current boot/provenance cho cả Technician/Customer sau session-lock wait, final expiry/freshness sau reads. POST historical/successor/0.1/authorization guards giữ nguyên. Probe gốc lưu nguyên; theo chấp thuận chỉ bỏ correlation_id khỏi comparison error envelopes, giữ expected refusal và thêm no-write asserts. Source cuối targeted6 Passed; targeted đầu42 Passed thuộc checkpoint trước bước dời final-time check, không cộng trùng. Real-process T và E exit0: old-boot cả hai Backend bị chặn, normal staged E vẫn một effect/audit và bảo toàn custody/Payment/holds. K chưa có kết quả: interrupted01, environment timeout02, interrupted03 sau Docker/process lại mất. Browser và full Backend mới **Not Run**, không dùng 587/15 lịch sử thay thế. Không tuyên bố Major fully FIXED hoặc nghiệm thu. [Bản sửa, XML/exit/checkpoints và việc còn thiếu](PHASE8A_IA01_FIX.md). Không Independent Acceptance lần hai, không commit/push/8B/8C.

## Terminal label — verification cuối source sửa, 14/11/2026

**BROWSER GATES PASSED cho matrix UI canonical 15 scenario; toàn Phase 8A vẫn PARTIAL, chưa Independent Acceptance.** Minor CONSUMED/EXPIRED đã sửa và kiểm chứng. Không coi các Browser variants chưa chạy bên dưới là Passed; phân loại theo acceptance/layer được trình bày ở checkpoint tiếp theo.

Production diff duy nhất của lượt này: `apps/web/src/Recovery.tsx`, phần text banner ưu tiên confirmation_status CONSUMED/CANCELLED/REVOKED, rồi EXPIRED hoặc actual elapsed expiry; active giữ nhãn còn hạn. Customer DTO không có consumed_at/cancelled_at nên banner cũ nhầm mọi closed thành expired. Giữ nguyên closed(op), requestFor, role guards, Backend/migration/overlay/physical simulator và deadlines. Không thêm trạng thái/transition domain. CONSUMED vẫn khóa cả CONFIRM và REJECT.

Frontend Recovery **39 Passed** (33 cũ +6 tests mới), 0 Failed/Skipped; npm run build (TypeScript noEmit + Vite) exit **0**. Tests mới kiểm CONSUMED, CANCELLED, REVOKED, EXPIRED, active và trường hợp đã consumed nhưng TTL cũng qua; không thay expected cũ. [Frontend log](PHASE8A_TESTS/terminal_ui_fix_20261114_01/frontend.log), [build](PHASE8A_TESTS/terminal_ui_fix_20261114_01/build.log), [exits](PHASE8A_TESTS/terminal_ui_fix_20261114_01/exits.json).

### Matrix source sau sửa — chạy mới hoàn toàn

Từng dòng có một fixture PostgreSQL/ledger riêng, hai Backend OS processes, worker/simulator thật và Chromium contexts độc lập; tất cả child runner **exit 0**, mỗi JUnit đúng 1 test Passed, 0 Failed/Errors/Skipped. Không cộng bước operator/API setup vào test Browser.

| Scenario | Kết quả | Thư mục dưới PHASE8A_TESTS |
|---|---|---|
| terminal-label (assertion gốc nguyên vẹn) | Passed | terminal_fix_terminal_label_20261114_01_browser |
| post: PRE → INTENT/ACK → activation → handover → POST → settlement/replay | Passed | terminal_fix_post_20261114_01_browser |
| successor / chain settlement | Passed | terminal_fix_successor_20261114_01_browser |
| PRE REJECT | Passed | terminal_fix_pre_reject_20261114_01_browser |
| POST REJECT | Passed | terminal_fix_post_reject_20261114_01_browser |
| durable closure | Passed | terminal_fix_closure_20261114_01_browser |
| actual stale/expired | Passed | terminal_fix_stale_expired_20261114_01_browser |
| wrong reference | Passed | terminal_fix_reference_20261114_01_browser |
| wrong stage | Passed | terminal_fix_wrong_stage_20261114_01_browser |
| version conflict | Passed | terminal_fix_version_20261114_01_browser |
| duplicate click | Passed | terminal_fix_duplicate_20261114_01_browser |
| response loss (confirmation) | Passed | terminal_fix_response_loss_20261114_01_browser |
| revoked session | Passed | terminal_fix_revoked_20261114_01_browser |
| Admin/Customer/station RBAC | Passed | terminal_fix_roles_20261114_01_browser |
| desktop/mobile smoke | Passed | terminal_fix_smoke_20261114_01_browser |

[Matrix XML references](PHASE8A_TESTS/terminal_ui_fix_20261114_01/browser_matrix.json). Mỗi thư mục chứa results.xml/results.json, console.log, exit.txt và safe-http JSON; parent cùng tên bỏ `_browser` chứa run.log/reports/PHASE8A_E2E_E.json. Ảnh `consumed-label.png` mới có trong artifacts của terminal-label. Source Playwright/failing assertion không thay đổi. Evidence **14 Passed/1 Failed trước sửa** và các harness failures lịch sử giữ nguyên, không sửa hoặc trộn vào 15 lượt mới.

[Audit read-only 15 fixtures sau khi dừng process](PHASE8A_TESTS/terminal_ui_fix_20261114_01/db_ledger_audit.json) exit **0**: không OPEN_SUPPLY; mỗi command effect ≤1 và service handover tổng ≤1/fixture; không duplicate proof/success audit; Payment đúng một SUCCEEDED, session REVIEW_REQUIRED, old_pin_settled=false, new_pin_delivered=UNKNOWN, ba holds, pin cũ đúng Customer và pin cấp COMPARTMENT. Fingerprint demo tám bảng của runner không đổi. Tool audit chỉ bổ sung allowlist prefix `terminal_fix_*` để đọc báo cáo mới, giữ default cũ; không viết DB hoặc tạo proof.

[Source delta](PHASE8A_TESTS/terminal_ui_fix_20261114_01/source_delta.json): Recovery.tsx, frontend test recovery.test.mjs và test-only phase8a_browser_audit.py. [Manifest trước](PHASE8A_TESTS/terminal_ui_fix_20261114_01/source_before.json)/[sau](PHASE8A_TESTS/terminal_ui_fix_20261114_01/source_after.json) xác nhận Backend/migrations/contracts/recoveryModel/Playwright assertions không đổi. Không chạy lại Backend 587 tests; 587/102 E2E/17 concurrency là bằng chứng lịch sử, không cộng vào lượt này. Scan 143 text artifacts không thấy fixture credential/JWT; raw HAR/trace/video vẫn tắt, private.json và ledger vẫn local ignored. [Security scan](PHASE8A_TESTS/terminal_ui_fix_20261114_01/security_scan.json).

Các biến thể reboot/old-boot, UNKNOWN/PREPARED closure, witness role/assignment race, legacy 0.1 và riêng settlement-response-loss vẫn **Browser Not Run**, có evidence tương đương ở Backend/operator/E2E như bảng phân loại bên dưới; chúng không bị bỏ khỏi technical acceptance. Mobile full staged là coverage mở rộng deferred, chỉ mobile smoke được ghi Passed. Matrix UI bắt buộc đã đạt; chưa tự tiến hành Independent Acceptance hoặc kết luận toàn 8A đạt nghiệm thu. Nếu nghiệm thu yêu cầu bổ sung Browser cho từng tổ hợp đó, cần chạy thêm, không lấy kết quả tầng khác đổi nhãn Browser.

Working/staged diff --check đạt. Git HEAD e4fb9f5 không đổi, index trống; [status và số file chính xác](PHASE8A_TESTS/terminal_ui_fix_20261114_01/git_summary.json), [toàn bộ paths cần bảo toàn](PHASE8A_TESTS/terminal_ui_fix_20261114_01/git_status.txt). Các sửa đổi tích lũy trước lượt được giữ nguyên. Không stage/commit/push, không xóa schema/cache/ledger/credentials/evidence hoặc volumes. Cache build dist có thể tái tạo trong lượt dọn riêng; không xóa .cache tổng vì chứa runtime ledger. Dừng sau UI verification, không triển khai 8B/8C.

## Customer terminal label fix — 14/11/2026, verification đang chạy

Root cause đã xác nhận: Customer DTO cung cấp confirmation_status, không cung cấp consumed_at/cancelled_at. Banner cũ dùng closed(op) như đồng nghĩa expired. Sửa duy nhất production `apps/web/src/Recovery.tsx`: ưu tiên CONSUMED/CANCELLED/REVOKED từ projection và các timestamp terminal hiện có, sau đó EXPIRED/expiry; active giữ “Operation còn hạn”. Không sửa closed(), requestFor(), Backend, schema, migration, protocol hoặc deadlines. Không thêm enum domain. Lời chứng/guards/controls giữ nguyên.

Frontend mới 39 Passed (33 cũ +6 label/guard cases), TypeScript/Vite exit 0; logs/exits trong `PHASE8A_TESTS/terminal_ui_fix_20261114_01`. Failing assertion terminal-label giữ nguyên; fixture mới `terminal_fix_terminal_label_20261114_01_browser` đã Passed, post cũng Passed. Matrix 15 nhánh đang chạy tuần tự, chưa có kết quả toàn bộ. Evidence 14 Passed/1 Failed trước sửa được giữ nguyên ở phần lịch sử bên dưới.

### Phân loại Browser variants (không đổi acceptance scope)

FR12/UC10/BR05/09/11/12, AD-04b/SM-03b và P8 overlays yêu cầu nguồn bằng chứng, phục hồi và guards; không quy định mọi tổ hợp lỗi thiết bị phải lặp ở Browser. CT06/08/09/10/11 kiểm durability/unknown/order/quyền/replay; dùng PostgreSQL và OS-process E2E để chứng minh chúng, không gọi kết quả đó là Browser Passed. Các thao tác người dùng PRE/POST/successor/closure, nhãn trạng thái và refusal UI là Browser gates bắt buộc của matrix canonical đang chạy.

| Variant | Phân loại / bằng chứng / giới hạn |
|---|---|
| Simulator reboot / old boot | Yêu cầu kỹ thuật bắt buộc CT06/09; bằng chứng tương đương real-process ER-01/ER-02/F và gate E2E102 trên Backend/simulator hash không đổi. Browser expiry/successor bắt buộc chạy mới; reboot/old-boot riêng ở Browser vẫn Not Run, không suy Passed |
| UNKNOWN/PREPARED closure negative | Bắt buộc fail-closed theo ER-02, đã có operator U/S và PostgreSQL/service-ledger tests; đây là trạng thái ledger, không phải proof người dùng được sửa trên UI. Browser positive closure/refusal status là gate riêng; negative physical-ledger variant Browser Not Run |
| Witness role/assignment race | Bắt buộc final-decision serialization, đã có 17 deterministic two-process scenarios và revocation fix, hash Backend không đổi. Browser revoked-session/403 station gates chạy mới; không gọi sequential Browser test là chứng minh race |
| Legacy 0.1 confirmation | Bắt buộc backward compatibility ở API/DTO/guards, đã có API/Customer projection regression và frontend guards; không sửa request model trong increment này. Browser 0.1 confirmation riêng chưa chạy; bằng chứng tầng khác được giữ riêng, không bỏ hỗ trợ legacy hoặc đổi protocol để né test |
| Settlement response-loss | Bắt buộc durable idempotency CT11; E/K/J crash trước/sau commit, exact settlement replay, source Backend không đổi. Browser response-loss tại confirmation và settlement exact replay được kiểm riêng; Browser drop-response riêng tại settle chưa chạy, không gộp với confirmation |
| Mobile full staged workflow | Optional mở rộng coverage trong lượt này: MVP không có workflow riêng cho mobile; NFR responsive cơ bản dùng mobile smoke. Full staged mobile deferred, không tuyên bố nó Passed hoặc dùng desktop làm bằng chứng mobile |

Các variant tương đương không phải waiver của business acceptance: Independent Acceptance vẫn phải kiểm source/log và freshness của evidence tương ứng. Nếu yêu cầu riêng bắt buộc Browser cho từng tổ hợp được bổ sung, các dòng Not Run vẫn là gate cần chạy; lượt này không tự đổi FR/UC/BR hay biến API-only thành Browser.

## Automated Browser — kết quả cuối lượt resume 14/11/2026

**BROWSER ACCEPTANCE PARTIAL: 14 scenario Passed, 1 Failed (Minor UI); không có Major/Blocker mới được tái hiện.** Không chốt toàn Phase 8A, không chạy Independent Acceptance. Các checkpoint phía dưới giữ nguyên theo thời điểm ghi nhận.

Playwright Test **1.65.1**, Chromium **159.0.8154.6** revision 1255, Node 24.22.1/npm 11.19.1. Dùng Chromium headless riêng, không Computer Use/CDP hoặc Chrome profile người dùng. Cấu hình workers=1/retries=0; fixture chạy tuần tự, mỗi nhánh schema PostgreSQL `phase5_test_*` và ledger riêng. Hai API OS processes 8070/8071, Vite 5190/proxy đúng Backend; Browser contexts sẵn sàng trước receipt mới. Không dùng SQL UPDATE custody/proof, chỉnh timestamp hoặc nới ACK15/physical60/freshness15/TTL120. Login một lần mỗi context, không reset limiter. Diagnostic cũ đã hết lockout nhưng counter vẫn 5; fixtures mới có credentials riêng, không dùng tài khoản cũ để brute force.

### Matrix Browser thật

Mỗi dòng là **một Playwright test**, dù chứa nhiều bước/assertions. INTENT/ACK, activation, handover, POST và settlement dùng chung test `post`, không cộng thành nhiều test. Các checks setup API của runner không tính là Browser Passed.

| Scenario / thư mục Browser trong PHASE8A_TESTS | Kết quả / exit con | Bằng chứng UI/HTTP/DB chính |
|---|---|---|
| playwright_smoke_20261114_01 | Passed / 0, kế thừa lượt cài | Frontend thật, hai contexts login 200, role projection, logout Technician 200 không ảnh hưởng Customer; mobile 390px không tràn ngang |
| playwright_post_20261114_03 | Passed / 0, thu hồi session cũ | PRE hai human proofs → INTENT/ACK → activation → HANDOVER → POST hai human proofs → settle 200; exact same-key/body replay 200 cùng response; một settlement audit/service effect |
| playwright_pre-reject_20261114_02 | Passed / 0, mới | Customer REJECT 201; authorization disabled, không service effect |
| playwright_post-reject_20261114_02 | Passed / 0, mới | POST REJECT 201; một handover effect, settlement disabled; chưa consume operation |
| playwright_reference_20261114_02 | Passed / 0, mới | Wire receipt hash sai → 409 RECOVERY_STAGE_CONFLICT; không accepted human proof/effect |
| playwright_version_20261114_02 | Passed / 0, mới | expected_version sai → 409 VERSION_CONFLICT; đúng một POST, hiển thị lỗi/refresh, không tự retry |
| playwright_duplicate_20261114_02 | Passed / 0, mới | Double click → một POST, một Customer attestation, không effect |
| playwright_response-loss_20261114_02 | Passed / 0, mới | Cho Backend commit confirmation rồi abort response; UI báo network error/tra cứu lại, một POST/attestation, không tự retry |
| playwright_revoked_20261114_02 | Passed / 0, mới | Logout qua API chỉ setup revoke; Browser click thật bị preflight GET 401, về login, không phát confirmation POST |
| playwright_closure_20261114_02 | Passed / 0, mới | Chờ TTL thật; UI CLOSE_NO_EFFECT 200, operator receipt/closure ACK hợp lệ; một closure audit, fence CLOSED, không service effect |
| playwright_successor_20261114_02 | Passed / 0, mới | Chờ expiry thật, successor inspection mới/read-only, hai human attestations ở RECONCILIATION_INSPECTION, chain settle/replay 200, hai operation consumed; một effect/audit; Customer refresh thấy CONSUMED và không thể confirm lại |
| playwright_wrong-stage_20261114_01 | Passed / 0, mới | Gửi stage POST với receipt PRE → 409 RECOVERY_STAGE_CONFLICT; không ghi accepted proof mới |
| playwright_stale-expired_20261114_01 | Passed / 0, mới | Đồng hồ thật vượt freshness15: Customer UNAVAILABLE/disabled; vượt TTL: EXPIRED/disabled, không effect/settlement |
| playwright_roles_20261114_02 | Passed / 0, mới | Admin UI read-only + supplemental Browser-origin mutation 403; Customer khác chủ GET 404 và không thấy context; Tech ngoài assignment GET Recovery 403; logout/đổi principal không giữ UI riêng của Admin |
| playwright_terminal-label_20261114_01 | **Failed / 1, Minor mới** | Backend CONSUMED/đúng DB nhưng Customer banner EXPIRED dù còn hạn; assertion giữ nguyên, không skip/xfail |

[Matrix JSON, schema/runtime, XML, từng exit và duration](PHASE8A_TESTS/playwright_resume_audit_20261114_01/browser_matrix.json), [tổng số](PHASE8A_TESTS/playwright_resume_audit_20261114_01/browser_totals.json). Từng thư mục Browser có results.xml/results.json và safe-http-*.json; thư mục `playwright_fixture_<scenario_dùng_underscore>_20261114_<run>/reports/PHASE8A_E2E_E.json` có DB snapshot/fingerprint. Operator INSPECT/ACK/HANDOVER/REINSPECT/CLOSE là API/device setup phối hợp; human confirmations và quyết định chính đi qua UI thật. Supplemental API calls được phân biệt với các UI flows.

### Lỗi mới và lịch sử test harness

**Minor: terminal label của Customer.** Repro: chạy scenario `terminal-label` trên fixture mới → workflow E settle thành công → refresh Customer. Projection trả confirmation_status=CONSUMED; UI đồng thời ghi EXPIRED. Operation còn khoảng 100 giây TTL khi consume, không phải expiry thật. `OperationDetails` trong `apps/web/src/Recovery.tsx` chỉ kiểm consumed_at/cancelled_at rồi dùng `closed(op)` làm nhánh EXPIRED; Customer DTO chỉ có confirmation_status. `closed()` chặn CONSUMED đúng cho mutation, không nên sửa guard đó. Bản sửa đề xuất: riêng phần rendering dùng trạng thái Backend hiện có để phân biệt consumed/cancelled/revoked/expired. **Chưa sửa production.** Nếu được giao sửa riêng, kiểm lại frontend 33 tests/typecheck/build và Browser terminal-label/PRE/POST/successor; Backend/contract không cần thay đổi để sửa nhãn này.

[JUnit failing regression](PHASE8A_TESTS/playwright_terminal-label_20261114_01/results.xml), [ảnh đúng tại assertion](PHASE8A_TESTS/playwright_terminal-label_20261114_01/artifacts/staged-staged-Browser-terminal-label-chromium/consumed-label.png). Test vẫn yêu cầu không có EXPIRED khi đã CONSUMED; DB/controls không bị thay đổi để làm Passed. Failure này không phải double effect, custody hay authorization bypass.

Giữ nguyên ba lượt harness cũ, không tính chúng là lỗi production đã được sửa: post 01 timeout do locator (chưa tạo operation); post 02 timeout vì Customer representation cũ sau Technician proof, UI không phát POST; roles 01 test mới chờ nhầm 403 ở GET swap khác chủ, thực tế 404 đúng OpenAPI gốc (“bị ẩn vì khác chủ”) và test_phase8a_customer_projection.py. Chỉ sửa expected của test Browser mới cho GET ownership theo contract 404; giữ nguyên tất cả regression Backend và expected business behavior. Không đổi 403 của mutation/Technician scope. Đồng thời sửa logger chờ error-body trước khi kết xuất để không mất status/code cuối lúc assertion thất bại.

Như vậy **canonical matrix 15 tests: 14 Passed, 1 Failed, 0 Errors/Skipped**. Nếu tính toàn bộ 18 Browser executions kể cả harness lịch sử: **14 Passed, 2 Failed, 2 Errors (timeout)**; không gọi tổng này là một full suite. Một lần lỗi LABEL chứa dấu gạch nối xảy ra trước fixture/Browser, không thuộc số test Browser. Tất cả log/XML/JSON cũ vẫn còn. Child runner exit 1 của terminal-label/roles 01 được giữ; outer PowerShell loop exit không thay thế exit con/JUnit. Run post 03 đã thu hồi exit Python 0, không phải suy từ progress log.

### Invariants và kiểm chứng cuối

[Audit read-only v2 trên 18 schema/ledger được giữ](PHASE8A_TESTS/playwright_resume_audit_20261114_01/retained_db_ledger_audit_v2.json) chạy exit 0: sau khi process fixture đã dừng, session đều REVIEW_REQUIRED, old_pin_settled=false, new_pin_delivered=UNKNOWN, đúng một Payment SUCCEEDED, ba holds còn giữ; pin cũ CUSTOMER đúng principal, pin cấp COMPARTMENT. Không có OPEN_SUPPLY; mỗi command effect ≤1, tổng service handover effect ≤1/fixture; không duplicate accepted (operation,stage,source), foreign-object settlement/closure success audit ≤1. Command OPEN_RETURN ban đầu và service handover là **hai loại effect riêng**, không gọi tổng mọi tác động là một. Case OPEN/EVIDENCE_RECORDED được phân biệt với swap session REVIEW_REQUIRED. Successor consume chain không giải quyết nghĩa vụ pin cũ; closure không giải phóng holds.

Mọi fingerprint demo trong parent reports và audit đều không đổi **trong phạm vi tám bảng của runner**: stations, devices, compartments, batteries, battery_telemetry, device_events, swap_transactions, resource_reservations. Không diễn giải thành checksum toàn Database. Ledger chưa khởi tạo được audit ghi null, không suy thành NEVER_PREPARED. Các closure dương có receipt/fence thật, không dựa vào missing receipt.

Chạy mới ngoài Browser: local operator/fence/closure **25 Passed**, frontend Recovery **33 Passed**, reporter redaction **1 Passed**, TypeScript/Vite build và typecheck riêng Playwright exit 0. Không cộng Node tests vào pytest. Backend **587 Passed**, E2E **102 checks**, concurrency **17 scenarios** và operator E/K/J/U/S là kết quả lịch sử giữ theo source tương ứng, không chạy lại full pytest. So sánh 247-file baseline đúng sau fixture fix và operator snapshot 120 file: không có delta production/migration/overlay; thay đổi package/lock/tooling được tách riêng. [Hash/dependency checks](PHASE8A_TESTS/playwright_resume_audit_20261114_01/source_comparison_corrected.json), [tooling checks](PHASE8A_TESTS/playwright_resume_audit_20261114_01/tooling_checks.json).

Reporter không ghi raw HAR/trace/video; screenshots chỉ sau login. Scan cuối 165 text artifacts không thấy password fixture/JWT, không có HAR/trace ZIP; reporter test dùng credential giả hoàn toàn. [Scan cuối](PHASE8A_TESTS/playwright_resume_audit_20261114_01/security_scan_02.json) có thẩm quyền cho lần quét đó; scan 01 là preliminary có lỗi xử lý file rỗng, không dùng làm bằng chứng quét hoàn chỉnh. Credentials thật chỉ ở private.json local, không chép vào report/Git.

### File, chạy lại và giới hạn

Giữ source/tooling: apps/web/package.json + package-lock.json (chỉ thêm devDependency @playwright/test và scripts); playwright.config.ts; e2e/{support,smoke.spec,staged.spec,roles.spec,redact-reporter}.ts và README; tests/playwright-reporter.test.mjs; tools/phase8a_branches.py, phase8a_manual_operator.py và phase8a_browser_audit.py; hai báo cáo và hướng dẫn. [Lệnh chạy lại, fixture isolation và toàn bộ scenario](../apps/web/e2e/README.md). Không đổi Backend/Frontend production, simulator business source, migration, overlay hoặc baseline trong lượt này; các sửa đổi tích lũy trước lượt vẫn được bảo toàn.

Mỗi scenario dùng label mới, ports riêng, không gọi npm test:e2e trống trên cùng một runtime để nối nhiều workflow độc lập. Runtime/metadata/ledger và private credentials giữ dưới .cache/p8-E-*; artifacts dưới PHASE8A_TESTS. Không đưa private/cache/node_modules/dist/screenshot/XML/runtime vào bulk commit. Chromium cache mới khoảng **742.73 MiB**, ba Playwright dev packages khoảng **18.18 MiB**; các thư mục này có thể tái tạo nhưng chưa xóa. Không được dọn toàn .cache vì còn ledger/evidence.

Sau test: ports **8070/8071/5190 không còn listener**, không còn Chromium thuộc workspace cache. Các listener manual cũ **5180/8030/8031** vẫn hiện với PID 27500/13760/25804, không bị dừng/thay thế. PostgreSQL healthy/pg_isready accepting. Đây là trạng thái cuối mới quan sát, không sửa ngược diagnostic lịch sử từng không thấy listener. [Process evidence](PHASE8A_TESTS/playwright_resume_audit_20261114_01/process_after.json).

Git cuối: main...origin/main, HEAD e4fb9f5, ahead/behind 0/0, index trống; 15 tracked modifications tích lũy và 632 untracked files được bảo toàn. [Status đầy đủ](PHASE8A_TESTS/playwright_resume_audit_20261114_01/git_status_final_v2.txt), [số lượng cuối](PHASE8A_TESTS/playwright_resume_audit_20261114_01/git_summary_v2.json). Cả working/staged diff --check đạt; cảnh báo CRLF→LF không phải whitespace error. [257 file source cuối khớp freeze](PHASE8A_TESTS/playwright_resume_audit_20261114_01/source_final_verification_v2.json). Không reset/restore/dọn file. Những sửa đổi production có từ các lượt Phase 8A trước vẫn nằm trong working tree, không được coi là thay đổi của lượt Browser này.

Chưa chạy Browser variants simulator reboot/old-boot, UNKNOWN/PREPARED closure negative, witness role/assignment race, legacy 0.1 confirmation hoặc response-loss riêng tại settlement. Những ca tương ứng có bằng chứng Backend/operator lịch sử theo scope trước; không ghi chúng là Browser Passed. Mobile chỉ smoke/projection, không phải toàn workflow mobile. Independent Acceptance và Phase 8B/8C Not Run. **Chưa chốt BROWSER GATES PASSED vì terminal-label còn Failed; toàn Phase 8A vẫn PARTIAL.** Dừng để review Minor/UI và các phạm vi Browser còn lại, không sửa production, stage, commit hoặc push.

## Playwright resume — 14/11/2026 (đang chạy staged matrix)

**Finding mới, Minor — Customer terminal label.** Screenshot thật `playwright_successor_20261114_02/artifacts/staged-staged-Browser-successor-chromium/customer-final.png` sau refresh hiển thị confirmation status CONSUMED nhưng dòng trạng thái operation là EXPIRED, dù successor còn hạn. DB consume hai operation đúng, các nút Customer disabled và session vẫn REVIEW_REQUIRED. Nguyên nhân: Customer projection có confirmation_status nhưng không trả consumed_at; OperationDetails kiểm consumed_at rồi dùng closed(op) (bao gồm CONSUMED) làm nhánh EXPIRED. Không sửa production trong lượt Browser. Cần sửa riêng rendering bằng status hiện có; không cần đổi contract/custody. Đã thêm scenario `terminal-label` với assertion không được hiện EXPIRED sau consume, không skip/xfail hoặc đổi expected để che lỗi. Kết quả chạy riêng sẽ được ghi khi hoàn tất. Nếu sửa UI này, phạm vi kiểm lại cần frontend Recovery/TypeScript/build và Browser terminal-label/PRE/POST/successor; không có lý do chạy lại Backend 587 khi Backend không đổi.

Đã cài devDependency @playwright/test 1.65.1 và Chromium 159.0.8154.6 trong workspace cache; không dùng Computer Use/CDP hoặc phiên đã bị Escape dừng. Auto-review phiên trước bị lỗi usage limit; lượt tiếp tục đã được phép kiểm tra/chạy bằng cùng cơ chế exec, không đổi shell để vượt review. Docker PostgreSQL healthy, pg_isready accepting connections. Lockout fixture cũ kiểm read-only đã hết lúc 10:56:08 UTC, failed_count vẫn 5; không reset counter/password hoặc thử login lại fixture cũ.

Thu hồi `playwright_post_20261114_03/results.xml`: 1 Browser test Passed, 0 errors/failures, browser_exit=0. Workflow thật qua UI PRE → INTENT/ACK → activation → handover → POST human confirmations → settlement/replay. Ledger một effect; một FOREIGN_OBJECT_RETURN_SETTLED audit; Payment SUCCEEDED, 3 holds, custody cũ CUSTOMER/cấp COMPARTMENT; old_pin_settled=false, session REVIEW_REQUIRED, fingerprint demo runner không đổi. Parent report cũ ghi MANUAL_STOPPED vì dùng nhánh manual handoff; browser_exit và JUnit mới là kết quả Browser, không suy từ nhãn đó.

Smoke trước đó 1 Passed (hai contexts, login/logout/role projection/mobile). Run post 01/02 được giữ nguyên: lần đầu locator combobox không khớp, chưa tạo operation; lần hai Customer representation cũ sau Technician proof nên preflight UI không gửi POST. Sửa test dùng combobox accessible role và refresh Customer sau proof của Technician, không sửa production hoặc expected assertions. Không có HTTP VERSION_CONFLICT ở hai lượt timeout này.

Lượt resume đã chạy PRE REJECT, POST REJECT, sai receipt hash, VERSION_CONFLICT và duplicate click trên năm schema/ledger riêng: mỗi scenario 1 Passed, runner exit 0. Các nhánh response-loss/revoked/closure/successor đang chạy tuần tự; chưa ghi Passed trước khi có kết quả. XML/HTTP/DB nằm trong `PHASE8A_TESTS/playwright_*_20261114_02` và `playwright_fixture_*_20261114_02`.

Chạy mới local tooling/fence/closure: 25 Passed (`playwright_tooling_regression_20261114_01`); frontend Recovery 33 Passed, TypeScript/Vite build exit 0. Hash baseline full source đã sửa fixture (247 file) và operator baseline (120 file) không có thay đổi production; delta là package/lock và tooling, xem `playwright_resume_audit_20261114_01/source_comparison_corrected.json`. Không chạy lại 587 Backend tests. Full regression/E2E/concurrency lịch sử không cộng vào các số Browser mới. Phase 8A vẫn PARTIAL, Independent Acceptance chưa chạy.

## Automated Browser preflight — 14/11/2026, BLOCKED

Người dùng đã chấp thuận một lượt Browser automation riêng, không tiếp tục Computer Use bị dừng. Lượt này không gọi Computer Use, không điều khiển Chrome và không thử đường CDP/raw Browser khác. Theo điều kiện người dùng yêu cầu dừng khi framework không khả dụng, đã dừng ở preflight.

Kiểm tra ngoài sandbox xác nhận Node có sẵn nhưng repository không resolve được playwright, @playwright/test, puppeteer hoặc selenium-webdriver; .venv không có Python playwright; không có thư mục ms-playwright tại cache user chuẩn. apps/web/package.json chỉ có dev/build/preview/test:recovery, không có Browser E2E script. 33 frontend tests trước đây là Node tests, không thay thế Browser. Không cài dependency hoặc tải Browser trong lượt này. Không có từ chối auto-review; blocker là framework chưa được cài, không tuyên bố automation bị policy cấm.

PostgreSQL pg_isready accepting connections. Metadata fixture mới nhất vẫn là schema phase5_test_e0e6127e6a44, swap 5236e3bb-378e-43ce-b99d-02d68509e1fa, runtime p8-E-849cb1eca3, Vite cấu hình proxy 5180 → API 8030. Preflight hiện không thấy listener 5180/8030/8031, vì vậy không có Backend live để xác minh schema đang phục vụ qua HTTP. Không suy metadata cũ là runtime hiện tại. Không tạo fixture mới vì Browser framework gate đã Blocked.

### Diagnostic LOGIN RATE LIMIT

Truy vấn read-only tại 10:43:26 UTC (17:43:26 Asia/Bangkok) trên đúng schema fixture:

- User technician tồn tại, role TECHNICIAN, state ACTIVE. Kiểm private password với hash bằng hàm verify hiện có trả true, không in password/hash/token.
- Bucket username technician và bucket IP loopback đều failed_count=5, window_started_at 10:38:25 UTC, locked_until 10:53:50.844445 UTC, currently_locked=true.
- Theo source identity.login, bucket đang khóa bị trả 429 LOGIN_LIMITED trước khi kiểm password. Username và IP đều có thể chặn request. Đây là hành vi limiter đúng quy tắc. Không thể kết luận nguyên nhân từng lần thất bại chỉ từ counter; không lưu/cố thu thập payload password để điều tra.
- Không gửi login request, không reset counters, đổi password, bỏ limiter hoặc UPDATE auth data. Thời điểm khóa dự kiến hết là **17:53:50.844 ngày 14/11/2026** theo đồng hồ DB; cần kiểm lại read-only trước lần thử tiếp theo, không giả định đã hết hoặc login chắc chắn thành công.

[Auth diagnostic đã loại secret](PHASE8A_TESTS/browser_automation_preflight_20261114_01/auth_readonly.json), [Browser gate/listeners](PHASE8A_TESTS/browser_automation_preflight_20261114_01/browser_gate.json).

| Browser flow được giao | Kết quả | Lý do/bằng chứng |
|---|---|---|
| 1 Login/logout và role isolation | Not Run / dependency Blocked | Framework unavailable; fixture username/IP còn lockout khi kiểm |
| 2 Customer/Technician projection | Not Run | Chưa có Browser automation hoặc live fixture |
| 3 PRE CONFIRM/REJECT | Not Run | Chưa có Browser run |
| 4 INTENT/operator ACK | Not Run | Chưa có Browser run |
| 5 Activation/operator HANDOVER | Not Run | Không gọi physical action |
| 6 POST receipt/human confirmations | Not Run | Chưa có Browser run |
| 7 Settlement/idempotent replay | Not Run | Chưa có Browser run |
| 8 Successor reboot/expiry | Not Run | Chưa tạo fixture Browser nhánh riêng |
| 9 Durable closure | Not Run | Chưa tạo fixture Browser nhánh riêng |
| 10 RBAC/ownership/reference/stale/revocation/duplicate/version | Not Run | Chưa có Browser run |

Tổng Browser tự động trong lượt: 0 Passed, 0 Failed, 10 nhóm Not Run; preflight framework Blocked và login fixture Blocked. Không có screenshot/trace Browser mới, không dùng API-only hoặc log lịch sử để ghi Passed. Manual smoke user-reported trước đây vẫn giữ nguyên nguồn và phạm vi.

Chỉ thêm bằng chứng read-only và cập nhật docs. Không sửa source, không chạy full pytest hoặc targeted Browser tooling (chưa triển khai tooling mới). Các gate regression/E2E/operator lịch sử vẫn giữ theo snapshot tương ứng. Phase 8A PARTIAL/BLOCKED cho Browser automation, Independent Acceptance chưa chạy. Bước tiếp theo cần một lượt thiết lập Playwright/framework cùng Browser binary phù hợp rồi kiểm lại lockout và dựng fixture Browser riêng; không ép Passed bằng né limiter. Git cuối preflight main...origin/main, HEAD e4fb9f5, 14 tracked modifications tích lũy, 453 untracked, index trống; diff --check đạt.

## Resume manual staged Browser — 14/11/2026

**Fixture ready cho người dùng, Browser gates vẫn PARTIAL.** Không Computer Use, không mở Chrome hoặc gửi human/operator action. Phiên cũ không có listener 5180/8030/8031 và không còn process đúng runtime. Log Vite chỉ ready; nguyên nhân biến mất **Unknown**, giữ nguyên evidence/runtime.

Tạo nhãn manual_staged_resume_20261114_01 bằng runner chuẩn, schema phase5_test_e0e6127e6a44, runtime .cache/p8-E-849cb1eca3, swap 5236e3bb-378e-43ce-b99d-02d68509e1fa. Frontend 5180, APIs 8030/8031. Listener PID 27500/13760/25804; operator launcher 7448, Python thực 19832, worker xử lý snapshot. Frontend/proxy/API health 200; ba role login/me/logout preflight 200. Không lưu token/password trong báo cáo. Credentials chỉ ở private.json cục bộ.

Đọc DB/ledger trước bàn giao: Recovery OPEN v1, chưa có operation, old_pin_settled=false, new_pin_delivered=UNKNOWN; Payment SUCCEEDED, 3 holds, service effects=0, có 28 accepted/processed snapshot tại thời điểm đọc. Không tự INSPECT, ACK, HANDOVER, confirm hoặc settle. Preflight auth là API readiness, không phải Browser Passed. [JSON readiness](PHASE8A_TESTS/manual_staged_resume_20261114_01/ready_checks.json).

[Hướng dẫn phiên hiện tại](PHASE8A_BROWSER_MANUAL.md) có thứ tự A–G, lệnh operator đúng runtime, yêu cầu hai Chrome contexts do người dùng tự mở, reference/accepted receipt/freshness, expected HTTP và đối soát DB/audit/ledger. Giữ processes mới chạy, chờ người dùng. Các nhánh REJECT/successor/closure/negative dùng phiên riêng sau khi E hoàn tất; chưa tạo hoặc chấm Passed ở lượt này. Không sửa source, migrations hoặc baseline; không chạy full pytest/Independent Acceptance, không commit/push.

## Operator real-process verification — 14/11/2026

Git cuối lượt main...origin/main, HEAD e4fb9f5; 14 tracked modifications tích lũy, 449 untracked được giữ nguyên, index trống; git diff --check đạt.

**OPERATOR ACTIONS PASSED IN VERIFIED SCOPE.** Năm scenario E/K/J/U/S riêng biệt đạt exit 0; 25 targeted tests trên tooling cuối đạt 25 Passed, 2,59 s. Không cộng 4 setup checks lặp lại trong mỗi runner vào số scenario, không cộng vào full pytest 587 hoặc E2E lịch sử 102. Browser stage flows vẫn Not Run; manual smoke cơ bản user-reported được giữ riêng.

Tái sử dụng nhánh E tạo fixture bằng API/domain services, hai Backend OS process 8050/8051, worker và simulator/SQLite ledger riêng từng schema. Hook --operator-check dừng trước operation rồi driver cấp request file cho **đúng adapter tools/phase8a_manual_operator.py** đang chạy ở OS process khác. Human role/INTENT/activation/settlement trong lượt này là API test tự động trên fixture, không phải thao tác Browser. Snapshot/inspection/effect lấy từ model thật; không UPDATE SQL custody/proof hay timestamp.

| Scenario/operator actions | Kết quả HTTP, version, custody và ledger |
|---|---|
| E: INSPECT → ACK lặp → HANDOVER → POST → confirmations/settle | Stage sai hoặc receipt hash sai: 409 RECOVERY_STAGE_CONFLICT. Customer activation: 403 FORBIDDEN; Technician activation: 200. POST accepted, hai human statements 200/201, settlement 200 và replay trả cùng identity. Case EVIDENCE_RECORDED v9, một FOREIGN_OBJECT_RETURN_SETTLED, service OBSERVED/effects=1, fence ACTIVE; old_pin_settled=false. HANDOVER lại sau accepted POST bị từ chối vì không còn ACTION task, không effect lần hai. |
| K: effect → operator restart → REINSPECT → chain settlement | Boot đổi thực sự trước negative probe (UUID/string đã chuẩn hóa), old POST proof bị từ chối 409 RECONCILIATION_REQUIRED. Chờ expiry thật; confirmation cũ 409 RECOVERY_OPERATION_EXPIRED. Successor có RECONCILIATION_INSPECTION và ba nguồn current proof, settlement/replay 200, case v10, chain consumed nguyên tử. Một effect predecessor, một success audit, fence ACTIVE. |
| J: NEVER_PREPARED → CLOSE → ACK_CLOSURE lặp | Closure request 200, local no-effect receipt accepted, một RECOVERY_NO_EFFECT_CLOSED. Case OPEN v7, operation cancelled, service không có effect, fence CLOSED và durable operation/command deny records còn trên disk. ACK_CLOSURE lặp idempotent. |
| U: crash thật sau PREPARED → restart → từ chối closure | Test wrapper gọi đúng fault point của simulator rồi process exit 86. Local action ledger PREPARED/service UNKNOWN effects=0 sống qua process restart. Cùng request chưa hoàn tất được xét lại nhưng không thực hiện effect. Backend có thể cấp closure intent (200); **intent không đồng nghĩa closure**. Operator CLOSE bị chặn bởi uncertainty, không có accepted closure receipt/audit, operation không cancelled/consumed, fence ACTIVE, case OPEN v7. |
| S: POST freshness hết hạn | Chờ đồng hồ thật vượt observed_at + policy 15 giây trong khi snapshot vẫn tiếp tục. Technician statement 422 EVENT_STALE; case giữ OPEN v6, không consumed hoặc success audit. Effect trước đó đúng một lần, fence ACTIVE. |

Mọi scenario giữ Payment SUCCEEDED, ba active holds, pin cũ ở Customer và pin cấp trong ngăn; old_pin_settled=false. Fingerprint demo 8 bảng của runner không đổi từng lượt. DB operation states, audit actions và ledger được đọc lại qua một tiến trình độc lập ở cuối. [Tổng hợp DB/ledger/HTTP/action results](PHASE8A_TESTS/operator_verified_20261114_01/summary.json).

Log/JSON/exit riêng: [E](PHASE8A_TESTS/operator_final_E_20261114_01/run.log), [K](PHASE8A_TESTS/operator_final_K_20261114_01/run.log), [J](PHASE8A_TESTS/operator_final_J_20261114_01/run.log), [U](PHASE8A_TESTS/operator_final_U_20261114_01/run.log), [S](PHASE8A_TESTS/operator_final_S_20261114_01/run.log), [targeted JUnit](PHASE8A_TESTS/operator_targeted_final_20261114_01/results.xml). Mỗi folder có exit.json và reports/PHASE8A_E2E_E.json; chữ E trong tên file là runner setup, mode thật nằm trong operator.mode.

Giữ hai failed evidence: operator_real_E_20261114_01 yêu cầu HANDOVER lần hai phải thành công, nhưng ACTION bị rút sau POST nên đúng ra phải từ chối; probe cuối kiểm từ chối và effects=1. operator_real_K_20261114_02 so UUID DB với chuỗi API trong barrier, dẫn tới kiểm trước khi reboot đã processed; HTTP POST statement khi đó còn hợp lệ. Sửa riêng driver để so cùng kiểu, giữ yêu cầu boot cũ phải bị từ chối. K cuối đã đo reboot rồi mới gửi request và bị từ chối. Không sửa production/guards để ép Passed.

Tooling changes: branches.py hỗ trợ cổng cấu hình và verification hook; manual_operator.py dùng trực tiếp activated handover adapter, hỗ trợ URL từ env khi test và drain durable observation outbox sau worker delay. Flush không thực hiện service effect, có thể hoàn tất transport ACK/closure acknowledgment đã được Backend cấp. Thêm operator_verify.py, operator_fault.py (chỉ entry point test schema) để chạy positive/negative/crash. Không thêm API hoặc production changes.

Source hashes trước E/K/J/U được giữ trong operator_final_*_20261114_01_hashes.json; [hash cuối](PHASE8A_TESTS/operator_verified_20261114_01/source_after.json). Production và simulator source khớp giữa các lượt. Driver verification thêm nhánh stale S sau khi batch đầu đã chạy, nên chỉ driver đó khác hash lúc tổng hợp; operator/production không đổi trong final batch. S chạy riêng sau bổ sung. Không tuyên bố source freeze của toàn driver ở mọi thời điểm. Full 587 giữ là bằng chứng production trước đó; chỉ tooling đổi nên không chạy full lại.

Không tác động/dừng/restart fixture Browser 5180. Diagnostic cuối không thấy listener 5180; nguyên nhân fixture cũ đã dừng chưa được xác lập, không tự khôi phục trong lượt này. Để dùng tooling mới cần người dùng mở fixture mới theo hướng dẫn sau khi kiểm các cổng. Không ghi Browser Passed từ các test này. Không có production Major/Blocker mới tái hiện. Chưa kiểm mọi cách crash giữa từng dòng IPC hoặc mọi tổ hợp lỗi mạng; dữ liệu UNKNOWN vẫn fail-closed. Chưa thực hiện Independent Acceptance.

## User-reported Browser smoke và fixture staged thủ công — 14/11/2026

**Passed — manual smoke do người dùng báo cáo**: người dùng đã trực tiếp login Chrome và xác nhận chức năng giao diện cơ bản hoạt động bình thường. Không có trace/status/screenshot theo từng role/stage nên chỉ ghi nhận đúng kết quả tổng quát này. Không dùng nó để đánh dấu PRE/POST/successor, authorization, closure, RBAC hoặc negative cases riêng là Passed.

Đối chiếu matrix cho thấy POST CONFIRM/REJECT, successor, Technician INTENT/ACK/activation/settlement, durable closure và negative ownership/revoke/version/network vẫn **Not Run trên Browser**. Đã thêm tools/phase8a_manual_operator.py và --manual-browser vào runner nhánh E. Setup real API/worker/simulator tạo wrong-return và chờ physical deadline gốc; dừng trước BEGIN_OPERATION. Người dùng tạo operation và mọi lời chứng/quyết định trên UI. Operator chỉ đọc task đã được Backend cấp và thực hiện INSPECT/ACK/HANDOVER/REINSPECT/CLOSE/ACK_CLOSURE khi người dùng tạo request file riêng. Không tự CONFIRM hoặc activate/settle.

25 targeted tests Passed, exit 0, 4,11 s: 6 ca tooling mới dùng SQLite thật/fixture HTTP và 19 fence/closure regression. Kiểm unavailable task không effect, inspection replay giữ original receipt. [JUnit](PHASE8A_TESTS/manual_operator_20261114_01/results.xml). Không coi nhóm này là Browser hoặc real-process positive của các action mới. Full pytest không chạy lại; production không sửa.

Fixture tương tác đang chạy: schema phase5_test_da667ba53f98, swap 20669b58-b66e-44b6-b7b5-bc390d0a6ca3; frontend http://127.0.0.1:5180/, Backend 8030, API thứ hai 8031. Listener PIDs 28236/29084/25700, frontend và proxy health 200. Runtime .cache/p8-E-72062a0670 chứa manual.json, state.json, private.json, logs và ledgers/S01.sqlite3. Recovery OPEN version 1, old_pin_settled=false/new_pin_delivered=UNKNOWN tại bàn giao; chưa có operation hay accepted human proof mới. Credentials chỉ ở file private local.

**PARTIAL**: cần người dùng kiểm các flow theo stage, real-process positive từng action operator mới và negative accounts; chưa có đủ evidence để nói Browser gates đạt. Freshness 15s giữ nguyên, cần hai profile role và operator sẵn sàng trước receipt; không làm mới timestamp. Khi miss window hoặc UNKNOWN, giữ fail-closed. [Hướng dẫn chi tiết, expected HTTP/DB và checklist Independent Acceptance](PHASE8A_BROWSER_MANUAL.md). Phiên PRE cũ giữ nguyên để bảo toàn smoke người dùng; không tự dừng nó.

Chỉ thay test tooling/tests và docs. Không có production changes, không cần full regression lại vì lượt này. Hai runner đã có trong manifest full là customer_browser (từ lượt trước) và branches; operator/test mới cần giữ làm regression. Toàn bộ source/test tooling mới chưa được full suite mới kiểm chung. Không commit/push, không Computer Use, không thực hiện Independent Acceptance.

## Manual Browser preparation — 14/11/2026, PARTIAL

Không sử dụng Computer Use hoặc điều khiển Chrome trong lượt chuẩn bị này. Preflight khớp 247 hashes, Docker/PostgreSQL healthy. Chỉ sửa tools/phase8a_customer_browser.py, thêm --manual để giữ server tới stop marker, giám sát child exit và xuất public.json (không secret). Chế độ mặc định 900 giây giữ nguyên. Không đổi protocol TTL/freshness hoặc source production.

Smoke riêng manual_browser_tooling_20261114_01 tạo schema mới, frontend và proxy /health đều 200; stop marker làm runner exit 0, result.json fingerprint demo 8 bảng không đổi. Schema/ledger/log giữ nguyên. Sau đó mở phiên manual_browser_live_20261114_01, schema phase5_test_f46737c22990, swap 91c2590e-cba6-4c14-8b25-23633473fd0b, operation PRE 36cdb526-73e5-4c5e-9619-cacf87d3e25c. Frontend 5178, Backend 8040, proxy health 200. Giữ các process fixture riêng đang chạy. Credentials chỉ ở .cache/customer-browser-533e8144c9/private.json, không in password/token.

**Chưa đủ full fixture manual acceptance.** Runner mới giữ được server nhưng chỉ có PRE inspection ban đầu, simulator setup đã đóng; freshness 15 giây và operation expiry vẫn giữ nguyên. Có thể kiểm login/read-only/expired-state và responsive. Chưa có legacy/POST/successor/closure dương và operator theo nhịp người dùng, nên không tuyên bố toàn môi trường sẵn sàng. Không tự gửi confirmation/activation/settlement thay người dùng. [Hướng dẫn, flow matrix, tiêu chí HTTP/DB và cách dừng](PHASE8A_BROWSER_MANUAL.md).

247 hashes baseline full regression chỉ khác runner Browser do thay đổi test tooling nêu trên, cần giữ cả manifest lịch sử. Full pytest không chạy lại; Browser chưa có flow Passed. Toàn Phase 8A PARTIAL. Không commit/push, không xóa dữ liệu.

## Real Browser verification — 14/11/2026, BLOCKED do phiên Computer Use bị dừng

**BROWSER GATES BLOCKED.** Computer Use trả thông báo bị dừng bằng phím Escape vật lý khi re-observe tab Chrome trước bước nhập URL fixture. Đã dừng toàn bộ thao tác Computer Use trong lượt, không thử công cụ khác để tiếp tục điều khiển Browser. Không có flow Recovery Browser nào được ghi Passed. Full regression 587 và các gate lịch sử bên dưới vẫn là bằng chứng kế thừa.

Preflight: 247 source hashes khớp manifest sau full run 03, 0 source changes. Docker/PostgreSQL ban đầu startup recovery sau lần shutdown không sạch; log báo redo/checkpoint hoàn tất rồi pg_isready nhận kết nối. Fixture hiện có tools/phase8a_customer_browser.py tạo schema phase5_test_59480d4a6f42 và swap fb421dd9-1ce3-43bd-aa53-5c01a9708a9a. Chuẩn bị bằng TestClient/domain helper + model inspection chỉ là setup fixture, không tính Browser. Không sửa source hoặc deadlines.

Frontend URL http://127.0.0.1:5178/ được Vite log công bố, PID 23584 lắng nghe 127.0.0.1:5178. Backend log công bố http://127.0.0.1:8040, PID 27984 lắng nghe cùng địa chỉ/port; vite.config.ts dùng DEV_API_TARGET=8040 từ runner và proxy /v1,/health. URL đã được xác minh ở lớp runtime/config; chưa mở/xác minh ứng dụng fixture trong Browser. Công cụ @oai/sky qua node_repl đã liệt kê và chọn Chrome window 197886, mở tab mới, quan sát New Tab. Lệnh re-observe tiếp theo trả user physical Escape. Không gửi credentials vào Browser, không login hoặc mutation qua UI.

| Flow bắt buộc | Kết quả Browser | Bằng chứng/điểm dừng |
|---|---|---|
| Xác minh app fixture qua thanh địa chỉ và nội dung Browser | Blocked | Computer Use bị dừng trước nhập URL |
| Customer login/logout, ownership, Customer projection | Not Run | Chưa truy cập app fixture |
| Customer PRE CONFIRM/REJECT | Not Run | Chưa đăng nhập Customer |
| Customer POST CONFIRM/REJECT và exact receipt reference | Not Run | Chưa có thao tác Browser |
| Customer successor RECONCILIATION_INSPECTION | Not Run | Chưa có thao tác Browser |
| Tamper fields, expired/revoked/consumed, reload, 401/403/409 | Not Run | Chưa có request Browser tới Backend fixture |
| Duplicate click, network response loss/no unsafe retry | Not Run | Chưa có mutation Browser |
| Technician operation/stage/context/receipt và attestation | Not Run | Chưa đăng nhập Technician |
| Technician INTENT/ACK/activation, POST và settlement controls | Not Run | Chưa có thao tác Browser |
| Technician successor/no-effect closure/version conflict/out-of-scope station | Not Run | Chưa có thao tác Browser |
| Admin RBAC và đổi principal không giữ dữ liệu cũ | Not Run | Chưa đăng nhập Admin |
| Desktop/mobile responsive | Not Run | Chưa render app fixture trong Browser |

Kết quả Browser trong ma trận: 0 Passed, 0 Failed, 1 Blocked và 11 nhóm Not Run. Không tái hiện lỗi UI hoặc production Major trong lượt; chưa có đủ thao tác để đánh giá các flow. HTTP audit/custody/effect của Browser không có vì chưa gửi request từ app Browser. Bằng chứng runtime/config không thay thế kết quả Browser.

Đã dừng đúng Backend/Vite do fixture này tạo bằng stop marker của runner. Runner exit 0, result.json xác nhận fingerprint demo 8 bảng không đổi. Schema, inspection.sqlite3, log, private.json và marker vẫn giữ trong .cache/customer-browser-12fd73ae89; private.json chứa credential test, tuyệt đối không commit hoặc chép vào báo cáo. [Runner log](PHASE8A_TESTS/browser_20261114_01/run.log). Không dừng PostgreSQL hoặc các tiến trình demo khác. Không có source code thay đổi, chỉ hai báo cáo. Git main...origin/main, HEAD e4fb9f5, 14 tracked modifications tích lũy, 408 untracked, index trống, diff --check đạt.

Hướng dẫn kiểm chứng thủ công trong lượt Browser tiếp theo: khởi chạy runner fixture để lấy runtime/schema/tài khoản test mới; giữ credentials trong file private cục bộ. Đối chiếu URL Vite, API target và PID lắng nghe, rồi kiểm chính URL trên thanh địa chỉ trước login. Đăng nhập từng role, mở Recovery và tra cứu swap của fixture; thực hiện các dòng ma trận trên, ghi HTTP/status cùng DB/audit trước/sau bằng dữ liệu test. Các gate PRE/POST/successor cần receipt mới đúng stage khi quyết định; runner hiện tại chỉ dựng PRE inspection ban đầu, chưa đủ fixture điều khiển thời điểm cho toàn bộ flow Browser 0.2. Cần bổ sung/chuẩn bị các fixture tương ứng một cách hợp lệ trước khi ghi những flow đó Passed. Không làm mới timestamp, kéo dài deadline hoặc dùng custody UPDATE để dựng thành công. Browser và Independent Acceptance còn mở; toàn Phase 8A PARTIAL.

## Full regression cuối — 13/11/2026, FULL REGRESSION GATES PASSED

**FULL REGRESSION GATES PASSED.** Toàn Phase 8A vẫn PARTIAL, chờ Browser và Independent Acceptance. Đã thu hồi run 02 trước khi khởi chạy run 03. Run 03 hoàn tất toàn bộ suite, không dùng --lf hoặc chỉ chạy phần thiếu.

| Lượt | Kết quả riêng | Exit và bằng chứng |
|---|---|---|
| Full run 01 | 586 Passed, 1 Failed, 0 Errors/Skipped. Failure fixture mock task-list không khớp legacy task, trước fence guard. | Exit 1; 2877,05 s. [JUnit](PHASE8A_TESTS/full_regression_20261113_01/results.xml), [log](PHASE8A_TESTS/full_regression_20261113_01/run.log) |
| Targeted sau sửa fixture | 19 Passed. Giữ assertions STATION_FENCED, UNKNOWN, model không đổi và effects=0. | Exit 0; 2,15 s. [JUnit](PHASE8A_TESTS/full_fixture_fence_fix_20261113_01/results.xml) |
| Full run 02 | Interrupted. Không còn pytest process, không có XML/exit code hoàn chỉnh. Log dừng 421 progress markers. | Exit cuối unavailable; không ghi nhận là Passed/Failed suite. [Log giữ nguyên](PHASE8A_TESTS/full_regression_20261113_02/run.log) |
| Full run 03, source cuối | **587 Passed, 0 Failed, 0 Errors, 0 Skipped, 0 xfail/xpass, 0 deselected.** XML có đủ 587 testcase, node IDs khớp collection sau chuẩn hóa UUID ngẫu nhiên. Test fence từng lỗi có mặt và Passed. | **Exit 0**, log 2961,72 s, XML 2961,708 s. UTC 13:56:47 → 14:46:21 (20:56:47 → 21:46:21 Asia/Bangkok). [JUnit](PHASE8A_TESTS/full_regression_20261113_03/results.xml), [full log](PHASE8A_TESTS/full_regression_20261113_03/run.log), [exit](PHASE8A_TESTS/full_source_resume_20261113_01/exits.json) |

587 là kết quả riêng full run 03. Không cộng 19 targeted, 33 frontend, 40 regression lịch sử, 17 race probes hoặc 102 checks E2E vào số này. Đối chiếu historical JUnit 493 và collection mới xác nhận 493 test cũ còn đủ, thêm 94 test; hai parameter IDs có UUID ngẫu nhiên chỉ được chuẩn hóa ở phép so sánh, source không sửa. [Collection delta](PHASE8A_TESTS/full_source_20261113_01/collection_normalized.json).

247 file trước/sau run 03 khớp hoàn toàn, 0 source changes; production/migrations/overlays/test/runners đều không đổi trong lượt. SHA256 manifest trước là F1165D5110CCDDAC77366505CA2914B43FDEB698AE1E9C004CA247ABBD9A7974. So với run 01, chỉ test_phase8a_staged_fence.py khác một dòng simulator(path, legacy) trong ca legacy task. Assertions và deadline không đổi. [Manifest trước](PHASE8A_TESTS/full_source_resume_20261113_01/source_before.json), [sau](PHASE8A_TESTS/full_source_resume_20261113_01/source_after.json), [kết quả đối chiếu XML/source](PHASE8A_TESTS/full_source_resume_20261113_01/verified_results.json), [delta fixture](PHASE8A_TESTS/full_source_20261113_01/fixture_source_delta.json).

Validator/frontend được kế thừa hợp lệ vì các file liên quan giữ hash: baseline OpenAPI/approved JSON Schema/SQL parser 278 statements/design hashes Passed; runtime OpenAPI 40 paths, 22 JSON schemas metavalidation Passed; Python pip check và npm dependencies exit 0; frontend Recovery 33 Passed/0 Failed/0 Skipped; TypeScript tsc --noEmit và Vite production build exit 0. [Exit codes](PHASE8A_TESTS/full_source_20261113_01/validation_exits.json), [validator](PHASE8A_TESTS/full_contracts_20261113_01/run.log), [runtime/schema/security](PHASE8A_TESTS/full_source_20261113_01/runtime_schema_security.json), [frontend tests](PHASE8A_TESTS/full_source_20261113_01/frontend_tests.log), [build](PHASE8A_TESTS/full_source_20261113_01/frontend_build.log).

PostgreSQL 17.11, schema fixture riêng. Environment chuẩn upgrade 0001 → head, upgrade lặp và giữ marker dữ liệu, rồi runtime grants. Một số test race tạo thêm environment/schema riêng; PHASE5_TEST_ENVIRONMENT.json là metadata của lần tạo fixture cuối, không phải inventory mọi schema. Report cuối chỉ đúng schema phase5_test_f788b9aa7ba1. Đọc lại trên schema đó xác nhận revision 0008_recovery_reconciliation, role doi_pin_runtime không có UPDATE/DELETE recovery_attestations. Migration/grants/context immutability/response contract/RBAC đều có testcase Passed trong full XML. Không áp migration vào DB demo. [Read-only grants](PHASE8A_TESTS/full_source_resume_20261113_01/runtime_grants.json).

Run 02 không đủ bằng chứng kết quả cuối, nguyên nhân process bị ngắt chưa xác định. Khi resume, Docker Engine ban đầu mất pipe; PostgreSQL automatic recovery hoàn tất trước run 03, pg_isready đạt trước/sau suite. Không suy ra nguyên nhân run 02 từ Docker recovery. Run 03 bật execution-state chống sleep trên thread chạy batch và giải phóng trong finally. Không ghi nhận interruption ở run 03, source freeze và exit/XML hoàn chỉnh.

Không có production Major/Blocker mới được tái hiện trong full run cuối. Còn 4 warnings: Starlette/httpx deprecation, OpenAPI validate_spec deprecation và hai record_property/xunit2 compatibility warnings trong P7 diagnostic; assertions Passed, 0 skipped. Browser và Independent Acceptance Not Run. Chưa kết luận nghiệm thu toàn Phase 8A.

Chỉ cập nhật hai báo cáo trong lượt resume; bản sửa fixture một dòng thuộc lượt trước được giữ. Bảo toàn run 01/02/03, XML/log/JSON/manifests, schema test, SQLite/device/payment ledgers và .local. Build/cache có thể tái tạo trong lượt dọn riêng; evidence và dữ liệu không được coi là cache. Git main...origin/main, HEAD e4fb9f5; index trống, không commit/push. Git cuối lượt có 14 tracked modifications tích lũy và 407 file untracked được bảo toàn. git diff --check đạt.

## Nhật ký full regression/source validation — checkpoint trước khi hoàn tất

Checkpoint resume lúc 20:54 Asia/Bangkok: run 02 không còn Python pytest/runner process, không có results.xml, fixed_exits.json hoặc source_fixed_after.json. Log dừng 15:44:13, 421 progress markers; đây là lượt Interrupted, không phải kết quả Passed. Không khởi chạy suite trùng. Đối chiếu 247 file hiện tại với source_fixed_before.json có 0 thay đổi. Fixture legacy task-list vẫn đúng legacy representation, giữ nguyên assertions. Docker ban đầu mất engine pipe; sau start, PostgreSQL automatic recovery (database interrupted, last known up 08:40:56 UTC), redo và checkpoint hoàn tất 13:56:40 UTC, pg_isready accepting. Chưa xác lập nguyên nhân tiến trình run 02 bị ngắt. Full run 03 đã khởi chạy trên schema riêng; chưa có kết quả cuối tại checkpoint này. [Log run 03](PHASE8A_TESTS/full_regression_20261113_03/run.log), [manifest/exit checkpoint mới](PHASE8A_TESTS/full_source_resume_20261113_01/). Giữ nguyên toàn bộ run 01/02 và dữ liệu.

Snapshot HEAD e4fb9f5 với working tree tích lũy. Manifest mới bao phủ 247 file source/tests/migrations/schemas/overlays/runners và baseline. Collection 587 tests, 0 deselected. So sánh JUnit 493 cũ với collection mới sau khi chuẩn hóa riêng UUID ngẫu nhiên trong parameter ID cho thấy 0 test bị mất, 94 ca thêm. Không đổi tên/assertion để so sánh. [Collection](PHASE8A_TESTS/full_collection_20261113_01/run.log), [delta](PHASE8A_TESTS/full_source_20261113_01/collection_normalized.json).

Full lượt 01 đã hoàn tất **586 Passed, 1 Failed, 0 Errors/Skipped**, exit 1 trong 2877,05 giây. Failure là test_phase8a_staged_fence.py::test_fence_blocks_legacy_handover_and_unknown_is_not_retried, ValueError SERVICE_TASK_NOT_AUTHORIZED tại service.py:94 trước fence guard. Fixture tạo sim với task 0.2 nhưng gọi perform bằng legacy task đã bỏ protocol_version/task_kind. Task-list mock vì vậy không chứa đúng task được yêu cầu. Sửa đúng một dòng ở test để simulator(path, legacy); inspection vẫn lấy op 0.2, toàn bộ assertions STATION_FENCED, UNKNOWN, model không đổi và effects=0 giữ nguyên. Production không sửa. [Full lỗi](PHASE8A_TESTS/full_regression_20261113_01/run.log), [JUnit lỗi](PHASE8A_TESTS/full_regression_20261113_01/results.xml).

Sau sửa fixture, toàn bộ staged_fence + closure_fence đạt **19 Passed**, exit 0, 2,15 s. Không cộng vào tổng full suite. [Targeted XML](PHASE8A_TESTS/full_fixture_fence_fix_20261113_01/results.xml). Full lượt 02 đã khởi chạy trên schema riêng, chưa có kết quả cuối tại checkpoint này. Runner session OS do công cụ quản lý; ưu tiên đọc run.log/results.xml/fixed_exits.json trước khi chạy lại. [Full lượt cuối](PHASE8A_TESTS/full_regression_20261113_02/run.log).

Validators đã đạt, exit 0. Baseline OpenAPI, approved JSON schema, 278 SQL statements và original design hashes. Runtime OpenAPI có 40 paths, 22 overlay JSON schemas qua metavalidation. Pip check, npm dependency check đạt. Frontend Recovery 33 Passed/0 Failed/0 Skipped; scripts hiện chỉ có test:recovery. Build chạy tsc --noEmit rồi Vite production, exit 0. Quét các secret PASSWORD/KEY/SECRET đang cấu hình (giá trị dài ít nhất 12 ký tự) trong production source và dist không có match. Đây là phạm vi quét, không phải chứng nhận mọi loại secret. [Validator log](PHASE8A_TESTS/full_contracts_20261113_01/run.log), [các log/manifest/exit codes](PHASE8A_TESTS/full_source_20261113_01/).

Browser và Independent Acceptance: Not Run. Toàn Phase 8A PARTIAL trong khi chờ full lượt cuối và đối chiếu manifest. Không commit/push, không dọn dữ liệu hoặc evidence.

## Final-source E2E A–F — 13/11/2026

**E2E INTEGRATION READY FOR FULL REGRESSION.** Toàn Phase 8A vẫn PARTIAL, chờ full regression, Browser và Independent Acceptance. Chạy mới tám runner tuần tự trên tám schema PostgreSQL riêng. Tất cả exit 0. B được kiểm bổ sung restart nên bảng dùng kết quả B cuối 7 checks, không cộng lại 6 checks của B đầu. Tổng kết quả không trùng là **56 checks A–F và 46 checks ER-01/ER-02**, 0 Failed/Blocked trong nhóm này. Đây là checks runner tiến trình, không phải số pytest.

| Nhánh | Checks Passed | Trạng thái DB/ledger cuối và bằng chứng mới |
|---|---:|---|
| A — VERIFY_OLD_POSSESSION | 5 | Case version 6, old_pin_settled=true; pin cũ vẫn đúng Customer, pin cấp trong ngăn. Một MANUAL_RECOVERY_SETTLED, 0 service effect, 3 holds. [JSON](PHASE8A_TESTS/final_source_A_20261113_01/reports/PHASE8A_E2E.json) |
| B — RETURN_OLD_TO_CUSTOMER | 7 | Return tự động trước đó được simulator/worker commit hợp lệ. Manual handover trả pin cũ cho Customer đúng một effect; case version 6, old_pin_settled=true. Kill simulator sau settlement commit, reboot cùng ledger, retry đúng body/key đã thắng trên Backend thứ hai trả lại cùng response. Một audit, 3 holds. [JSON cuối](PHASE8A_TESTS/final_source_B_restart_20261113_01/reports/PHASE8A_E2E.json) |
| C — Pickup UNKNOWN | 5 | C là checkpoint trong runner CD. Ngăn rỗng/EXECUTED và thiếu ba nguồn proof không được settle, custody pin cấp chưa đổi, 3 holds. Late DOOR/PRESENCE bị từ chối trước khi manual proof được cung cấp. [JSON CD](PHASE8A_TESTS/final_source_CD_20261113_01/reports/PHASE8A_E2E_CD.json) |
| D — VERIFY_NEW_DELIVERY | 3 | Cùng runner CD, sau proof thật và deadline gốc. Hai Backend replay một kết quả, một audit. Case version 6, COMPLETED, old_pin_settled=true, pin cũ trong ngăn, pin cấp đúng Customer; terminal holds=0. Command/charge history bằng trước settlement. |
| E — RETURN_FOREIGN_OBJECT 0.2 | 28 | Đủ inspection → intent/ACK → activation → effect → durable receipt → hai human statements → settlement. Crash OS trước commit trả exit 91, consumed=false, 0 settlement audit. Hai Backend retry 200/409 rồi replay cùng kết quả. Một effect và một FOREIGN_OBJECT_RETURN_SETTLED, case version 9, old_pin_settled=false, 3 holds, network custody giữ nguyên. [JSON](PHASE8A_TESTS/final_source_E_20261113_01/reports/PHASE8A_E2E_E.json) |
| F — Offline/reboot/late/UNKNOWN | 8 | Offline giữ review/holds; event muộn có timestamp gốc không advance custody; PREPARED crash thành UNKNOWN qua restart, 0 service effect; proof boot cũ bị từ chối. Case version 6, old_pin_settled=false, 0 success audit, 3 holds. [JSON](PHASE8A_TESTS/final_source_F_20261113_01/reports/PHASE8A_E2E_F.json) |
| ER-01 — successor chỉ đọc | 26 | Có một effect predecessor. Successor dùng proof hiện tại sau reboot, không thêm effect. Backend chết trước commit, chain chưa consumed, 0 audit. Hai Backend retry 200/409, replay một kết quả; cả hai operation consumed, case version 10, một foreign settlement audit. Custody giữ nguyên, 3 holds, old_pin_settled=false. [JSON K](PHASE8A_TESTS/final_source_K_20261113_01/reports/PHASE8A_E2E_K.json) |
| ER-02 — durable no-effect closure | 20 | NEVER_PREPARED, fence ACTIVE trước commit; crash exit 92 sau commit trước HTTP. Replay duplicate, một RECOVERY_NO_EFFECT_CLOSED audit, 0 service effect. Acknowledgment sau commit mới đóng fence và giữ deny record. Case version 7, old_pin_settled=false, custody và 3 holds giữ nguyên. [JSON J](PHASE8A_TESTS/final_source_J_20261113_01/reports/PHASE8A_E2E_J.json) |

Payment ở cả tám fixture vẫn SUCCEEDED. Mỗi runner kiểm fingerprint demo trong phạm vi 8 bảng của helper, không dùng fingerprint đó làm bằng chứng cho toàn Database. Bảng pins, payment, holds, recovery và audit còn được đọc riêng trên từng schema. [Tổng hợp read-only, PID Backend và DB facts](PHASE8A_TESTS/final_source_20261113_01/verified_summary.json).

Snapshot HEAD e4fb9f5 kèm working tree hiện tại. Lưu SHA256 của 116 file Backend, simulator, migrations, overlay, frontend và tools, trước/sau loạt bảy runner đầu hoàn toàn khớp. SHA256 file manifest là 959faeeef1b7fd63ad790b11b859fd231dd02bf302b02f35109044932bcbf08d. Sau loạt đầu, chỉ tools/smoke_phase8a.py thay đổi để bổ sung --handover --restart-after-settlement. Bổ sung này chạy riêng và đạt 7 checks. Không có thay đổi production/contract trong lượt này. [Manifest trước](PHASE8A_TESTS/final_source_20261113_01/source_before.json), [sau](PHASE8A_TESTS/final_source_20261113_01/source_after.json), [exit codes và thời gian](PHASE8A_TESTS/final_source_20261113_01/exits.json), [B bổ sung](PHASE8A_TESTS/final_source_20261113_01/B_restart_exit.json).

Docker healthy, pg_isready accepting connections, PostgreSQL 17.11. Tám schema đều được đọc lại revision 0008_recovery_reconciliation; fixture chạy Alembic/grants riêng. Mỗi runtime có log API, worker, simulator và ledger riêng; hai Backend OS PID được trích từ startup logs trong tổng hợp. Khóa ngăn Windows sleep đặt trên đúng thread chạy batch và được giải phóng tại finally. Không sửa timestamp, không UPDATE custody để tạo proof. Fixture trả phí bằng domain services + mock outcome như thiết kế runner; Payment provider OS E2E không thuộc lượt Recovery này.

ER-01/02 được chạy lại vì các báo cáo cũ không có manifest đủ để chứng minh source trùng với snapshot hiện tại. 17 race probes và 40 pytest revocation kế thừa được giữ, không chạy lại hay cộng vào kết quả trên. Negative quyền/thiếu proof lấy bằng chứng mục tiêu/race đã có; lượt này không tái chạy đầy đủ từng negative trên mọi workflow. B bổ sung chứng minh crash/retry sau commit; crash service PREPARED và restart được kiểm ở F, crash trước/sau DB commit được kiểm ở E/K/J.

Giữ source runner, toàn bộ JSON/log, source manifests, schemas test và ledgers. Logs/runtime/cache và manifest là evidence chưa chọn để commit. Không dọn các file đó trong lượt này. Full-project pytest, Browser và Independent Acceptance còn Not Run. Không có lỗi mới hoặc Major tái hiện. Chỉ thay runner B và hai báo cáo. Git cuối lượt main...origin/main, HEAD e4fb9f5, 14 tracked modifications tích lũy, index trống; 353 file untracked được bảo toàn. git diff --check đạt.

## Final-decision concurrency — 13/11/2026

**FINAL-DECISION RACE GATES PASSED** trong phạm vi ma trận bên dưới. Toàn Phase 8A vẫn PARTIAL. Lượt tiếp tục có 4 probe tiến trình đạt trên lần chạy cuối của từng kịch bản. Hai lần chạy chẩn đoán freshness 02 Failed ở fixture được giữ riêng. 13 kịch bản tiến trình đạt đã có log hoàn chỉnh trước khi tiếp tục, gồm operation expiry và staged freshness. Tổng cộng 17 kịch bản riêng biệt đã đạt, không cộng các assertion lồng nhau, 6 testcase ledger hoặc 40 pytest lịch sử vào con số này.

**Closure cuối trước successor.** Hai Backend OS PID 27632 và 8084. Sau audit write, khi transaction vẫn mở, kết nối khác thấy operation chưa cancelled và PG 1736 chặn 1719. Backend đầu commit closure rồi chết trước khi trả response. Successor đang chờ dùng version 6 nhận 409 VERSION_CONFLICT. Thử lại với version 7 nhận 409 RECONCILIATION_REQUIRED. Chỉ một operation, một closure audit và 0 service effect. Ba receipt không hợp lệ (thiếu NEVER_PREPARED, PREPARED, UNKNOWN) đều trả 422 trước đó, chưa có closure receipt/audit, fence ACTIVE và operation chưa đổi. Sau replay closure đã commit, simulator xác nhận, fence CLOSED và deny record vẫn bền vững. Custody pin cũ ở Customer, pin cấp ở ngăn, Payment SUCCEEDED, 3 holds, swap REVIEW_REQUIRED. Runner có 24 checks bao gồm cả setup, replay và các assertion nói trên. [JSON và danh sách checks](PHASE8A_TESTS/final_gate_committed_closure_01/reports/PHASE8A_E2E_J.json).

File thay đổi trong lượt tiếp tục: `tools/phase8a_final_races.py`, `tools/phase8a_branches.py`, `tools/phase8a_expiry_smoke.py` và hai báo cáo tiến độ. Entry point hiện có `tools/smoke_phase8a.py`. Để chạy lại, đặt TEST_REPORT_ROOT=PHASE8A_TESTS, dùng tools/run_phase6_fix.py với nhãn mới và chế độ script. Các đối số cho smoke_phase8a.py là `--final-gate witness-first`, `--final-gate legacy-freshness`, `--final-gate fresh-before-expiry` hoặc `--branch J --expired-recovery --final-closure`. Giữ run.log, JSON, schemas và ledgers riêng từng lượt. Barrier chỉ nằm trong factory của runner. Full regression, Browser và nghiệm thu độc lập toàn Phase 8A: Not Run trong lượt này. Không tái hiện Major thuộc nhóm concurrency. Git cuối lượt main...origin/main, HEAD e4fb9f5, 14 tracked modifications tích lũy, 331 file untracked, index trống, git diff --check đạt.

Các probe dưới đây dùng hai Backend OS process trên 8030/8031, PostgreSQL 17, schema riêng từng lượt và ledger simulator riêng. Phần role-first đặt barrier trước lock_context sau khi route xác thực. Các cặp PID còn lại được đo bằng pg_blocking_pids trong khi transaction đầu chưa commit. Việc nhận HTTP response ở client có thể xảy ra sau khi transaction kế tiếp đã bắt đầu. Thứ tự serialization được xác định từ blocker, kết quả HTTP và dữ liệu đã commit.

| Workflow và thứ tự đã đo | Kết quả HTTP và DB | Bằng chứng mới |
|---|---|---|
| 0.1, AssignStations rút quyền trước settlement | 200 rồi 403 STATION_FORBIDDEN. Version 5, operation còn mở, 0 success audit. PG 850 chặn 813. | [assignment-first](PHASE8A_TESTS/final_gate_assignment_first_01/run.log) |
| 0.1, settlement trước AssignStations | 200 rồi 200. Version 5 → 6, consumed, old_pin_settled=true, đúng một audit. PG 990 chặn 954. | [settle-first](PHASE8A_TESTS/final_gate_settle_first_01/run.log) |
| 0.1, đổi role Technician trước hoặc sau settlement | Trước quyết định, Admin bỏ assignment rồi đổi role thành ADMIN, cả hai commit. Phiên cũ trả 401 và settlement trả 401 SESSION_REVOKED. Thứ tự ngược, UpdateUser chờ settlement 200 rồi bị từ chối 409 USER_REFERENCED vì Technician vẫn còn assignment. PG 1137 chặn 1101 ở thứ tự ngược. | [role-first](PHASE8A_TESTS/final_gate_role_first_01/run.log), [settle-before-role](PHASE8A_TESTS/final_gate_settle_before_role_01/run.log) |
| 0.1, REJECT hoặc CONFIRM commit trước khi hai request đang chờ được tiếp tục | Nguồn thắng trả 201, nguồn đối lập trả 409 RECOVERY_ATTESTATION_EXISTS. Khi REJECT thắng, settle trả 422, version 4 → 5 và 0 success audit. Khi CONFIRM thắng, settle trả 200, version 4 → 6 và một success audit. | [REJECT](PHASE8A_TESTS/final_gate_reject_first_01/run.log), [CONFIRM](PHASE8A_TESTS/final_gate_confirm_first_01/run.log) |
| 0.1, snapshot cửa OPEN từ boot mới cạnh tranh settlement | Worker giữ transaction sau xử lý, kết nối độc lập vẫn thấy inbox chưa processed. Sau commit, accepted=true, processed=true và settle trả 422 EVIDENCE_REQUIRED. Ngược lại, entry còn chưa tồn tại khi receipt HTTP đang chờ station lock, settle 200, sau đó mới có 202 QUEUED rồi worker commit. Version cuối lần lượt 5 và 6. | [worker trước](PHASE8A_TESTS/final_gate_snapshot_first_01/run.log), [settle trước](PHASE8A_TESTS/final_gate_settle_before_snapshot_01/run.log) |
| 0.1, UpdateUser khóa Customer đã làm witness | Khi UpdateUser giữ khóa trước, PG 1132 chặn 1100. Settlement trả 403 RECOVERY_ACTOR_UNAVAILABLE; version 5, 0 success audit. Thứ tự ngược, PG 3303 chặn 3270, settlement và khóa user lần lượt thành công, phiên Customer sau đó trả 401. | [witness trước, mới](PHASE8A_TESTS/final_gate_witness_first_02/run.log), [settlement trước, thu hồi](PHASE8A_TESTS/final_gate_settle_before_witness_01/run.log) |
| 0.1, snapshot hết freshness trong lock wait | PG 1229 chặn 1314. Thấy wait khi còn 2,50 s, nhả khóa sau hạn 0,16 s. Settlement trả 422 EVIDENCE_REQUIRED. Toàn bộ facts trước/sau bằng nhau, version 5, 0 audit thành công. | [freshness, mới](PHASE8A_TESTS/final_gate_legacy_freshness_03/run.log) |
| 0.1, nhả khóa khi snapshot còn mới | PG 1382 chặn 1459. Settlement 200, một audit. Kết nối độc lập thấy commit lúc 06:42:04.237271 UTC, trước hạn 06:42:06.640497 UTC. | [trước hạn, mới](PHASE8A_TESTS/final_gate_fresh_before_expiry_03/run.log) |
| 0.1, operation hết TTL trong lock wait | PG 3650 chặn 3727 đến sau expires_at. Settlement trả 422 EVIDENCE_REQUIRED, version 5, chưa consumed, 0 success audit. | [operation expiry, thu hồi](PHASE8A_TESTS/final_gate_operation_expiry_01/run.log) |
| 0.2, POST receipt hết freshness trong lock wait | PG 3354 chặn 3366. Sau hạn 0,128 s, settlement trả 422 EVENT_STALE. Một effect trước đó, không thêm effect hoặc audit settlement. | [staged freshness, thu hồi](PHASE8A_TESTS/final_gate_staged_freshness_01/reports/PHASE8A_E2E_E.json) |
| ER-01, successor trước yêu cầu closure | PG 2656 chặn 2689, 200/409 VERSION_CONFLICT, version 6 → 7. Tại mốc này chưa consumed. Sau khi có proof successor, crash trước commit rồi retry chỉ ghi một settlement audit; ledger có đúng một effect của predecessor. | [K, thu hồi](PHASE8A_TESTS/final_gate_cross_K_01/reports/PHASE8A_E2E_K.json) |
| ER-02, closure intent trước yêu cầu successor | PG 2179 chặn 2199, 200/409 VERSION_CONFLICT, version 5 → 6. Phải có closure receipt và acknowledgment sau đó mới đóng fence. Một closure audit, 0 service effect. | [J, thu hồi](PHASE8A_TESTS/final_gate_cross_J_01/reports/PHASE8A_E2E_J.json) |

Hai lỗi harness freshness được giữ nguyên trong log. Lượt legacy 01 lấy mốc snapshot 01:19:53.055480 UTC khi một snapshot mới hơn đã gửi nhưng chưa processed. Truy vấn read-only trên schema giữ lại cho thấy snapshot 01:19:57.287093 đã được worker commit trước quyết định 01:20:08.213561. Snapshot thực dùng vẫn còn hạn. Hai lượt 02 đợi cả telemetry seed mang processing_error=SIMULATION_SEED_UNVERIFIED (10 dòng ở schema legacy 02). Worker không claim các dòng đã có lỗi này. Runner 03 dừng simulator S01, đợi hết đúng tập inbox mà worker có thể claim, rồi đọc snapshot cuối và tính biên từ policy. Assertion nghiệp vụ vẫn là 422 khi quá hạn. Witness-first 01 dừng ở barrier vì chưa quan sát được cạnh PG. Lượt 02 làm mới snapshot thống kê khi polling và ghi được cạnh thực. [Legacy 01](PHASE8A_TESTS/final_gate_legacy_freshness_01/run.log), [legacy 02](PHASE8A_TESTS/final_gate_legacy_freshness_02/run.log), [trước hạn 02](PHASE8A_TESTS/final_gate_fresh_before_expiry_02/run.log), [witness 01](PHASE8A_TESTS/final_gate_witness_first_01/run.log).

ER-02 có thêm bằng chứng kế thừa ở lớp simulator. Sáu testcase dùng ledger SQLite bền vững, gồm thiếu witness, PREPARED, command chưa phân giải và restart. Các nhánh bất định giữ fence ACTIVE. JUnit này kiểm ledger; các probe tiến trình dùng run.log/JSON riêng. [JUnit](PHASE8A_TESTS/er_local_20261111_01/results.xml).

Lock graph kiểm tra ở recovery.lock_context, recovery_authorization.guards, recovery_settlement.settle_foreign, recovery_reconciliation.settle, recovery_closure.receive và station_locks. Recovery lấy khóa trạm, user theo UUID, swap/ngăn/pin, rồi các session liên quan. UpdateUser giữ khóa account-administration trước khóa user và thu hồi session. AssignStations khóa user trước khi thay tập trạm. Worker snapshot và API mutation dùng chung serialization theo station. Decision đọc version, quyền, evidence và đồng hồ theo từng nhánh, sau đó commit business write, audit và idempotency trong cùng transaction.

Mỗi log ghi schema, OS PID và cạnh chờ PostgreSQL tại barrier đo được. Snapshot lấy từ model simulator đã reboot trên ledger fixture. Fingerprint demo bao phủ 8 bảng của runner; Payment, custody, holds và audit được đọc riêng trên fixture. 40 pytest của bản sửa revocation phía dưới là bằng chứng kế thừa.

## Sửa race thu hồi phiên tại settlement 0.1 — 12/11/2026

**SETTLEMENT 0.1 REVOCATION MAJOR FIXED.** Ngoài hai probe gốc và hai tình huống ordering thực bên dưới, regression mục tiêu chạy mới trên PostgreSQL 17.11 đạt **40 Passed, 0 Failed/Errors/Skipped**, exit 0 trong 413,94 s. Gồm 16 settlement 0.1 (witness bị revoke dù caller có login khác còn hạn, rollback audit, replay, custody và holds), 4 staged settlement 0.2 và 20 P7-A01. [JUnit theo từng testcase](PHASE8A_TESTS/fix_legacy_session_regression_01/results.xml). Không cộng kiểm tra của runner tiến trình vào số pytest. Toàn Phase 8A vẫn PARTIAL; các gate race evidence/assignment/role ngoài phạm vi, Browser và full regression chưa được chạy trong lượt này.

Git cuối lượt: `main...origin/main`, HEAD `e4fb9f5`, 14 tracked modifications tích lũy, 305 file untracked, index trống. Các file Recovery mới của Phase 8A còn untracked; giữ source, runner, XML/JSON, log và ledger của cả lượt lỗi lẫn lượt sau sửa.

Trước sửa, hai probe bên dưới đều ghi nhận logout commit trước lần kiểm proof cuối nhưng settlement vẫn consume operation và ghi success audit. Lỗi nằm ở việc settlement đọc auth_sessions thường; logout khóa hàng phiên độc lập với hàng user/station. Bản sửa chỉ thay transaction `application/recovery.py::settle` sau khi đã phân nhánh 0.2.

Nhánh 0.1 lấy ID phiên caller từ principal đã xác thực và ID từng phiên witness từ attestation đã lưu, kiểm user/role/assignment dưới khóa user. Sau `quiet()`, nó khóa hợp các session ID theo UUID, từng hàng bằng SELECT FOR UPDATE như `recovery_authorization.guards`. Tại decision nó đối chiếu lại caller/scope, version, boot, snapshot, chủ thể của từng phiên, revoked_at, expiry, proof và freshness. Cùng một principal có thể dùng hai phiên khác nhau. Khóa giữ đến commit/rollback chung với custody, consumption, audit và idempotency.

Thứ tự liên quan là idempotency theo principal/route/key → station advisory → users theo UUID → swaps/ngăn/pin có thứ tự → tập session theo UUID. UpdateUser khóa user trước khi revoke sessions; AssignStations khóa user trước khi thay assignment; logout chỉ cập nhật hàng session, không lấy khóa station/user sau đó. Worker giữ thứ tự station/resources đang dùng. Điểm quyết định nghiệp vụ nằm tại lần kiểm cuối dưới khóa, ngay trước các ghi nghiệp vụ; thay đổi trở nên nhìn thấy cùng lúc ở commit. Thời gian chờ khóa được tính vào expiry/freshness. Barrier dùng cho kiểm thử chỉ tồn tại trong test server.

| Chạy mới với hai Backend OS process và PostgreSQL riêng | HTTP và trạng thái đã đo |
|---|---|
| [Probe gốc, Customer logout trước](PHASE8A_TESTS/fix_legacy_revocation_customer/race.json) | Logout 200, me 401 trước decision, settle 403 RECOVERY_ACTOR_UNAVAILABLE. |
| [Probe gốc, Technician logout trước](PHASE8A_TESTS/fix_legacy_revocation_technician/race.json) | Logout 200, me 401 trước decision, settle 401 SESSION_REVOKED. |
| [Caller hết hạn trong lúc chờ khóa phiên](PHASE8A_TESTS/fix_legacy_session_order_01/run.log) | Caller và witness là hai login của cùng Technician. Dùng expiry ngắn riêng cho login fixture; PostgreSQL báo đang chờ hàng trước expiry, nhả hàng sau expiry theo đồng hồ DB thật. Settle 401 SESSION_REVOKED. |
| [Settlement giữ khóa trước logout](PHASE8A_TESTS/fix_legacy_session_order_01/race.json) | Backend dừng sau success audit trước commit. pg_blocking_pids xác nhận Backend logout chờ Backend settle. Settle 200, logout 200 sau đó; me của caller 401, me của Technician witness khác session vẫn 200. |

Hai probe gốc giữ nguyên assertion, exit 0. Hai tình huống bổ sung chạy cùng fixture khác, exit 0. Khi từ chối: version 5, old_pin_settled=false, chưa consumed, 0 success audit. Khi settlement thắng: version 6, old_pin_settled=true, consumed, đúng 1 success audit. Nhánh A giữ REVIEW_REQUIRED, pin cũ tại Customer, pin cấp trong ngăn, Payment SUCCEEDED, ba holds và 0 service effect trong cả hai thứ tự. Cả ba lượt runner kiểm tra fingerprint tám bảng demo. Không đổi migration, giao thức, deadline hoặc fence.

Giữ `application/recovery.py`, ca nhiều login trong `tests/test_phase8a_settlement.py`, chế độ `--session-order` trong `tools/smoke_phase8a.py`, `tools/phase8a_session_order.py` và probe gốc `tools/phase8a_logout_race.py`. Chạy lại qua `tools/run_phase6_fix.py LABEL script tools/smoke_phase8a.py` với `--logout-race customer`, `--logout-race technician` hoặc `--session-order`; đặt TEST_REPORT_ROOT=PHASE8A_TESTS, mỗi lượt dùng LABEL mới. Giữ JSON, XML, run.log, schema và ledgers của fixture làm bằng chứng.

## 12/11/2026 — Settlement và thu hồi phiên tại điểm quyết định

| Kiểm chứng mới | Kết quả | Bằng chứng |
|---|---|---|
| 0.1, logout Customer witness trước final decision | **Failed**, exit 1. Logout 200, me 401, settle 200 | [DB trước/sau](PHASE8A_TESTS/settlement_logout_customer_race_02/race.json) |
| 0.1, logout chính Technician caller trước final decision | **Failed**, exit 1. Cùng thứ tự và cùng hậu quả như Customer. Hai Backend OS PID 18804 và 29120, PG PID settlement 9419 | [DB trước/sau](PHASE8A_TESTS/settlement_logout_technician_race_01/race.json) |
| 0.2, staged guards trên PostgreSQL, `test_foreign_settlement_final_guards_atomicity_and_replay` | **4 Passed**, 0 failed/errors/skipped, exit 0, 277,99 s. CONFIRM/REJECT, old boot, conflicting-model; ca dương còn kiểm revoke trước request, version, rollback và replay | [JUnit](PHASE8A_TESTS/settlement_staged_guards_race_review_01/results.xml) |

Hai failures dùng fixture khác nhau và cùng phát hiện **một Major**. Kết quả 0.2 là bốn ca kiểm guard; race final-decision của 0.2 vẫn chưa được chứng minh đầy đủ. Git khi bàn giao: HEAD e4fb9f5, main...origin/main, 14 tracked modifications và 296 untracked files tích lũy, index trống. Lượt này chỉ bổ sung/sửa runner, hai báo cáo và evidence test riêng. Full regression/Browser Not Run.

**BLOCKED. Major ở đường settlement P8-REC-0.1.** Trong nhánh A, Backend 1 đọc phiên của người làm chứng, chạy `quiet()` rồi tạm dừng ngay trước lần kiểm proof/freshness cuối. Backend 2 logout Customer dùng đúng token đã xác nhận. Logout trả 200 và GET /v1/me từ chối token với 401 trước khi runner cho Backend 1 chạy tiếp. Settlement vẫn trả 200 và commit. Đây là thứ tự được điều khiển bằng barrier trong runner, không suy ra từ timestamp log. Hai tiến trình Uvicorn riêng dùng cùng schema ngẫu nhiên. Simulator đọc ledger thật. Barrier không thay kết quả `quiet()`, timestamp, evidence hoặc dữ liệu nghiệp vụ.

| Probe Customer 0.1 | Trước logout | Sau commit settlement |
|---|---|---|
| Swap / case | REVIEW_REQUIRED / EVIDENCE_RECORDED | REVIEW_REQUIRED / EVIDENCE_RECORDED |
| Case version / operation consumed | 5 / false | 6 / true |
| old_pin_settled / success audit | false / 0 | true / 1 |
| Custody cũ / mới | CUSTOMER / COMPARTMENT | Cùng pin, holder và ngăn |
| Payment / holds đang giữ / service effects | SUCCEEDED / 3 / 0 | SUCCEEDED / 3 / 0 |

Chuyển trạng thái sai được commit nguyên tử. Probe không ghi nhận partial write, double effect hoặc thay đổi fingerprint tám bảng demo. Không ngoại suy kết quả nhánh A sang việc thực tế chuyển custody ở nhánh B/D. [Log, schema và trạng thái trước/sau](PHASE8A_TESTS/settlement_logout_customer_race_02/run.log). Lượt sandbox `settlement_logout_customer_race_01` bị chặn TCP trước fixture.

**Thứ tự khóa và điểm quyết định.** `recovery.lock_context` và `device.station_locks` khóa station advisory → users theo UUID → swaps → compartments → batteries. AssignStations và UpdateUser khóa hàng user trước khi cập nhật assignment/role. Logout lại cập nhật hàng `auth_sessions`. Trong `recovery.settle` 0.1, authorize và vòng kiểm chứng đọc session thường. Sau `quiet()`, lần kiểm cuối chỉ đánh giá proof, boot và freshness trước các ghi custody/case/audit. Dữ liệu bền vững khi dependency session commit. Khóa station/user không bảo vệ khoảng giữa lần đọc session và điểm quyết định này. Idempotency khác route cũng không tuần tự hóa hai giao dịch.

Ở 0.2, `settle_foreign` và ER-01 truyền tập session ID vào `recovery_authorization.guards`, khóa hàng phiên PRE/POST hoặc successor cùng phiên caller theo UUID, kiểm lại hạn ngay tại decision. ER-02 `recovery_closure.receive` khóa phiên của closure intent, kiểm quyền và freshness trước ghi receipt/cancel/audit. Confirmation, xử lý device observation và worker áp dụng snapshot cũng qua khóa trạm. Việc nhận event vào inbox và việc worker chấp nhận event vào projection là hai thời điểm riêng. Các nhận định này là review source, không chứng minh mọi lịch xen kẽ đã chạy.

**Đề xuất review riêng:** thống nhất thứ tự khóa tập phiên caller và witnesses của 0.1 với thứ tự khóa 0.2; kiểm lại revoked/expiry tại decision sau các bước có thể chờ. Khi logout commit trước thì settlement phải từ chối và giữ nguyên operation/case/audit. Khi settlement giữ khóa trước thì logout có thể commit sau. Cần chứng minh cả hai thứ tự, gồm caller có phiên khác phiên witness. Source production chưa sửa.

**Gate còn mở.** Race thực giữa assignment/role và commit; REJECT–CONFIRM–settle ba bên; receipt/snapshot mâu thuẫn trong lúc kiểm proof; freshness hết hạn trong lock wait; successor đối đầu closure. Kết quả hai Backend tranh settle khác key và replay trong [workflow E trước đây](PHASE8A_TESTS/staged_settlement_real_E_final_02/reports/PHASE8A_E2E_E.json) là bằng chứng kế thừa. Các kết quả UI 46/33, ER-01/02, crash/retry giữ nguyên phạm vi cũ.

Giữ `tools/phase8a_logout_race.py`, chế độ `--logout-race customer|technician` trong `tools/smoke_phase8a.py`, log/report mới, schema fixture và ledger tương ứng. Chạy qua `tools/run_phase6_fix.py LABEL script tools/smoke_phase8a.py --logout-race customer` với TEST_REPORT_ROOT=PHASE8A_TESTS và LABEL mới. Giữ cả bằng chứng run lỗi. Dừng nhánh phụ thuộc để review transaction.

## Kết luận increment Customer Projection / POST — 12/11/2026

**RECOVERY UI READY FOR ACCEPTANCE TESTING** về implementation/API/frontend mục tiêu. Không có Blocker/Major nghiệp vụ được tái hiện sau sửa; Browser đang Blocked bởi công cụ. Đây không phải nghiệm thu toàn Phase 8A, hiện vẫn PARTIAL.

| Gate / lượt mới trên source cuối | Passed | Failed / Errors / Skipped | Bằng chứng |
|---|---:|---|---|
| Projection Customer PRE/POST, ownership, revoked intent, wrong reference, replay, hai Backend app/kết nối PG riêng | 4 | 0/0/0 | customer_projection_pg_resume_01/results.xml |
| POST regression/provenance/revoke/rollback và boot cũ | 7 | 0/0/0 | Cùng XML, gồm chính ba failures lịch sử |
| Recovery API legacy 0.1, RBAC, append-only | 4 | 0/0/0 | Cùng XML |
| Input contract tests | 29 | 0/0/0 | Cùng XML |
| Successor CONFIRM/REJECT qua GET Customer reference | 2 | 0/0/0 | customer_projection_successor_resume_01/results.xml |
| Frontend render/controller/payload | 33 | 0/0/0 | customer_projection_resume_01/frontend.log |

Backend targeted là **46 ca riêng biệt**, không cộng 43 Passed lịch sử vào tổng này. Run 44 ca exit 0 trong 326,85 giây; successor 2 ca exit 0 trong 383,43 giây. Successor dùng expiry thật, actual simulator model và durable ledger, không rewrite timestamp/custody. CONFIRM consume chain đúng một lần, REJECT không consume và không ghi success audit; Payment/custody/ba holds giữ nguyên, service effect bằng một. Ca concurrency mới là hai app instance trong cùng OS process, hai PostgreSQL backend PID khác nhau; không gọi là hai Backend OS process hay Browser E2E.

[XML 44 ca](PHASE8A_TESTS/customer_projection_pg_resume_01/results.xml), [XML successor](PHASE8A_TESTS/customer_projection_successor_resume_01/results.xml). Cả hai có schema phase5_test_* riêng, PostgreSQL 17.11, migration upgrade head hiện hữu và runtime grants. Không có migration mới của increment này, không áp dụng migration vào schema demo. Không đo fingerprint tám bảng demo mới trong lượt này; báo cáo test schema ghi production_schema_modified_by_tests=false.

### Acceptance checklist còn mở

- [x] GET projection chỉ cho Customer sở hữu swap; Customer GET Technician recovery vẫn 403.
- [x] PRE/POST/successor chọn stage/accepted reference ở Backend; POST so lại dưới khóa.
- [x] Wrong operation/context/reference, expired/consumed/cancelled/revoked, old boot, REJECT, idempotency/replay và concurrent insert có targeted evidence.
- [x] TypeScript/Vite và validators/static hashes/runtime OpenAPI/role allowlist Passed.
- [ ] Browser click flow PRE/POST/successor, login/revoke/reload và responsive. Công cụ dừng trước đăng nhập/fixture vì không xác minh URL; không có Browser Passed.
- [ ] Real-process UI/Backend end-to-end trên source cuối. Không dùng TestClient/SSR thay cho E2E tiến trình.
- [ ] Full regression và Independent Acceptance toàn 8A, theo lượt được giao sau.

### Source và bằng chứng cần bảo toàn

Bản tích hợp gồm application/recovery_projection.py, confirmation_context/confirmation trong application/recovery.py, RecoveryConfirmationContext trong api/recovery_schemas.py, schema assembly/version metadata trong api/recovery_contract.py. Giữ RecoveryConfirmationContext.schema.json, CUSTOMER_PROJECTION_1.md và README trong overlay 0.2; overlay 0.1/baseline không đổi. Giữ Recovery.tsx/recoveryModel.ts và tests/recovery.test.mjs cho UI projection; CustomerConfirmation input không được thêm field tự chọn state/provenance/expected_version.

Giữ tests/test_phase8a_customer_projection.py và các assertion successor từ tests/test_phase8a_expired_recovery.py. Những test POST phát hiện lỗi gốc không bị sửa expected, skip hay xfail. Source sửa tối thiểu đã được lưu tại checkpoint trước; lượt resume thu hồi log và kiểm lại source đó, không xây dựng lại authorization/handover/settlement.

Giữ customer_projection_20261112_01 (43 Passed/3 Failed lịch sử), customer_projection_pg_resume_01, customer_projection_successor_resume_01, customer_projection_resume_01 và customer_projection_validators_resume_01. Giữ source-hashes.json để đối chiếu; log không chứa credential. tools/phase8a_customer_browser.py còn là helper test-only chưa chạy, không import trong production. Dist/.cache có thể tái tạo ở lượt dọn riêng; SQLite ledger/schema fixture/evidence được giữ.

Git tại bàn giao: HEAD e4fb9f5, main...origin/main, 14 tracked modifications và 289 untracked files toàn workspace (gồm summary mới). Index trống. git diff --check Passed, có cảnh báo line ending CRLF. Không commit/push/full regression; không thay guards/custody/Payment/holds/deadlines hoặc triển khai 8B/8C.


## 12/11/2026 — Customer projection integration: reprise POST regressions

### Gap analysis và phạm vi đã được giao

GET swap gọi confirmation_context, trong khi Customer không được GET Technician recovery. Projection 0.1 chỉ có operation/context/serial/owner/station/expiry; CustomerConfirmation(StageReference) 0.2 cần stage và exact accepted receipt ID/hash. Không thể giải quyết bằng cách để Customer nhập tay reference hoặc đọc raw Technician proof.

Increment đã thêm read projection protocol_version, stage, receipt_id/hash/observed_at, case_version và confirmation_status; không thêm endpoint hoặc Customer input field. File CUSTOMER_PROJECTION_1.md và RecoveryConfirmationContext.schema.json version P8-REC-0.2/customer-projection-1 ghi phạm vi user đã giao. Schema/README 0.1 và baseline GĐ1/GĐ2 giữ nguyên. Đây là metadata phục vụ view, không thêm state vào domain machine.

Backend chỉ project operation cùng swap/case/customer/station đã xác thực. Response không chứa raw attestation, service/command ledger, auth session, tên Technician hoặc authorization secret. PRE lấy accepted PRE receipt, POST thay reference hiện hành bằng accepted POST receipt, successor lấy RECONCILIATION_INSPECTION. Khi POST, khóa station/users/context hiện có vẫn được dùng; Backend suy lại stage/reference từ DB và so exact binding, sau đó chạy human/human_post guards đã có. case_version dùng so representation trên UI, không được tự thêm expected_version vào CustomerConfirmation ngoài schema.

### Ba failures đã thu hồi

[Run gốc XML](PHASE8A_TESTS/customer_projection_20261112_01/results.xml) hoàn tất 43 Passed, 3 Failed, 0 Errors, 0 Skipped trong 666,80 giây. Hai failure POST được nhắc ở checkpoint là hai tham số True/False của test_post_statements_provenance_refusals_replay_and_rollback, line 78: khi case.operation_id bị displaced, expected 409 nhưng wrapper projection trả 422. Failure thứ ba hoàn tất sau checkpoint là test_post_statement_cannot_promote_old_boot_receipt_to_current_proof, line 137: expected 409 RECONCILIATION_REQUIRED, actual 422 EVIDENCE_REQUIRED.

Root cause là lớp tích hợp mới coi confirmation_status=UNAVAILABLE như một business rejection chung trước khi human_post kiểm tra. Metadata này có nhiều nguyên nhân nên làm mất mã lỗi hợp đồng của guard cũ. Cả ba request vẫn bị từ chối; chưa thấy false confirmation/custody hoặc lỗi transaction. Đây là mismatch HTTP/error contract trong production integration, không phải lỗi fixture.

Source checkpoint đã sửa trước lượt resume: kiểm case.operation_id/context trước projection và trả 409 RECOVERY_CONTEXT_MISMATCH; bỏ shortcut EVIDENCE_REQUIRED cho mọi UNAVAILABLE, để human_post giữ kiểm chronology/current boot/snapshot/freshness và 409 RECONCILIATION_REQUIRED vốn có. PRE có kiểm boot riêng để không dùng receipt cũ qua reboot. Revoke intent vẫn bị từ chối. Không sửa expected results hoặc nới guard. Lượt resume kiểm lại bản sửa đã lưu; không triển khai lại.

### Frontend và phép kiểm mới

Customer dùng reference read-only do Backend trả, không tự nhập stage/receipt/serial/recipient. PRE hiển thị ý nghĩa trước action, POST xác nhận sau action, successor xác minh possession hiện tại. Confirmation đã có/REJECT/stale/expired/closed/revoked chặn mutation trên UI. Backend vẫn kiểm mọi điều kiện tại POST. Technician giữ đúng các payload theo stage, Admin chỉ xem.

Controller giữ duplicate-click lock, key theo path/body, preflight GET và representation comparison (bao gồm case_version/receipt), generation guard chống stale response. 409/403/503 hoặc response mất không thành success và không tự retry POST. Chỉ sau API thành công và GET lại thành công mới thông báo ghi nhận.

[Frontend log](PHASE8A_TESTS/customer_projection_resume_01/frontend.log) ghi 33 Passed, exit 0; TypeScript/Vite build Passed trong [build.log](PHASE8A_TESTS/customer_projection_resume_01/build.log). Runtime OpenAPI, schema snapshot và role allowlist Passed trong runtime-openapi.json. Baseline OpenAPI/JSON schema/SQL/hash validators Passed ở customer_projection_validators_resume_01. Không dependency/migration mới.

Browser **Blocked**: Computer Use dừng vì không xác định được URL hiện tại trên Windows đủ tin cậy để enforce policy. Chưa mở Browser fixture và chưa nhập credential/test mutation trong Browser. Không chuyển sang cơ chế điều khiển khác để vượt giới hạn công cụ. Các render/controller tests không thay thế Browser UI tests.

Docker Engine lúc đầu mất pipe cả ngoài sandbox. Đã khởi động Docker Desktop; PostgreSQL startup log ghi fsync rồi chuyển healthy/pg_isready accepting. Không reset/drop dữ liệu. Tests chạy từng runner trên schema riêng và không full regression.


## 12/11/2026 — Recovery UI P8-REC-0.2: PARTIAL/BLOCKED

### Phạm vi đã triển khai và API

Technician xem operation/context, serial/recipient, expiry/consumed/cancelled, proof theo LEGACY/PRE_ACTION_INSPECTION/POST_ACTION_RECEIPT/RECONCILIATION_INSPECTION, receipt ID/hash và thời điểm quan sát. Payload TECHNICIAN_ATTEST lấy stage/reference từ accepted simulator proof đúng operation/context, serial do Technician trực tiếp nhập. CONFIRM và REJECT độc lập, không ghi đè testimony. Successor chỉ đọc không được xin intent/activation.

UI dùng GET /v1/swaps/{id}/recovery và POST /recovery/evidence cho BEGIN_OPERATION, TECHNICIAN_ATTEST, AUTHORIZE_ACTION phase INTENT/ACTIVATE, REINSPECT_OPERATION, CLOSE_NO_EFFECT; POST /recovery/settle cho StructuredSettlement. ACTIVATE tham chiếu đúng authorization_id và acknowledgment_id; chỉ mở yêu cầu khi PRE có ba nguồn CONFIRM và intent đã ACK, còn hạn. Backend kiểm mọi guard còn lại. Không có nút gọi device endpoint hoặc thực hiện handover; operator vẫn dùng simulator riêng. Closure chỉ hiển thị là yêu cầu đối soát, không tự coi fence đã đóng.

Customer dùng GET /v1/swaps/{id} và POST /recovery/confirmations. Các operation 0.1 ngoài RETURN_FOREIGN_OBJECT giữ legacy confirmation đúng immutable context; không có input Customer chỉnh stage/serial/recipient/actor. Admin chỉ có view, builder từ chối mọi mutation.

Mỗi mutation có expected_version (Technician) và Idempotency-Key ổn định theo path/body. Controller GET lại trước POST, nếu representation/receipt thay đổi thì hiển thị bản mới và yêu cầu quyết định mới. Duplicate click được chặn bằng cờ đồng bộ, không chỉ state React. Sau lỗi hoặc response mất, tra cứu lại, không tự retry POST hoặc suy effect thành công. Response GET/mutation cũ bị generation guard ngăn ghi đè màn hình mới. Component remount theo user ID/role; logout/401 vẫn theo API client chung. Error mang code/status, VERSION_CONFLICT làm mới dữ liệu mà không tự gửi mutation lại.

### Blocker Customer 0.2 đã xác định bằng source

application/recovery.py:confirmation_context chỉ trả operation_id/context_hash/purpose/expected_serial/station/customer/expiry/simulation_only. RecoveryConfirmationContext trong api/recovery_schemas.py cũng chỉ có các trường đó. GET swap gọi projection này; GET recovery từ chối Customer trong authorize. Customer không có nguồn hợp lệ để lấy protocol, stage, accepted receipt ID/hash, consumed/cancelled/revocation hoặc proof hiện tại.

Trong khi đó CustomerConfirmation(StageReference) và human_post/human yêu cầu exact stage/receipt binding cho 0.2 và successor. RETURN_FOREIGN_OBJECT được Backend tạo protocol_version 0.2. UI hiện **chặn** Customer foreign-object confirmation, hiển thị thiếu projection; không gửi legacy body để vượt guard, không cho nhập receipt do Technician chuyển tay, không lấy dữ liệu qua API vượt quyền.

Cần bổ sung projection Customer do Backend xác thực principal và suy stage/reference hiện hành, kèm schema/overlay tương ứng, trước khi mở Customer PRE/POST/successor UI. Đây là thay đổi Backend/contract cần giao riêng theo giới hạn lượt này; chưa triển khai. Frontend không khai báo một response mở rộng chưa tồn tại.

GET recovery hiện cũng chưa trả closure intent/receipt summary hoặc activation summary. Technician có thể gửi intent/activation/closure qua API hiện có, nhưng UI ghi rõ trạng thái vận chuyển/effect chưa thể suy ra. cancelled_at chỉ chứng minh operation closed; không chứng minh local fence đã được tháo. UI không tạo endpoint mới để lấy ledger.

### Kiểm thử mới

[Frontend log](PHASE8A_TESTS/recovery_ui_20261112_01/frontend-final.log): 30 Passed, 0 Failed/Skipped, exit 0. Dùng Node test runner, TypeScript transpiler đã có và React server renderer, không dependency mới. Các test render stage/reference/RBAC và kiểm controller/payload có thực thi; không phải Browser click tests. Gồm CONFIRM/REJECT, missing/wrong context/receipt, expiry/revocation, successor/no-effect, idempotency/duplicate click, version conflict/403/503/network unknown, reload, response đến muộn và không gửi desired custody/state/payment/provenance.

[Build log](PHASE8A_TESTS/recovery_ui_20261112_01/build-final.log): TypeScript noEmit + Vite production build Passed, exit 0. Dist JS 301,41 kB (gzip 95,62 kB). Cache transpilation trong apps/web/.cache/recovery-test-* giữ lại, có thể tái tạo. Node tests chạy bằng npm --prefix apps/web run test:recovery.

Browser smoke Backend thật: **Not Run**. Chưa dựng Browser fixture trong lượt này; luồng Customer 0.2 bị blocker projection trước khi có thể nghiệm thu end-to-end. DOM interaction, responsive và role/session revocation trong Browser chưa kiểm chứng; không suy từ SSR/controller tests. Không chạy PostgreSQL/full regression hoặc dùng DB demo cho UI tests.

### Files và điểm dừng

Sửa Recovery.tsx, thêm recoveryModel.ts và tests/recovery.test.mjs; thêm npm script test:recovery, giữ package/dependency versions. main.tsx thêm code/status vào Error và remount Recovery khi đổi principal/role. Cập nhật hai tài liệu tiến độ, giữ các log/result.json trong recovery_ui_20261112_01. Không sửa Backend, migrations, baseline, approved overlays, deadlines hoặc ledgers trong lượt UI.

**PARTIAL/BLOCKED — chưa UI READY FOR ACCEPTANCE TESTING trọn phạm vi.** Technician/legacy Customer đã có source và targeted tests; Customer staged POST/PRE/successor bắt buộc chờ projection. Những workflow kỹ thuật khác của toàn 8A và full regression vẫn là gate riêng. Git tại bàn giao vẫn main...origin/main, HEAD e4fb9f5, 14 tracked modifications, 273 untracked files toàn workspace; index trống và diff --check Passed. Dừng trước Backend extension, full regression và independent acceptance.


## 12/11/2026 — Điều tra P7-A01 và readiness toàn 8A

### Nguyên nhân và giới hạn bằng chứng

Windows System log cho thấy Kernel-Power 506 lúc 11:17:54 (Modern Standby, Reason Lid), cặp 507/506 lúc 11:41:20 (Austerity Battery Drain Budget Exceeded), và 507 lúc 12:03:19 (thoát Standby, Reason Lid). Đã lưu đúng các event trong [power_events.json](PHASE8A_TESTS/p7_pause_diagnostic_20261112_01/power_events.json).

Timeline cộng duration từ JUnit đặt ca 61-return khoảng 11:17:51–11:41:19 (1408,267 giây), ca 61-pickup khoảng 11:41:19–12:03:15 (1315,836 giây). Đây là thời gian ước lượng theo tổng testcase, không phải timestamp ghi tại từng câu lệnh. Hai khoảng khớp Modern Standby. [Timeline](PHASE8A_TESTS/p7_pause_diagnostic_20261112_01/historical_timeline.json).

Fixture test_phase5.prepare → test_phase4.connected/send/process phát một SNAPSHOT và TELEMETRY rồi xử lý worker đồng bộ, không có simulator heartbeat chạy nền. Sau pause, last_received_at/slot observation cũ hơn telemetry_stale_seconds=15. reservations.station_online trả 503 tại verification. Đối với pickup, stack lỗi nằm trong lần drive đầu tiên tạo OPEN_RETURN; tên pickup chỉ chỉ định nhánh đích, chưa tới OPEN_SUPPLY/custody decision. command_allowed kiểm online/freshness và kiểm lại clock trong final_fresh, nên có thể từ chối 409 khi thời gian trôi giữa resources_valid và enqueue.

Kết luận có bằng chứng là máy bị Standby trong đúng hai ca và fixture không duy trì heartbeat. Chưa có snapshot diagnostic tại chính thời điểm lỗi lịch sử để chỉ ra riêng từng predicate interlock. Không có log health Docker/PostgreSQL lịch sử trong khoảng Standby để kết luận Engine đã mất kết nối; traceback là business guard trả lỗi qua các query PostgreSQL, không phải lỗi connection. Health kiểm mới là Engine 29.9.2, PostgreSQL healthy/pg_isready accepting, không đại diện quá khứ.

ER-01/ER-02 không được gọi trong hai ca. Test client dùng transaction rollback theo test trong schema phase5_test_*; race_environment tạo schema khác. Không có worker/simulator OS chạy bởi runner pytest này. command_allowed có guard recovery_operations còn mở, nhưng không có thao tác tạo recovery trong fixture P7. Diagnostic mới kiểm thêm command/recovery/closure-intent trống, boot không đổi. Không có bằng chứng lỗi custody/locking production. Source production giữ nguyên trong lượt điều tra.

### Kết quả chạy mới

- [Run 01 XML](PHASE8A_TESTS/p7_pause_diagnostic_20261112_01/results.xml) có 21 Passed, 1 Failed, 0 Errors, 0 Skipped, exit 1, 153,78 giây. Cả 20 test_phase7_deadline Passed. Diagnostic enqueue đặt pause trước resources_valid nên chưa đi tới command_allowed; production chuyển review sớm thay vì raise. Assertion diagnostic đã đặt sai vị trí.
- Đã sửa riêng test diagnostic, đặt pause thật ngay khi command_allowed bắt đầu, sau resources_valid. Giữ expected error/custody/Payment. [Run 02 XML](PHASE8A_TESTS/p7_pause_diagnostic_20261112_02/results.xml) có 2 Passed, 0 Failed/Errors/Skipped, exit 0, 39,27 giây. Heartbeat age 16,2405 và 16,748038 giây, boot không đổi. Verification tái hiện STATION_OFFLINE; enqueue tái hiện COMMAND_INTERLOCK_FAILED và rollback command/swap, giữ Payment.
- Đây là 22 ca riêng biệt được xác minh mới. Không cộng các run trùng. Các số 33/2, E2E 26/20, regression 493/111 ở mục cũ là kế thừa.
- Không sửa fixture P7 hoặc source production. Không tăng freshness hay tự phát heartbeat để ép deadline test qua sau suspend. Health Docker/PG lịch sử vẫn UNKNOWN; đường lỗi do elapsed-time đã tái hiện khi Engine healthy.
- SHA256 các recovery application/simulator modules, device.py và swaps.py giữ nguyên từ đầu lượt.

### Ma trận nghiệm thu hiện tại

Traceability giữ FR12/UC10/BR05/09/11/12, AD-04b/SM-03b, invariants 6–8, TC12 và CT07/08 phần recovery. FR16/UC14/BR08 và CT13 refund/final compensation thuộc 8B/8C.

| Hạng mục | Implemented | Tested / Passed | Trạng thái còn lại |
|---|---|---|---|
| A — xác minh đúng pin cũ ngoài tủ | Có, recovery.settle/VERIFY_OLD_POSSESSION | Kế thừa acceptance_A_01, 5 checks | Partial xác nhận lại trên migration 0008; hash lịch sử chưa đủ chứng minh source đồng nhất |
| B — trả lại pin cũ đúng chủ thể | Có, service/RETURN_OLD_TO_CUSTOMER | Kế thừa acceptance_B_02, 6 checks | Partial tái xác minh trên head cuối |
| C — pickup UNKNOWN, không suy giao pin từ ngăn rỗng | Có, recovery.quiet/settle | Kế thừa acceptance_CD_01 C, 5 checks | Partial rerun sau tích hợp ER |
| D — delivery ba nguồn, quyết định thủ công | Có, VERIFY_NEW_DELIVERY | Kế thừa acceptance_CD_01 D, 3 checks | Partial rerun trên head cuối; không coi foreign-object proof thay delivery pin cấp |
| E — foreign-object staged settlement | Có, recovery_authorization/handover/settlement | Kế thừa E 28 checks; targeted source cuối er_resume_pg_01 4 Passed | Tested/Passed phạm vi E; negative wrong presenter end-to-end còn Partial |
| F — offline/reboot/late/UNKNOWN | Có, simulator/service + current_snapshot | Kế thừa acceptance_F_01, 8 checks | Partial rerun sau ER, gồm fence và unknown-effect không sống lại |
| ER-01 expired effect successor | Có, recovery_reconciliation + 0008 | Kế thừa er_k_compete_01 26 checks, 3-source, crash rollback, hai OS Backend 200/409 | Passed trong verified scope; không thay toàn bộ A–F |
| ER-02 durable no-effect closure | Có, recovery_closure + local witness/deny/ack | Kế thừa J 20 checks, local 6, PG closure/migration | Passed trong verified scope; packet stale chưa được nhận vẫn giữ fence/review |
| Logout/session/role/assignment tại final decision | Có token/user/station locks | Sequential negative đã Passed trong staged/expired recovery | Partial, race có barrier với logout/role revoke commit đúng ranh giới còn Not Run |
| Evidence mới mâu thuẫn ngay trước decision | Có version/current boot/freshness | Sequential staged negative Passed | Partial, concurrency evidence-vs-settlement chưa chứng minh bằng barrier |
| Crash/restart/replay | Durable Inbox/outbox/SQLite/PG | E/ER-01 trước commit; E/ER-02 sau commit; cùng identity/audit/effect đã Passed | Passed phạm vi các runner; không suy bao phủ mọi phase |
| Migration/grants/idempotency/append-only | 0003–0008, runtime grants và constraints | er_resume_pg_01 migration 2 Passed | Passed; cần final validators sau source freeze |
| Customer/Technician UI | Recovery.tsx có legacy form | Build lịch sử Passed, Browser Not Run cho 8A | Partial: payload hiện thiếu stage/receipt_id/hash cho 0.2; chưa có intent/ACK/activation/ER controls. Không thể dùng build làm chứng nhận workflow UI |
| Service operator UI | CLI explicit operation có | E2E thực dùng CLI | Partial so với khả năng demo thao tác staged của hai vai trò |
| NFR/monitoring/backup | Audit và persistent ledgers có | Crash/restart đã có bằng chứng | Not Run p95≤2s/20 sessions/1000 requests; restore đồng bộ DB+ledger CT14; structured runtime monitoring cần review. Không coi restart là backup/restore |
| Whole 8A acceptance | Các slice trên có source | Full regression trước ER 493/111 là lịch sử | Partial; full current regression, Browser và independent acceptance chưa chạy |

### Prerequisite và trình tự final regression

1. Khép các kiểm chứng race logout/revoke, evidence mâu thuẫn và wrong presenter staged còn thiếu. Hoàn thiện tối thiểu UI payload theo stage của overlay, rồi kiểm Browser riêng. Đây là phần việc đề xuất, chưa triển khai trong lượt này.
2. Freeze source và lưu SHA256. Đã lưu [source_hashes](PHASE8A_TESTS/p7_pause_diagnostic_20261112_01/source_hashes.json) để so sánh về sau. Rerun A/B/C/D/F trên 0008 sau thay đổi shared transport/fencing, không suy từ evidence 0007.
3. Host phải hoạt động liên tục khi chạy các test wall-clock; ghi nhận Windows power events nếu bị gián đoạn. Không tăng TTL, restamp evidence hay tự retry để che lần Failed. Chưa sửa fixture để tự tạo heartbeat vì điều đó đổi điều kiện test.
4. Preflight Docker health, pg_isready, kết nối runtime/owner trên schema fixture. Mỗi runner một schema phase5_test_*, mỗi ledger/runtime một path riêng. Chỉ một suite hoặc E2E PG hoạt động tại một thời điểm. Advisory locks theo key vẫn tranh chấp xuyên search_path; tách schema không tách advisory lock namespace.
5. Chạy migration/grants/overlay validators, targeted 8A và P6/P7 guards, rồi toàn pytest một lượt tuần tự. Sau đó E2E A–F/ER tuần tự và frontend/Browser theo phạm vi được giao. Giữ log/XML, exit code, schema và fingerprint. Không reset/drop schema, demo volume hoặc ledgers.
6. Review NFR 8A và phân định test restore/performance trước nghiệm thu độc lập. Không đưa refund/compensation vào tiêu chí 8A đã giới hạn.

**PARTIAL.** Hai lỗi P7 có đường gây lỗi do elapsed-time đã được đối chiếu với power events. Các race, UI staged và phạm vi tái kiểm A–F trên head mới vẫn là khoảng trống nghiệm thu. Chưa chạy full regression trong lượt này.

### File và Git bàn giao

Lượt này thêm `tests/test_phase8a_p7_pause_diagnostic.py` và bằng chứng hai run diagnostic, cập nhật hai tài liệu tiến độ. Không thay source production, migration hay contract. HEAD e4fb9f5, main...origin/main, index trống, 13 tracked modifications và 270 untracked files toàn workspace. git diff --check Passed, chỉ có cảnh báo CRLF.

Phải giữ toàn bộ source recovery API/application/domain, recovery contract assembly, simulator service/recovery/fence/ledger handlers, integration changes trong device/swaps/main/config, migration 0003–0008 và provision_database runtime grants. Giữ overlays P8-REC-0.1/0.2 cùng JSON schemas/README/traceability và approved design proposals. Giữ tests/test_phase8a_*.py, tests/test_phase7_deadline.py, tools/run_phase6_fix.py, smoke_phase8a.py, phase8a_branches.py, phase8a_expiry_smoke.py và phase8a_process.py để tái hiện; Recovery.tsx/main.tsx hiện có cũng phải được bảo toàn khi hoàn thiện UI.

Giữ nguyên XML/log/JSON và power_events/historical_timeline/source_hashes của diagnostic. Các schema fixture và SQLite ledgers đều được bảo toàn. Runtime/cache/build chỉ được xem xét dọn trong lượt riêng sau khi đã lưu bằng chứng; lượt này không dọn file. Không dùng untracked count làm danh sách stage, vì nhiều source 8A còn untracked.


## 12/11/2026 — Kiểm chứng hai workflow sau expiry

**ER-01/ER-02 GAPS RESOLVED IN VERIFIED SCOPE.** [Smoke K cuối](PHASE8A_TESTS/er_k_compete_01/reports/PHASE8A_E2E_K.json) đạt 26 checks, exit 0. Sau rollback do crash, hai Backend OS process tranh quyết định trên cùng chain chưa consumed với hai idempotency key khác nhau. Một request trả 200, request kia trả 409; replay key thắng trên cả hai Backend giữ một success audit. Lượt 26 checks bao phủ lại lượt K 25 checks bên dưới. Toàn Phase 8A vẫn PARTIAL.

| Workflow | Điều kiện quyết định | Bằng chứng thực thi |
|---|---|---|
| ER-01 | Successor chỉ đọc liên kết predecessor đã hết hạn. Simulator đọc external position trên boot hiện tại và đối chiếu effect/receipt gốc. Hai lời chứng Customer và Technician cùng tham chiếu hash của observation mới. | [Smoke K](PHASE8A_TESTS/er_k_resume_02/reports/PHASE8A_E2E_K.json) có 25 checks Passed. Backend chết sau audit trước commit (91), cả hai operation chưa consumed. Retry commit cả hai cùng một audit. Ledger có một service effect gốc. |
| ER-02 | Witness NEVER_PREPARED từ inspection, model và command ledger khớp. Simulator khóa writer, ghi DISABLED cùng deny set và closure outbox. Chỉ acknowledgment khớp receipt đã commit mới đóng fence. | [Smoke J kế thừa](PHASE8A_TESTS/er_e2e_J_20261111_01/reports/PHASE8A_E2E_J.json) có 20 checks Passed, exit 0. Backend chết sau commit trước HTTP response (92). Replay cùng receipt trả duplicate, chỉ một closure audit. Restart xác nhận fence CLOSED và deny operation bền vững; số service effect bằng 0. |

Cả hai schema E2E giữ swap REVIEW_REQUIRED, Payment SUCCEEDED và ba holds. Vị trí pin cũ là CUSTOMER, pin cấp là COMPARTMENT, refund count bằng 0. Fingerprint tám bảng demo do runner theo dõi không đổi.

| Pytest trên source hiện tại | Kết quả |
|---|---|
| ER-01/02, operation hết hạn thật | 3 Passed. Có kiểm tra thu hồi session Technician và station assignment ngay tại quyết định, từ chối boot/recipient sai, REJECT append-only, rollback audit và retry. |
| Migration 0008 và grants | 2 Passed trên PostgreSQL 17.11, schema riêng. |
| Durable fence/ledger simulator | 6 Passed với SQLite ledger thật; gồm lệnh chưa phân giải, PREPARED, mất witness và command mới xuất hiện trước acknowledgment. |
| Staged foreign-object settlement P8A-E01 | 4 Passed, gồm negative Customer REJECT, boot cũ và model mâu thuẫn. |
| Deadline P7-A01 | 18 Passed, 2 Failed trong lượt nhóm. Hai ca 61 giây dừng trước guard deadline tại bước xác thực/trước khi enqueue command (503 STATION_OFFLINE và 409 COMMAND_INTERLOCK_FAILED). Chạy lại đúng hai node trên schema riêng đạt 2 Passed trong 21,78 giây. Nguyên nhân môi trường sâu hơn của hai lỗi setup nghiệp vụ chưa được xác lập. |

[JUnit lượt nhóm](PHASE8A_TESTS/er_resume_pg_01/results.xml) ghi 33 Passed, 2 Failed, 0 Errors, 0 Skipped. [JUnit chạy lại hai node](PHASE8A_TESTS/er_deadline_resume_01/results.xml) ghi 2 Passed, 0 Failed. Đây là 35 ca riêng biệt. Full regression, Browser và nghiệm thu độc lập toàn 8A thuộc lượt khác.

Lượt K đầu tiên [er_k_resume_01](PHASE8A_TESTS/er_k_resume_01/run.log) dừng trước bước ER-01. Fixture vào REVIEW_REQUIRED với COMMAND_INTERLOCK_FAILED và chưa có device command; truy cập phần tử đầu danh sách gây IndexError. Runner hiện khởi động hai API trước bước chuẩn bị payment để thời gian khởi động không tiêu tốn cửa sổ evidence của fixture. Giữ nguyên clock, policy, guards và lịch sử lượt lỗi.

Khi thiếu witness, command chưa terminal, ledger PREPARED/UNKNOWN, participant bị thu hồi quyền hoặc current evidence mâu thuẫn, giữ review. Nếu closure đã ghi cục bộ nhưng chưa được Backend chấp nhận và current proof hết hạn, giữ fence cùng outbox; chưa có cơ sở tự gia hạn observation hoặc tháo fence. Các migration/tests chỉ dùng schema fixture. Phần thay đổi ở lượt tiếp tục thuộc runner, regression tests và tài liệu.

File của lượt tiếp tục gồm `tests/test_phase8a_expired_recovery.py`, `tools/phase8a_branches.py`, `tools/phase8a_expiry_smoke.py` và hai báo cáo tiến độ. Giữ log/XML/JSON mới trong `er_k_resume_01`, `er_k_resume_02`, `er_resume_pg_01`, `er_deadline_resume_01`, `er_k_compete_01` dưới PHASE8A_TESTS, cùng schema/ledger fixture tương ứng. Git tại bàn giao là main...origin/main, HEAD e4fb9f5, 13 tracked modifications, 262 file untracked trong toàn workspace, index trống.

## 11/11/2026 — ER-01 và ER-02 đã duyệt, đang kiểm chứng

Phê duyệt của người dùng áp dụng cho cả hai quyết định ER bên dưới. Source hiện
có migration 0008, hai statement trên evidence API, receipt/observation và task
trên device API hiện có. Simulator ghi witness NEVER_PREPARED cùng inspection,
chuyển witness khi PREPARED và giữ deny set qua restart. PostgreSQL ghi closure
và audit cùng transaction. Successor chỉ đọc model và liên kết effect gốc.

Lượt er_storage_20261111_01 có 42 Passed, 2 setup Errors. Đã sửa biểu thức
JSON trong DDL để Alembic không hiểu `:true` là bind parameter.
er_closure_20261111_01 có 3 Passed (2 migration/grants, 1 ER-02 với expiry thật,
audit rollback và replay). er_local_20261111_01 có 6 Passed trên ledger cục bộ.

## 06/11/2026 — Expired successor / no-effect: contract review, NEEDS APPROVAL

Lượt yêu cầu `RESOLVE EXPIRED OPERATION & DURABLE NO-EFFECT GAPS` đã đối chiếu
source với proposal P8-REC-0.2 mục 3–9, README overlay 0.1/0.2 và schemas hiện có.
**Chưa triển khai hoặc kiểm thử hai workflow mới. PARTIAL/BLOCKED.** Các kết quả
55 E2E check executions và 111 pytest ở các mục dưới là lịch sử, không chạy mới.
Không phát hiện regression mới qua runtime vì lượt này chưa chạy runtime tests.

### Phần đã được duyệt và phần còn phải biểu diễn rõ

Mục 7 đã cho phép inspection-only successor liên kết predecessor/authorization,
quan sát actual external holder, consume chain nguyên tử; và durable no-effect
closure trước supersede. Không cần xin lại chủ trương này. Tuy nhiên, triển khai
hai đường mới cần chốt ý nghĩa lời chứng và message/transition bổ sung dưới đây;
không thể cho payload mới âm thầm đi qua schema nghiêm ngặt đang dùng.

| Khoảng trống | Root cause / source cụ thể | Vì sao không dùng lại đường hiện tại |
|---|---|---|
| Expired effect successor | `application/recovery.py:record` chặn foreign operation còn mở, `open_operation` chặn expired; `api/recovery_schemas.py:RecoveryContext/InspectionTask` chưa có predecessor/authorization binding | Không được đổi expires_at hoặc giả operation cũ còn live |
| External observation | `application/recovery_inspection.py:accept` bắt actual serial hiện diện trong return slot; `simulators/device/recovery_fence.py:inspect` chỉ đọc slot/presenter | Vật đã ở external model không thể chứng minh bằng slot trống; phải đọc actual `service_positions` và đối chiếu receipt/ledger |
| Human proof của successor | Proposal mục 3/8 định nghĩa PRE là đã trình/đồng ý nhận, POST là đã nhận qua receipt; `0004_recovery_stages.validate_recovery_stage` buộc human reference cùng operation và stage | Successor không có action/POST receipt mới. Không được chuyển PRE thành delivery proof hoặc reference receipt predecessor trái constraint |
| Durable no-effect | `recovery_fence` có ACTIVE/CLOSED nhưng chưa có closure handler/outbox; observation union chỉ có inspection, POST receipt, authorization ACK và legacy observation | ACK/effect_count_delta=0 của inspection không có nghĩa permit đã bị vô hiệu hóa vĩnh viễn |
| Commands cũ | `simulators/device/main.py:_handle` kiểm ACTIVE fence ngay trước effect; command chưa ghi vào ledger có thể đã được process khác tải về | Chỉ đổi fence CLOSED không chứng minh cached command đã bị chặn; phải giữ durable deny record có kiểm tra tại effect boundary |

Không có thay đổi production, migration, API hoặc overlay trong lượt review này.
Các lỗi trên là thiếu đường khôi phục có kiểm soát, không phải bằng chứng hệ thống
đang cho double effect. Guard hiện tại tiếp tục fail-closed.

### Hai quyết định bổ sung đề nghị phê duyệt (chưa có hiệu lực)

**ER-01 — Lời chứng đối soát successor.** Thêm stage chỉ đọc
`RECONCILIATION_INSPECTION`, không phải PRE authorization hay POST action mới.
Technician tạo successor qua evidence endpoint hiện có, có predecessor ID và
expected_version; Backend suy immutable context, không nhận holder/serial override.
Successor tham chiếu predecessor context hash, authorization/activation, ledger
identity và receipt lịch sử. Không tạo intent/activation/action cho successor.

Simulator quan sát actual external serial/recipient và snapshot hiện tại dưới
fence gốc, ghi receipt mới của *lần quan sát mới*, không thay thời điểm effect cũ.
Technician và Customer chính chủ xác nhận độc lập receipt successor: “hiện tại
Customer này đang giữ đúng vật này”; lời chứng đó không tự chứng minh một action
mới. Settlement cần cả receipt effect lịch sử hợp lệ lẫn ba nguồn current proof,
current boot/snapshot/freshness, actor/session/assignment và toàn bộ ledger guards.
Consume predecessor + successor + audit/idempotency trong cùng transaction;
không custody/Payment/holds/old_pin_settled changes. Bất kỳ REJECT hoặc mâu thuẫn
chưa được phân giải trong chain vẫn chặn; không dùng successor ghi đè lời chứng.
Không có authenticated historical effect receipt thì chỉ ghi nhận inspection và
giữ UNKNOWN/review, không tự tái dựng receipt từ expected values hoặc slot rỗng.

Đây là ý nghĩa lời chứng bổ sung cần xác nhận: mục 7 cho phép current proof nhưng
chưa ánh xạ nó vào hai ý nghĩa human-stage hiện hành. Đề xuất stage mới tránh
làm yếu ràng buộc cùng operation/stage và không đổi ý nghĩa PRE/POST đã kiểm thử.

**ER-02 — Giao thức đóng permit no-effect.** Qua endpoints hiện có, bổ sung
Technician request có version/idempotency, task `CLOSE_NO_EFFECT` và device message
`NO_EFFECT_CLOSURE`; đây là chứng cứ vô hiệu hóa permit, không phải physical proof.
Backend tạo intent closure; simulator kiểm intent từ API, giữ SQLite writer lock
chung với mọi effect, kiểm exact operation/context/ledger/fence và toàn bộ pending
commands/service tasks. Không close khi service PREPARED/UNKNOWN, đã effect hoặc
ledger mâu thuẫn. Không suy no-effect từ việc không có dòng ledger riêng lẻ.

Simulator ghi durable deny/tombstone cho operation/permit và tập command cũ đã
đối soát trước khi ghi closure receipt. Effect handlers phải kiểm deny record
ngay trước tác động, kể cả cached command chưa có ledger row; không đổi command
UNKNOWN thành NOT_EXECUTED. Nếu không chứng minh được tập command đầy đủ thì giữ
fence. Pending command/effect chưa phân giải chặn closure. Ghi receipt/outbox cùng
local commit; response loss chỉ replay cùng receipt, không mở lại permit.

Backend xác thực closure, recheck actor/version/current source, rồi đóng operation
bằng cancelled_at + audit + idempotency nguyên tử, không “settled successfully”.
Station fence chưa được bỏ chỉ vì nhận request hoặc TTL; chỉ kết thúc exclusivity
sau closure đã được Backend nhận bền vững, và deny/tombstone phải còn vĩnh viễn
cho các identity cũ. Mất acknowledgment giữ fenced, retry/query cùng closure ID.
Không mở action successor tự động. Không có endpoint unlock/custody/no-effect
outcome do user tự khai. Chi tiết transport này cần được ghi rõ vào versioned
overlay trước khi mở union/DB grants; không sửa baseline GĐ1/GĐ2.

### Ma trận effect / no-effect / UNKNOWN

| Tình huống | Hành vi an toàn hiện tại / đề xuất, chưa phải test mới |
|---|---|
| Effect OBSERVED, receipt bền vững, operation expired | Giữ fence/review; sau ER-01: readonly successor + historical receipt + fresh current proof, không action lần hai |
| Effect OBSERVED, HTTP receipt thất lạc | Replay đúng packet ID/body/boot/time từ durable outbox; không sửa timestamp, không fabricate receipt |
| PREPARED/UNKNOWN | Không no-effect closure/reissue; readonly inspection có thể lưu thông tin nhưng không tự phân giải effect |
| Chưa effect, permit có thể đã tải xuống | Chỉ ER-02 durable revocation + đầy đủ ledger/fence/command proof mới đủ; absence/TTL không đủ |
| Boot khác hoặc snapshot stale | Lịch sử vẫn giữ; không dùng làm current proof; yêu cầu quan sát mới hợp lệ |
| Ledger/snapshot/recipient mâu thuẫn, human REJECT | Tiếp tục REVIEW_REQUIRED, không consume/release |
| Pending command/task cũ còn có thể tác động | Chặn closure; không chỉ đổi ACTIVE thành CLOSED |

### Verification và bàn giao lượt này

- Review source/contract và `git diff --check`: đã thực hiện; diff check đạt.
- PostgreSQL, targeted workflow tests, concurrency/crash và real-process smoke
  hai workflow mới: **Not Run / blocked pending contract decisions**, không có
  Passed/Failed runtime mới. Không chạy lại full suite hoặc E2E lịch sử.
- Sau phê duyệt: typed schemas/forward constraints + durable local interlocks;
  targeted expiry/boot/context/revoke/replay/rollback; hai Backend cạnh tranh;
  crash trước/sau closure commit và receipt replay; real-process cả hai đường;
  regression P8A-E01/P7-A01 liên quan. Không dùng SQL custody/proof để vượt guards.
- Chỉ hai báo cáo tiến độ thay đổi trong lượt này. HEAD `e4fb9f5`,
  `main...origin/main`, 231 untracked files và mọi tracked changes cũ giữ nguyên;
  không stage/commit/push, không ghi DB demo hoặc sửa/xóa ledger/evidence.

**NEEDS APPROVAL cho ER-01/ER-02; Phase 8A vẫn PARTIAL/BLOCKED.** Không khẳng định
GAPS RESOLVED. Không chuyển sang các nhóm kiểm thử/UI/Browser/8B/8C.

## 06/11/2026 — Remaining acceptance gaps: PARTIAL/BLOCKED

**Chưa READY FOR FINAL REGRESSION AND BROWSER VERIFICATION.** P8A-E01 vẫn FIXED
trong staged workflow E đã kiểm chứng. Không tái hiện lỗi double custody/charge/
settlement; còn thiếu capability bắt buộc và concurrency evidence của toàn8A.
Lượt này chỉ review/kiểm thử, không sửa production, không làm8B/8C/UI/Browser.
Traceability: FR12/UC10/BR05/09/11/12, TC12/CT07/CT08 phần recovery; invariants6–8.
FR16/UC14/TC16/CT13 và final compensation tài chính thuộc8B/8C, không tính thiếu8A.

### Ma trận acceptance criteria 8A

Done dưới đây chỉ là gate/phạm vi đã có evidence, không phải toànPhase Passed.
Paths application=services/backend/app/application; sim=simulators/device.

| Gate | Trạng thái | Source / test / evidence thực tế |
|---|---|---|
| Scope/RBAC API, đúng principal/station, Admin không thay Technician | Done, evidence kế thừa | api/recovery.py; tests/test_phase8a_api.py: test_recovery_read_role_and_station_scope, test_admin_cannot_attest_as_technician; api_contract_02, tests đã có; không chạy lại lượt này |
| Typed input, immutable context/evidence, unique stage/source, migration/grants | Done trong phạm vi tests | api/recovery_schemas.py; migrations0003–0007; test_phase8a_stage_storage/contract/migration; reg111 kế thừa. New A–F fixtures upgrade head0007 trên schema riêng |
| A: đúng pin cũ còn ở Customer, ba nguồn, chỉ settle nghĩa vụ old | Done | recovery.settle, sim/service; test_A_old_possession_settles_only_old_obligation_and_keeps_charge_holds; NEW acceptance_A_01:5checks |
| B: đã trả nhưng chưa nhận, trả lại đúng old một effect, giữ tiền/holds | Done sau runner barrier | recovery.settle, sim/service; test_B_D_manual_settlement_keeps_finance_separate; NEW acceptance_B_02:6checks; B01 Failed giữ nguyên |
| C: pickupUNKNOWN/EXECUTED, ngăn trống không suy custody | Done nhánh fail-closed | recovery.quiet/settle; test_C_unknown_pickup_cannot_complete_even_with_two_human_confirmations; NEW acceptance_CD_01 C:5checks |
| D: positive delivery ba nguồn, manual reconcile sau deadline, atomic custody/terminal release | Done | recovery.settle VERIFY_NEW_DELIVERY; test_executed_positive_proof_commits_once_without_repairing_command; NEW CD D:3checks,2OSBackends replay200/200,1audit |
| E: staged inspection→intent/ACK→activation→effect→post3nguồn→settle foreign-only | Done phạm vi bounded E | recovery_authorization/handover/settlement, sim/recovery_fence/handover; source-final5+2overlap kế thừa; NEW acceptance_postcommit_E_01:28checks |
| F: offline/restart/late proof/old boot, UNKNOWN không rerun | Done nhánh fail-closed | sim/service; recovery.current_snapshot/settle; test_F_reconnect_does_not_reuse_old_boot_service_proof; NEW acceptance_F_01:8checks |
| Effect at most once, PREPARED durable, fence chặn cached commands | Done phạm vi tests | sim/recovery_fence/handover; test_already_received_command_cannot_execute_after_inspection, test_prepared_crash_never_reexecutes_effect; reg111 kế thừa, E/F mới |
| Crash trước commit rollback, restart, idempotency/audit | Done | staged_settlement_real_E_final_02 kế thừa:28checks,exit91; targeted rollback tests. Không chạy lại vì production unchanged |
| Crash sau commit trước HTTP, lost-response same-key retry | Done MỚI | acceptance_postcommit_E_01:exit92,HTTPdisconnect,consumed=true,audit1;2OSBackends retry;service1; schema phase5_test_3d402f0d71b7 |
| Revoked session/role/assignment trước final decision | Done tuần tự; Partial concurrency | recovery_settlement token/user locks; staged_settlement_final_03 kế thừa; concurrent logout/role revoke tại đúng final-decision barrier Not Run |
| Contradictory current snapshot trước settle | Done tuần tự; Partial concurrency | staged_settlement_physical_04 kế thừa:2Passed dùng version mới nhất; race mới giữa accepted observation và final decision Not Run |
| Wrong foreign presenter/recipient | Partial | authorization.guards, receipt binding; test_foreign_object_requires_matching_recorded_presenter (local ledger), handover receipt wrong recipient tests, foreign_identity_01:11Passed kế thừa. Full negative staged E với wrong presenter/recipient chưa chạy mới; không coi local legacy coverage là complete0.2E2E |
| Expiry/supersede/stale boot reject | Done refusal; Partial recovery liveness | staged_settlement tests/old-boot proof; old0.1 expired handover reinspection test có. Displaced pointer chỉ là negative fixture, không chứng nhận successor workflow0.2 |
| Effect xảy ra, proof/operation hết hạn: inspection-only successor, chain consume atomically | Blocked: capability chưa hoàn thiện | P8-REC-0.2 proposal mục7 bắt buộc; recovery.record không có foreign inspection-only successor gắn authorization; open_operation từ chối expired; sim.inspect giữ active fence. Không tự tạo transition hoặc bỏ fence |
| Permit expired trước effect: durable no-effect closure để supersede an toàn | Partial / thiếu implementation & E2E | Proposal mục7; sim/fence có ACTIVE/CLOSED storage nhưng chưa có approved end-to-end closure/receipt path. Backend TTL không được tự chứng minh no effect |
| Post-E VERIFY_OLD_POSSESSION sau foreign operation | Partial, integration Not Run | Không được suy old_pin_settled từ foreign receipt. Cần probe riêng toàn chain: UNKNOWN OPEN_RETURN vẫn giữ lịch sử, quiet không được nới blanket; không giả định E success đã giải quyết old |
| Worker restart đúng ranh giới recovery settlement/custody | Partial | E restart Backend/simulator, F restart simulator/UNKNOWN, P7 historical restart tests có; không đồng nghĩa đã test worker kill/restart tại final recovery-decision barrier |
| RESUME_SWAP full real-process recovery | Partial | test_resume_uses_normal_custody_workflow_and_closes_case_only_at_completion có kế thừa; A–F runner mới không tự chứng nhận full RESUME_SWAP real-process |
| Full regression / Browser / independent acceptance | Not Run theo giới hạn lượt này | Chưa đủ điều kiện bỏ qua các gate kỹ thuật trên. Không dùng inherited493/111 làm final whole8A suite |

### E2E A–F trên source hiện tại: kết quả chạy mới

| Run | Checks Passed | DB/ledger sau cùng |
|---|---:|---|
| acceptance_A_01 |5|Old possession verified; swapReview,3holds; no physical service effect;demo fingerprint unchanged|
| acceptance_B_02 |6|Old returned to correctCustomer; swapReview,3holds;1handover effect,1manual audit;fingerprint unchanged|
| acceptance_CD_01 C / D |5 /3|C no unsupported custody; D COMPLETED,oldCOMPARTMENT/newCUSTOMER,holds0 only after full positive proof,PaymentSUCCEEDED,1manual audit;fingerprint unchanged|
| acceptance_postcommit_E_01 |28|SwapREVIEW_REQUIRED,oldCUSTOMER/newCOMPARTMENT,PaymentSUCCEEDED,3holds,refund0;serviceOBSERVED/effects1,foreign audit1;fingerprint unchanged|
| acceptance_F_01 |8|Review,3holds,old/newCOMPARTMENT,PaymentSUCCEEDED; UNKNOWN serviceeffects0 survivesrestart,no repeat;fingerprint unchanged|

**55Passed check executions ở các run thành công cuối, không phải55pytest hoặc
55unique assertions toàn hệ thống.** Lượt này không chạy pytest mới và không full
regression. Giữ inherited111Passed/XML và source-final5+2overlap đúng bản chất.
A/B/C/D/F chạy lại vì dùng chung recovery/service path đã thêm0.2; production
không đổi trong lượt này. E post-commit dùng thêm test-only ASGI interception;
legacy B-only barrier bổ sung sau E không đổi đường branchE/C/D/F. Không có
source hash lịch sử nên không khẳng định byte-identical từ commit: new evidence
summary lưu current hashes để so sánh ở lượt sau, không giả hash tại quá khứ.

### Failure mới B01 và cách xử lý runner

acceptance_B_01 có1assertion Failed,exit1:422EVIDENCE_REQUIRED/200 thay vì200/409.
Batch dừng trướcCD/F, không xóa log. DB fixture phase5_test_790ac1cb30c2:
receipt nhận15:59:59.050482UTC,Customer confirm15:59:59.450430,
post-handover snapshot processed15:59:59.644363,settlement consumed15:59:59.998760.
Receipt và inbox processing độc lập: runner cũ không đợi processed snapshot trước
khi race. Chưa instrument exact internal failing guard nên không suy diễn mạnh
hơn timeline. Không có bằng chứng double-settlement hoặc custody sai.

Sửa test prerequisite trong tools/smoke_phase8a.py: B chờ snapshot accepted+
processed, observed>=service observation, actual source CLOSED/empty. Không
refresh timestamp, không UPDATE custody và không đổi expected200/409. B02 đạt6
checks,exit0. Giữ snapshot_diagnostic.json và toàn bộ B01 log/schema/ledger.
Kết quả mới gồm1failed attempt đã xử lý bằng barrier runner, không báo toàn lượt
zero failures. Không sửa production để hợp thức hóa assertion.

### Crash sau commit: chứng cứ mới

ASGI test factory intercept http.response.start200 của settle sau function-scoped
DB dependency commit, rồi os._exit(92). HTTP client bị ngắt; Backend còn lại đọc
DB xác nhận consumed=true/audit1 trước retry. Restart8031 bình thường, retry cùng
key và race khác key trả200/409;response replay không ghi audit/effect thứ2.
Runtime `.cache/p8-E-a4d671902b`, schema phase5_test_3d402f0d71b7. Test hook chỉ ở
runner, đòi phase5_test_ và signal .cache; không services/simulators import nó.
Pre-commit exit91 path vẫn giữ nguyên; không đánh tráo hai crash windows.

### Kết luận gate và công việc còn thiếu

**PARTIAL/BLOCKED.** Blocker nghiệm thu là capability successor/no-effect closure
đã được phê duyệt nhưng chưa triển khai đủ; không phải bằng chứng đã làm sai
custody/Payment. Giữ fail-closed, không sửa transaction/locking/custody trong lượt
này. Các deterministic concurrency tests cho revoke/observation và worker restart
boundary còn Not Run; cần khép trước final regression. Full negative presenter/
recipient và post-E old-possession integration cần được test riêng.

Thứ tự tiếp theo đề xuất: review/triển khai riêng approved successor/no-effect
closure dưới fence+version+audit, không reissue action; sau đó deterministic
revoke/observation/worker races và các negative integration probes; cuối cùng
final full regression và Browser. Không tự đổi FR/UC/BR/QD hoặc chọn policy mới.
P8A-E01 bounded workflowE vẫn FIXED; không coi đó là wholePhase acceptance.

File thay đổi mới: tools/phase8a_branches.py (postcommit test mode),
tools/smoke_phase8a.py (B-only snapshot prerequisite barrier), hai báo cáo tiến độ.
Không production/migration/dependency/baseline change. Evidence mới:5successful
runs ở bảng,1failedB01, snapshot_diagnostic.json, acceptance_gaps_20261106.json
(gồm DB/ledger summary và current source hashes). Test-only hooks cần giữ để
reproduce regression; log/JSON/runtime/.local test ledgers là artifact không đưa
vào source commit. Không xóa bất kỳ bằng chứng hay tài nguyên nào.

HEAD e4fb9f5,main...origin/main; tracked/untracked8A được giữ nguyên. Không stage,
commit,push,không resetDB/volumes/ledgers. Runner chỉ dừng children do nó tạo.

## 06/11/2026 — Staged Settlement: kiểm chứng cuối P8A-E01

**P8A-E01 FIXED trong phạm vi staged workflow E đã kiểm chứng trên source cuối.**
Không còn Blocker/Major được tái hiện trong workflow này. Toàn Phase8A vẫn PARTIAL,
chờ nghiệm thu độc lập/toàn bộ các gates còn lại. Không diễn giải kết quả này là
nghiệm thu toàn8A, successor reconciliation, Refund8B hay Compensation8C.
Các checkpoint pending/blocked bên dưới được giữ nguyên làm lịch sử.

### Kết quả thực tế và phạm vi số liệu

| Run | Kết quả | Bằng chứng/trạng thái |
|---|---|---|
| staged_settlement_regression_02 |111Passed,0Failed/Errors/Skipped;1094.081s XML|Kế thừa, thu hồi XML/log hoàn chỉnh; không chạy lại. Old PTY không còn nên OS exit code không truy xuất được|
| staged_settlement_final_03 |5Passed,0Failed/Errors/Skipped;285.197s;exit0|Mới: source cuối, 4settlement matrix nodes +inspection-only refusal|
| staged_settlement_physical_04 |2Passed,0Failed/Errors/Skipped;143.962s;exit0|Mới: 2node trùng nhóm5, assertion mạnh hơn dùng version hiện hành và từ chối khác VERSION_CONFLICT|
| staged_settlement_real_E_final_02 |28checksPassed;exit0|Mới: PostgreSQL +2Backend OS processes +worker +simulator durable ledger; actual OS crash trước commit|
| staged_settlement_real_E_01 |27checksPassed|Lịch sử trước guard cuối và crash probe; không cộng vào28|
| Full-project regression / UI / Browser |Not Run|Ngoài nhiệm vụ lượt này|
| Crash sau commit trước HTTP response |Not Run trực tiếp|Replay kết quả đã commit đã Passed; không coi replay là actual post-commit process crash|

5+2 là7lần thực thi nhưng5nodeIDs riêng;111 đã bao gồm các node liên quan ở trạng
thái trước guard legacy cuối. Không cộng111+5+2 thành118tests độc lập và không
cộng28E2Echecks vào pytest. Các run dùng nhãn/schema riêng, không ghi đè bằng chứng.
XML/log nằm `PHASE8A_TESTS/<run>/`; E report ở
`staged_settlement_real_E_final_02/reports/PHASE8A_E2E_E.json`.

### Các guard trên source cuối

`test_foreign_settlement_final_guards_atomicity_and_replay[True/False/boot/conflicting-model]`
và `test_real_model_inspection_transport_is_readonly_idempotent_and_stage_bound`:
settlement hợp lệ; inspection-only; legacy thiếuoperation_id→409RECOVERY_STAGE_CONFLICT;
missing human/REJECT→422EVIDENCE_REQUIRED; stale/expired operation; displaced active
operation pointer; boot đổi; snapshot OPEN thực từ simulator model; Customer session,
Technician role và assignment revoke; wrong version; same-key replay/body conflict;
new-key duplicate; audit exception rollback. Displaced pointer là fixture âm dưới
savepoint, không chứng nhận workflow supersede thành công. Clock injection chỉ
kiểm refusal, không sửa timestamp để tạo proof thành công. Snapshot mâu thuẫn chỉ
fault actual simulator model cho ca âm; không SQL UPDATE custody/proof Backend.

Hai ca boot/model bổ sung lấy lại version hiện hành sau snapshot và kiểm refusal
không phải VERSION_CONFLICT. Không sửa expected business outcome để làm Passed.
Không có production source changes trong lượt resume này; chỉ siết test assertion.

### Real-process E cuối và crash window

Schema `phase5_test_87e1040bde75`; runtime `.cache/p8-E-f7b2a4defe`.
Đi đầy đủ API/simulator: wrong return→inspection→pre3nguồn→intent/ACK→activation
→physical handover→durable receipt→Technician/Customer POST→settlement. Auth qua
API thật; Payment setup dùng domain mock fixture, không phải provider-process E2E.

- Hai Backend8030/8031 là OS processes độc lập. API8031 restart sau receipt;
  hai API race intent/activation/receipt/human proofs rồi settlement.
- Test factory `phase8a_branches:crash_test_app` gọi audit INSERT thực, sau đó
  `os._exit(91)` trước transaction commit. HTTP connection đứt, process exit91,
  marker `settlement-crash.crashed` tồn tại. Đọc PostgreSQL qua API8030 xác nhận
  operation chưa consumed,0foreign success audits,3holds. API8031 restart bằng
  factory production bình thường rồi retry cùng key đã rollback.
- Hai requests khác key cạnh tranh:200/409VERSION_CONFLICT. Replay key thắng từ
  cả hai API trả cùng committed result. Đúng1FOREIGN_OBJECT_RETURN_SETTLED audit,
  operation consumed đúng1lần. Audit failure trong targeted cũng rollback mọi writes.
- Test crash hook chỉ nằm tools/phase8a_branches.py; factory đòi schema prefix
  phase5_test_ và signal trong workspace .cache. Production services/simulators
  không import hoặc tham chiếu hook/env. Không có control bật trong app.main.
- Ledger gốc OPEN_RETURN EXECUTED/effects1; service OBSERVED/effects1. Restart
  simulator và replay receipt không tạo effect thứ2. Không OPEN_SUPPLY mới và
  không đăng ký foreign serial thành network battery.
- Swap REVIEW_REQUIRED; recovery case EVIDENCE_RECORDED, chưa RESOLVED. Không thêm
  enum REVIEW_REQUIRED vào recovery_cases. old_pin_settled=false và không biến
  new_pin_delivered thànhYES. OldCUSTOMER/newCOMPARTMENT, PaymentSUCCEEDED,
 3holds,refund0. Settlement không cập nhật custody/charge hoặc release resources.
- Demo fingerprint unchanged. Runner chỉ dừng children do nó tạo; giữ schema,
  ledgers và evidence. Runtime mới khoảng2.8MiB (2,914,737bytes), chưa dọn.

### File, giới hạn và tái hiện

Lượt resume thay đổi `tests/test_phase8a_staged_settlement.py` (2assertion mạnh hơn),
`docs/PHASE8A_IMPLEMENTATION.md`, `docs/IMPLEMENTATION_STATUS.md`; thêm3run evidence.
Bản sửa kế thừa cần giữ: application/recovery_settlement.py + dispatch recovery.py
+ guard mode recovery_authorization.py; test settlement; runner phase8a_branches.py;
overlay0.2README. Không migration/dependency/API/schema mới, head vẫn0007.

Giữ test/runner làm regression. Giữ run.log/results.xml/E JSON và crash marker làm
bằng chứng nghiệm thu; runtime chứa test ledgers, không commit. Không xóa artifact
hoặc `.local`, không reset DB/volume. Baseline diff rỗng, git diff --check đạt;
HEAD e4fb9f5, main...origin/main, working tree8A vẫn dirty/untracked được bảo toàn.
Không stage/commit/push. Chưa chạy full-project regression theo chỉ dẫn.

Đường expired/old-boot/REJECT/ambiguous proof vẫn fail-closed và giữ fence/holds.
Inspection-only successor khi effect đã xảy ra và proof hết hạn còn là giới hạn
8A cần nghiệm thu/triển khai riêng; không reissue action hoặc refresh evidence.
Crash-after-commit OS fault chưa chạy; không che giới hạn này bằng replay checks.

Tái hiện tuần tự, dùng LABEL mới vì runner không ghi đè:

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py LABEL pytest tests/test_phase8a_staged_settlement.py tests/test_phase8a_inspection_transport.py::test_real_model_inspection_transport_is_readonly_idempotent_and_stage_bound
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py OTHER_LABEL script tools/smoke_phase8a.py --branch E
```

## 06/11/2026 — Source-final targeted checkpoint

Docker recovered: container healthy and pg_isready accepting connections. The
first readiness probe saw startup/rejecting; targeted fixture nevertheless
connected successfully and completed. staged_settlement_final_03:5Passed,
0Failed/Errors/Skipped,285.20s,observed runner exit0. Four settlement matrix nodes
plus inspection-only refusal. This verifies the final legacy-body and session
expiry guards. No production changes in this resume.

Only test change: boot/model contradiction refusal now refreshes expected_version
after the actual snapshot and asserts error is not VERSION_CONFLICT. Follow-up
staged_settlement_physical_04 runs those two strengthened nodes; E crash run is
next. These overlap the5tests and must not be added as seven distinct tests.

## 06/11/2026 — Resume verification checkpoint

Recovered staged_settlement_regression_02: complete run.log + results.xml,
111Passed/0Failed/0Errors/0Skipped,1094.081s XML (1094.09s log). No running
pytest/runner/uvicorn children were found in elevated process inventory. The old
PTY process handle30508 no longer exists; its OS exit code cannot be recovered.
pytest summary/XML prove test completion, but do not claim a newly observed OS
exit0. This is inherited evidence, not a rerun. The legacy-body guard was added
after this suite loaded its modules, so source-final targeted validation remains
necessary. No full-project suite will be rerun.

Current environment check: Docker Engine pipe absent even outside sandbox;
PostgreSQL/E2E source-final gates are BLOCKED pending Docker recovery. User was
asked to reopen Engine/container. No failed test run has been manufactured for
this infrastructure precheck. Initial E27checks stays historical. Existing crash
runner is test-only; production services/simulators do not reference its factory
or P8_TEST_SETTLE_CRASH_SIGNAL. No production source changed in this resume so far.

Terminology: swap/session stays REVIEW_REQUIRED; recovery_cases uses approved
EVIDENCE_RECORDED after a foreign-object operation is consumed, not RESOLVED.
REVIEW_REQUIRED is not added as a new recovery-case enum. The real old-pin
obligation/three holds remain unresolved; this is not whole-case closure.

## 06/11/2026 — Staged foreign-object settlement (validation in progress)

User authorized only RETURN_FOREIGN_OBJECT Stage C and real-process E. No 8B/8C,
UI, Browser, baseline change or commit. This section supersedes the earlier
statement that staged settlement is unimplemented; expiry successor remains pending.

Root cause P8A-E01: the legacy quiet policy cannot authorize a new foreign-object
transfer from UNKNOWN/EXECUTED history alone, and the 0.2 settlement dispatcher
still refused every request after the prior staged increments. The new dedicated
settle_foreign path consumes positive three-source staged proof; it does not
broaden quiet() or change automatic custody/command deadlines.

Writes in one existing transaction: operation.consumed_at; case version,
EVIDENCE_RECORDED, current snapshot/note/assigned Technician; one
FOREIGN_OBJECT_RETURN_SETTLED audit plus request idempotency. Swap stays
REVIEW_REQUIRED/COMPENSATING. old_pin_settled/new_pin_delivered are preserved,
not inferred from the foreign object. Both network-pin records, Payment, refunds
and three holds are untouched. Durable simulator fence is retained. No new
command, network battery, generic unlock or HTTP call within the transaction.

The final decision validates intent/ACK/activation hashes and original effect
window, PRE chain/presenter, independent POST humans bound to exact receipt,
current actors/roles/sessions/assignment, same-boot current snapshot, full command
ledger and original local fence/service-effect proof. Station -> sorted users ->
swap/slots/pins locks are reused. All PRE/POST/current auth sessions are locked in
UUID order and expiry rechecked at decision. PRE is historical chain, POST and
snapshot remain fresh; no evidence timestamp renewal. Inspection-only requests
stay409; staged activation missing POST proof returns422 EVIDENCE_REQUIRED.
Legacy settlement cannot omit operation_id to bind implicitly to a0.2 operation.

No migration/dependency/API/schema addition. Existing migration head0007 and
consumed_at/audit storage suffice. Overlay README records activation of the
already approved settle endpoint; baseline OpenAPI/FR/UC/BR/QD remain unchanged.

Changed this increment: application/recovery.py, recovery_authorization.py;
new application/recovery_settlement.py; new tests/test_phase8a_staged_settlement.py;
tools/phase8a_branches.py; overlay0.2 README; this report and IMPLEMENTATION_STATUS.
All earlier untracked8A files and historical evidence retained.

Initial evidence: staged_settlement_01 =2Passed,0Failed,140.55s (prior guard
follow-ups). staged_settlement_real_E_01 =27checksPassed, two OS Backends;
schema phase5_test_0471638bc27f, runtime .cache/p8-E-71c07c55e9. One service effect,
one foreign settlement audit, 200/409 concurrent settlement, committed response
replay, original custody, chargeSUCCEEDED,3holds and demo fingerprint unchanged.
Payment setup uses domain mock fixture, not real payment-provider process E2E.

Final related regression, added boot/model refusal probes and explicit OS crash
before commit E2E are still pending at this checkpoint. Do not interpret initial
runs or inherited results as final acceptance. Full-project regression and
Browser are Not Run in this narrow increment. Expired/old-boot/rejected proof
stays review; inspection-only successor reconciliation remains unfinished and
must never be replaced by reissuing an effect or refreshing timestamps.

## 06/11/2026 — Human POST confirmations: kết luận kỹ thuật

**POST-ACTION CONFIRMATIONS READY FOR NEXT STEP trong phạm vi đã kiểm chứng.**
Không còn blocker/major tái hiện trong increment này. Phase8A/P8A-E01 tổng thể
vẫn PARTIAL: Staged Settlement và inspection-only successor reconciliation chưa
triển khai; lời chứng POST không cho phép tự settle, đổi custody hoặc release.

### Kết quả, không cộng trùng

| Run | Kết quả | Trạng thái bằng chứng |
|---|---|---|
| post_confirmations_02 |47Passed,0Failed;338.23s|Kế thừa, log đã xác minh; không chạy lại|
| post_confirmations_final_03 |5Passed,0Failed/Errors/Skipped;76.498s|XML hoàn chỉnh được khôi phục;1matrix rerun+4input tests|
| post_confirmations_boot_04 |1Passed,0Failed/Errors/Skipped;70.393s;exit0|Mới chạy sau Docker healthy; old-boot actual simulator restart|
| post_confirmations_real_L_02 |23checksPassed;exit0|Mới chạy, PostgreSQL +hai Backend OS processes +worker +simulator|
| Full regression/Browser/Frontend build |Not Run|Ngoài phạm vi lượt này|

47+5 có1test trùng; thêm1old-boot mới tạo52nodeIDs đã kiểm chứng qua các lượt,
không phải một full-suite52 mới chạy. Không cộng23E2Echecks vào pytest. Evidence:
`PHASE8A_TESTS/<run>/run.log`, pytest có `results.xml`; smoke có
`post_confirmations_real_L_02/reports/PHASE8A_E2E_L.json`.

### Real-process L và các bất biến

Schema test `phase5_test_b47d89d3f00e`; runtime `.cache/p8-L-b287e9b580`.
Hai uvicorn OS processes8030/8031 dùng PostgreSQL thật. Sau durable receipt,
runner dừng rồi restart API8031 trước human confirmations. Simulator tiếp tục
phát snapshot actual; không chỉnh clock, deadline, custody hoặc observed timestamps.
Payment ban đầu chuẩn bị bằng domain mock fixture; không gọi đây là payment
provider OS-process E2E. Customer/Technician đăng nhập API thật trên schema riêng.

- Technician gửi POST statement cùng key qua hai Backend: cả hai200, cùng một
  lời chứng. Customer gửi hai key khác nhau đồng thời:201/409, không overwrite.
  Replay key thành công trả cùng identity; đúng2RECOVERY_POST_ACTION_CONFIRMED audits.
- POST stage có đúng SIMULATOR+TECHNICIAN+CUSTOMER; hai human rows tham chiếu đúng
  receipt và confirmed=true, không tái sử dụng PRE confirmations. Pytest cũng
  chạy nhánh confirmed=false/REJECT, lưu lời chứng riêng, không xác nhận delivery.
- Simulator ledgerOBSERVED/effects1; original OPEN_RETURN effects1, không có
  effect mới hoặc duplicate. Restart simulator sau confirmations và replay receipt
  không lặp effect. Fence ACTIVE không bị clear. Backend vẫn REVIEW_REQUIRED,
  PaymentSUCCEEDED,3holds,oldCUSTOMER/newCOMPARTMENT,old_pin_settled=false,refund0.
- Demo DB fingerprint unchanged. Runner chỉ dừng processes do nó tạo, giữ toàn
  bộ test schema, ledger và log; không sửa dữ liệu demo hoặc reset volumes.
- Test mới boot04 reboot cùng durable simulator ledger rồi gửi snapshot actual:
  POST receipt từ boot cũ bị409RECONCILIATION_REQUIRED khi dùng làm current human
  proof; receipt lịch sử vẫn giữ và effect vẫn1. Không dùng reboot để renew action.

Các tests kế thừa kiểm receipt trước/sau action, PRE-as-POST refusal, wrong serial/
context/hash/actor/recipient override, current session/role/assignment revoke,
expiry/freshness, displaced active-operation pointer, audit rollback và idempotency.
Displaced-pointer test là negative storage fixture, không chứng nhận workflow
supersession thành công. Missing/stale/expired/old-boot/mismatched/rejected proof
tiếp tục giữ REVIEW_REQUIRED và fence. Đường an toàn theo proposal mục7 là
inspection-only successor gắn predecessor/authorization và actual holder/model;
chưa có đường tự refresh evidence, reissue effect hoặc terminal settlement.

### Lỗi môi trường / file thay đổi / tái hiện

post_confirmations_real_L_01 giữ nguyên exit1: Engine mất pipe và DB timeout trước
fixture, không có checksPassed. User mở Docker; pg_isready ban đầu rejecting rồi
accepting. Migration/connection trong boot04 và L02 đã hoạt động. Không có sửa
production code trong lượt resume này. Thay đổi mới: test old-boot trong
`tests/test_phase8a_post_confirmations.py`; assertion human replay/audit count ở
`tools/phase8a_branches.py`; hai tài liệu tiến độ. Các source/schema/overlay human
confirmations từ phiên trước được giữ nguyên, không viết lại. Không migration mới,
source head0007. Git HEAD e4fb9f5/main; không stage/commit/push; baseline Git diff rỗng.

Chạy lại riêng các gate còn mới với label mới, tuần tự từ workspace:

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py post_boot_new pytest tests/test_phase8a_post_confirmations.py::test_post_statement_cannot_promote_old_boot_receipt_to_current_proof
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py post_real_new script tools/smoke_phase8a.py --branch L
```

Giữ source/tests/runner/contract làm regression. Reports XML/JSON/log, retained
PostgreSQL schema và `.cache/p8-L-b287e9b580` chứa bằng chứng, không tự xóa/stage.
Không đụng `.local`, provider/command ledgers, DB demo hoặc volumes.

## 06/11/2026 — Human POST confirmations: tiếp tục nghiệm thu

**PARTIAL / ENVIRONMENT BLOCKED**, chưa kết luận POST-ACTION CONFIRMATIONS READY.
Đã khôi phục kết quả cuối phiên trước từ log/JUnit, không chạy lại nhóm đã Passed:

| Bằng chứng | Kết quả thực tế | Phân loại |
|---|---|---|
| post_confirmations_02 |47Passed,0Failed;338.23s|Lịch sử đã xác minh lại log; PostgreSQL CONFIRM/REJECT +Authorization13/schema29/migration2/OpenAPI1|
| post_confirmations_final_03 |5Passed,0Failed/Errors/Skipped;76.498s|XML hoàn chỉnh được tìm thấy khi resume;1PG matrix rerun +4strict-schema cases|
| post_confirmations_real_L_01 |exit1 trước fixture, PostgreSQL connection timeout|Run mới bị BLOCKED môi trường; Docker Engine mất pipe dockerDesktopLinuxEngine;0E2E checks hoàn tất|
| New old-boot post-proof test |Not Run|Đã lưu source, chờ Docker/PostgreSQL healthy|

Không cộng47+5 thành52 test khác nhau:1matrix bị trùng. Không dùng K03 handover
19checks để chứng nhận human confirmations. Smoke L đã chuẩn bị hai Backend OS
process, restart Backend sau receipt trước human proof, Technician same-key race,
Customer different-key race, giữ1effect/custody/Payment/3holds/fingerprint. Chưa
có bằng chứng smoke L thành công ở checkpoint này.

POST transport dùng hai endpoint cũ: Technician POST evidence với TECHNICIAN_ATTEST,
stagePOST_ACTION_RECEIPT,receipt_id/hash,operation/context,actual_serial,CONFIRM/REJECT,
expected_version và Idempotency-Key; Customer POST confirmations với cùng binding,
confirm boolean và Idempotency-Key. Actor/recipient lấy từ session/context/receipt;
không cho client khai role/actor/recipient/serial thay mặt Customer. Một lời chứng
append-only/source/stage, audit+version+idempotency cùng transaction, không settlement.
Current role/session/assignment được kiểm dưới station/user/session locks. Chronology,
freshness,expiry,boot,current source-empty/supply-present snapshot và command ledger
được kiểm lại trước insert. Lời chứng REJECT lưu confirm=false, không xác nhận delivery
hoặc ownership. Sau effect mà proof không đủ, giữ receipt lịch sử/fence/REVIEW_REQUIRED;
proposal mục7 yêu cầu inspection-only successor liên kết authorization và actual
external holder, không handover lại. Successor và staged settlement chưa triển khai.

Source kế thừa: recovery_schemas.py,recovery_authorization.py,recovery_handover.py;
test_phase8a_post_confirmations.py,test_phase8a_authorization.py;runner phase8a_branches.py
(branchL);overlay0.2 README và CustomerConfirmation/TechnicianAttest schemas.
Không cần migration mới, head source vẫn0007. Trong lượt resume chỉ thêm test old-boot
đúng thiếu coverage và cập nhật tài liệu; chưa sửa source nghiệp vụ. Displaced-pointer
probe là negative storage fixture trên schema test, không phải workflow supersession
thành công. Log post_confirmations_01 Failed do helper lấy version sau mất quyền đọc
được giữ nguyên; helper đã sửa dùng version đã biết. Expected stage-refusal test cũ
đổi422→409 vì POST nay là syntax hợp lệ nhưng PRE receipt vẫn bị từ chối.

Full regression, Browser và Frontend build Not Run theo scope. Không commit/push,
không xóa DB/volume/.local/ledger/evidence; baseline Git diff rỗng. Cần Engine healthy
để chạy riêng test old-boot mới và smoke L, không lặp47/5test đã có chứng cứ hợp lệ.

## Kết luận authorized handover / receipt — 05/11/2026

**HANDOVER/RECEIPT READY FOR NEXT STEP trong phạm vi đã kiểm chứng.**
**Phase8A và P8A-E01 tổng thể vẫn PARTIAL**: chưa triển khai human POST
confirmations hoặc staged settlement. Không kết luận toàn bộ workflow E đã được
nghiệm thu. Không triển khai8B/8C, không commit/push, không dọn dữ liệu.

### Kết quả cuối (mới chạy, không cộng log lặp)

| Run | Kết quả | Bằng chứng |
|---|---|---|
| Targeted final04 | 91 Passed,0Failed/Errors/Skipped; exit0;603.178s | `PHASE8A_TESTS/handover_targeted_final_04/run.log`, `results.xml` |
| Revocation/prepared05 | 2 Passed,0Failed/Errors/Skipped; exit0;139.369s | `PHASE8A_TESTS/handover_revocation_prepared_05/` |
| Real-process K03 | 19 checks Passed,exit0 | `PHASE8A_TESTS/handover_real_K_03/run.log`, `reports/PHASE8A_E2E_K.json` |
| Updated JSON schemas | 3 schema checks Passed | AuthorizeAction,ActionTask,PostActionReceipt; Draft202012Validator.check_schema |
| Merged OpenAPI/allowlist + migration | Passed, included in91 | `test_phase1_contract_and_no_future_endpoints` +2 migration tests |
| Full regression / Browser / Frontend build | Not Run this increment | Scope Backend/simulator only; no full regression requested |

91 gồm4 handover,13 authorization,9 inspection,2 migration,29 schema input,
13 local fence và20 P7-A01 deadline tests, cộng1 OpenAPI/allowlist. Run05 gồm
1case mới revoke activated permit và1case chạy lại có thêm crash-before-PREPARED/
boot mismatch assertions. **Không cộng91+2 thành93 test khác nhau**. Các kết quả
2Passed và18checks của checkpoint trước cũng không cộng vào tổng cuối.

### Bằng chứng effect, crash và concurrency

- K03 dùng schema `phase5_test_b99b1fa38842`, hai uvicorn OS processes8030/8031,
  Device worker và simulator qua HTTP. Payment chuẩn bị bằng domain mock fixture;
  không gọi đây là E2E provider thanh toán. Customer/Technician đăng nhập API thật.
- Hai Backend tranh intent:200/409VERSION_CONFLICT. Activation cùng key replay
  cùng response, một row append-only. Intent gốc vẫn effect_allowed=false.
- Simulator ghi PREPARED bền vững; effect actual foreign serial trả về đúng
  Customer, service ledgerOBSERVED/effects1. Chỉ original OPEN_RETURN có effect1;
  không OPEN_SUPPLY mới, không import vật lạ vào bảng batteries.
- Test wrapper cố ý trì hoãn POST receipt (503 test-only), rồi dừng OS simulator
  sau effect nhưng trước Backend receipt. Không sửa model/time/observation. Gửi lại
  source snapshot nguyên bản từ ledger; hai Backend cạnh tranh receipt lần đầu:
  một insert và một replay, chỉ một RECOVERY_POST_ACTION_RECEIPT_STORED audit.
- Restart đọc cùng ledger; retransmit receipt không chạy lại effect. Fingerprint
  DB demo unchanged. Cuối run: REVIEW_REQUIRED,PaymentSUCCEEDED,3holds,
  old pinCUSTOMER/new pinCOMPARTMENT,old_pin_settled=false,refund0.
- Pytest kiểm crash trước PREPARED; sau PREPARED; rollback giữa model transaction;
  restart trước first receipt; audit rollback activation/receipt; bad-recipient
  rejection không thể được sửa bằng replay cùng event ID; expired local permit,
  boot mismatch, Admin bị từ chối và revoked permit bị chặn trước effect.
- Crash trước/giữa transaction được inject bằng exception trong pytest,
  không khai thành OS kill ở mọi instruction boundary. OS-process stop sau effect
  được chạy thật trong K03. Local UNKNOWN/PREPARED luôn giữ fence, không retry effect.

### Giới hạn còn lại / điều kiện đi tiếp

Không còn lỗi tái hiện trong increment handover/receipt sau các kiểm thử trên.
Vẫn REVIEW_REQUIRED nếu proof thiếu/stale/mismatch, revoke/expiry, ledger UNKNOWN,
PREPARED bị gián đoạn hoặc receipt không chứng minh được effect. Không force-settle,
không giải phóng holds, không tự điều chỉnh Payment/custody. Polling không thực
hiện handover; real-process operator signal chỉ nằm trong tools/phase8a_process.py,
không được import/kích hoạt từ production. UI/operator UX và human confirmations
chưa nghiệm thu trong lượt này. Chưa chứng minh OS kill tại mọi instruction.
Không thay đổi hoặc tuyên bố giải thích lỗi503 lịch sử; 503 ởK03 là fault injection
có nhãn TEST_RECEIPT_DELIVERY_LOSS, độc lập với lỗi lịch sử đó.

### Tái hiện và tài nguyên

Runner từ workspace (đổi label thành tên mới, không ghi đè bằng chứng):

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py handover_review_new pytest tests/test_phase8a_handover.py tests/test_phase8a_authorization.py tests/test_phase8a_inspection_transport.py tests/test_phase8a_migration.py tests/test_phase8a_contract.py tests/test_phase8a_staged_fence.py tests/test_phase7_deadline.py tests/test_phase1.py::test_phase1_contract_and_no_future_endpoints
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py handover_real_new script tools/smoke_phase8a.py --branch K
```

Chạy tuần tự, Docker/PostgreSQL healthy. Runner tạo schema test riêng; giữ nguyên
schema/ledger làm bằng chứng, chỉ dừng child processes do nó tạo. Migration0007
chưa chạy trên DB demo; không có dependency mới hoặc sửa baseline.

Git HEAD e4fb9f5, main...origin/main; không staged. Toàn workspace còn13 tracked
modified và40 untracked entries (192files gồm evidence), có thay đổi8A kế thừa.
`git diff --check` Passed (chỉ cảnh báo CRLF); baseline Git diff rỗng. Danh sách
file increment ở checkpoint ngay dưới; test source/runner/overlay/migration/docs
cần giữ. Logs/XML/JSON và các runtime là evidence cục bộ, không tự stage.
Ba runtime `.cache/p8-K-*` mới khoảng8MiB, reports handover khoảng55KiB; pytest
fixtures/caches và schemaPG cũng được giữ. Không xóa `.local`, ledger, cache có
bằng chứng, DB hoặc volume. Việc chọn artifact dọn sau nghiệm thu cần lượt riêng.

## 05/11/2026 — Activation + authorized handover/receipt (đang kiểm thử cuối)

Người dùng đã chấp thuận activation append-only 1:1 với intent/ACK qua evidence
endpoint (`AUTHORIZE_ACTION`, `phase=ACTIVATE`, exact refs, expected_version và
idempotency). Design gate intent→action bên dưới là lịch sử, đã được giải quyết
bằng chấp thuận này; không sửa immutable intent false hoặc tạo intent thứ hai.

Đã nối Backend activation, ACTION task, simulator PREPARED→effect→POST receipt
và authenticated receipt inbox. Migration0007 chỉ chạy trên schema test, chưa
áp dụng DB demo. Guard tái kiểm actor/source, station/fence/current boot, toàn bộ
command ledger, actual serial/presenter/recipient và original expiry. Activation
có proof_valid_until tính từ timestamp bằng chứng gốc + policy freshness; kiểm
lại trước PREPARED, trước effect và trước commit model. Không gia hạn15s/60s.

Simulator dùng cùng SQLite writer lock với command effects; PREPARED commit
trước effect. Sau đó actual model, service position, source snapshot, ledger và
receipt commit cùng nhau. PREPARED bị ngắt giữ UNKNOWN và không chạy lại. Fence
giữ ACTIVE. Backend lưu receipt lịch sử với grant/effect-window/source-event
binding; không dùng receipt lịch sử làm current proof hoặc human confirmation.
Audit+attestation+inbox nguyên tử. Không thay custody/Payment/holds/case terminal.
Human POST confirmations và staged settlement vẫn ngoài phạm vi lượt này.

Checkpoint mới (không cộng với kết quả lịch sử):

- `handover_integration_01`: 4 setup Errors, sandbox chặn localhost10013; chưa
  kiểm tra nghiệp vụ. Rerun ngoài sandbox đã truy cập PostgreSQL healthy.
- `handover_integration_02`: 2 migration Passed, 2 handover Failed trước PREPARED.
  Nguyên nhân hash ACK: typed Backend UTC `Z` khác local wire `+00:00`. Đã chuẩn
  hóa bằng cùng AuthorizationAcknowledgment schema khi đối chiếu; không sửa
  packet/ledger lịch sử hoặc bỏ hash guard.
- `handover_integration_03`: 2 Passed,135.72s. Single effect/receipt, audit rollback,
  immutable replay, PREPARED crash không retry effect, Payment/custody/holds giữ.
- `handover_real_K_01`: 14 checks đạt rồi workflow Failed trước PREPARED vì lượt
  revalidation thứ hai qua freshness. PG: inspection15:05:59.785671Z;
  activation15:06:08.046464Z; proof_valid_until15:06:14.785671Z. Test operator chờ
  telemetry cycle nên quá hạn. Guard giữ đúng; demo fingerprint không đổi.
- `handover_real_K_02`: 18 checks Passed, hai uvicorn OS processes + Device worker
  + simulator thật, schema phase5_test_b78e1c9c96d3; runtime.cache/p8-K-4b48484197.
  Test-only operator signal được xử lý trên simulator thread trong khoảng idle,
  không đổi nhịp telemetry/đồng hồ/timeouts production. One intent/ACK/activation,
  one service effect/POST audit, restart/replay không lặp; PaymentSUCCEEDED,
  REVIEW_REQUIRED,3holds,oldCUSTOMER/newCOMPARTMENT,refund0; demo hash unchanged.
- Ba updated JSON Schema check Passed. Merged OpenAPI/allowlist nằm trong targeted
  cuối đang chạy; không kết luận trước khi có XML hoàn chỉnh.

Đang bổ sung crash giữa effect và first receipt + cạnh tranh first receipt ở hai
Backend (K), restart tests và regression inspection/authorization/P7-A01. Chưa
kết luận HANDOVER/RECEIPT READY hoặc Phase8A hoàn tất ở checkpoint này.

Files của increment: migration0007; api/recovery_schemas.py,recovery.py,
recovery_contract.py; application/recovery_handover.py,recovery.py,
recovery_inspection.py; simulators/device/recovery_handover.py,service.py;
tools/provision_database.py,phase8a_process.py,phase8a_branches.py;
tests/test_phase8a_handover.py,test_phase8a_migration.py,test_phase8a_contract.py;
overlay0.2 README và AuthorizeAction/ActionTask/PostActionReceipt schemas;
hai tài liệu tiến độ. Tất cả thay đổi8A cũ giữ nguyên. Không commit/push/dọn file.

## 05/11/2026 — Authorized handover/receipt: BLOCKED tại intent → action

Lượt yêu cầu AUTHORIZED HANDOVER & POST-ACTION RECEIPT đã rà soát AGENTS,
P8-REC-0.1/0.2, proposal mục5–9, API/schema, authorization/ack, migration0004/0006,
local fence và service dispatch. HEAD vẫn e4fb9f5; toàn bộ dirty/untracked giữ
nguyên. **Chưa sửa production/test/migration/overlay trong lượt này.**

### Khoảng trống xác nhận bằng source và contract

1. Proposal P8-REC-0.2 mục5 ban đầu mô tả AUTHORIZE_ACTION tạo authorization,
   GET tasks trả ACTION và revalidation trước PREPARED. Phụ lục transport được
   chấp thuận sau đó chỉ triển khai intent/ACK không effect; nó không xác định
   transition kích hoạt intent đó thành quyền tác động.
2. `recovery_authorization.issue` hash `effect_allowed=false` trong payload.
   Trigger `protect_recovery_authorization` (0004) cấm sửa payload/hash/expiry,
   chỉ cho revoke một chiều. `UNIQUE(operation_id)` cấm tạo authorization thứ hai.
   Vì vậy không được UPDATE false→true hoặc INSERT permit thay thế cho cùng op.
3. `AuthorizationIntentTask` literal false; `recovery.tasks` chỉ trả INSPECT hoặc
   AUTHORIZATION_INTENT. `recovery_authorization_acks` lưu acknowledgment vận
   chuyển, không lưu activation decision. Simulator `perform`0.2 chỉ inspect/
   acknowledge; không có representation ACTION đã duyệt nối với intent+ACK.
4. Không thể bỏ qua immutable false chỉ vì ACK tồn tại, tự tạo action qua GET,
   hoặc dùng permit/cache sau reboot. Như vậy sẽ tự thay đổi trust boundary mà
   yêu cầu lượt này chỉ cho phép triển khai khi representation đã được phê duyệt.

Đây là **design gate còn thiếu**, không phải khẳng định double effect đã xảy ra.
Các25pytest/14smoke authorization trước vẫn là bằng chứng no-effect lịch sử;
không dùng chúng để chứng nhận authorized handover.

### Đề xuất tối thiểu để người dùng duyệt — CHƯA ÁP DỤNG

- Giữ nguyên authorization intent/hash/ACK và UNIQUE operation. Bổ sung một
  **activation record append-only**, quan hệ1:1 với authorization hiện có, bắt
  buộc tham chiếu ACK cụ thể. Đây là quyết định kích hoạt cùng authorization,
  không phải khoản authorization mới, không sửa flagfalse trong intent lịch sử.
- Technician creator chủ động gọi endpoint evidence hiện có. Đề xuất mở rộng
  statement AUTHORIZE_ACTION với discriminator kỹ thuật `phase=ACTIVATE` và
  authorization_id/acknowledgment_id/context_hash, cùng expected_version và
  Idempotency-Key. Không có endpoint unlock mới; không tự kích hoạt khi ACK hoặc
  polling. Exact typed schema này cần được duyệt trước khi thêm vào overlay.
- Dưới station/user/resource/session locks hiện có: recheck cả3pre-proof,
  quyền/session/assignment,boot/ledger/fence,actual serial/presenter/recipient,
  full pending ledger,current snapshot/freshness,verified Payment,3holds,
  expiry/revoke/supersede và không có effect/activation xung đột. Ghi activation
  hash+audit+version+idempotency cùng commit. Hash bind intent/ACK/context,action
  RETURN_FOREIGN_OBJECT,source/destination/recipient,device/boot/ledger/fence và
  original expires_at; không reset TTL/deadline. Mỗi intent tối đa một activation.
- Chỉ typed ACTION task mang activation ID/hash mới cho phép simulator xét
  PREPARED. Intent vẫnfalse; quyền tác động thuộc activation đã được kiểm chứng,
  không phải diễn giải lại ACK. Polling không ghi activation. Operator vẫn chủ
  động invoke service; không tự chuyển việc flush ACK thành physical effect.
- Simulator re-fetch/revalidate online ngay trước PREPARED; check actual model,
  permit+activation+ACK,local fence/boot/ledger và TTL dưới writer lock. Giữ fence
  ACTIVE chặn mọi command/legacy effect; chỉ scoped authorized foreign operation
  được xét. PREPARED bền vững trước effect; UNKNOWN không rerun. Sau effect,model/
  effect counter/POST_ACTION_RECEIPT commit cùng SQLite transaction; replay chỉ
  truyền receipt. Receipt bind cả activation và original authorization để giữ
  traceability; Backend chỉ lưu evidence, không settlement/custody/hold release.
- Mất response sau activation commit: retry cùng key trả cùng record; khác key
  không tạo activation thứ hai. Revoke/expiry/boot mismatch trước action chặn
  start; nếu PREPARED/possible effect thì giữ UNKNOWN/review/query ledger, không
  tự rollback tác động hoặc cấp quyền thay thế. Không thay chính sách revocation
  đã duyệt ở P8-REC-0.2 mục5 hoặc late-history ở mục7.

Cần phê duyệt representation/transition activation trên trước khi tạo migration,
schema/task ACTION và nhánh physical effect. Nếu không duyệt, giữ no-effect và
REVIEW_REQUIRED; không tự chọn phương án nới guard.

### Kết quả lượt này và điểm dừng

| Nhóm | Trạng thái |
|---|---|
| Review contract/source/Git |Đã thực hiện; xác định blocker intent→action ở trên |
| git diff --check |Passed, CRLF warnings; không staged files |
| Targeted PostgreSQL/durable effect/crash/concurrency |Not Run — phụ thuộc activation contract chưa chốt |
| Real-process authorized handover/POST receipt |Blocked; chưa khởi chạy effect |
| Human post-confirmations/settlement/8B/8C |Không triển khai, ngoài phạm vi |

Chỉ bổ sung mục này và IMPLEMENTATION_STATUS.md. Không tạo effect,receipt giả,
fixture mới/cache mới; không ghi DB, sửa ledgers, xóa bằng chứng,commit/push.
**HANDOVER/RECEIPT BLOCKED; P8A-E01 và8A vẫn PARTIAL.** Giữ25pytest/14smoke
authorization bên dưới làm lịch sử, không báo Passed mới từ kết quả cũ.

## 05/11/2026 — Backend Authorization acceptance gates (sau chấp thuận ACK)

Người dùng đã chấp thuận acknowledgment vận chuyển; điểm chờ quyết định ở mục
bên dưới đã được giải quyết. Phạm vi chỉ authorization/ack, **effect_allowed=false**,
không post-action, handover, settlement,8B/8C. P8A-E01 toàn workflow vẫn PARTIAL.

### Implementation và guard

- `recovery_authorization.py`: pre-stage Technician/Customer xác nhận receipt
  ID/hash đúng stage/op; lời từ chối append-only, không ghi đè. AUTHORIZE_ACTION
  chỉ creator Technician còn assignment, đúng version/context, ba nguồn proof.
  Kiểm current device/boot/snapshot, actual foreign serial/presenter chính chủ,
  supply battery còn đúng vị trí, old obligation không bị giả nhận, charge verified
  SUCCEEDED và đúng amount/currency, không refund, đúng ba holds.
- Đối chiếu full device command ledger/hash/body/expiry với DB, snapshot ledger
  và chuỗi ACK→OPEN→PRESENCE→CLOSED. EXECUTED không tự là delivery; ngoại lệ manual
  chỉ OPEN_RETURN của chính phiên đã có chuỗi đầy đủ, inspection/snapshot sau
  original physical60. Chuỗi lịch sử có thể thuộc boot cũ nhưng phải cùng một boot,
  đúng device/swap/command/slot và đã xử lý hợp lệ; inspection hiện hành phải đúng
  boot hiện hành. Không nâng rejected late/unknown/stale event thành accepted.
- Giữ `quiet()` mặc định. Mọi UNKNOWN chưa phân giải, ledger thiếu/mâu thuẫn,
  service entry chưa có closure protocol, unrelated EXECUTED command chưa được
  đối soát đều từ chối. Hạn chế bảo thủ này cần giữ rõ: không tuyên bố mọi lịch sử
  terminal service/command đều đã được hỗ trợ authorize.
- Mutation ghi một immutable authorization/op + case version + audit + idempotency
  trong transaction. Hash bind context/receipt/pre-proof/boot/ledger/fence/digest/
  nguồn/recipient/expiry; original TTL giữ nguyên. GET tasks không cấp permit mới;
  chỉ trả AUTHORIZATION_INTENT với effect_allowed=false khi proof/quyền còn hợp lệ.
- Simulator giữ ACTIVE fence, xác thực task rồi kiểm lại local model/ledger trong
  BEGIN IMMEDIATE; persist ACK outbox trước HTTP. Không PREPARED service, không
  effect. Backend nhận AUTHORIZATION_ACK qua endpoint observations hiện có; bind
  permit/op/hash/device/boot/ledger/fence/seq/time, recheck guards, lưu ACK+audit
  nguyên tử. Same event/body replay; changed body409; refused event không thể sửa
  thành accepted. Replay kết quả lịch sử không phải quyền thực hiện mới.
- Migration0006_authorization_ack forward từ0005: append-only ACK, unique permit,
  event/device-boot-seq, runtime SELECT/INSERT. Chỉ chạy migrations trong test
  schemas. Không migrate demo. Năm JSON Schema overlay đã xuất; baseline giữ nguyên.

### Lock ordering và sửa khi nghiệm thu

Idempotency → station advisory → sorted users → swaps/slots/pins → operation/proof
→ sorted auth_session rows → authorization/ack/audit. Không HTTP trong PG transaction.
Review phát hiện logout chỉ UPDATE auth_sessions, không lấy user row lock; bản mới
khóa đúng proof sessions và current requester session để logout không commit giữa
check và permit commit. Current role/assignment được bảo vệ bởi user locks chung
với API quản trị; recheck session expiry ở decision. Không đổi Payment worker,
P6-A01–A03, P7-A01 hoặc deadlines15/60/15.

Fixture từng chọn seed_db chỉ vì key có trong environment. Fixture rollback cũng
có key này: owner connection thứ hai bị chính test giữ row lock, gây55P03 khi
UPDATE compartments. Đã dùng `committed` tường minh chỉ ở race fixture; tests
rollback tiếp tục dùng cùng connection. Không nới lock timeout hoặc đổi expected.
Đây giải thích lỗi **lượt authorization_targeted_final_01**, không chứng minh
nguyên nhân lỗi503 lịch sử khác.

### Kết quả thực chạy, không cộng trùng

| Evidence dưới docs/PHASE8A_TESTS | Kết quả |
|---|---|
| authorization_foundation_01 |49Passed; checkpoint schema/fence/migration/inspection |
| authorization_pg_01 /02 |1Failed; rồi5Passed/1Failed: fixture boot sau dispatch làm history COMMAND_LATE_OR_UNKNOWN, guard đúng; giữ logs |
| authorization_pg_03 |1Failed setup: boot mới chưa có BMS hiện hành để dispatch |
| authorization_pg_04 |6Passed,90.79s; simulator boot/BMS trước dispatch, chờ60s thật và gọi timeout worker; không SQL rewrite custody/time |
| authorization_targeted_final_01 |72Passed,19Failed,325.70s;19fixture row-lock failures mô tả trên. Trong72 có P7deadline20, pickup reconciliation11, contract25, fence13, migration2, authorization race1 |
| authorization_gates_02 |20Passed,192.40s sau sửa fixture; checkpoint trước session-lock cuối |
| authorization_gates_final_03 |**25Passed,0Failed/Errors/Skipped,225.11s**: authorization13,inspection9,migration2,OpenAPI allowlist1 |
| authorization_decision_restart_04 |**1Passed,70.21s**; chạy lại riêng ca positive với asserts bổ sung; là một trong25 tests, không cộng thành26 tests khác nhau |
| Merged OpenAPI |Passed; xuất5JSON Schema self-contained vào overlay |
| authorization_real_J_01 |**14checksPassed**,exit0; hai OS Backend8030/8031, Device worker và simulator HTTP thật; PostgreSQL schema phase5_test_e9afec7c398e |

Gate covered: audit failure rollback cả permit/case/idempotency; retry cùng key,
khác key/version; missing/rejected/wrong-stage/receipt proof; user session revoke,
assignment revoke, Technician đổi Admin không thừa kế quyền; expiry/freshness;
hai Backend app/PID PostgreSQL riêng chỉ một permit/audit. Test bổ sung expire
clock trong lúc đọc history xác nhận final-decision EVENT_STALE/OPERATION_EXPIRED,
không chỉ validate input. Clock injection chỉ tạo refusal, không làm success.

Restart/lost-response: commit ACK qua API nhưng local outbox còn unsent; đóng và
mở lại simulator/SQLite, giữ nguyên event/body/boot/time; retry duplicate không
thêm ACK/effect. Sau snapshot của boot mới, Backend không trả intent cũ; local
fence vẫn ACTIVE. Network custody/Payment/3holds giữ; command effect1 là wrong
return gốc, service effect0. Đây là PostgreSQL+TestClient+durable SQLite, không
đánh đồng với OS process kill.

Real-process authorization-only branch J đã Passed14checks, không cộng vào25pytest.
Hai Backend cạnh tranh khác key:200/409VERSION_CONFLICT, một authorization và
một ACK audit. SQLite giữ ACTIVE fence, commands EXECUTED/effects1 là wrong-return
gốc, service_operations rỗng/effect0. DB REVIEW_REQUIRED, PaymentSUCCEEDED,
3holds, oldCUSTOMER/newCOMPARTMENT, refund0; demo_fingerprint_unchanged=true.
Runner dừng các test process của chính nó. Runtime `.cache/p8-J-01ee1ba03d` và
reports/PHASE8A_E2E_J.json dưới authorization_real_J_01 được giữ nguyên. Provider
charge chuẩn bị bằng domain/mock fixture; đây không phải Payment provider E2E.
Full regression/Browser/
post-action/settlement Not Run theo scope. Những tests/process crash tại mọi
instruction boundary hoặc concurrent logout đúng điểm commit chưa được chứng
minh đầy đủ. Không chốt toàn8A hoặc handover từ các gate authorization này.

**AUTHORIZATION READY FOR NEXT STEP trong phạm vi intent/transport ACK không
effect đã kiểm chứng.** Không phải chứng nhận actuator permit/action, staged
settlement, toàn P8A-E01 hoặc8A. Các guard fail-closed cho history chưa được hỗ trợ
và các mục Not Run ở trên phải tiếp tục được giữ trong bàn giao.

### File và bảo toàn

Source/schema: migration0006; api/recovery.py,recovery_schemas.py,recovery_contract.py;
application/recovery.py,recovery_authorization.py,recovery_inspection.py;
simulators/device/recovery_fence.py,service.py; tools/provision_database.py.
Tests: test_phase8a_authorization.py mới, inspection helper chọn fixture/boot có
chủ đích, migration head expectation0006. Runner branchJ bổ sung trong
tools/phase8a_branches.py; không thay branches A–I. OverlayREADME +5schemas và
hai tài liệu tiến độ cập nhật. Giữ các source/tests làm regression; run.log/XML,
reports và runtime test ledgers là bằng chứng local cần chọn lọc, không tự xóa.
HEAD e4fb9f5, main...origin/main; staged rỗng; mọi dirty/untracked cũ bảo toàn.
git diff --check Passed (CRLF warnings), không commit/push/dependency mới/reset.

## 05/11/2026 — Backend authorization: handshake decision pending

**PARTIAL/BLOCKED ở đường cấp phép; chưa AUTHORIZATION READY FOR NEXT STEP.**
Lượt này rà soát yêu cầu Backend Authorization mới và source hiện có tại HEAD
`e4fb9f5`. Không sửa production code, schema, migration hoặc baseline; không
chạy lại các suite inspection đã có bằng chứng. Các số 68/16/9 ở mục sau là
kết quả lịch sử, không phải kiểm thử chạy mới trong lượt review này.

### Điểm cần xác nhận trước khi triển khai phần phụ thuộc

Yêu cầu mới, mục 3, bắt buộc durable authorization intent **và acknowledgment**.
P8-REC-0.2 mục 5 mô tả commit một authorization rồi GET tasks trả ACTION,
simulator kiểm lại trước PREPARED. Mục 8 chỉ định device observation gồm
PreInspection hoặc PostReceipt; mục 9 chỉ có authorization bất biến/revoked_at.
Chưa quy định message xác nhận nhận permit, nơi lưu acknowledgment, hoặc thời
điểm intent trở thành permit dùng được. Đây là khoảng trống giữa yêu cầu mới
và phụ lục, không phải bằng chứng lỗi double effect trong implementation.

Đối chiếu source: migration0004 có unique operation và proof binding nhưng
không có acknowledgment; migration0005 chỉ là inspection inbox. Schema/API
observations nhận PreActionInspection hoặc legacy DeviceObservation. Receipt
inspection chứa ledger identity/fence generation được tạo **trước** authorization,
nên không chứng minh simulator đã nhận authorization ID/hash sau đó. Không dùng
HTTP GET thành công, cờ fence hoặc ACK command làm acknowledgment nhận permit.

Đã gửi câu hỏi xin chấp thuận bổ sung acknowledgment vận chuyển riêng vào overlay,
qua endpoint observations hiện có, ràng buộc authorization ID/hash, operation,
context, boot, ledger và fence; append-only/idempotent, không phải physical proof.
**Đề xuất chưa được áp dụng.** Cần chốt thêm semantics: intent chưa được phép gây
effect; acknowledgment chỉ xác nhận lưu bền vững, không phải handover; kiểm lại
quyền/expiry/proof trước khi permit có thể dùng; timeout/reboot không được suy ra
NOT_EXECUTED hoặc cấp permit thứ hai. Không tự thêm stage evidence, task kind,
API union hoặc trạng thái permit để giải quyết thiếu quyết định này.

### Rà soát transaction/fencing hiện tại

- Recovery `lock_context`: station advisory lock → sorted participant user rows
  → station swaps/slots/pins qua `device.station_locks`; mutation wrapper giữ
  idempotency bên ngoài. Authorization tương lai phải dùng cùng thứ tự và kiểm
  freshness sau locks/reads, không gọi HTTP trong transaction.
- Device worker dùng cùng station lock; Payment `lock` lấy station → customer →
  swap → payment. Payment worker đã commit claim trước provider HTTP và mở
  transaction mới để ghi kết quả. Không thay đổi cơ chế retry P6-A03.
- Simulator inspection và command effect dùng chung SQLite writer transaction;
  local ACTIVE fence chặn cached command/legacy service trước effect. Đây là
  cơ chế fencing đã có, không phải acknowledgment của authorization mới.
- `quiet()` mặc định không thay đổi. Foreign0.2 hiện chỉ trả INSPECT; legacy
  confirmations/attestations/settlement vẫn chặn RECONCILIATION_REQUIRED.
  Chưa expose AUTHORIZE_ACTION hoặc ACTION, nên không tạo permit mồ côi mới.

### Kết quả và phần còn thiếu

| Nhóm | Kết quả lượt này |
|---|---|
| Review contract/storage/API/fence/lock ordering | Đã thực hiện, phát hiện điểm cần chốt handshake ở trên |
| Git status, HEAD, diff và staged inventory | HEAD e4fb9f5; giữ nguyên thay đổi8A có sẵn; staged rỗng |
| git diff --check | Passed; chỉ cảnh báo CRLF→LF |
| Authorization PostgreSQL/concurrency/rollback/revocation tests | Not Run: chưa triển khai authorization |
| Real-process smoke tới AUTHORIZED, effect_count0 | Not Run: phụ thuộc handshake và implementation |
| Full regression/UI/Browser/handover/settlement | Not Run, ngoài phạm vi lượt này |

Không có test Passed mới để cộng vào lịch sử. Chỉ cập nhật tài liệu này và
IMPLEMENTATION_STATUS.md; không thêm runner/cache/artifact, không kết nối ghi
DB, không migrate demo, không chạm ledgers, không xóa/stage/commit/push.
P8A-E01 vẫn Major/PARTIAL. Nhánh cấp phép chờ quyết định handshake, sau đó còn
phải triển khai pre-confirmations, full ledger guards, durable authorization và
kiểm thử mục tiêu; chưa chuyển sang post-action hoặc8B/8C.

## 05/11/2026 — PRE-ACTION INSPECTION integration

Phạm vi riêng lượt này: nối BEGIN → INSPECT task → actual simulator inspection
→ structured observation → accepted PRE_ACTION_INSPECTION attestation. Chưa cấp
AUTHORIZE_ACTION, post-action transfer/confirmation hoặc staged settlement.
P8A-E01 tổng thể tiếp tục PARTIAL. Các mục tiến độ trước bên dưới là lịch sử.

### Source và contract

- BEGIN RETURN_FOREIGN_OBJECT tạo operation protocol_version0.2 dưới locks/quyền
  Technician hiện có. Việc chỉ đọc không gọi action quiet; vẫn giữ guard phiên
  review, actual foreign serial, operation đang active và station exclusivity.
  Expiry không tự đóng operation/fence. Không ghi custody/payment/holds.
- GET `/v1/device/recovery-tasks` trả strict InspectionTask, task_kind INSPECT;
  cùng Device-Key/station scope. Không trả quyền ACTION. Legacy confirmation,
  attestation và settlement từ chối operation0.2 bằng RECONCILIATION_REQUIRED.
- POST `/v1/device/recovery-observations` nhận union PreActionInspection/legacy.
  Mọi nested input strict; kiểm device enabled/key, context, station, boot/seq,
  stage, expiry, original observation time, accepted processed snapshot, current
  slot/serial và ledger coverage. Presenter thiếu giữ null, không tự điền từ
  expected/customer. UNKNOWN ledger được lưu như observation chưa phân giải,
  không thành proof delivery hoặc authorization.
- Durable outbox lưu envelope/seq trước HTTP, gửi actual model facts. Receipt
  không cập nhật timestamp khi retry/restart. Fence ACTIVE không tự hết hạn;
  cached command và legacy physical service vẫn bị fence chặn.
- Migration **0005_inspection_inbox** forward từ0004: lưu immutable event ID,
  canonical payload hash, outcome/response, device và receipt time. Cần bảng này
  để semantic rejection được commit thay vì mất khi rollback DomainError.
  Same ID/different content409; same refusal không được rehabilitate bằng replay.
  Thành công ghi attestation+audit+inbox nguyên tử. Invalid Device-Key hoặc invalid
  JSON/schema bị từ chối trước service; không gọi chúng là accepted evidence.
- Giữ event/source-boot-seq unique và stage/source constraints0004. Runtime chỉ
  SELECT/INSERT inbox, không UPDATE/DELETE; append-only trigger. Chỉ migrate test
  schema, không migrate demo. Error envelope giữ code/message/correlation/details.
- Overlay0.2 có PreActionInspection.schema.json và InspectionTask.schema.json;
  OpenAPI runtime được merge qua allowlist hiện có, quyền và baseline giữ nguyên.

### Kiểm thử mới, không cộng trùng

| Evidence trong PHASE8A_TESTS | Kết quả | Giải thích |
|---|---|---|
| inspection_transport_01 | 23Passed,1Failed,11setupErrors | Docker mất Engine/TCP timeout; một legacy test truyền task0.2 nay có dispatch inspection. Giữ nguyên log, sửa fixture về legacy path, không sửa expected |
| inspection_local_02 | **68Passed**,0Failed | Fence/service và strict contracts/evidence; không cần DB |
| inspection_pg_02 | 2Passed,9Failed | Migration/grants đạt; fixture mới chưa gọi domain advance để enqueue command |
| inspection_pg_03 | 1Failed (stop-first) | Sửa thứ tự poll vẫn chưa enqueue; không phải production failure |
| inspection_pg_04 | **9Passed** | Fixture gọi domain drive hợp lệ; actual simulator model, API và PostgreSQL; không SQL custody/evidence rewrite |
| inspection_pg_final_05 | **16Passed**,0Failed,0Errors,0Skipped;50.34s | 9inspection +2migration +4legacy API +1OpenAPI allowlist, thêm asserts changed payload và out-of-order replay |
| Merged OpenAPI validation | Passed | Không cần DB, không thay baseline |
| inspection_real_I_01 | **9checksPassed**,0Failed,exit0 | Hai Backend OS processes, device worker và simulator thật; inspection-only, không handover |

**Kết quả inspection increment: đạt phạm vi đã giao.** Schema smoke:
`phase5_test_721231b9b4f4`; ledger/cache riêng `.cache/p8-I-fabd59e03e`.
Backend BEGIN200, receipt được ghi stage PRE_ACTION_INSPECTION, sequence1,
read_only=true, effect_count_delta0. Receipt ID
`86c3d90b-aed6-40e6-b88c-38ae3ef9dfa0`; xác minh chỉ đọc từ PostgreSQL trong
`inspection_real_I_01/receipt_verification.json`. Local fence ACTIVE, replay202
duplicate và một attestation. Command gốc EXECUTED/effect1 không đổi; service
operations rỗng (service physical effects0). Không nhập vật lạ vào network.
DB REVIEW_REQUIRED, PaymentSUCCEEDED,3holds,oldCUSTOMER/newCOMPARTMENT,refund0;
audit thêm RECOVERY_OPERATION_CREATED/RECOVERY_INSPECTION_RECORDED, không success
handover/completion audit. Demo fingerprint không đổi. Chỉ dừng process test do
runner tạo. Không xóa schema, runtime ledgers hoặc evidence.

Smoke có Payment preparation bằng domain fixture/mock outcome như runner cũ;
không phải provider-process E2E. Nó không được tính thành E handover Passed.
Authorization/post receipt/staged settlement vẫn chờ lượt sau, Major P8A-E01
tổng thể vẫn mở. Full regression/UI/Browser/handover E: Not Run theo phạm vi.
Git diff --check Passed; không staged files, main HEAD e4fb9f5, working tree có
cả thay đổi8A cũ lẫn increment mới; tất cả untracked được bảo toàn.

Các tests kiểm: readonly effect0; correct stage; Device-Key/scope/boot/context/
serial/seq/stage bị từ chối; duplicate và changed-body conflict; rejected receipt
không được sửa thành accepted; restart giữ original receipt và ACTIVE fence;
custody/payment/holds không đổi; settlement chưa triển khai vẫn409. Test fixture
HTTP transport trong pytest không được tính là OS-process smoke.

### File thay đổi trong increment

Mới: migration0005, application/recovery_inspection.py,
tests/test_phase8a_inspection_transport.py và hai JSON Schemas overlay0.2.
Sửa: api/recovery_schemas.py, api/recovery.py, api/recovery_contract.py,
application/recovery.py, simulator recovery_fence.py/service.py,
tools/provision_database.py, tools/phase8a_branches.py (inspection-only branch I),
test_phase8a_migration.py (head0005), test_phase8a_staged_fence.py (fixturelegacy),
overlay README và hai tài liệu tiến độ.

Không thay deadline/P6/P7 domain, không triển khai handover/refund/UI. Không chạy
full regression. Giữ schema test, cache runtime, logs/XML/ledger và evidence cũ;
không tự dọn. Không stage/commit/push.

## P8A-E01 / P8-REC-0.2 — tiến độ 05/11/2026, PARTIAL

Người dùng đã chấp thuận có điều kiện thiết kế ba stage. Đã đối chiếu mục 2,
8–9 với điều kiện mới; chưa phát hiện mâu thuẫn nghiệp vụ cần thay FR/UC/BR/QD.
Traceability và các gate chưa hoàn tất được lưu riêng tại
`docs/implementation-contracts/P8-REC-0.2/README.md`; proposal và overlay 0.1 giữ
nguyên. **P8A-E01 vẫn Major mở; KHÔNG FIXED và chưa ready for acceptance.**

### Root cause và phần đã thực hiện

0.1 gọi `quiet()` trước BEGIN, khi trả task và lúc settle. UNKNOWN OPEN_RETURN
với ledger EXECUTED không có đủ nguồn chứng cứ trước action, trong khi schema
chỉ cho một attestation/source/operation. Bỏ một guard sẽ không giải quyết
nguồn chứng cứ, authorization và fence cho command đã nhận trước đó.

Phần nền mới đã ghi xuống repository:

- Migration forward `0004_recovery_stages`: protocol_version nullable (0.2 chỉ
  foreign purpose); LEGACY metadata cho chứng cứ cũ; unique
  `(operation_id,stage,source_kind)`; FK receipt và trigger kiểm cùng operation,
  stage, nguồn SIMULATOR và chronology. Không sửa payload/hash/time/custody cũ.
- Bảng authorization duy nhất/operation, kiểm tham chiếu pre-proof trio,
  actor/device/boot/context/expiry; bất biến, chỉ revoke một chiều. Runtime không
  UPDATE context/expiry hoặc DELETE. Đây là defense tại storage, **không phải
  domain authorization đã hoàn thành**. Không seed permit hoặc promote legacy.
- Response views nhận metadata mới. Chưa thêm endpoint, request AUTHORIZE_ACTION
  hoặc nới allowlist/authentication. Migration chỉ áp trên schema test mới.
- `simulators/device/recovery_fence.py`: internal readonly inspection đọc actual
  model, presenter, toàn bộ command/service rows và lịch sử event; persist
  receipt + ledger identity + một ACTIVE fence trong cùng SQLite transaction.
  Không lấy expected_serial làm observation; presenter thiếu giữ null. Replay
  giữ nguyên boot/time/body. Chưa nối primitive này vào authenticated task API.
- Command handler commit UNKNOWN trước effect, sau đó giữ SQLite BEGIN IMMEDIATE
  chung với inspection, kiểm fence ngay trước effect và commit model/events/
  completion nguyên tử. Command cached trước inspection cũng không vượt fence.
  Exception rollback effect, giữ UNKNOWN. Legacy physical service kiểm cùng
  fence; không retry UNKNOWN, không tự đóng fence do TTL/reboot.

Không sửa Backend quiet/pickup exception, custody decision, ACK15/physical60/
freshness15, Payment, resource holds hoặc quyền Admin/Technician. Không thêm
generic unlock. Bản nền hiện chưa cấp phép hoặc thực thi staged handover.

### Kiểm thử mới (không cộng lặp các lượt)

| Lượt trong PHASE8A_TESTS | Kết quả | Phạm vi |
|---|---|---|
| e01_staged_fence_01 | 24 Passed | 13 fence mới + 11 service cũ; SQLite/local, không phải API E2E |
| e01_staged_local_02 | 73 Passed | Local fence/service, input/evidence và simulator replay/clock regression |
| e01_stage_pg_01 | 15 setup Errors | Sandbox chặn TCP 5432, WinError10013; chưa chạy assertion, không lỗi nghiệp vụ |
| e01_stage_pg_02 | 15 Passed | PostgreSQL migration/grants, stage binding và API 0.1 |
| e01_stage_pg_03 | 41 Passed, 1 Failed | Race probe dùng nhầm fixture cần test_connection; 31 pickup/P7-A01 Passed; không thay expected result |
| e01_stage_pg_04 | 11 Passed | Sửa fixture committed, hai PostgreSQL backend PID khác nhau, unique permit, revoke/rollback; không phải hai OS Backend authorization API |
| e01_staged_real_E_01 | 5 checks Passed, 1 workflow Blocked | Backend/worker/simulator thật; handover vẫn409 RECONCILIATION_REQUIRED |
| e01_staged_validators_01.json | Passed | OpenAPI/JSON Schema/baseline SQL278 statements và baseline hashes |
| e01_staged_targeted_final_01 | **122 Passed, 0 Failed, 0 Errors, 0 Skipped; 192.58s** | Lượt hoàn chỉnh sau chuẩn hóa literal0.2: fence/service, input/evidence, migration/grants/storage race/rollback, API0.1, pickup/P7-A01, simulator và OpenAPI allowlist. XML/run.log đã xác minh sau khi session shell không còn |

Một lỗi cú pháp CASE trong trigger mới được phát hiện bằng parser, đã sửa trước
PostgreSQL tests; 14 DDL statements và hai PL/pgSQL functions parse Passed.
Literal protocol_version được chuẩn hóa thành `0.2` theo mục8, thay vì dùng tên
phụ lục làm literal. Lượt targeted cuối kiểm chứng lại phiên bản này được ghi
bảng trên; các lượt trước là lịch sử snapshot, không cộng vào122.

### Real-process E và bảo toàn dữ liệu

E2E mới tạo schema `phase5_test_3581bfdde212`, cache/ledger riêng
`.cache/p8-E-21351709e9`. Runner hiện có khởi động hai Backend, worker và simulator
S01, authenticates Customer/Technician qua HTTP. Payment preparation dùng domain
fixture/mock outcome; không tuyên bố provider-process E2E. Chỉ dừng process do
runner tạo; schema/ledger/logs được giữ lại.

Sau wrong return/restart/physical deadline thực: command EXECUTED, effect count1;
service operations rỗng; không OPEN_SUPPLY; không nhập vật lạ vào batteries.
DB REVIEW_REQUIRED, pin cũ CUSTOMER, pin cấp COMPARTMENT, Payment SUCCEEDED,
3holds, refund_count0. Không foreign settlement/completion audit. Fingerprint
demo không đổi. Đây là bằng chứng **guard vẫn chặn**, không phải successful
staged handover. E2E này chưa kích hoạt local staged fence qua Backend API.

### Gate bắt buộc còn thiếu

1. Typed staged request/response overlay và dispatch INSPECT/ACTION; durable seq,
   receipt outbox, xác thực provenance/snapshot/full ledger ở Backend.
2. AUTHORIZE_ACTION transaction: scope/revocation/version, đủ ba pre-proof,
   freshness tại quyết định, durable fence/command chain, idempotency/audit.
3. Authorized local PREPARED/effect/post receipt và riêng hai human post-stage
   confirmations; crash/restart/replay và revoke trên luồng này.
4. Staged settlement và expiry/supersede/reconciliation chain; không coi pre-proof
   là post-proof hoặc slot trống là delivery. Giữ fail-closed khi chưa đủ.
5. Hai OS Backend cạnh tranh authorization/settlement và positive real-process E
   trên full workflow; wrong recipient/station/context, revocation và rollback.

Không có bằng chứng để đóng P8A-E01. Không quy việc thiếu implementation thành
mâu thuẫn hợp đồng hay lỗi Docker: Docker hiện healthy, PostgreSQL đã kiểm thử.
Không chạy full regression/UI/Browser/8B/8C trong lượt này.

### File và tài nguyên

Mới: `0004_recovery_stages.py`, `simulators/device/recovery_fence.py`,
`tests/test_phase8a_staged_fence.py`, `tests/test_phase8a_stage_storage.py`,
`docs/implementation-contracts/P8-REC-0.2/README.md` và evidence e01_staged*/e01_stage*.
Sửa trong phần đã uncommitted trước: simulator main/service, recovery_schemas,
tools/provision_database, test_phase8a_migration, tài liệu tiến độ này và STATUS.
Không sửa source application/recovery.py hoặc baseline trong lượt này.
Không stage/commit/push. Giữ tất cả thay đổi cũ, DB, .local và ledgers.

Giữ code/tests/forward migration/traceability làm công việc dở; giữ log/XML và
ledger test để chẩn đoán, không commit artifact tự động. Cache mới từ runner nằm
trong `.cache/p6-fix-*` và cache E nêu trên; không tự dọn hoặc tải dependency/image.

## P8A-E01 — rà soát ranh giới cấp phép trước handover, 04/11/2026

**BLOCKED, chưa sửa/đóng Major.** Lượt này không thay production hoặc baseline.
Đã xác định ba điểm phải phân giải, không chỉ một if gây409:

1. record/BEGIN_OPERATION RETURN_FOREIGN_OBJECT gọi quiet() trước INSERT
   operation. UNKNOWN+EXECUTED không nằm trong tập command được đối soát nên
   trả409RECONCILIATION_REQUIRED. Chưa có task/context/attestation ở thời điểm đó.
2. tasks() gọi lại quiet() trước authorize service effect. Chỉ bỏ guard ở BEGIN
   vẫn không chạy được và không cung cấp thêm chứng cứ.
3. settle() gọi quiet() lần cuối. Ngoại lệ hiện chỉ dành VERIFY_NEW_DELIVERY;
   không được tái sử dụng bằng cách coi return EXECUTED là delivery/old custody.

Khoảng trống chứng cứ trước action: current SNAPSHOT truyền slots+command ledger,
không truyền service_presenters hoặc trạng thái đầy đủ service_operations.
Simulator command_effect ghi actual foreign serial, swap và customer lấy từ
command vào service_presenters; đây là liên kết mô hình mô phỏng, chưa phải một
Customer confirmation độc lập. perform() kiểm presenter tuple đúng context,
nhưng chỉ sau khi nhận task đã authorize. Observation hiện sinh sau thao tác;
schema chỉ có result/actual_serial/supporting_event_ids/simulation_only, không
phân biệt inspection trước action với handover receipt sau action. Mỗi operation
chỉ có một attestation mỗi source. Vì vậy không được nhét inspection vào receipt
OBSERVED rồi dùng nó như proof handover, hoặc đọc SQLite local trực tiếp từ
Backend để vượt trust boundary. P8-REC-0.1 quy định mục tiêu verified presenter
và full ledger, chưa có representation rõ cho bước pre-action này trong overlay.

Phương án tối thiểu cần chốt trước khi đổi representation: trong cùng purpose
RETURN_FOREIGN_OBJECT, tách inspection không effect và authorize handover;
inspection chứng minh command/device/boot, actual serial/source slot, presenter
mapping và toàn bộ pending effects. Backend kiểm station fence/current snapshot,
positive new-pin-at-supply và xác nhận actor trước cấp action. Receipt sau effect
vẫn riêng, append-only; cả hai bind cùng immutable context, không ghi đè nguồn
cũ. Cần quy định rõ payload/stage, số receipt mỗi source và thời điểm confirmation
trước/sau action; không tự thêm enum/API trong lượt này. Nếu adapter không chứng
minh presenter hoặc không loại trừ pending effect thì giữ UNKNOWN. Đây là đề
xuất chưa triển khai, không phải nới quyền hoặc đổi FR/UC/BR/QD.

Lượt mới `e01_contract_boundary_01`: **11Passed/0Failed/0Errors/0Skipped**,
exit0,0.99s. Bộ service ledger hiện có bao phủ missing/different customer/
different swap/correct presenter, crash PREPARED/restart, replay và effect fence.
Đây là SQLite model + mock HTTP tests, không gọi là PostgreSQL/E2E proof.
Không thêm regression cho đường thành công chưa được triển khai. Targeted PG
settlement/race/rollback/pickup/P7 và E2E E mới: **Not Run** do nhánh cấp phép còn
blocked; kết quả ledger_fix_02, real_E_02 là lịch sử, không chạy lại rồi gọi là sửa
thành công. Historical E02 vẫn5checksPassed/1workflowBlocked, fingerprint demo
không đổi. Cần thực hiện các test bắt buộc sau khi representation/authorization
đủ cơ sở. Không dùng11Passed để kết luận P8A-E01 đã khắc phục.

Chỉ cập nhật tài liệu này và IMPLEMENTATION_STATUS.md, thêm report local của
lượt11tests. Git HEAD e4fb9f5/main...origin/main, working tree Phase8A cũ giữ
nguyên; diff --check exit0 với cảnh báoCRLF. Không DB demo write, commit/push,
cleanup,8B/8C hoặc reset deadline. P8A-E01 tiếp tục chặn nghiệm thu toàn8A.

## 04/11/2026 — Real-process C/D/E/F (lượt tiếp theo)

**Kết luận: PARTIAL / BLOCKED, chưa đủ independent acceptance 8A.** Các lượt
cuối CD03/E02/F02 có **20 checks Passed**,0 assertion Failed, **1 workflow
Blocked** (foreign handover). Không cộng checks trùng từ CD01/CD02/E01/F01;
ba lần dừng CD01/CD02/F01 do test harness được giữ riêng, không xóa bằng chứng.
Pytest11service riêng không cộng vào20. Exit0 của E02 nghĩa runner đã ghi nhận
trạng thái PARTIAL đúng, không có nghĩa workflow foreign handover Passed.

E02 sau sửa simulator:5checksPassed, vẫn409 RECONCILIATION_REQUIRED. Đọc lại
PostgreSQL: OPEN_RETURN UNKNOWN, review_reason PRESENCE_MISMATCH (không còn
DEVICE_OFFLINE như E01); snapshot/heartbeat tiếp tục qua nhiều cycle. Ledger
EXECUTED/effect1,không service effect,không thêm pin/command/refund. Đây là
**Major P8A-E01: manual foreign-object workflow chưa có đường phân giải return
command UNKNOWN/EXECUTED**. BEGIN handover phải qua quiet() nhưng quiet() chặn
return command này; nhánh positive pickup mới không áp cho return. Không dùng
EXECUTED làm proof old return/delivery và không nới guard. Cần thiết kế/kiểm
chứng đường phân giải return trước authorize action; vật lạ/người trình phải
được xác minh độc lập. Chưa tạo endpoint hoặc ép custody để khép nhánh.

5 nhóm E2E còn **Not Run**: refund-start vs manual completion; positive proof
mâu thuẫn mới trước settlement; foreign presenter/recipient không xác định;
handover effect commit rồi crash trước Backend receipt/settlement; worker
restart riêng ngay ranh giới custody settlement. E02 chặn trước handover nên
test missing-proof/handover success thêm trong runner cũng chưa được thực thi.
F02 chỉ chứng minh PREPARED/UNKNOWN của inspection không effect, không thay cho
handover crash test. Các giới hạn này cùng P8A-E01 ngăn tuyên bố toàn bộ8A đạt.

File lượt này: mở rộng smoke_phase8a.py,thêm phase8a_branches.py và
phase8a_process.py; sửa tối thiểu simulator main.py và thêm regression trong
test_phase8a_service.py; cập nhật hai tài liệu tiến độ. Chỉ process helper mới
đọc P8_TEST_CRASH_SERVICE; production không import helper và không có flag mới.
HEAD e4fb9f5/main...origin/main; diff --check exit0,cảnh báoCRLF; giữ mọi thay
đổi/untracked cũ. Không stage/commit/push hoặc dọn DB/ledger/.local/evidence.
7thư mục runtime .cache/p8-* mới tổng12.376.951bytes (~11,8MiB), gồm SQLite
ledger/outbox và process logs; PostgreSQL schemas test giữ lại, chưa đo dung
lượng riêng. Không thêm dependency/image. Không tự dọn runtime dù có thể tái
hiện; giữ tới khi nghiệm thu vì đang chứa evidence lỗi. .local/demoDB bảo toàn.

Runner A/B được giữ và mở rộng `--branch CD|E|F`; orchestration ở
`tools/phase8a_branches.py`, fault injection riêng `tools/phase8a_process.py`.
Hai uvicorn OS process (8030/8031), device worker, simulator có SQLite ledger
riêng trong .cache và schema PostgreSQL mới. Tất cả attestation, confirmation,
settlement qua HTTP và actor đăng nhập thật. Setup reservation/charge dùng
domain services qua TestClient và mock outcome có sẵn, **không chạy Payment
Provider process**; không coi lượt này là payment E2E. Không SQL UPDATE custody,
command age, timestamp hay fabricated physical observation. Chờ deadline60 và
operationTTL120 thực. Chỉ dừng children do runner tạo; fingerprint demo trước/sau.

| Nhánh / lượt cuối | Kết quả mới | DB / ledger |
|---|---|---|
| C / real_CD_03 | 4 checks Passed | Trước proof: REVIEW_REQUIRED,3holds,chargeSUCCEEDED,new custody vẫn COMPARTMENT; EXECUTED/ngăn rỗng không đủ; restart không tăng command/effect |
| D / real_CD_03 | 3 checks Passed | Ba nguồn proof, manual COMPLETED sau deadline,oldCOMPARTMENT/newCUSTOMER,0holds,refund0; hai OS Backends cùng key đều200/cùng response,một MANUAL_RECOVERY_SETTLED |
| E / real_E_01 | 5 checks Passed; 1 workflow Blocked | Wrong-return không OPEN_SUPPLY/không nhập vật lạ; oldCUSTOMER/newCOMPARTMENT,3holds,chargeSUCCEEDED,old_pin_settled=false; RETURN_FOREIGN_OBJECT trả409 RECONCILIATION_REQUIRED |
| F / real_F_02 | 8 checks Passed | Offline/reboot giữ3holds; event gốc muộn bị reject; service inspection UNKNOWN/effect0 qua process exit86/restart; hết TTL120 thực tạo inspection mới; proof boot cũ bị từ chối,review/charge/custody giữ |

C/D: ledger hai command EXECUTED, mỗi effect1; service inspection OBSERVED với
effect0. Payment không đổi, command history không sửa để completion. E: một
OPEN_RETURN UNKNOWN trong DB, ledgerEXECUTED/effect1; service chưa được authorize.
Snapshot/presence mismatch được giữ làm evidence. Sau reconnect, simulator E có
HTTPStatusError và session reason DEVICE_OFFLINE; do đó **không quy toàn bộ409
cho riêng EXECUTED**. Source quiet() vẫn chặn UNKNOWN OPEN_RETURN/EXECUTED và
device thiếu freshness; cần phân giải cả provenance/health của wrong-return
trước authorize handover. Không nới guard hoặc cho trả vật lạ khi thiếu proof.
Nhánh kiểm chứng người trình/người nhận và handover foreign object thành công
đang Blocked, không kết luận E hoàn tất.

Giữ failed attempts: real_CD_01 assertion so full battery row trong khi BMS
telemetry thay đổi (đã sửa chỉ so custody fields); real_CD_02 settlement trước
physical deadline vì presence mismatch vào review sớm (sửa runner chờ clock
thực). Không đổi expected business rule hoặc production code. real_F_01 giữ
5 checks an toàn nhưng crash injection chỉ ném RuntimeError, bị loop bắt; không
phải process-crash Passed. Helper sửa thành exit86 ngay sau durable PREPARED.

E2E tìm thấy lỗi simulator wrong-return: slot chứa serial vật lạ nhưng vẫn gán
expected_battery_id của pin cũ, làm cycle gửi TELEMETRY sai phạm vi pin và mất
health. Sửa tối thiểu `simulators/device/main.py`: chỉ gán battery_id nếu serial
quan sát khớp expected serial. Không thay đổi serial/model effect, Backend guard
hoặc nhập vật lạ thành pin. Thêm regression
`test_wrong_return_does_not_emit_network_bms_identity_for_foreign_object`;
`foreign_identity_01`: **11Passed/0Failed/0Errors/0Skipped**,exit0,1.00s,
gồm10 service tests cũ và1test mới. Chưa full regression sau sửa simulator.

F dùng UNKNOWN của **read-only VERIFY_NEW_DELIVERY inspection**; không được
suy thành đã chạy E2E UNKNOWN của handover có effect. Ledger giữ hai command
EXECUTED/effect1 mỗi command, một service UNKNOWN/effect0 và inspection sau
TTL OBSERVED/effect0. Không có manual completion audit trong F; valid manual
completion được kiểm riêng tại D. Không có refund ở các schema này.

Giữ 56targeted và493full làm kết quả lịch sử,
không cộng vào checks E2E. Refund-start race, contradictory proof E2E, unidentified
foreign presenter/recipient bị chặn, crash sau service effect trước DB receipt,
và worker restart độc lập giữa settle chưa được lượt này chứng minh đầy đủ.
Full regression, validators/build, UI/Browser không chạy trong nhiệm vụ này.

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py UNIQUE_CD script tools/smoke_phase8a.py --branch CD
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py UNIQUE_E script tools/smoke_phase8a.py --branch E
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py UNIQUE_F script tools/smoke_phase8a.py --branch F
```

Chạy tuần tự; mỗi label phải mới. JSON summaries tại reports/PHASE8A_E2E_*.json
trong thư mục lượt tương ứng; JSON chỉ giữ kết quả, schema và đường dẫn runtime,
không secret. Process logs và physical/service ledger ở đường dẫn .cache trong
JSON. Giữ test helpers/runner để tái hiện; raw ledger/log/fixtures chỉ giữ local,
không tự commit hoặc xóa. Không sửa baseline, không8B/8C/UI/Browser/commit/push.


## 04/11/2026 — Bản sửa hẹp command/ledger reconciliation

Kết quả chạy mới cuối `PHASE8A_TESTS/ledger_fix_02`: **56 Passed, 0 Failed,
0 Errors, 0 Skipped**, exit0,182.59s (XML182.584s). Gồm11 command-reconciliation
tests mới,15 settlement tests,10 durable service-ledger tests,20 P7 deadline
tests. Không cộng lượt `ledger_fix_01`9Passed/30.89s vào56 vì bị trùng coverage;
lượt01 là checkpoint trước final freshness guard và race test.

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
.\.venv\Scripts\python.exe -X utf8 tools/run_phase6_fix.py NEW_UNIQUE_LABEL pytest tests/test_phase8a_command_reconciliation.py tests/test_phase8a_settlement.py tests/test_phase8a_service.py tests/test_phase7_deadline.py
```

Log và JUnit XML của cả hai lượt được giữ. Sáu file báo cáo mới tổng11.714bytes;
schema PostgreSQL fixture và SQLite test ledgers được giữ trong khu vực test,
không dùng DB demo/.local. Có cảnh báo Starlette TestClient deprecation;
không cài dependency để loại cảnh báo. `git diff --check` exit0 (có cảnh báo
CRLF), HEAD e4fb9f5, không stage/commit/push. Working tree Phase8A cũ giữ nguyên;
lượt này sửa recovery.py, thêm test_phase8a_command_reconciliation.py,
cập nhật tài liệu này và IMPLEMENTATION_STATUS.md. Không thay runner/source
Phase1–7. Giữ test và source làm regression; raw report/fixture không tự xóa
hoặc đưa vào commit. Full regression493 và build trước đây chỉ là lịch sử.

Checkpoint 30/10 bên dưới là lịch sử, bao gồm 493 Passed; không phải kết quả
full regression cho bản sửa mới. Phase8A vẫn PARTIAL, chưa nghiệm thu độc lập.

Nguyên nhân P8A-L01: cùng `quiet()` dùng cho cấp phép thao tác vật lý và cho
settlement. Guard NOT_EXECUTED bảo vệ thao tác đúng, nhưng cũng chặn manual
completion khi command UNKNOWN, ledger EXECUTED và đã có đủ proof độc lập.

Thay đổi duy nhất về source trong lượt này là `application/recovery.py`:

- Giữ default `quiet()` nghiêm ngặt cho BEGIN, polling/handover và resume.
- Chỉ settlement VERIFY_NEW_DELIVERY đã đạt điều kiện payment, old custody,
  ba nguồn SIMULATOR/TECHNICIAN/CUSTOMER, serial/holder/context và snapshot mới
  mới cung cấp danh sách command được đối soát cho `quiet()`.
- Chỉ UNKNOWN OPEN_SUPPLY đúng device/ngăn/pin/serial, nằm trong immutable
  operation context, ledger EXECUTED trong accepted snapshot boot hiện hành,
  snapshot quan sát sau deadline vật lý mới đủ điều kiện. Không sửa command,
  deadline, timestamp hoặc gọi lại automatic advance. Command vẫn UNKNOWN.
- Ledger mâu thuẫn terminal state hoặc NOT_EXECUTED mâu thuẫn positive pickup
  bị chặn. Các operation chưa giải quyết khác giữ fence, trừ predecessor
  handover được chứng minh bằng inspection theo đường có sẵn.
- Đọc ledger dưới station/resource locks; recheck TTL/freshness sau ledger read
  ngay trước custody writes. Custody, consumption, audit và release terminal
  cùng transaction; audit ghi command IDs đối soát và snapshot ID.

| Tình huống | Quyết định sau sửa |
|---|---|
| NOT_EXECUTED, snapshot hiện hành sau physical deadline | Giữ guard cũ; không tự chứng minh delivery |
| UNKNOWN command + EXECUTED, không đủ positive proof | REVIEW_REQUIRED, giữ custody/holds/Payment |
| UNKNOWN OPEN_SUPPLY + EXECUTED, đủ positive proof và old custody hợp lệ | Manual COMPLETED nguyên tử; không đổi command history; không effect mới |
| UNKNOWN/thiếu ledger, sai boot/device/serial, snapshot cũ hoặc chưa qua deadline | Chặn; không tự chuyển thành NOT_EXECUTED |
| UNKNOWN OPEN_RETURN chưa có chuỗi return proof được chấp nhận | Tiếp tục chặn; bản sửa không suy ra return custody từ EXECUTED |
| Service PREPARED/UNKNOWN sau restart | Giữ fence, không chạy lại effect; chưa đủ proof thì không settle |
| Service đã commit effect nhưng mất response | Replay durable observation cùng operation; không effect lần hai; Backend vẫn kiểm proof riêng |
| Handover hết hạn, inspection mới đủ proof old possession | Đường predecessor có sẵn; consume cả hai fence cùng custody/audit |

Test mới `tests/test_phase8a_command_reconciliation.py`: positive completion
và replay, bảy trường hợp thiếu/mâu thuẫn proof, rollback khi audit lỗi,
freshness hết hạn trong lúc đọc ledger, hai Backend app cạnh tranh settlement.
Test race kiểm PostgreSQL PID khác nhau và chỉ một custody increment/audit;
đây là hai app/kết nối trong cùng tiến trình pytest, **không phải E2E hai OS
process**. Fixture chỉ thay tuổi command trong schema test để đi qua deadline;
không ghi outcome/custody hay làm mới timestamp proof để tạo kết quả mong muốn.

Không migration, dependency, API hoặc baseline thay đổi. Không đổi simulator
trong lượt này; chạy lại service-ledger tests hiện có. Giữ toàn bộ bằng chứng
cũ. Real-process reconciliation C/D/E/F, UI/Browser và full regression không
chạy trong nhiệm vụ hẹp này. Lỗi503 lịch sử vẫn chưa xác định nguyên nhân;
không dùng kết quả mới để tuyên bố đã giải thích lỗi cũ.

P8A-L01 đã có đường positive pickup cụ thể, không được coi là đóng mọi nhánh
UNKNOWN. P8A-L02 và gate nghiệm thu toàn8A còn mở. Những nhánh thiếu nguồn
chứng minh phải giữ REVIEW_REQUIRED, không mở guard để hoàn tất workflow.


## Checkpoint tiếp tục ngày 30/10/2026 — PARTIAL / chưa đủ nghiệm thu

Đã lấy được kết quả đầy đủ của regression chạy ở phiên trước, không chạy lại:
`PHASE8A_TESTS/regression_checkpoint_01/run.log` và `results.xml`:
**493 Passed, 0 Failed, 0 Errors, 0 Skipped**, XML 1117.114 giây
(pytest log 1117.13 giây). Đây là kết quả snapshot hiện tại, không phải bằng
chứng rằng các nhánh chưa viết/chưa kiểm đã đạt. Không còn tiến trình
`pytest`, `run_phase6_fix` hoặc `smoke_phase8a` khi kiểm tra PID cuối lượt.

HEAD vẫn `e4fb9f5`, `main...origin/main`. Không stage/commit/push. Không sửa
source production thêm trong lượt resume ngày30/10 này; các source/test từ
lượt trước được giữ nguyên. Docker Engine đã dừng khi bắt đầu; khởi động lại
Docker Desktop hiện có và xác nhận `doi-pin-dev-db-1` healthy. Không reset DB,
volume hoặc ledger, không áp migration lên schema demo.

### Kết quả mới và kết quả kế thừa

| Bằng chứng | Kết quả | Phân loại |
|---|---|---|
| regression_checkpoint_01 | 493 Passed / 0 Failed / 0 Errors / 0 Skipped | Phiên trước chạy hoàn tất, lượt này xác minh log + XML; không chạy trùng |
| recovery_targeted_06 | 75 Passed | Kế thừa, có diagnostic hai PostgreSQL PID |
| resume_01 | 33 Passed | Kế thừa; settlement/resume và tests Phase7 |
| resume_contract_02 | 20 Passed | Kế thừa; response schemas, allowlist/security, settlement |
| realtime_A_01 | 5 checks Passed | Kế thừa; inspection actual external model, hai API cạnh tranh |
| realtime_B_01 | 6 checks Passed | Kế thừa; real return → service handover; một effect, một settlement/audit, ba holds giữ, fingerprint demo không đổi |
| lock_diagnostic_07 | **11 Passed**, 0 Failed, 5.68s, exit0 | Chạy mới; diagnostic PG +10 service-ledger tests |
| npm run build | **Passed**, exit0 | Chạy mới; tsc --noEmit + Vite,84modules |
| validators_01 | OpenAPI/JSON Schema/278 SQL statements/baseline hashes Passed | Kế thừa log đã đối chiếu; script không thực thi DDL |
| Browser 8A | Not Run | Không suy ra từ build/API |
| Real-process C/D/E/F, toàn bộ revocation/worker race | Not Run đầy đủ | Chưa đủ gate A–F |

Không cộng targeted/E2E vào493. Các lần thất bại trước vẫn giữ nguyên:
`foundation_full_01`466/1 lỗi ghép OpenAPI; `api_contract_02`48/1 với503;
`sequential_api_03`5setupErrors khi Docker không hoạt động;
`recovery_retry_01`collection error do indentation assertion mới, đã sửa;
`recovery_targeted_05`74/1 do diagnostic dùng fixture chung connection,
đã sửa harness để dùng hai connections/PID thật. Không đổi expected result
của nghiệp vụ để che các lỗi này.

### Call graph và ma trận ledger hiện tại

`record(BEGIN_OPERATION)` → station/user/resource locks → `quiet()` cho
handover/resume → durable operation/fence. `tasks()` kiểm lại payment,
ba holds, pin cấp và snapshot trước authorize action. Simulator `perform()`
xác thực Technician + Device-Key, ghi UNKNOWN trước action, effect+model+
observation cùng SQLite commit; polling/flush chỉ replay receipt.
`settle()` lấy cùng lock graph, ba nguồn/role/session/current snapshot/commands,
rồi consume/custody/case/audit/holds cùng PostgreSQL transaction.
`command_allowed()` chặn command khi còn operation chưa consume/cancel,
kể cả operation đã hết TTL. `RESUME_SWAP` chỉ enqueue bước chưa từng phát;
completion sau resume chạy guard Phase7 nguyên vẹn rồi mới đóng recovery case.

| Backend command / ledger hiện tại | quiet()/hành vi | Custody/delivery |
|---|---|---|
| OBSERVED | quiet cho qua | Vẫn cần đúng chain, current evidence và các guard settlement; không chỉ đọc enum |
| REJECTED hoặc EXPIRED | quiet cho qua theo terminal semantics hiện có | Không tự chứng minh NO/YES; settlement vẫn kiểm ba nguồn và vị trí |
| QUEUED/DISPATCHED/ACKNOWLEDGED/UNKNOWN + NOT_EXECUTED | Chỉ cho qua nếu accepted snapshot đúng boot còn mới, observed_at >= created_at+physical60 | Không đổi command state/deadline; không tự chuyển UNKNOWN→NOT_EXECUTED |
| Các trạng thái chưa kết thúc + EXECUTED | **Đang bị chặn** | EXECUTED không là proof nhận/trả pin; chưa có đường manual reconciliation đầy đủ cho trường hợp này |
| Các trạng thái chưa kết thúc + UNKNOWN/thiếu ledger | Chặn, giữ review/fence/holds | Không reissue, không suy từ TTL |
| Service UNKNOWN sau PREPARED, chưa có observation | Replay không thực hiện lại; fence không tự hết hạn | Chưa có đủ proof để settle; không biến thành no-effect |
| Service OBSERVED có observation bền vững | Replay cùng event; một effect | Ba nguồn độc lập và snapshot mới vẫn bắt buộc |
| Handover old hết hạn, inspection mới chứng minh old ngoài ngăn | Giữ fence predecessor cho đến settle; consume cả hai nguyên tử | Có PG regression; không cấp phép handover lần hai |
| Service bị từ chối/serial hoặc presenter mâu thuẫn | Không overwrite attestation; UNKNOWN hoặc reject | Không chuyển custody/giải phóng holds |

**Khoảng trống P8A-L01 — Major về khả năng hoàn tất workflow:** command đã
thực thi cơ khí nhưng Backend chưa có custody proof hợp lệ có thể còn UNKNOWN,
trong khi ledger EXECUTED; `quiet()` hiện không cho nhánh này đối soát tiếp.
Điển hình sai pin hoặc evidence muộn. Giữ nguyên guard trong lượt này; không
đổi thành chấp nhận mọi EXECUTED. Cần tách proof “không còn actuation có thể
phát sinh” khỏi proof delivery, ràng buộc ledger với đúng command/device/boot,
snapshot hiện hành và station fence, rồi kiểm độc lập custody ba nguồn.
Không sửa event rejected thành accepted, command UNKNOWN thành OBSERVED,
timestamp/deadline hoặc reissue OPEN_SUPPLY để giải quyết khoảng trống.

**P8A-L02 — chưa đủ coverage crash/recovery:** unit ledger chứng minh không
double effect và retry receipt; E2E A/B chưa thay thế real-process C/D/E/F,
đặc biệt crash sau PREPARED/commit trước receipt, service UNKNOWN qua restart,
vật lạ và evidence mâu thuẫn sau settlement. Nhánh phụ thuộc L01 chưa thể
đánh dấu hoàn thành. Đây là công việc triển khai/kiểm chứng còn thiếu, không
phải kết luận rằng PostgreSQL đã làm sai custody trong các test đã chạy.

### Đối chiếu P8-REC-0.1 / TC12, CT07, CT08

| Yêu cầu | Source/test/bằng chứng | Trạng thái |
|---|---|---|
| Migration/context bất biến/append-only/grants | 0003_recovery_evidence; test_phase8a_migration | Done trên schema test; demo chưa migrate |
| Sáu APIs, role/ownership/Device-Key/idempotency | api/recovery*.py; test_phase8a_api/contract; test_phase1 allowlist | Done trong phạm vi tests; chưa independent acceptance |
| Ba nguồn độc lập, rejection/replay/expiry | domain/recovery.py; evidence/API/settlement tests | Done phần đã kiểm |
| A old possession, B old return, D manual completion | application/recovery.py; settlement A/B/D; E2E A/B | Partial: D real-process sau deadline chưa chạy |
| C pickup UNKNOWN | test_C_unknown_pickup_cannot_complete_even_with_two_human_confirmations | Done fail-closed PG; real-process crash còn thiếu |
| E foreign object/presenter | service.py; 4 presenter cases | Partial: full PG/workflow và E2E E còn thiếu, có L01 |
| F reconnect/old boot/expiry | test_F_reconnect_does_not_reuse_old_boot_service_proof; expired handover inspection test | Partial: real-process recovery đầy đủ còn thiếu |
| RESUME_SWAP hai nhánh | test_resume_uses_normal_custody_workflow_and_closes_case_only_at_completion,2cases | Passed; case chỉ RESOLVED sau Phase7 custody guards |
| Atomic rollback | test_settlement_audit_failure_rolls_back_custody_consumption_and_holds | Passed |
| Hai Backend settle/một effect | E2E A/B, SQLite concurrent callers | Passed trong các kịch bản này; chưa toàn bộ lock graph |
| Concurrent revoke/worker contention/new contradictory evidence | Chưa có đủ probes riêng | Not Run đầy đủ |
| UI Customer/Technician/Admin | Recovery.tsx + nav; build mới Passed | Partial: Browser Not Run |
| Operator action | CLI --service-operation + SERVICE_TECHNICIAN_TOKEN; E2E B | Có demo CLI chủ động; không có web generic unlock hay tự action khi poll |
| TC12/CT07/CT08 trọn 8A | Cần A–F và recovery concurrency đầy đủ | **Chưa đạt gate đầy đủ** |

### Diagnostic 503

`test_phase8a_lock_diagnostic.py` dùng Database riêng, assert hai
`pg_backend_pid()` khác nhau, key UUID ngẫu nhiên (không khóa trạm demo).
Đổi search_path của contender sang pg_catalog không tránh contention;
lock_timeout100ms trả55P03; rollback cả hai rồi lấy lại lock thành công.
Không đổi production advisory key, timeout hay retry. `api_contract_02` chỉ
có HTTP DATABASE_UNAVAILABLE, thiếu SQLSTATE/server log tại đúng thời điểm:
**nguyên nhân503 lịch sử vẫn chưa được xác định chắc chắn**.

### Git, tài nguyên và các bước tiếp theo

`git diff --check` sạch về whitespace (có cảnh báo CRLF→LF). File
PHASE5_TEST_ENVIRONMENT.json vẫn hiện M nhưng diff nội dung rỗng; không tự
restore/normalize. Toàn bộ untracked source/tests/docs/evidence được giữ.
PHASE8A_TESTS khoảng247KB tại lần đo; runtime/ledger mới nhất ở
`.cache/phase8a_e56ba1f12abc` và `.local/phase8a_e56ba1f12abc`, giữ nguyên.
Không thêm dependency. Frontend dist/cache là generated, không đưa vào commit;
không dọn trong lượt này. Giữ DB và cả command/service/payment ledgers.

Tiếp tục cần khép L01 bằng proof/guard có căn cứ P8-REC-0.1 và test trước,
sau đó E2E C/D/E/F, concurrency/revocation và Browser. Nếu source đổi, chạy
targeted và full regression mới; không dùng493 làm chứng nhận cho source sau
đó. **PARTIAL/BLOCKED các nhánh phụ thuộc L01; chưa PHASE 8A READY FOR
INDEPENDENT ACCEPTANCE.** Không có thay đổi8B/8C/baseline/commit/push.

---

## Nhật ký triển khai trước checkpoint (giữ làm lịch sử)

Ngày 29/10/2026. HEAD nền `e4fb9f5`. Người dùng đã phê duyệt phụ lục
P8-REC-0.1 và các điều kiện bổ sung; chỉ 8A, không Refund 8B/finalizer 8C.
**PARTIAL — chưa sẵn sàng nghiệm thu độc lập. Không commit/push.**

## Phần đã có trong working tree

- Migration `0003_recovery_evidence`, hai bảng operation/attestation và pointer
  nullable trên case. Context bất biến, attestation append-only, FK/CHECK/index
  và runtime grants hạn chế. Live schema được đọc trước khi viết migration là
  `0002_user_approval`, chỉ có `recovery_cases`. Chưa áp lên demo.
- Input contracts, TTL cấu hình `RECOVERY_OPERATION_TTL_SECONDS=120`, các API
  đọc/evidence/confirmation và receipt helper. Settlement và device task/receipt
  đã được bổ sung tiếp, đang kiểm chứng.
- Shared station lock nhận thêm danh sách actor để lấy user locks theo thứ tự;
  không thay logic timeout/retry P6 hoặc physical deadline P7.
- Simulator service adapter đang triển khai, ledger riêng trong cùng SQLite,
  chủ động qua `--service-operation`, không thực hiện handover khi polling.
- UI Recovery tối thiểu đã thêm; chưa chạy Browser acceptance.
- Phụ lục ở `docs/implementation-contracts/P8-REC-0.1/`. Baseline không sửa.

Không xem các mục “đã có code” là đã nghiệm thu. Chưa chốt toàn bộ provenance,
crash/restart, A–F và concurrency. Những nhánh không đủ proof phải giữ review.

## Bằng chứng chạy đến thời điểm cập nhật

| Lượt | Kết quả thực tế | Ghi chú |
|---|---|---|
| Schema inputs trực tiếp | 25 Passed | Trước runner mới |
| Migration/grants trực tiếp | 2 Passed | PostgreSQL schema riêng; không migrate demo |
| foundation_01 | 50 Passed | Log/XML trong PHASE8A_TESTS |
| foundation_full_01 | 466 Passed, 1 Failed, 0 Errors, 0 Skipped; 527.933s | Snapshot source trước sửa OpenAPI; lỗi KeyError confirmations; không phải full regression cuối |
| api_contract_02 | 48 Passed, 1 Failed | Fixture nhận DATABASE_UNAVAILABLE tại device event; SQLSTATE không được log trong response, chưa đủ cơ sở khẳng định nguyên nhân |
| sequential_api_03 | 5 Errors setup | PostgreSQL không kết nối được; Docker Engine không hoạt động khi kiểm tra. Không có assertion nghiệp vụ được chạy |
| sequential_api_04 | 51 Passed | Chạy tuần tự sau Docker healthy; không suy ngược rằng đã chứng minh nguyên nhân lần 503 cũ |
| settlement_01 | 7 Passed | A và reject/mismatch/expiry/offline/revoked + OpenAPI |
| settlement_02 | Đang lấy kết quả | B/D được bổ sung; không cộng vào số lịch sử |
| Frontend build | Passed ở lượt đã chạy | tsc và Vite; lượt đầu sandbox EPERM, chạy lại được phép Passed |
| Real-process E2E A–F / Browser / full regression source cuối | Not Run | Bắt buộc trước kết luận ready |

Runner `tools/run_phase6_fix.py` được mở rộng cho `TEST_REPORT_ROOT=PHASE8A_TESTS`;
mỗi LABEL mới từ chối ghi đè thư mục bằng chứng. Hai test migration ban đầu chạy
trực tiếp làm fixture ghi lại file environment Phase5; metadata mới đã được lưu
sang `PHASE8A_TESTS/foundation_initial_environment.json` và nội dung lịch sử
Phase5 được trả lại. Những lượt sau luôn dùng runner riêng. Không xóa schema,
logs, ledgers hoặc bằng chứng Phase7.

## Công việc bắt buộc còn lại

1. Hoàn chỉnh và kiểm chứng toàn bộ settlement A–F, gồm manual return custody
   sau deadline, foreign-object presenter, UNKNOWN/restart và operation hết hạn.
2. Service fencing và durable action giữa Backend/Simulator; không retry UNKNOWN;
   các snapshot/history/nguồn độc lập phải thực sự hỗ trợ quyết định.
3. Kiểm thử multi-connection/multi-process, revoke, rollback, duplicate effect,
   deadlock, worker contention. Không thay expected result để hợp thức implementation.
4. Hoàn thiện schema response/error mapping overlay và UI, E2E tiến trình thật.
5. Chạy validators và full regression sau khi hoàn tất code; không dùng 466
   Passed của snapshot trung gian thay thế regression cuối.

## Bảo toàn và tái hiện

```powershell
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
# Chọn LABEL mới mỗi lần; chạy tuần tự các nhóm PostgreSQL.
.\.venv\Scripts\python.exe tools/run_phase6_fix.py NEW_LABEL pytest tests/test_phase8a_contract.py tests/test_phase8a_evidence.py tests/test_phase8a_migration.py tests/test_phase8a_api.py tests/test_phase8a_settlement.py
```

Giữ source/migration/tests và overlay làm bàn giao. `PHASE8A_TESTS` là raw
evidence local, cần chọn lọc trước commit tương lai. Giữ `.local`, PostgreSQL
volume và schema test; không dọn. Build `apps/web/dist`/cache có thể tái tạo trong
lượt dọn riêng được cho phép. Không thêm dependency hay phần mềm hệ thống.

TC12/CT07/08 chỉ được kết luận cho phần thực sự kiểm chứng. TC16/CT13 chưa hoàn
thành vì 8B chưa triển khai. Chưa kết luận Phase8A hoặc toàn Phase8 hoàn thành.
