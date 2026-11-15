# Phase 8A — Independent Acceptance Round 2

## Checkpoint quyết định mới — 15/11/2026

**PHASE 8A — CONDITIONAL ACCEPTANCE APPROVED BY USER.** Người dùng đã phê duyệt allocation R2-D01/NFR04, R2-D02/NFR07/CT14 và R2-D04/NFR08 sang final MVP integration acceptance. Các tests/gates này vẫn **NOT RUN / OPEN, bắt buộc trước full MVP acceptance/release**, không PASSED/WAIVED. Owner TV1–TV5 là đề xuất theo R3; nhóm chưa xác nhận cá nhân nhận việc. IA01/NFR06 Recovery findings FIXED/CLOSED technical scope; evidence603 Backend,21 audit actions,8 real runners và Browser/frontend được kế thừa theo R3, không chạy mới. Không full MVP PASS, không hoàn tất refund/compensation hoặc tự mở8B/8C.

[Biên bản quyết định](PHASE8A_CONDITIONAL_ACCEPTANCE.md) · [Release gates/criteria/owners](MVP_RELEASE_GATES.md) · [Đề xuất staging, không git add](PHASE8A_GIT_READINESS.md).

Các kết luận/pending tại những checkpoint bên dưới là **lịch sử trước approval này**, giữ nguyên, không sửa R1/R2/R3 thành PASS hồi tố. Không đổi production/baseline hoặc xóa dữ liệu/evidence.

## Checkpoint sửa R2-NFR06-01 — 15/11/2026 17:44 +07

**Đề xuất đóng R2-NFR06-01 trong technical scope Recovery8A sau fix + verification; không phải Independent Acceptance Round3.** Root cause trước–sau thiếu tại audit helper đã được sửa bằng actual transaction-local snapshots tại từng mutation. Creation case dùng before-object null; giữ action/actor/device/time/correlation/IDs và metadata, không ghi raw proof/freeform secrets, không backfill hay sửa audit lịch sử. Audit/mutation/idempotency atomic; rollback không giữ success audit và replay không tạo audit/effect trùng.

Gates mới: **86 targeted Passed; coverage21/21 actions;8 real-process runners A/B/CD/E/F/J/K/T exit0; SQL read-only8 fixtures/63 committed audit rows Passed;3 affected Chromium tests Passed; frontend39/TS/Vite exit0. Full603 Passed,0Failed/Errors/Skipped,exit0**, pytest54:56.43,16:46:41–17:41:46 +07. Giữ599 historical tests, thêm4 audit tests;179 source hashes trước/sau khớp. Trạng thái custody/Payment/holds/effects đúng từng nhánh, không thay business guards. Browser post01 Interrupted do host power off được giữ riêng, không tính Passed.

[Fix report/coverage matrix và giới hạn](PHASE8A_NFR06_FIX.md) · [Full XML](PHASE8A_TESTS/nfr06_full_20261115_01/results.xml) · [Exit/collection/source verification](PHASE8A_TESTS/nfr06_fix_20261115_01/full_verification.json) · [Persisted audit SELECT verification](PHASE8A_TESTS/nfr06_fix_20261115_01/audit_all_03.json).

**Kết luận R2 lịch sử bên dưới không bị sửa thành PASS. Toàn8A vẫn PARTIAL/chờ quyết định nghiệm thu. R2-D01/D02/D04 vẫn PENDING APPROVAL**; lần sửa này không tự cấp waiver/approval cho performance, coordinated restore hoặc usability, không chứng nhận NFR06 toàn bộ module MVP. Không stage/commit/push, không8B/8C hoặc xóa evidence. Checkpoint triển khai trước đó và finding gốc giữ nguyên.

**Checkpoint sửa 15/11/2026:** Người dùng đã giao D03/R2-NFR06-01; snapshot before/after và coverage đang được kiểm chứng trong [PHASE8A_NFR06_FIX.md](PHASE8A_NFR06_FIX.md). Finding chưa đóng cho đến khi đủ gates; D01/D02/D04 còn PENDING APPROVAL. Đây là checkpoint triển khai, không phải Independent Acceptance Round3. Finding/kết luận R2 gốc bên dưới giữ nguyên làm lịch sử.

