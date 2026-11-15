# Phase 8A — Independent Acceptance Round 3

## Checkpoint quyết định mới — 15/11/2026

**PHASE 8A — CONDITIONAL ACCEPTANCE APPROVED BY USER.** Người dùng đã phê duyệt allocation R2-D01/NFR04, R2-D02/NFR07/CT14 và R2-D04/NFR08 sang final MVP integration acceptance. Các tests/gates này vẫn **NOT RUN / OPEN, bắt buộc trước full MVP acceptance/release**, không PASSED/WAIVED. Owner TV1–TV5 là đề xuất theo R3; nhóm chưa xác nhận cá nhân nhận việc. IA01/NFR06 Recovery findings FIXED/CLOSED technical scope; evidence603 Backend,21 audit actions,8 real runners và Browser/frontend được kế thừa theo R3, không chạy mới. Không full MVP PASS, không hoàn tất refund/compensation hoặc tự mở8B/8C.

[Biên bản quyết định](PHASE8A_CONDITIONAL_ACCEPTANCE.md) · [Release gates/criteria/owners](MVP_RELEASE_GATES.md) · [Đề xuất staging, không git add](PHASE8A_GIT_READINESS.md).

Các kết luận/pending tại những checkpoint bên dưới là **lịch sử trước approval này**, giữ nguyên, không sửa R1/R2/R3 thành PASS hồi tố. Không đổi production/baseline hoặc xóa dữ liệu/evidence.

Ngày review: **15/11/2026, Asia/Bangkok**. HEAD `e4fb9f540195d4cbd10c97b03cd4dccc959c3a9d`, main, source Phase8A chưa commit. Phạm vi: tái review **P8A-IA01** và **R2-NFR06-01**, đối chiếu evidence và các quyết định NFR còn mở; không triển khai hoặc tự phê duyệt nghiệm thu thay người dùng.

## 1. Acceptance recommendation

**PARTIAL/BLOCKED đối với quyết định nghiệm thu Phase8A vô điều kiện.**

- **P8A-IA01: FIXED/CLOSED trong technical scope**, giữ kết luận R2 sau khi kiểm source và regression hiện hành.
- **R2-NFR06-01: FIXED/CLOSED trong technical scope Recovery8A**. Before/after đúng mutation được review; 21 action types có SQL-backed assertions; read-only PostgreSQL mới của R3 kiểm63 audit rows trên8 fixture. Không phát hiện Major/Blocker mới thuộc hai finding.
- Các technical gates của hai bản sửa có evidence hợp lệ. Không có source delta để biện minh chạy lại603 pytest, Browser hoặc physical workflows trong R3.
- **R2-D01/D02/D04 vẫn PENDING APPROVAL**, không có chấp thuận rõ ràng trong hội thoại cho việc phân bổ chúng sang final MVP/release. Vì vậy chưa cấp PASS hoặc một CONDITIONAL ACCEPTANCE có hiệu lực cho toàn8A. Đề xuất conditional acceptance chỉ có thể được người dùng xem xét sau khi chốt allocation, owner và release gates ở mục7; không coi đề xuất đó là approval đã có.

Không gộp Refund8B, Compensation8C, toàn UC10/TC12 hoặc CT14 end-to-end vào kết luận hoàn thành của Recovery slice8A. [R1](PHASE8A_INDEPENDENT_ACCEPTANCE.md) và [R2](PHASE8A_INDEPENDENT_ACCEPTANCE_R2.md) giữ nguyên lịch sử finding/fix; không đổi chúng thành PASS hồi tố.

## 2. Phương pháp và nguồn chuẩn

Review độc lập theo expected-from-contract: đọc source thực, liệt kê mutation/audit call sites bằng AST rồi kiểm transaction/guards thủ công; đọc trực tiếp XML, exit checkpoints, native reports, logs và tính lại SHA256; đối chiếu dữ liệu PostgreSQL bằng transaction **READ ONLY**. Không chỉ dùng bảng Passed của implementation report hoặc nhập audit helper để tự tính expected.

