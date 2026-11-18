# Phase 8B — B1a Refund database, API, domain & audit foundation

## IA01 final remediation checkpoint17/11/2026 — ready for independent re-review

P8B-B1A-IA01 is implemented for the confirmed compartment/battery/alert stale-authority pattern. Original station/compartment probes now403 with unchanged assertions; new sibling pre-fix failures remain preserved. Protected route uses station NO KEY UPDATE, a rolled-back read-only resource wait, then sorted actor users/resources/exact session; current authority is held through write/audit/receipt commit and checked even on idempotency replay. No B0/protocol/financial/physical change. [Root cause, inventory, lock graph and evidence](PHASE8B_B1A_IA01_FIX.md).

**P8B-B1A-IA01 FIXED — B1a READY FOR INDEPENDENT RE-REVIEW**, not accepted. Targeted02 **42 Passed,exit0**; final targeted03 **37 Passed,exit0**, overlapping groups, not a sum. Final affected `b1a_ia01_affected_20261117_04`: **543 Passed,0 Failed/Errors/Skipped,exit0**,38:56; exact original543 IDs,191 hashes before/after/current unchanged, original failing probe unchanged,0 captured40P01, demo8-table fingerprint/revision0002 unchanged. Original two schemas also verified403/no success audit/receipt by read-only SQL. Static77checks/34definitions and diff check Passed. This is not a full Backend rerun or new Browser/OS-process E2E claim. [Final evidence/limits](PHASE8B_B1A_IA01_FIX.md#final-evidence--safety-decision).

Five production files changed against the prior completed543: assets application, identity idempotency callback and assets/batteries/device routes. No migration/grants/baseline/protocol/custody/Payment/holds/physical-effect change. Independent review/history below is retained, not retroactively rewritten as PASS. No stage/commit/push, demo migration or B1b–B5.

## Final remediation checkpoint17/11/2026 — current status

**P8B-B1A-01 FIXED — B1a READY FOR INDEPENDENT REVIEW**, không phải accepted hoặc Refund hoàn chỉnh. Shared station advisory/row writer serialization được giữ với **FOR NO KEY UPDATE** để FK KEY SHARE của AssignStations không tạo cycle; mọi user/resource/session/RBAC/final-time guards giữ nguyên. Production remediation chỉ thay assets.py, không migration/contracts/provider/custody changes.

Final replacement06: **543 Passed,0 Failed/Errors/Skipped,exit0**,38:26; đủ192 tests cũ,189 hashes before/after/current khớp,0 captured40P01, demo8-table fingerprint và revision0002 unchanged. Original failing probe Passed cùng bytes/assertions; both-ordering PG/Backend routes, revoke/expiry/freshness/audit/rollback/shared callers được kiểm. Static77checks/34definitions đạt. Run05 giữ Interrupted do power-off, không coi dots là kết quả và không cộng smaller overlapping runs. [Final fix report/evidence/limits](PHASE8B_B1A_DEADLOCK_FIX.md).

B1b–B5 chưa triển khai; missing certificate vẫn fail-closed trước business mutation, không positive Refund/provider effect/compensation/release. Không stage/commit/push hoặc xóa data/evidence. Phase8A conditional acceptance/NFR release gates không đổi. Các checkpoint OPEN/PENDING bên dưới là **lịch sử**, không thay kết luận hiện hành này.

## Remediation checkpoint17/11/2026

P8B-B1A-01 đã có minimal shared-helper fix; original probe sau sửa1Passed, targeted11Passed, settlement-race2Passed, role-revoke1Passed và static77checks đạt. **Chưa đóng finding**: broad543 run05 bị Windows power-off, không XML/exit cuối; PostgreSQL vừa hoàn tất startup recovery và **replacement run06 đang chạy**. Source189 hashes delta0; không sửa original assertions hoặc bỏ user/session/station guards. [Fix report và stop/resume checkpoints](PHASE8B_B1A_DEADLOCK_FIX.md). Các đoạn16/11 phía dưới là lịch sử trước remediation; chưa dùng chúng hoặc các targeted pass để tuyên bố B1a READY.

## Historical checkpoint16/11/2026

Checkpoint 16/11/2026. **B1a PARTIAL/BLOCKED — P8B-B1A-01 Major OPEN (lock ordering)**. Bộ foundation/affected regression 192 Passed nhưng probe lock graph bổ sung tái hiện PostgreSQL40P01. Không dùng192Passed để tuyên bố READY. Dừng nhánh phụ thuộc; không phải nghiệm thu TC16/CT13 hoặc Refund hoàn chỉnh.

## Scope và baseline

B1a triển khai theo [B0 freeze](PHASE8B_B0_CONTRACT_FREEZE.md), [approved D01/D02](PHASE8B_DECISIONS_APPROVED.md), P8-REF-0.1 và P8-REC-0.3. Giữ FR16/UC14/BR08/TC16/CT13 và database invariants 6–8. Không thay baseline/QD, Payment charge, custody, holds, physical effects, deadline hoặc Recovery 0.1/0.2. Phase8A vẫn CONDITIONAL ACCEPTANCE; NFR04/NFR07/CT14/NFR08 OPEN trước full MVP release.

Preflight read-only: Docker Engine 29.9.2, PostgreSQL container healthy, pg_isready accepting; actual demo schema `doi_pin` ở `0002_user_approval`, SELECT1 thành công, refunds có 11 cột gốc, runtime chưa có INSERT refund. Source trước B1a ở `0008_recovery_reconciliation`. Không suy demo ở head; không chạy migration demo. Không có pytest cũ được tìm thấy trước khi chạy. Sandbox ban đầu chặn Docker pipe/TCP; kiểm tra được phép ngoài sandbox thành công, không thay logic để vượt lỗi môi trường.

Static B0 trước sửa source: `implementation-contracts/P8-REF-0.1/validation_b1a_pre_20261116.json`, 77 checks, 34 definitions, exit của validator 0. Lệnh shell ghép có exit1 do CIM bị chặn sau validator; không gọi exit shell đó là exit validator. Kiểm tra CIM read-only tiếp theo ngoài sandbox không thấy runner cũ.

## Source và migration

| File | Implementation |
|---|---|
| `services/backend/alembic/versions/0009_refund_foundation.py` | Forward-only sau0008; reuse refunds/payment_events/outbox/audit, không backfill |
| `services/backend/app/api/refunds.py` | Strict ReasonAction và RefundView, ba public operations gốc |
| `services/backend/app/application/refunds.py` | Read/ownership, repository locks, Admin/session/version recheck, fail-closed certificate gate |
| `services/backend/app/domain/refunds.py` | Năm state gốc; ordinary transitions; UNKNOWN query-only, FAILED không retry tự động, SUCCEEDED không downgrade |
| `services/backend/app/application/refund_audit.py` | Actual DB snapshots, allowlist, typed UUID references, transaction-local INSERT; không tự lấy thêm lock |
| `services/backend/app/main.py` | Chỉ register refund router; runtime OpenAPI dùng đúng ba operations baseline |
| `tools/provision_database.py` | Grants tối thiểu cho tables mới; không thay credentials hoặc demo khi chạy tests |

Migration thêm **5 tables**: `refund_attempts`, `refund_retry_permissions`, `refund_permit_redemptions`, `refund_eligibility_certificates`, `refund_certificate_redemptions`. Một refund/payment và provider key/reference UNIQUE gốc giữ nguyên. Full amount chỉ bind verified SUCCEEDED original charge/VND; không thêm currency vào Refund. Immutable identity/money/requester/reason/creation, stable provider reference sau khi đã có; version phải tăng đúng1 khi UPDATE; retained history không DELETE. Ordinary DB transitions ngăn UNKNOWN→PENDING và SUCCEEDED downgrade.

Attempt generation UNIQUE(refund,generation), initial generation0 không permit; successor bắt buộc exact permission/refund/attempt/generation binding. Permission liên kết prior attempt qua composite FK, generation=prior+1; redemption UNIQUE permit/attempt, bound identity và within issued/expiry. Append-only attempts/permissions/redemptions. Đây là **storage references**, chưa xác thực authenticated provider receipt/no-effect proof hay consume permission để dispatch. B1a fail-closed cả FAILED→PENDING; B3 cần reviewed forward integration với permit consumer trước khi có retry thật, không nới guard bằng cờ boolean.

Certificate tables chỉ là relationships: operation/payment/proof FKs, immutable receipt/hash/time storage, same-payment certificate→refund redemption composite FKs. Guard cấm dùng Recovery0.1/0.2 làm certificate0.3. Runtime **SELECT only**, chưa INSERT issuer/redemption; Recovery0.3 operation/stage widening và issuance thuộc B1b. Không có certificate hợp lệ được tạo trong lượt này, không giả positive eligibility từ storage fixtures.

| Runtime object | Allowed | Forbidden |
|---|---|---|
| refunds | SELECT, INSERT; UPDATE(state,version,provider_reference,verified_at) | UPDATE identity/money/reason; DELETE |
| attempts/permissions/permit redemptions | SELECT, INSERT | UPDATE, DELETE |
| eligibility certificates/certificate redemptions | SELECT | INSERT/UPDATE/DELETE trong B1a |
| Recovery/audit cũ | Giữ grants/append-only | Không thay policy/history |

## Public API và boundary

| Method/path | Permission/version | B1a behavior |
|---|---|---|
| POST `/v1/payments/{payment_id}/refund` | Admin; Payment.expected_version; UUID Idempotency-Key | Unverified charge/state/version reject; thiếu certificate →422 REFUND_EVIDENCE_REQUIRED trước mọi business write |
| GET cùng path | Admin hoặc owning Customer; Technician403 | Strict Refunds gốc nếu có row; absent404; cross-customer403 trước lookup refund |
| POST `/v1/refunds/{refund_id}/reconcile` | Admin; Refund.expected_version; UUID Idempotency-Key | FAILED→409 REFUND_RETRY_NOT_AUTHORIZED; UNKNOWN query-only nhưng B3 chưa có nên fail-closed422, không tạo job/attempt; state terminal/conflict409 |

Không nhận client amount/currency/actor/desired state/custody. RefundView giữ đúng 11 fields baseline, không currency/raw ledger/Technician proof. B1a **chưa có positive request/reconcile**, không provider refund endpoints/effects/worker/callback support mới, không mở VERIFY_NO_DELIVERY API. Error không cache thành successful idempotency receipt. Vì refused mutation không có successful receipt, cùng key/body khác vẫn đi qua guard và bị từ chối; không bịa IDEMPOTENCY_CONFLICT của một success chưa xảy ra.

Lock order: existing HTTP idempotency advisory →station advisory/row →sorted participant users (caller/customer/Recovery creators) →station swaps/slots/pins →Payment →Refund nếu có →exact caller session. Không HTTP dưới lock. Current role/state/session principal/revoked/expiry và resource version đọc lại sau wait; logout commit trước decision bị401, không partial write. B1a không có witness certificate; B1b phải gather toàn bộ witness users/session IDs trước bước lock tương ứng, sorted UUID, revalidate current proof/boot/freshness/version sau waits; không lấy user lock mới sau session locks.

## Audit coverage — foundation, không gộp với runtime chưa triển khai

| Action/boundary | Coverage hiện tại |
|---|---|
| REFUND_REQUEST_CREATED | Storage-level actual creation snapshot; before null; after REQUESTED/full amount/payment/swap refs; idempotent replay không ghi thêm |
| REFUND_UNKNOWN | Storage-level REQUESTED→UNKNOWN, exact version1→2, charge_state SUCCEEDED không đổi |
| REFUND_RESULT_VERIFIED | Fault sau audit INSERT trước commit: rollback state+audit; không claim provider result verification |
| Audit INSERT failure | Real PostgreSQL NOT NULL error rollback mutation |
| Missing certificate / concurrent requests / revoked caller | Zero refund/attempt/redemption/outbox/success audit/idempotency writes |
| Other P8-REF frozen events | NOT RUN/not implemented: dispatch/permission consumer/provider result/reconciliation jobs thuộc B2/B3 |
| Existing21 Recovery actions | Source helper và semantics không đổi; affected audit/settlement/IA01 regressions chạy riêng trong nhóm cuối; không claim21 new Refund actions |

Allowlist loại free-text reason, provider payload, headers/password/token/raw QR. UUID IDs/provider_key là identity công khai trong contract, không phải Service-Key. Snapshot helper chỉ đọc actual DB dưới transaction do caller bảo vệ; không tự tạo before-object hay thêm lock edge. Audit/mutation/idempotency cùng transaction, không backfill audit lịch sử.

## Verification

Kết quả lịch sử trong lượt này (không cộng trùng):

- `b1a_targeted_20261116_01`: **41 Passed, exit0**, 96.02s; source và demo fingerprint8 bảng unchanged.
- `b1a_targeted_20261116_02`: **48 Passed,1 Failed,0 Errors/Skipped,exit1**,129.53s. Failure fixture migration copy enum `station_state` giữa hai schema khác type. Đã sửa chỉ copy UUID/text station fields, dùng default của target; giữ assertions/migration/business guards. Evidence fail được giữ.
- `b1a_static_20261116_02.json`: **77 static shape checks/34 definitions**, runtime và design-composed OpenAPI valid, B0 normative contracts và prior overlays không đổi. Design composition không bật runtime provider/0.3.
- `b1a_final_20261116_03`: **192 Passed,0 Failed/Errors/Skipped,exit0**,903.26s (15:03); wrapper14:19:35–14:34:41 UTC. **187 source hashes before/after khớp**, fingerprint8 bảng demo và revision0002 không đổi. Gồm48 tests B1a,3 compatibility tests,141 affected regressions; không cộng lại các run01/02 chồng lặp.
- `b1a_lock_graph_20261116_04`: **1 Failed,0 Errors/Skipped,exit1**,15.31s. Refund503 khi assignment đang giữ user; lưu source probe gốc riêng ở report04.
- `b1a_lock_graph_20261116_05`: **1 Failed,0 Errors/Skipped,exit1**,14.72s; chỉ thêm diagnostic SQLAlchemy handle_error trong test, assertions/production giữ nguyên. Xác nhận **SQLSTATE40P01 / deadlock detected**. Không cộng hai lượt này như hai ca độc lập; cùng probe với diagnostic đầy đủ hơn.

Latest foundation/affected report: [public summary](PHASE8B_TESTS/b1a_final_20261116_03/summary.public.json), [redacted JUnit](PHASE8B_TESTS/b1a_final_20261116_03/results.redacted.xml), [exit/source preservation](PHASE8B_TESTS/b1a_final_20261116_03/exit.json). Latest Major: [public summary](PHASE8B_TESTS/b1a_lock_graph_20261116_05/summary.public.json), [redacted failing JUnit](PHASE8B_TESTS/b1a_lock_graph_20261116_05/results.redacted.xml). Raw artifacts chỉ local, không stage. Historical603 chỉ baseline8A; không chạy full new Backend suite.

Runner `tools/run_phase8b.py` dùng schema mới từ conftest, private temp riêng, route report writes ra label riêng; lưu run.log/results.xml/exit.json/source before–after. Chỉ fingerprint read-only demo8 bảng + revision, không tuyên bố fingerprint toàn DB/volume/ledger. Real PG PID lock diagnostics chứng minh wait trước release; tests dùng threads/TestClient trong **một OS process**, không gọi là hai OS Backend. Không có provider effect B1a nên chưa cần two-OS financial E2E.

Test sources: `tests/test_phase8b_b1a.py`, `tests/test_phase8b_b1a_transactions.py`. Bổ sung direct clean-head và0008→0009 historical refund preservation, grants/constraints/FK/immutable/version, schema/RBAC/ownership, missing certificate/no partial writes, domain state guards, audit/redaction/replay/rollback, same/different-key concurrency và logout thắng trong station wait. Storage fixtures không tạo no-delivery/custody proof, không dùng để công bố positive API refund Passed.

Affected regression counts từ XML03: P6=62, P6 blocker fixes=25, worker recovery=5; Recovery audit=4, settlement0.1=16, staged settlement0.2=4, IA01=5; P7 deadline=20. Tổng141, không lấy các con số lịch sử thay lượt chạy này. Có3 deprecation warnings (httpx TestClient và validate_spec); không thay dependency để che warnings.

### P8B-B1A-01 — Major: Refund/AssignStations lock cycle

**OPEN; không sửa source production sau khi tìm thấy.** Root cause source: `application/refunds.py::lock_context` lấy station advisory + station row FOR UPDATE, rồi thêm **mọi historical recovery_operations.created_by** vào sorted user locks. `main.py::assign_stations` giữ target user FOR UPDATE trước DELETE/INSERT assignments. FK INSERT tới stations cần parent FOR KEY SHARE, xung đột station FOR UPDATE mà Refund đang giữ:

`Refund: station row → waits Technician user`;
`AssignStations: Technician user → waits station FK key-share`.

Probe `tests/test_phase8b_lock_graph_probe.py` tái hiện trên PostgreSQL thật, hai connections/PIDs: assignment holder25448, Refund waiter25465 trong run05. `pg_blocking_pids` quan sát waiter trước bước FK INSERT, sau đó engine hook test-only ghi40P01. Assignment SQLSTATE null (transaction này không bị chọn làm victim); Backend Refund trả503 DATABASE_UNAVAILABLE thay vì422 REFUND_EVIDENCE_REQUIRED. Không suy deadlock chỉ từ503/timing: SQLSTATE và primary message đã xác nhận ở05.

Probe dùng API Refund thật và **SQL lock/DELETE/INSERT sequence tương ứng AssignStations** trên connection thứ hai; không claim đã chạy hai OS Backend hoặc full HTTP AssignStations E2E. Historical consumed operation là storage-only participant để kiểm user lock, không accepted physical proof, không certificate/NO flag. Case giữ version1, new_pin_deliveredUNKNOWN, old_pin_settledfalse; protected snapshots (refunds/attempts/audit/outbox/idempotency/payment/custody/holds/commands) không đổi. Demo fingerprint8 bảng giữ nguyên trong cả04/05. JSON chi tiết nằm `b1a_lock_graph_20261116_05/reports/PHASE8B_TESTS/lock_graph_*.json` cùng JUnit/log/exit/source hashes; giữ cả failing source04.

Minimal repair proposal cần review riêng: loại lock participants lịch sử không tham gia quyết định B1a, **đồng thời** chuẩn hóa station/user/FK lock graph với AssignStations (ví dụ station-before-user được revalidated, hoặc reviewed station parent lock mode vẫn giữ đầy đủ advisory/row serialization). Không chỉ bỏ toàn bộ user/session guards, bắt40P01 rồi báo success hoặc retry mù. B1b có witness thật phải giữ đúng participant/session locks; cần probe cả hai ordering và role/assignment transitions để chứng minh không chuyển cycle sang nhánh khác. Không tự sửa shared station/Identity/Recovery locking trong lượt B1a sau finding.

Gate trước READY: sửa reviewed lock graph, original failing probe Passed cùng assertions, thêm full-HTTP/2OS nếu cần xác minh boundary route, rollback/audit/role/assignment regression, rồi chạy lại đúng affected scope trên source sửa. **BLOCKED** readiness B1a/B1b; không mở provider effects.

Hai historical contract tests có delta tương thích được giải thích rõ: `test_phase1.py` thêm **đúng hai public paths FR16 gốc** vào exact allowlist và giữ toàn bộ operation/security assertions; `test_phase8a_migration.py` kiểm actual single Alembic head thay hardcode0008, giữ grants/history/trigger assertions. Không skip/xfail hoặc đổi expected business outcome để hợp thức hóa lỗi.

## Handoff B1b và giới hạn

B1b mới được triển khai purpose/stage0.3, actual model+complete history+durable cached-command fencing, ba nguồn current proof, append-only revocation, certificate issuance/redemption và atomic Admin intent/outbox. Cần forward constraint/grant updates có review; certificate tables hiện chưa đủ semantics/provenance validation để làm issuer. Phải bảo vệ exact session/witness locks, role/assignment/boot/freshness và recheck final clock; NO flag hay certificate row không tự cho phép refund. Đồng thời giữ existing refund-present interlock của8A.

B2/B3 mới có provider authorized retry/ledger/authenticated permits, query/callback/worker/result application. TC16/CT13 end-to-end, positive refund request, provider crash/restart/double-effect và full new Backend suite **NOT RUN** trong B1a. Không8C, UI/Browser, full MVP acceptance hoặc Independent Acceptance.

## Git/data preservation

HEAD `de9b9288452f3c4e2b6703ed0ce641668ac8fc78`, main; không stage/commit/push. Original179-source freeze có expected delta4 paths: main.py, provision_database.py và hai compatibility tests kể trên; Refund source/migration/tests/tools mới được hash riêng. Runtime source before/after comparison của mỗi runner không delta. B0 freeze giữ nguyên để làm lịch sử, IMPLEMENTATION_STATUS là docs-only checkpoint delta được ghi riêng.

Giữ `docs/PHASE5_TEST_ENVIRONMENT.json` và mọi untracked evidence cũ. Không dọn schema/DB/volumes/.local/ledgers. Raw XML/log có thể chứa hostname/user-directory nên chỉ local; `tools/summarize_phase8b.py` tạo **bản sao redacted mới**, không ghi đè bằng chứng gốc. Credentials/.env/private/cache/ledger/raw runtime tuyệt đối ngoài Git. Test tooling/source/docs có thể đề xuất Git sau independent review nhưng lượt này không stage.

Cache `.cache/b1a-*`, Python bytecode có thể tái tạo khi được phép dọn ở lượt riêng; schema/ledger/raw evidence và source/migrations phải giữ. Không tự xóa trong lượt này.

Final Git checkpoint: **6 tracked modifications,1047 untracked files,0 staged**, main ở de9b928, không ahead origin/main. Tracked changes gồm IMPLEMENTATION_STATUS, environment artifact đã có từ trước, main router, provision tool và hai compatibility tests. New B1a source/tests/tools/docs **17 paths** cùng hashes và content-scan result được liệt kê trong [handoff inventory](PHASE8B_TESTS/b1a_handoff_20261116.json); scan không thấy blocking credential/private-key/binary/large-file/trailing-whitespace finding trong candidate set này. Đây không phải scan toàn bộ1047 local files hoặc permission stage. `git diff --check` exit0. Ngoài set runtime187 của run03, run05 chỉ bổ sung source probe lock graph; existing187 hashes không đổi. Static/redaction tooling và docs có hash riêng trong inventory.

### Chạy lại có kiểm soát

Dùng label mới chưa tồn tại; runner tự đọc private `.env` qua Settings, không in credentials. Chạy tuần tự, không chạy trên schema demo:

```powershell
.venv/Scripts/python.exe tools/run_phase8b.py LABEL_MOI tests/test_phase8b_b1a.py tests/test_phase8b_b1a_transactions.py
.venv/Scripts/python.exe tools/run_phase8b.py LABEL_LOCK_MOI tests/test_phase8b_lock_graph_probe.py
.venv/Scripts/python.exe tools/summarize_phase8b.py LABEL_LOCK_MOI
```

Probe lock graph hiện **expected assertion FAIL** trên source chưa sửa; không đổi assertion thành chấp nhận503/40P01. Regression192 command: cùng runner với hai file B1a, `test_phase1.py::test_phase1_contract_and_no_future_endpoints`, `test_phase8a_migration.py`, `test_phase6.py`, `test_phase6_blocker_fix.py`, `test_phase6_worker_recovery.py`, `test_phase8a_audit.py`, `test_phase8a_settlement.py`, `test_phase8a_staged_settlement.py`, `test_phase8a_ia01_fix.py`, `test_phase7_deadline.py`. Không dùng subset này làm full Backend suite.

**Kết luận: B1a PARTIAL/BLOCKED.** Foundation đã triển khai và có192Passed trong nhóm đã chạy, nhưng Major lock graph mới được xác nhận; chưa READY FOR INDEPENDENT REVIEW hoặc B1b. B1b eligibility/positive API, provider B2/B3, full TC16/CT13/Browser/full-new-suite vẫn NOT RUN theo giới hạn increment. Dừng sau finding/evidence/handoff, không sửa shared production locks hoặc tiếp tục increment khác.