Ngày review: **15/11/2026**, Asia/Bangkok. HEAD `e4fb9f5`, `main`, working tree Phase 8A chưa commit. Đây là review source/contract/evidence và một truy vấn PostgreSQL **read-only**, không triển khai tính năng, không chạy lại full pytest hoặc Browser. Tính độc lập là phương pháp đối chiếu expected-from-contract; không phải kiểm toán của một tổ chức/người ngoài nhóm triển khai.

## 1. Quyết định

**PARTIAL/BLOCKED cho nghiệm thu toàn Phase 8A vô điều kiện.**

- **Đóng P8A-IA01: FIXED trong scope kỹ thuật đã tái kiểm chứng.** Shared guard, rollback, provenance, replay và evidence source cuối nhất quán. Lịch sử fail/fix được giữ, không sửa kết luận lịch sử [R1](PHASE8A_INDEPENDENT_ACCEPTANCE.md).
- Full Backend mới **599 Passed / 0 Failed / 0 Errors / 0 Skipped, exit 0** có JUnit/exit/collection/hashes hợp lệ. Đây là kết quả của lượt trước được **xác minh lại**, không phải một full run mới ở R2.
- Có **R2-NFR06-01 — Major về completeness của audit trước–sau**, được xác nhận bằng source và dữ liệu fixture E read-only. Không có bằng chứng mới về double charge/effect hoặc custody sai; finding này không tái mở IA01.
- NFR04, full NFR07/CT14 và NFR08 còn thiếu evidence; phân bổ gate giữa acceptance increment 8A và final MVP/release **PENDING APPROVAL**, không tự dời sang một Phase10 đã được duyệt.

Chức năng Recovery trong slice 8A có evidence tốt; chưa cấp CONDITIONAL ACCEPTANCE có hiệu lực khi các điều kiện/owner/gate chưa được phê duyệt và audit gap chưa được xử lý. Không đề nghị commit tuyên bố hoàn tất Phase 8A. Không triển khai 8B/8C.

## 2. Nguồn và cách review

Đối chiếu AGENTS; START_HERE/CODEX_HANDOFF; approved QD/config; FR12→F5→UC10→TC12 trong `contracts/traceability.csv`; INVARIANTS6–8, ACCEPTANCE CT05–11/14; báo cáo thiết kế/triển khai 8A, overlays0.1/0.2 và ER-01/02. Số nhóm handoff gốc không phải số Phase thực tế; không đổi ID để khớp tên Phase.

Yêu cầu NFR được đọc trực tiếp từ DOCX GĐ1 bằng XML, không dựa riêng vào diễn giải của báo cáo triển khai. [Trích đoạn và paragraph index](PHASE8A_TESTS/independent_r2_20261115_01/baseline_nfr.json). Kế hoạch/handoff đặt đo NFR, restore và tổng kiểm audit ở bước tích hợp/nghiệm thu cuối; gap analysis Phase9/10 là **đề xuất**, không phải waiver hoặc approval cho gate mới.

R2 chỉ thêm báo cáo/evidence và helper review cục bộ. Không có test execution mới; không cộng các phép kiểm artifact/SELECT vào pytest/E2E. [Validation R2](PHASE8A_TESTS/independent_r2_20261115_01/evidence_validation.json).

## 3. Re-review IA01 — FIXED

### Đường gọi và guard

| Điểm kiểm | Source cuối / kết luận |
|---|---|
| Technician PRE | `application/recovery.py::record` lấy `lock_context`, đọc lại quyền/scope và version, sau đó dispatch `TECHNICIAN_ATTEST`0.2 vào `recovery_authorization.human` |
| Customer PRE | `recovery.py::confirmation` lấy cùng context locks, kiểm owner/current role/session, đối chiếu projection binding rồi gọi cùng `human`. Projection không thay thế mutation guard |
| Current boot/provenance | Trong `human`, sau khi lấy **exact actor auth_session FOR UPDATE**, kiểm device đúng trạm, enabled, device ID/boot bằng nguồn receipt; canonical payload hash, operation context, OBSERVED/read_only, actual serial; source event đúng device/boot, SNAPSHOT, accepted và processed |
| Final time | Sau các lần đọc provenance, lấy `now` mới, gọi lại `open_operation`, kiểm session expiry/revocation và proof freshness trước INSERT. Đây là decision-time policy dưới khóa, không cam kết đồng hồ tại WAL commit |
| Refusal | Throw DomainError trước attestation/change_case/audit. Dependency transaction rollback; idempotent() chỉ INSERT receipt sau execute thành công. Error envelope có correlation UUID riêng/request, không phải cached successful receipt |
| POST | Dispatch sang `recovery_handover.human_post` trước guard PRE; historical PRE chain không bị áp current PRE boot để thay thế POST. POST receipt/current snapshot/actor guards còn nguyên |
| Successor | Stage RECONCILIATION_INSPECTION dùng `recovery_reconciliation.current`, liên kết predecessor/effect history và current proof; không tạo activation/effect mới |
| Legacy0.1 | Hai đường legacy tách khỏi branch0.2; không đưa receipt/stage bắt buộc vào request0.1. Full599 có regression legacy/settlement0.2/P7 |