Đây là review trong cùng workspace/công cụ cộng tác, không phải chứng nhận của một tổ chức kiểm toán độc lập. R3 **không chạy pytest mới, không mở Browser mới, không mutation API, không tạo fixture hoặc migration**. Những số Passed dưới đây thuộc lượt verification trước R3, nay được xác minh lại.

Nguồn đã đối chiếu: AGENTS; CODEX_START_HERE; CODEX_HANDOFF; QD01–09 approved/config; baseline DOCX GĐ1/GĐ2, traceability.csv; OpenAPI gốc; database/INVARIANTS6–8 và handoff/ACCEPTANCE; P8-REC-0.1/0.2 cùng ER-01/02; implementation/status; IA01 và NFR06 fix reports. Không đổi ID FR/UC/BR/TC hoặc lấy số Phase hiện tại thay số nhóm handoff gốc.

Yêu cầu NFR gốc được đọc lại từ DOCX bằng XML, không chép kết luận của R2 làm nguồn yêu cầu. [Original requirement excerpts và hashes](PHASE8A_TESTS/independent_r3_20261115_01/requirements_original.json), GĐ1 paragraphs354/360/363/366. NFR06 yêu cầu mọi thao tác đổi trạng thái có actor/device, thời gian, ID giao dịch/lệnh, trước–sau; không password/raw QR token. Handoff và IMPLEMENTATION_PLAN đặt đo NFR/restore/audit ở bước tích hợp cuối; đây là cơ sở cho **đề xuất** allocation, chưa phải approval mới hoặc miễn trừ.

## 3. Source review

### P8A-IA01

`recovery.py::record` và `::confirmation` cùng lấy station/context locks; Technician PRE và Customer PRE đều vào `recovery_authorization.py::human`. Sau exact actor session FOR UPDATE, shared PRE guard đọc current enabled device/boot, kiểm source event accepted+processed SNAPSHOT, device/boot/context/serial và canonical payload hash. Sau provenance reads, `utcnow` mới, operation/session expiry và freshness được kiểm trước attestation INSERT/change_case/audit. Customer projection chỉ cung cấp binding, không thay thế mutation guard.

Refusal nằm trước writes; outer request transaction rollback và idempotency chỉ ghi response sau execute thành công. Retry lỗi không bị cache thành successful confirmation; correlation UUID riêng/request không phải business replay identity. Probe gốc còn nguyên ở [archive](PHASE8A_TESTS/ia01_fix_20261114_01/original_probe.py). R3 tính lại diff với probe hiện tại: **đúng diff đã chấp thuận tại R2**, chỉ bỏ correlation_id khỏi so envelope và thêm assertions version/attestations không đổi; business assertions không bị skip/xfail hoặc nới. [Inheritance/probe validation](PHASE8A_TESTS/independent_r3_20261115_01/inheritance_validation.json).

POST dispatch sang `human_post` trước current PRE guard; successor dùng `recovery_reconciliation.current`, không biến receipt effect gốc thành current observation. Legacy0.1 vẫn ở nhánh riêng. No-refund/no-duplicate-command, ACK15s/physical60s/freshness15s và P7-A01 không thay đổi. Current T runner xác nhận reboot thật,0 effect/confirmation audit; E/K kiểm positive staged/successor paths trên source audit cuối.

### NFR06 helper và transaction boundary

| Điểm review | Kết luận source/evidence |
|---|---|
| Capture BEFORE | Mỗi call site truyền keyword `before` bắt buộc. Snapshot đọc actual SQL rows trong context station/resource locks, trước mutation tương ứng; không dựng từ response sau mutation hoặc dùng cache Session.info |
| Capture AFTER | `recovery.audit` đọc lại cùng session sau writes rồi INSERT audit; `jsonable_encoder` tách giá trị khỏi row mappings. Case flags/state/version, operation lifecycle và child metadata/references có before/after thực |
| Lock/serialization | Idempotency advisory → station advisory/row → sorted participant users → swap/compartments/pins → exact session(s), theo đường hiện có. Worker và Payment dùng cùng station mutex; snapshot chỉ SELECT, không thêm FOR UPDATE/network call/commit hoặc lock-order edge mới |
| Linearization | Existing domain decision sau revalidation dưới locks, atomic commit của mutation+audit+idempotency. Không dựa dependency auth ban đầu; IA01 guard vẫn sau session wait. Không cam kết wall-clock của WAL commit là deadline policy mới |
| Creation | `RECOVERY_CASE_CREATED` chỉ khi INSERT ON CONFLICT RETURNING thực sự tạo row; `before_data.recovery_snapshot=null`, after chứa DB defaults thực. Child mới vắng trong before-map, có trong after-map; không fake before-object |
| Supersede/consume/closure | Cancelled/consumed timestamps và case version phản ánh writes thật. K ghi predecessor+successor consumption cùng transaction; J có intent/receipt/cancellation, không release holds |
| Audit failure | Request dependency rollback toàn transaction; workers dùng transaction/savepoint hiện có. Test mới gây lỗi **sau actual audit INSERT**, kiểm proof/version/audit/idempotency không commit rồi retry/replay đúng một lần |
| Replay | `idempotent()` trả durable response trước execute khi cùng key/body; mismatch409. Device inspection inbox giữ accepted/rejected receipt identity; duplicate không gọi business audit lại. Rejected transport có thể có inbox row nhưng không có accepted proof/success audit |
| Append-only | Migration0002 reject UPDATE/DELETE audit, runtime grant chỉ SELECT/INSERT audit. Helper mới chỉ INSERT; không có backfill hoặc thay policy lịch sử |
| Redaction | Snapshot allowlist cột, không wholesale row/context/payload; recursive safe loại password/token/key/header/raw payload/note. Proof statements nằm trong immutable attestations có ID/hash/source/stage để truy vết; không copy raw proof. `auth_session_id` lưu ở closure là UUID reference, không bearer token/hash đăng nhập |
| Scope resume | `close_resumed` capture trước/sau **Recovery case closure**, sau Phase7 automatic custody writes trong cùng transaction. Không gọi snapshot đó là trước physical pickup; Phase7 swap/custody audit là sự kiện riêng |

`change_case` là primitive tăng version, không tự emit audit. R3 tìm toàn bộ callers và hai case-creation entrypoints ngoài Recovery (`swaps.review`, `payments.review`); không thấy mutation nghiệp vụ8A bắt buộc bị bỏ khỏi inventory hiện tại. Technical inbox/idempotency insertion là append-only receipt vận chuyển, không phải thêm một business state transition hoặc bằng chứng giao pin. [Source inventory có file/function/line/write/audit/capture](PHASE8A_TESTS/independent_r3_20261115_01/source_review.json).

### Audit coverage matrix

Mỗi hàng **Passed trong targeted86/full603** với SQL value assertions; cột cuối chỉ fixture mà R3 thực sự SELECT được. “Targeted/full” không bị gọi là committed real-process audit nếu fixture native không exercise action đó.