`human` chỉ ghi attestation, case version và audit; không đổi custody, Payment, holds, command, receipt cũ hoặc fence.

### Lock graph và linearization

Idempotency advisory lock → station advisory/row lock → users UUID order → swaps/compartments/batteries UUID order → exact session(s). `station_locks` được worker snapshot và Recovery dùng chung; thiết bị/current projection không thể được worker commit qua station mutex trong decision transaction. `human` chỉ khóa một actor session và không lấy user/station mới sau session đó.

Logout lấy idempotency riêng rồi UPDATE một session, không quay lại station/user. UpdateUser khóa administration→user→sessions; AssignStations khóa user trước thay assignment, không giữ station rồi quay lại user. Recovery đã giữ các participant user locks trước session locks; authorization/settlement nhiều sessions dùng UUID order. Không thấy inversion mới do IA01 hoặc HTTP/network wait trong guard. Thay đổi chỉ thêm current proof validation sau session wait, không kéo network vào transaction.

Role/state/assignment được đọc lại trong context đã serialize. Nếu logout commit trước thì token row được đọc là revoked; nếu Recovery giữ token trước thì logout phải chờ transaction này. Expiry/freshness vẫn trôi khi chờ và được kiểm sau chờ. Không tuyên bố formal proof mọi interleaving: IA01 concurrent proof test là **hai app/PG connections**, không phải hai OS process. Bằng chứng OS-process của T/E/K và 17 settlement races có scope riêng.

### Probe và bằng chứng

- R1 boot probe run01/run02: mỗi lượt **1 Failed** do Technician accepted old boot. [Original source archive](PHASE8A_TESTS/ia01_fix_20261114_01/original_probe.py) còn nguyên, không skip/xfail.
- So archive với test hiện tại: chỉ tách so status/envelope và loại **correlation_id** khỏi so error body theo phê duyệt người dùng; thêm assertions version/attestations không đổi. Status/code/message/details và assertions nghiệp vụ không bị nới. [Diff độc lập R2](PHASE8A_TESTS/independent_r2_20261115_01/probe_delta.diff).
- Sau sửa có một run Failed chỉ vì correlation UUID khác, giữ nguyên; không coi đó là lỗi boot còn tái hiện. Probe hiện tại vẫn được collect trong full599 và Passed.
- Final targeted6: old boot, same-boot CONFIRM/REJECT, audit rollback/replay, hai app tranh một proof, final freshness/operation expiry. Các ca delayed decision dùng clock injection, **không phải** bằng chứng OS lock-wait riêng cho PRE và không sửa timestamp persisted.
- Real **T** exit0: reboot simulator thật, cả Technician requests409, Customer từ chối, case unchanged, **0 service effect, 0 confirmation audit**. Real **E** exit0: PRE→intent/ACK→activation→handover→POST→settle/replay, **1 effect, 1 success audit**. Real **K** exit0: expired predecessor/successor/current proof/chain settle, **1 original effect, 1 success audit**, không cấp effect thứ hai. Ba fixture đều giữ Payment SUCCEEDED, old pin tại Customer, supply pin tại compartment và3 holds; demo fingerprint chỉ scope8 bảng của runner.

[T/E/K reports, hashes và exits](PHASE8A_TESTS/independent_r2_20261115_01/historical_validation_corrected.json). **IA01 CLOSED/FIXED trong technical scope**, không đồng nghĩa các NFR đã đạt.