| Action | Mutation được kiểm | Persisted fixture R3 |
|---|---|---|
| RECOVERY_CASE_CREATED | Không có before-object → case OPEN/v1 thực | A/B/CD/E/F/J/K/T |
| RECOVERY_EVIDENCE_RECORDED | Evidence ref/assigned/state/version trước → sau,+1 | Targeted/full |
| RECOVERY_OPERATION_CREATED | Child vắng → operation/context/ref hiện hành,case+1 | A/B/CD/E/F/J/K/T |
| RECOVERY_OPERATION_ATTACHED | Current op ref/case version trước → sau,+1 | Targeted/full |
| RECOVERY_OPERATION_SUPERSEDED | cancelled_at null → timestamp; case version không đổi | F |
| RECOVERY_ATTESTATION_RECORDED | Source vắng → proof metadata,case state/version+1 | A/B/CD/F |
| RECOVERY_INSPECTION_RECORDED | SIMULATOR PRE metadata mới,case version giữ | E/J/K/T |
| RECOVERY_PRE_ACTION_CONFIRMED | Human PRE CONFIRM/REJECT ref mới,case+1 | E/J/K |
| RECOVERY_AUTHORIZATION_INTENT_CREATED | Intent absent → binding/expiry/hash,case+1 | E/J/K |
| RECOVERY_AUTHORIZATION_ACKNOWLEDGED | ACK absent → durable ACK metadata,case version giữ | E/J/K |
| RECOVERY_ACTION_ACTIVATED | Activation absent → intent/ACK/hash refs,case+1 | E/K |
| RECOVERY_POST_ACTION_RECEIPT_STORED | POST metadata absent → actual receipt refs,case version giữ | E/K |
| RECOVERY_POST_ACTION_CONFIRMED | Hai human POST độc lập,case+1 từng nguồn | E |
| FOREIGN_OBJECT_RETURN_SETTLED | Operation(s) chưa consumed → consumed,case+1; không custody/hold/payment mutation | E/K |
| RECOVERY_REINSPECTION_REQUESTED | Successor read-only absent → current successor,case+1 | K |
| RECOVERY_REINSPECTION_RECORDED | Current successor receipt mới,case version giữ | K |
| RECOVERY_REINSPECTION_ATTESTED | Human successor source mới,case+1 | K |
| RECOVERY_NO_EFFECT_CLOSURE_REQUESTED | Closure intent absent → intent mới,case+1 | J |
| RECOVERY_NO_EFFECT_CLOSED | Receipt mới,cancelled timestamp,case+1; protected facts giữ | J |
| MANUAL_RECOVERY_SETTLED | Case/op/custody/terminal holds đúng nhánh,+1 | A/B/CD |
| RECOVERY_RESUMED_COMPLETED | Case chưa RESOLVED → RESOLVED/old settled/new YES,+1 | Targeted/full |

Coverage label21/21 không tự chứng minh mọi interleaving. R3 đã đọc observer: raw SQL equality lúc capture, detached-before digest, version delta, child absence/addition, consumption/cancellation và protected facts, không chỉ assert before_data!=NULL. Ba action không có committed native fixture ở bảng vẫn có transaction-backed tests trong suite; không ghi giả18 thành21 persisted action types. Observer là test wrapper có thêm SELECT/khả năng ảnh hưởng timing; các native process/Browser không import nó và cung cấp evidence bổ sung.

## 4. Evidence validation thực tế

[Artifact/JUnit/collection/hash validation R3](PHASE8A_TESTS/independent_r3_20261115_01/evidence_validation.json) không nhập kết quả boolean từ fix verifier làm expected; đọc lại testcase nodes, exit file, full log và hash source hiện tại.

| Evidence verification trước R3 | R3 kiểm trực tiếp | Kết luận/giới hạn |
|---|---|---|
| Full `nfr06_full_20261115_01` |603 XML testcase,0 failure/error/skipped; full_exit0; log603 passed/4 warnings;16:46:41–17:41:46 +07,pytest3296.43s | **Passed hợp lệ**; không chạy mới ở R3 |
| Collection | Multiset nodes XML=collection603;599 cũ không mất; đúng4 mới trong test_phase8a_audit | **Passed**, không cộng86 hoặc E2E vào603 |
| Source freeze | Tính SHA256 hiện tại179 files; khớp từng entry trước/sau full,delta0 | **Passed**; không khẳng định hai file JSON manifest có byte hash giống nhau khi serialization khác |
| Targeted | XML86,0 failed/errors/skipped; runner exit0 | **Passed** trên source cuối;9/14 smoke trước đó không cộng vào86 |
| Coverage | AST action strings/source review khớp21 labels coverage; counts>0; no missing; full coverage exit0 | **Passed21 action types**, không phải mọi state combination |
| Real-process A/B/CD/E/F/J/K/T | Tám native JSON reports và8 exit0; runtime log có hai OS PID riêng từng fixture (A/B8030/8031, các nhánh khác8070/8071) | **8 runners Passed**, không đổi cách đếm thành102 checks mới; [PID/log evidence](PHASE8A_TESTS/independent_r3_20261115_01/inheritance_validation.json) |
| SQL audit trước R3 | Original SELECT validation8 fixtures/63 rows/exit0 được đọc và hash | **Passed**; R3 còn thực hiện SELECT độc lập bên dưới |
| Browser affected source audit | Ba XML/JSON Chromium,runner exit0 và parent.browser_exit0: post,successor,closure | **3 Passed**; không có exit.txt ở runner mới, dùng durable child status thật |
| IA01 affected Browser | Sáu XML và parent browser_exit0: post/successor/old_boot/pre_reject/revoked/stale_expired | **6 Passed kế thừa**; frontend/guards không đổi bởi audit snapshot |
| Canonical Browser | Đọc lại15 XML/exit.txt terminal_fix matrix,0failure/error/skipped | **15 Passed lịch sử**, không gọi15+6+3 là24 scenarios mới/khác nhau |
| Frontend/build | Log39 pass/0 fail; test_exit/build_exit0; tsc --noEmit+Vite log | **39 Passed/build đạt**; không dùng build thay Browser |
| E2E102/races17/tooling25 | Source/summary/traceability của R2 và evidence lịch sử liên quan, current8 runners/full/affected Browser bù audit delta | **Kế thừa đúng scope**, không tuyên bố R3 rerun102/17/25 |

Bốn full warnings là Starlette/httpx deprecation, OpenAPI validate_spec deprecation và hai record_property/xunit2 warnings. Không phải skipped test. Full NFR06 source603 là gate kế nhiệm599, không dùng source cũ thay source mới. Các interrupted full/browser/environment runs và original failing probes còn nguyên; không suy Passed từ dots.

### SELECT độc lập trong R3

R3 dùng strict fixture-schema allowlist, `SET TRANSACTION READ ONLY` được xác nhận `on`, SELECT rồi rollback; không row-lock/write. Không dùng `tools/phase8a_audit_verify.py` hoặc helper production để tính expected. [SQL review mới](PHASE8A_TESTS/independent_r3_20261115_01/sql_readonly_review.json):

- **8 fixture,63 committed audit rows,18 distinct action types**: case identity/version/state trước–sau đúng delta; child creation absence, immutable refs, consumption/cancellation; actor/type/time/swap correlation có; latest case snapshot khớp case hiện tại; không forbidden secret fields.
- E casev9 và K casev10 giữ old_pin_settled=false,session review,Payment SUCCEEDED,3 holds/custody ban đầu; native effect1/success settlement audit1. K consume2 operation records trong một settlement event, không effect thứ hai. J effect0/closure audit1,không release holds. T proof refusals không tăng casev2 hoặc human confirmation audit,effect0. CD chỉ chuyển custody/giải phóng0holds sau completion hợp lệ; không áp “mọi nhánh luôn3holds” sai nghiệp vụ.
- Query aggregate **fixture R2 gốc** vẫn11 audit rows,0 before_data,11 after_data. Lịch sử thiếu before-state không được bịa/backfill. Closure finding là sửa prospective mutations trong scope8A, không phải sửa hồi tố tất cả lịch sử.
- Facts custody/payment/holds/effects lấy thêm từ native runner assertions và read-only validation trước R3; SQL R3 tập trung audit, không giả gọi riêng SELECT audit là phép kiểm physical model mới. Demo fingerprint8 bảng chỉ scope của runner, không chứng nhận toànDB.