R2 đọc riêng startup lines của hai Uvicorn logs trong mỗi runtime, không đọc/in credentials: T OS PID27060/21520, E7868/848, K27440/26740; đều là hai process riêng ở8070/8071, không phải hai TestClient cùng process. [Process evidence](PHASE8A_TESTS/independent_r2_20261115_01/process_evidence.json). Không khởi động hoặc điều khiển lại các process đó ở R2.

## 4. Evidence validation và inheritance

| Gate | R2 đã kiểm | Status / giới hạn |
|---|---|---|
| Full `ia01_full_20261115_02` | JUnit599 testcase; failures/errors/skips0; exit.json0; full log; 11:20:51–12:10:06 +07, pytest2947.95s | **Passed, evidence source cuối**; không chạy mới |
| Collection | Multiset node IDs, chỉ normalize random UUID params: current599 khớp XML, historical587 không missing, thêm12=6IA01+6operator | **Passed**, không cộng targeted/E2E vào599 |
| Hash freeze | Actual SHA256 của175 file khớp before/after source cuối; delta0 | **Passed**, không sửa source từ verification |
| Full run01 | Không XML/final exit, log bị shutdown ngắt | **Interrupted**, không dùng làm Passed; log giữ nguyên |
| Browser affected | Sáu XML và sáu exit0: post, successor, old-boot, pre-reject, revoked, stale-expired | **6 Passed trên Backend mới**, không rerun ở R2 |
| Canonical Browser | Đọc trực tiếp15 XML/exit.txt của terminal_fix;0 failure/error/skipped | **15 Passed lịch sử**, không gọi15 chạy trên Backend mới. Không cộng6 thành21 scenarios độc lập |
| Canonical hash delta | Manifest257 so actual chỉ đổi `recovery.py`, `recovery_authorization.py`, `staged.spec.ts`, `phase8a_manual_operator.py` | Frontend production/package/contracts không đổi; role/UI/terminal-label có thể kế thừa. Đường PRE/POST/successor chịu ảnh hưởng được bù bằng6 Browser + T/E/K mới |
| A–F/ER01/02 | Verified summary + exits/B restart replacement; A5+B7+CD8+E28+F8+J20+K26 | **102 checks lịch sử**. Thay B6 bằngB7, không cộng cả hai; không gọi tất cả102 đã rerun sau IA01 |
| Concurrency |17 labels/logs đầy đủ, source barriers/lock graph và các cặp PG blocker/commit order trong báo cáo tiến trình | **17 scenarios Passed kế thừa**, không chạy mới; không giả lập đó là mọi actor/interleaving. Không phải mọi runner cũ có exit.txt riêng như batch T/E/K; giữ JSON/log cuối và scope assertions |
| Frontend/tooling | terminal_ui_fix frontend39/build exits0; operator25; validators/OpenAPI22 schemas/deps exits phù hợp source | **Passed lịch sử tương ứng**; không coi SSR/build là Browser hoặc bằng chứng NFR tải |
| Protected facts | T/E/K JSON và Browser affected database metadata | Không double effect/audit settlement, Payment/custody/holds đúng từng nhánh; không suy fingerprint8 bảng thành toàn DB |

Các checkpoint42 targeted dùng source trước final-time adjustment không được gộp vào final targeted6. K01/K02/K03 interrupted/environment failures còn giữ; chỉ K cuối có exit0 được dùng làm gate. [Full R2 validation](PHASE8A_TESTS/independent_r2_20261115_01/evidence_validation.json), [history validation đã sửa bộ đếm nested checks](PHASE8A_TESTS/independent_r2_20261115_01/historical_validation_corrected.json). Bản `historical_validation.json` sơ bộ đếm mapping keys thay vì nested check entries, được giữ để truy vết; không dùng tổng18 sơ bộ làm kết quả.

## 5. Traceability trong scope 8A

Đường source application dưới `services/backend/app/`; test source dưới `tests/`. “Verified slice” không hoàn tất chức năng tài chính của8B/8C hoặc toàn UC10.