Một lần parser review đầu đoán nhầm runner mới có exit.txt nên dừng read-only verification; đã đối chiếu source/report để đọc đúng browser_exit, không sửa artifact/assertion nghiệp vụ hoặc chạy lại Browser. [Method notes](PHASE8A_TESTS/independent_r3_20261115_01/review_method_notes.json). Không tính thao tác parser/SELECT vào pytest Passed.

## 5. Requirement → Source → Test → Evidence → Status

| Requirement | Source thực tế | Tests | Evidence / status R3 |
|---|---|---|---|
| FR12/UC10/TC12 Recovery slice | api/recovery; recovery/context/projection/settlement | phase8a_api/evidence/settlement/customer_projection | Full603,current A–F/Browser; **Verified slice**, không hoàn tất phần tài chính ngoài8A |
| NFR06 / R2-NFR06-01 | recovery.audit + recovery_audit.snapshot và21 call-site actions | phase8a_audit,SQL observer,rollback/replay/concurrent workflows | Coverage21,SQL63/8,full603; **FIXED/CLOSED phạm vi8A** |
| BR05/QD04/CT05 | foreign purpose guards,actual serial/recipient,staged settlement | command_reconciliation/staged_settlement/post_confirmations | E/K; **Passed**, không nhập vật lạ thành pin mạng/old obligation |
| BR09/CT08/Invariant6 | quiet,fencing,reconciliation,no-effect closure | staged_fence/closure_fence/expired_recovery/service | C/F/J/K; **Passed**, UNKNOWN không suy no-effect/delivery/refund |
| BR11/P7-A01/CT04/06/09 | shared human PRE,current_snapshot,worker station mutex,swaps physical deadline | independent_acceptance/ia01_fix/phase7_deadline | T + full603 + inherited old-boot Browser; **IA01 remains FIXED**, không đổi15/60/15 |
| BR12 | immutable proof/context/audit triggers,restricted grants,idempotency | migration/stage_storage/audit rollback/tests Phase1 | Full603 + source grants; **Passed slice**, không sửa/xóa lịch sử |
| P8-REC-0.1/CT07 | legacy3-source settlement,sorted session locks,manual custody guards | api/evidence/settlement/audit/command_reconciliation | A/B/CD,F + full603; **Passed slice**. Hoàn phí vẫn8B |
| P8-REC-0.2/CT10/11 | human PRE/POST,inspection,intent/ACK,activation,receipt,settle | authorization/handover/post_confirmations/staged_settlement | E,new Browser post,full603; **Passed workflow E**, không generic unlock |
| ER-01 | recovery_reconciliation/current successor chain | expired_recovery,post/chain regressions | K,current successor Browser; **Passed**, read-only successor không action mới |
| ER-02 | recovery_closure,simulator durable deny/NEVER_PREPARED | closure_fence/staged_fence/expired_recovery | J,current closure Browser; **Passed**, revocation không tự chứng minh past no-effect |
| Invariant7 | 8A lưu new_pin_delivered theo proof,giữ UNKNOWN/holds | settlement UNKNOWN/refusal paths | **Prerequisite slice verified**; refund workflow8B chưa nghiệm thu |
| Invariant8 | old obligation/foreign settlement tách biệt;không CLOSED_COMPENSATED thiếu refund | staged settlement/old possession/resume tests | **Recovery portion verified**; Compensation8C chưa triển khai/nghiệm thu |
| CT14/NFR07 restore | Coordinated DB+device/service/payment durable ledgers | Chưa có restore drill đủ scope | **Not Run**, restart evidence không thay restore |

Nguồn trace ID: `doi-pin-giai-doan-2/contracts/traceability.csv`, database/INVARIANTS.md và handoff/ACCEPTANCE.md; không tự đánh số TC cho probes bổ sung.

## 6. Finding closure register

| Finding | Evidence đủ để đóng | Quyết định review kỹ thuật |
|---|---|---|
| P8A-IA01 Major | Shared post-session-wait PRE boot/provenance guard; final-time recheck; original business assertions giữ;full603 có probe,real T/E/K + Browser inheritance | **FIXED/CLOSED**, giữ R1 fail/R2 closure. Không ảnh hưởng POST/successor/legacy hoặc custody/payment |
| R2-NFR06-01 Major | Actual snapshots21 actions; creation semantics; live SQL63; rollback/replay/concurrency;full603 source179 | **FIXED/CLOSED trong scope Recovery8A**, giữ R2 historical11 incomplete audits. Không đóng NFR06 toàn module MVP ngoài scope |

Không có finding Major/Blocker mới trong phạm vi review này. Việc đóng finding kỹ thuật không tự cấp acceptance cho release hoặc phê duyệt D01/D02/D04.

## 7. NFR decision register và release gates

Owner dưới đây là **đề xuất theo vai trò nhóm trong handoff**, chưa gán tên người hoặc nhận thay việc người dùng xác nhận. Người dùng/TV1 cần chốt người chịu trách nhiệm và thời điểm; chưa có approval thì không gọi owner assignment hoàn tất. Đổi nơi đo không thay tiêu chí gốc và không miễn NFR.

| Decision/NFR | Trạng thái hiện tại | Owner đề xuất | Test criteria / release gate bắt buộc |
|---|---|---|---|
| R2-D01 / NFR04 | **PENDING APPROVAL** allocation; benchmark **Not Run** | TV5 accountable QA;TV3 hỗ trợ workload/API,TV1 duyệt evidence | Máy demo2trạm×6ngăn,20 authenticated sessions,1000 measured read requests **sau warm-up**,p95≤2s. Ghi hardware/dataset/endpoint mix/warm-up/error rate/percentiles và raw samples đã redaction. Không cherry-pick endpoint hoặc dùng functional tests thay load. **Chặn nghiệm thu/phát hành toàn MVP** nếu thiếu report đạt; nếu người dùng chọn gate ngay8A thì phải đo trước chốt8A |
| R2-D02 / NFR07,CT14 | Restart/reconcile8A **Passed slice**; coordinated restore **Not Run**, allocation **PENDING APPROVAL** | TV5 coordinator/QA;TV3 DB+Backend;TV4 payment ledger;TV5 device/service ledger;TV1 sign-off | Chốt consistent/quiescent backup boundary cho PostgreSQL + mọi durable ledger đang dùng (device/service/payment;refund chỉ khi đã triển khai),kèm versions/hashes/record counts. Restore sang runtime riêng,so audit/idempotency/custody/holds/in-flight state,đối soát trước tiếp tục;không repeat charge/command/service effect. **Release gate phải có drill Passed**, không dùng restart đơn lẻ thay restore |
| R2-D03 / NFR06 | **APPROVED FOR FIX** theo prompt giao sửa;finding8A nay CLOSED. Approval này không bao gồm tự miễn full monitoring | TV3/TV5 audit owner đề xuất;TV1 duyệt release checklist | Gate audit8A đã đạt. Trước toàn MVP phải có mutation→audit coverage các module còn lại,append-only/correlation/redaction/monitoring/runbook phù hợp yêu cầu. Không dùng21 Recovery labels hoặc63 fixture rows chứng nhận toàn hệ thống |
| R2-D04 / NFR08 | Browser/UI slice **Passed trong flows đã kiểm**,3-person trial **Not Run**;allocation **PENDING APPROVAL** | TV1 accountable bàn giao;TV2/TV3 UI;TV5 ghi kết quả;3 người thử thật | Ba người thực hiện đúng kịch bản MVP đã chốt,không sửa DB tay;UI rõ bước/phí/timeout/trợ giúp. Lưu role/scenario/result/errors/help/timeout,không credentials. Không đặt thêm score/time threshold ngoài approval. **Chặn nghiệm thu toàn MVP** nếu chưa đủ3 người/kịch bản đạt; nếu chọn gate ngay8A thì trial là prerequisite |