| Requirement | Source | Test cụ thể | Evidence | Status R2 |
|---|---|---|---|---|
| FR12/UC10/TC12 recovery | api/recovery.py; application/recovery.py/projection | test_phase8a_api/evidence/settlement/customer_projection | Full599; A–F; Browser affected | **Verified slice**, NFR acceptance còn thiếu |
| BR05 / CT05 | recovery_settlement.py; simulator service/fence; foreign context | test_phase8a_staged_settlement/command_reconciliation | E28 lịch sử, E mới exit0 | Không nhập vật lạ vào kho, không tự old_pin_settled; **Passed scope** |
| BR09 / CT08 | quiet(), recovery_closure/reconciliation; giữ holds | test_phase8a_service/staged_fence/closure_fence | C/F, J/U/S, full599 | UNKNOWN không suy delivery/refund/cấp lại; **Passed scope** |
| BR11 / CT06/09 | shared human; current_snapshot; worker ordering | test_phase8a_ia01_fix/independent_acceptance; P7 deadline tests | T, old-boot Browser, full599 | **IA01 fixed**, không đổi ACK15/physical60/freshness15 |
| BR12 | append-only migrations/grants, immutable context, no arbitrary-state API | test_phase8a_stage_storage/migration, audit rollback tests | Full599 + grant evidence | Append-only **Passed**; chưa đồng nghĩa NFR06 trước–sau đạt |
| P8-REC-0.1 | legacy record/confirmation/settle; sorted session locks | test_phase8a_api/evidence/settlement; legacy revocation tests | Full599;17 races kế thừa | **Verified scope**, không đổi payload0.1 |
| P8-REC-0.2 | inspection→intent/ACK→activation→effect→POST→human→settle | inspection_transport/authorization/handover/post_confirmations/staged_settlement | E mới, Browser post, full599 | **Verified workflow E**, không final-compensate |
| ER-01 | recovery_reconciliation.py + simulator reconciliation | test_phase8a_expired_recovery[successor/successor_rejected] | K mới + successor Browser | Current3 sources+original receipt, read-only successor; **Passed scope** |
| ER-02 | recovery_closure.py, permanent deny, closure ACK | test_phase8a_expired_recovery[closure], closure_fence/staged_fence | J20 lịch sử, Browser closure kế thừa, full599 | NEVER_PREPARED + future revocation, UNKNOWN/PREPARED fail-closed; **Passed scope** |
| Invariant6 | recovery paths + reservation/resource guards | settlement/service/command reconciliation tests | A–F/T/E/K facts | Review giữ3 holds, không tự mở ngăn mới; **Passed scope** |
| Invariant7 | new_pin_delivered derivation/refund absence guards | staged_settlement/settlement negative tests | D/E/J/K facts | **8A inputs verified**; refund engine/one-refund intent thuộc8B, không Passed toàn invariant7 |
| Invariant8 / CT07 | old-pin possession/return evidence, settlement | settlement A/B/D/E; expired recovery | A/B/D và E mới | **8A obligation evidence verified**; CLOSED_COMPENSATED cần refund và8C, chưa hoàn tất toàn invariant8/CT07 |
| CT10/11 | owner/assignment, version/idempotency/append-only | customer_projection, API, staged_settlement | Browser RBAC/version lịch sử, affected revoked, full599 | **Passed scope**; API-only không được gọi Browser |
| CT14 | persistent ledger restart; coordinated restore chưa có | restart/drill tests hiện có chỉ một phần | J/K/T/restarts | **Partial**, restart không thay restore |

## 6. NFR acceptance allocation — chưa có waiver

A=bắt buộc trong8A; B=final MVP/release sau8A; C=evidence đủ cho slice nêu rõ; D=thiếu evidence/cần test hoặc sửa. Một NFR có thể có C cho phần đã kiểm và D cho phần còn lại; không được dùng C của slice để đóng toàn yêu cầu.