**Quyết định cần bàn giao cho người dùng:** Với từng D01/D02/D04, chọn (a) hoàn tất trước khi chốt8A, hoặc (b) phê duyệt phân bổ sang final MVP integration với owner cụ thể và release gates nêu trên. Handoff hỗ trợ phương án(b), nhưng R3 không tự chọn. Không tự dời sang Phase10 hoặc đánh dấu approval từ sự im lặng/yêu cầu review. Khi quyết định và owners chưa chốt, recommendation hiện hành vẫn PARTIAL/BLOCKED. Nếu người dùng phê duyệt(b), có thể cân nhắc CONDITIONAL ACCEPTANCE **riêng8A**, ghi rõ điều kiện còn mở và không release MVP trước các gate.

## 8. Open risks và giới hạn

- NFR04,full CT14 và3-user NFR08 chưa có evidence đủ; không Not Run→Passed. Technical recovery restart được kiểm không thay coordinated backup/restore.
- Before-state audit lịch sử không đầy đủ và được giữ nguyên theo append-only/no-backfill. Chỉ các mutations sau bản sửa có representation mới; không sửa số liệu lịch sử cho đẹp.
- Snapshot chứa lịch sử nhiều operations/attestations của case; chi phí đọc/lưu tăng theo lịch sử. Chưa benchmark tải hoặc giới hạn retention/sizing trong review này; NFR04 phải đo source audit cuối. Không tự thêm chính sách purge.
-21 action types và các probes không là formal proof mọi interleaving. SQL observer có thể đổi timing; native E2E và prior17 final-decision races có scope riêng. Không khẳng định concurrency matrix đã rerun trong R3.
- NFR06 timestamps dùng semantics DB `now()`/transaction time hiện có; version/proof references xác định transition,không dựa thứ tự UUID cho nhiều audit cùng transaction. Decision-time freshness/deadline policy không đổi thành WAL-commit-time SLA.
- Mô phỏng không chứng minh an toàn tủ/pin thật. Fingerprint demo chỉ8 bảng theo runners. Không review toàn raw artifacts/credentials hoặc cấp chứng nhận security toàn repository.
- Git có nhiều untracked từ các lượt trước; evidence tồn tại local không đồng nghĩa đã bàn giao qua clone. Khi được giao commit cần curated source/test/runner/contracts/docs manifest,loại private.json/.local/runtime/trace/cache/dist,giữ evidence đã chọn và hướng dẫn tái hiện. Không git add -A.

## 9. Files, Git và điểm dừng

R3 chỉ tạo báo cáo này, artifacts review mới trong `docs/PHASE8A_TESTS/independent_r3_20261115_01/` và helper phân tích local ignored trong `.cache`. Không sửa production/test expectations/migrations/overlays/requirements hoặc R1/R2/IA01/NFR06 reports. Không chạy lại full suite/Browser hoặc thao tác vật lý. Các statements trên dựa review source/evidence và SELECT,không gọi chúng là test executions mới.

HEAD/index và179 hashes được đối chiếu trước/sau review; trạng thái file cuối và diff checks lưu trong [review close state](PHASE8A_TESTS/independent_r3_20261115_01/review_close_state.json). Không stage/commit/push,không xóa schema/ledger/credentials/logs/evidence. Không8B/8C. Build/cache tái tạo được chỉ xét dọn trong lượt được giao riêng,không xóa `.cache` tổng vì chứa runtime/evidence.

**Bàn giao:** Hai finding kỹ thuật đủ cơ sở đóng; người dùng quyết định allocation/owner/gates của D01/D02/D04 và chấp thuận nghiệm thu. R3 không ký thay người dùng. Dừng sau báo cáo này.