| NFR gốc | Allocation và cơ sở | Evidence hiện có | Còn thiếu / decision |
|---|---|---|---|
| NFR04 p95 đọc≤2s,20 sessions,1000 requests sau warm-up,2×6 | **B đề xuất, PENDING APPROVAL** dựa bước tích hợp/nghiệm thu cuối trong handoff; không tự gán Phase10 | Functional API/Browser không phải benchmark | **D/Not Run**: dataset, hardware, endpoints, warm-up,1000 mẫu/20 authenticated sessions,p50/p95/max/error rate. Nếu người dùng chọn A, phải đo trước khi chốt8A |
| NFR07/CT14 | Restart/reconcile8A: **A+C**. Coordinated restore: **B đề xuất, PENDING APPROVAL** theo handoff | Real-process crash/restart và ledger replay có evidence | **D/Not Run restore**: cùng snapshot boundary PostgreSQL+device/payment/service ledgers, manifests/hashes/revisions; restore vào runtime riêng, kiểm audit/idempotency/custody/holds/no repeat effect/charge. Không cần refund ledger chưa triển khai |
| NFR06 audit/correlation | Atomic append-only trace cho mutations8A: **A**. Tổng monitoring/release coverage có thể **B đề xuất**, không miễn thiếu hụt hiện có | Actor/device,time,swap correlation,immutable proof/audit, rollback: **C cho slice** | **D**, R2-NFR06-01 bên dưới. Chưa có coverage100% before–after; không có evidence monitoring/supervision toàn hệ thống. Không ghi NFR06 Passed |
| NFR08 usability | Role/UI recovery correctness: **A+C trong flows đã kiểm**. Ba người dùng thật: **B đề xuất, PENDING APPROVAL** | Playwright và manual smoke cơ bản user-reported | **D/Not Run 3-person trial**: ba người thực hiện kịch bản độc lập, ghi success/errors/help/timeout và không sửa dữ liệu tay. Browser headless không thay thử người dùng |

### R2-NFR06-01 — Major: thiếu before-state trong audit thay đổi Recovery

**Expected:** NFR06 gốc yêu cầu100% thao tác đổi trạng thái có actor/device,time,transaction/command ID và **trước–sau**, không có password/raw QR token. Append-only là cần nhưng chưa đủ.

**Actual source:** `application/recovery.py::audit` chỉ INSERT `after_data`, không `before_data`. `change_case` cập nhật version/state; `human`, activation và settlement gọi helper này. Không có global INSERT trigger tự bổ sung before-state. `MANUAL_RECOVERY_SETTLED` có flags/references trong after-data, nhưng không phải snapshot trước/sau của state/version đã thay đổi.

**Actual DB read-only:** schema E hiện có `phase5_test_431e179e0940`, thuộc real-process E sau sửa, không phải demo. `SET TRANSACTION READ ONLY`, SELECT aggregate counts và trigger definitions, rồi rollback. **11 recovery audit events có after_data, 0 có before_data**; gồm1 FOREIGN_OBJECT_RETURN_SETTLED,1 RECOVERY_ACTION_ACTIVATED và hai nguồn PRE/POST confirmations. Trigger duy nhất của audit là BEFORE UPDATE/DELETE reject, không điền before khi INSERT. Không phải mọi event creation đều cần một before-object, nhưng activation/settlement/case version mutation có trạng thái trước thực tế mà audit không ghi. [Evidence SELECT không chứa credentials](PHASE8A_TESTS/independent_r2_20261115_01/audit_readonly.json).

Không kết luận chỉ vì tên cột NULL: [kiểm payload keys độc lập](PHASE8A_TESTS/independent_r2_20261115_01/audit_transition_keys.json) cho thấy activation chỉ có `activation_id/authorization_id/acknowledgment_id`, không có before/after state/version của case. Foreign settlement có `case_version` ở after cùng proof/flags, nhưng không snapshot/reference biểu diễn rõ before-state. Các references giữ provenance, chưa có chứng minh coverage100% trước–sau tương đương qua reconstruction. NFR không bắt buộc một JSON shape mới; đề xuất dùng cột before/after hiện có là cách sửa nhỏ, không phải tự thêm hợp đồng nghiệp vụ.

**Impact/severity:** Major về requirement/audit completeness phục vụ recovery/reconciliation và acceptance; không chứng minh Payment/custody sai. Audit count1 và atomic rollback vẫn đúng. Full599 không kiểm nội dung before-state nên Passed không phủ định finding. Không tự miễn yêu cầu bằng cách dời monitoring sang phase sau.

Đây là **1 acceptance criterion Failed từ source/SELECT**, không phải một pytest test mới Failed và không sửa số599 của full run. [Finding record](PHASE8A_TESTS/independent_r2_20261115_01/finding_NFR06.json). Chưa viết hoặc sửa regression source trong R2; bản sửa/test mới cần được giao riêng.

**Sửa nhỏ nhất đề xuất cho lượt riêng:** truyền snapshot before/after thật của aggregate/state/version liên quan vào audit, giữ actor/correlation/proof references/redaction và atomic transaction. Phân biệt creation với transition; thêm assertions audit payload cho PRE/POST, activation, settlement, closure/resume và audit-failure rollback/replay. Không backfill dữ liệu lịch sử bằng suy đoán, không UPDATE audit append-only, không đổi custody/deadline/fence hoặc hiệu ứng simulator. Sau đó chạy regression theo impact; không tự giả định599 vẫn là collection mới.

## 7. Quyết định cần người dùng phê duyệt

| ID | Đề xuất cụ thể | Trạng thái / hệ quả |
|---|---|---|
| R2-D01 | Chốt NFR04 là gate final MVP/release integration, trước nghiệm thu/phát hành toàn MVP; chỉ định owner và lưu load report đủ tiêu chí gốc. Hoặc chọn hoàn tất ngay trước8A | **PENDING APPROVAL**; chưa có benchmark Passed, không tự chọn Phase10 |
| R2-D02 | Chốt coordinated restore NFR07/CT14 là gate final integration, giữ restart/no-replay như gate8A. Hoặc yêu cầu restore drill trước8A | **PENDING APPROVAL**; không miễn restore, cần runtime/dung lượng riêng và kế hoạch consistency trước drill |
| R2-D03 | Giao sửa R2-NFR06-01 trong lượt riêng trước chốt8A; tổng monitoring/coverage mọi module vẫn là release gate, có owner/evidence checklist | **PENDING APPROVAL cho công việc tiếp theo**, finding hiện **OPEN**. Phê duyệt kế hoạch không tự làm finding Fixed |
| R2-D04 | Chốt3-person usability trial NFR08 ở final MVP integration sau khi đủ UI module; giữ Browser/UI Recovery evidence hiện có là slice8A | **PENDING APPROVAL**; nếu yêu cầu3 người ngay8A thì vẫn Blocked đến khi có trial thật |

Các allocation này không sửa FR/UC/BR/QD hoặc tiêu chí đo NFR. Chưa có approval thì không coi điều kiện đã được giải quyết. Sau khi xử lý audit gap và chốt allocation có thể xem xét CONDITIONAL ACCEPTANCE **riêng chức năng8A** với release checklist còn mở; không tự chuyển trạng thái trong R2.

## 8. Git readiness — đề xuất, không stage

Preflight git có15 tracked modifications và912 untracked files; phần lớn artifacts chưa chọn. HEAD vẫn `e4fb9f5`, index trống. R2 tạo thêm báo cáo/evidence nên số cuối sẽ lớn hơn912. Không dùng `git add -A`.

[Curated staging manifest](PHASE8A_TESTS/independent_r2_20261115_01/curated_staging_manifest.txt) liệt kê từng path đề xuất, **không phải lệnh đã chạy**. Nhóm cần giữ:

1. Backend Recovery/domain/API/projection/composer; integrations reservations/device/swaps/main/config/workers; migrations0003–0008 và grants.
2. Simulator service/inspection/fence/handover/reconciliation và integration main; không runtime ledger.
3. Recovery UI/model/main, frontend tests, Playwright config/specs/redaction reporter và package/lock devDependency.
4. Tests Phase8A gồm IA01, historical original probe archive; runners process/race/crash/operator và runner chuẩn. Các regression P6/P7 đã tracked ở HEAD được giữ, không cần copy.
5. Overlays0.1/0.2 và approval/design/implementation/manual/R1/R2/status docs. Chọn summary R2 nhỏ với hashes/counts và test/runner instructions để clone có thể tái hiện; không phụ thuộc duy nhất raw local log.

`docs/PHASE5_TEST_ENVIRONMENT.json` là runtime evidence tích lũy, không source; **exclude** khỏi commit8A trừ khi người dùng chọn một evidence public riêng. Không stage cả `docs/PHASE8A_TESTS/`. Giữ local các XML/log/screenshots/raw traces, private.json, runtime folders, SQLite/payment/device/service ledgers, host events/machine metadata và các interrupted/failed runs. `.cache` chứa cả ledger/evidence không thể coi toàn bộ là cache xóa được.

Manifest cuối có **126 paths đề xuất**, không có path thiếu. Tệp lớn nhất trong nhóm vượt250KB là `PHASE8A_IMPLEMENTATION.md` (252118 bytes), tài liệu lịch sử có chủ ý, không binary/generated runtime; không tự cắt hoặc xóa. Bảy nhóm path bị cấm vẫn loại khỏi staging, kể cả khi có artifacts untracked. Một số public R2 summaries nhỏ được chọn rõ; toàn bộ raw batches vẫn giữ local.

Heuristic scan115 candidate files chỉ flag một literal trong `apps/web/tests/playwright-reporter.test.mjs:9`; đã đọc và xác định là **synthetic redaction fixture, không phải credential thật**. Không tìm thấy private-key/provider-token/literal credential thực trong phạm vi scan; **không phải chứng nhận không có secret bằng mọi hình thức**. Không xuất giá trị credentials/tokens. `.env`, `.local`, `.cache`, node_modules/dist/.vs được git check-ignore xác nhận; không có index entry staged. Cần final staged scan/diff khi người dùng giao commit sau xử lý finding. [Inventory/scan không chứa giá trị](PHASE8A_TESTS/independent_r2_20261115_01/git_review.json).

Không có source/migration/overlay change ở R2, không network mutation, không tạo/xóa schema hoặc can thiệp demo. SELECT read-only chỉ trên schema E đã giữ. Source freeze175 vẫn khớp; baseline Git paths không đổi. Không add/commit/push, clean/reset/delete hoặc triển khai8B/8C.

Git cuối: `main...origin/main`, HEAD `e4fb9f5`, **15 tracked modifications tích lũy / 927 untracked files / 0 staged**, `git diff --check` exit0. [Final review/scan/link/hash state](PHASE8A_TESTS/independent_r2_20261115_01/final_review_state.json); source delta0, không broken report link tại lần kiểm. Scan cuối126 paths vẫn chỉ có synthetic redaction fixture đã giải thích, không raw secret phát hiện trong phạm vi heuristic. Không chứng nhận toàn927 untracked files sạch để stage hàng loạt.

Tái hiện sau clone phải dựng fixture mới bằng runner đã commit, không trông chờ các schema/runtime cục bộ trong link lịch sử. Ví dụ targeted IA01 dùng `tools/run_phase6_fix.py LABEL_MOI pytest tests/test_phase8a_ia01_fix.py tests/test_phase8a_independent_acceptance.py`, với `TEST_REPORT_ROOT=PHASE8A_TESTS`. T/E/K dùng `P8_OPERATOR_MODE` tương ứng và `tools/run_phase6_fix.py LABEL_MOI script tools/smoke_phase8a.py --branch E --operator-check`, sau preflight cổng/PG; runner sinh schema và private credentials riêng. Browser theo [E2E README](../apps/web/e2e/README.md) và [manual/fixture runbook](PHASE8A_BROWSER_MANUAL.md). Không dùng lại label/runtime đã có.

Để kiểm NFR06 trên **schema fixture mới vừa tạo**, chạy read-only aggregate query `SELECT action,count(*),count(before_data),count(after_data) FROM <fixture_schema>.audit_events WHERE aggregate_type='recovery' GROUP BY action`, đối chiếu các transition thực và helper audit. Không sửa audit hoặc custody để dựng kết quả. Các helper review dưới `.cache` chỉ là công cụ phân tích cục bộ, không phải dependency production hoặc nguồn duy nhất để tái hiện workflow.

## 9. Gate còn lại và điểm dừng

| Gate | R2 status |
|---|---|
| IA01 current-boot/provenance | **FIXED/CLOSED technical scope** |
| Backend599 / affected Browser6 / T/E/K | **Evidence validated Passed**; không thực thi lại |
| Recovery A–F/ER01/02/17 races | **Verified slice + historical inheritance**, không gọi toàn MVP hoàn thành |
| R2-NFR06-01 | **OPEN Major**: thiếu before–after audit |
| NFR04 / full NFR07/CT14 / NFR08 | **Not Run/Partial + PENDING APPROVAL allocation**, không Passed |
| Git commit hoàn tất8A | **Not ready to declare completion**; curated manifest chỉ là đề xuất |

**Decision cuối: PARTIAL/BLOCKED.** Không phải IA01 còn lỗi, mà audit requirement gap và NFR gate allocation còn mở. Dừng sau báo cáo để người dùng phê duyệt các quyết định/công việc tiếp theo; không tự sửa production, không mở8B/8C.
