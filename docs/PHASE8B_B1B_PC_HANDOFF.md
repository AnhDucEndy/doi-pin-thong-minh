# Phase 8B B1b — portable laptop-to-PC handoff

27/11/2026 (+07). **WIP / NOT ACCEPTED. Business Adapter PARTIAL.**
This document transfers source and sanitized conclusions, not raw evidence or
permission to execute integration/business scenarios. No ZIP is required.

## Checkpoint and reading order

Parent: `297d0f39b5798db1860572866781c1bcbcb0fdc4`, WIP branch
`wip/phase8b-b1b-transfer-20261119`, GitHub `AnhDucEndy/doi-pin-thong-minh`.
The handoff commit is the commit introducing this file; obtain its full SHA
from the handoff result / `git log -1`, not a fabricated self-referential SHA.
Main accepted checkpoint remains `0024c5f2ddac4c1652e77dcff2acf48fd791b8e0`.

Read AGENTS.md; this document; PHASE8B_S1_EXECUTION_CONTRACT.md;
PHASE8B_B1B_TEST_PLAN.md and PREIMPLEMENTATION_REVIEW.md;
PHASE8B_B0_CONTRACT_FREEZE.md / DECISIONS_APPROVED.md; frozen P8-REF-0.1 and
P8-REC-0.3; then tools/g6_business/ and tests/test_g6_business_adapter.py.
Older IMPLEMENTATION_STATUS/TRANSFER_HANDOFF entries describe their own dates,
not completion of the later laptop gates summarized here.

## Acceptance register G0–G9

| Gate | Current allocation / evidence |
|---|---|
| G0 | B1b implementation scope approved historically; no B1b user acceptance |
| G1 | Migration0010/grants foundation implemented, historical tests; new laptop startup fixture provisioned/verified. Not fresh business-role integration acceptance |
| G2 | No-delivery proof/history/fence implemented, historical target/Guard support; broad final acceptance not implied |
| G3 | Certificate/binding/revocation implemented, historical tests/rows; current authority/provenance residuals remain |
| G4 | Admin REQUESTED/redemption/attempt0/inert outbox implemented, historical rollback/replay support; after-audit-write/all-action residuals remain |
| G5 | PARTIAL: T03/T04/X01–X04/X07 partial; X05/X06 dedicated concurrency missing |
| G6 | Infrastructure/readiness verified; audit acceptance PARTIAL despite39 rows/eight actions |
| G7 | PARTIAL: six historical Guards corroborated, lifecycle/request/transaction and variant gaps |
| G8 | Historical PC Backend805/805 PASS checkpoint; not new laptop execution or adapter integration acceptance |
| G9 | OPEN: no independent final review/user acceptance of B1b |

G1–G4 are implementation/historical-test statements, not newly approved gates.
Phase8A remains user-approved Conditional Acceptance; B0 frozen/B1a accepted.
Final-MVP NFR04/NFR07-CT14/NFR08 remain mandatory OPEN release gates.

## Historical regression and startup evidence

PC transfer `79d663022d74f1305462d3ce27414f7fcf171646` includes earlier Backend
checkpoint/tooling; PHASE8B_G6_LAPTOP_HANDOFF.md records historical805/805 and
IPC/Browser evidence. Its raw PC evidence stays on PC and must be validated
there if needed. Laptop did not rerun805. Old interrupted laptop runs remain
interrupted; they are not retroactively converted to PASS.

Readiness correction in parent297d0f3 catches ConnectTimeout along with
ConnectError, preserving20s overall deadline/1s request timeout/30s API bound.
Focused9 Passed; negative control pins original79d6630 in memory. Laptop
startup recovery ran once: supervisor14128/child12940 exit0/0, health200,
database connected, ~3.656s, intentional shutdown; all39 fixture table digests
unchanged. Initial failed startup and diagnostic artifacts retained separately.
Startup-only guard remains unchanged and cannot run business workflows.

## G6 audit and G5/G7 historical review

Laptop read-only SQL inventory retrieved39 persisted rows in six historical
Guard schemas: operation-created6, successor-linked1, inspection-accepted6,
human-attested11, certificate-issued5/revoked2/redeemed4, Refund-request-created4.
All39 implemented snapshot consistency assertions passed. G6-R01 action/aggregate
identity and R08 redaction are VERIFIED only in their stated retained-data scope.
G6-R02–R07/R09–R12 remain PARTIAL: decision-time authority, request/transaction
linkage, independent before-state/version/child history, immutable intent mapping,
invariants, runtime denial, atomic rollback/replay and crash/concurrency completeness.
Current final rows and audit snapshots are not independent historical pre-state.

Three tests linked to matching test-source/JUnit/exit0 in historical
b1b_terminal_fence_20261119_02: human audit failure rollback, certificate atomicity,
first-intent rollback/replay/no-dispatch. They inject before audit helper writes,
not after actual audit INSERT. No full G6-R11 promotion. Effective audit ACL/trigger
observed read-only; complete runtime mutation-denial behavior is still unresolved.

G5 review checked40 bundles:33 raw-completed,6 failed,1 summary-only;22 D bundles,
33 runs with distinct actual API log PIDs,19 with PG lock/blocker records. These
are inventory counts, not new tests. Some older reported PIDs are venv launcher
IDs; logs/barriers identify different actual server PIDs. Parent/start/exit/wait
journals and exact request/session identities are not uniformly available.

| Requirement | Coverage / limitation |
|---|---|
| B1b-T03 | PARTIAL: actual Backend audit-ready kill/rollback/retry support; numeric version/idem pre-state and explicit lifecycle missing |
| B1b-T04 | PARTIAL: postcommit OS-exit/lost-response/replay support; older original assertion-source/exit linkage incomplete |
| B1b-X01 | PARTIAL: both-order authority/revoke subsets; exact lifecycle/FK/session-specific proof incomplete |
| B1b-X02 | PARTIAL: role/state/logout evidence; same-principal multiple exact issuer/witness sessions not fully proved |
| B1b-X03 | PARTIAL: inbox/projection and intent-first evidence; exact processed-event/request transaction linkage incomplete |
| B1b-X04 | PARTIAL: human/certificate source winner barriers; not every competing Admin order |
| B1b-X05 | MISSING dedicated successor-vs-DECIDE/redemption/closure both-order concurrency |
| B1b-X06 | MISSING dedicated legacy0.1/0.2 settle/resume/authorization-vs-Admin both orders |
| B1b-X07 | PARTIAL: key/conflict/replay/count evidence; exact old request/process provenance limited |

Authoritative definitions: B1b test plan lines89–99 (T03/T04/X01–X07/A01/A02),
scenario table120–125, deterministic methods101–112, gate table near164.
Frozen REF README44/50/60 specifies locks/atomic intent/audit; REC0.3 README
three-source/decision/supersede sections govern current proof/fence semantics.

## Six Guard findings (not Browser flows)

| Guard run suffix | Corroborated evidence / remaining limit |
|---|---|
| a | Positive NO certificate/intent/replay/counts; lifecycle/request authority incomplete |
| b | UNKNOWN command/effects0/no receipt/active fence; no separate service PREPARED variant proof |
| c_expiry | Sequential real expiry/current successor, two retained receipts; not X05 race proof |
| d_precommit | Matching actual PID20280/PG barrier, rollback/retry; assertion named review-version tests only state |
| e_inbox | Inbox-only refusal then accepted reboot invalidation; exact accepted-event/transaction links incomplete |
| e_intent_first | PG wait/order, intent before accepted contradiction and durable replay; full session/lifecycle incomplete |

All six b1b_guard_*_20261119_01 exits0/assertions true. WAL-aware verified copies
corroborate one ACTIVE fence each, command effects0, six valid journal chains,
command denials and positive receipt/attestation identity links. No original SQLite
was opened during review. Three source/exit-linked tests support helper-entry
rollback, not exhaustive after-write faults. No confirmed business defect found.

Latest Guard source216/223 raw matches; seven deltas are Browser/tests/fixture/
operator/provisioner/runner/validator tooling, not a whole-source equivalence.
Older crash runs have additional Backend/simulator/smoke deltas and must be
assessed per run. Exact historical tools/validate_phase8b_b1b.py bytes remain
unresolved after bounded local search; do not repeat that search without a new
location, or reject independently supported raw facts solely for this gap.

## Minimum supplementary work (not executed)

- S1: X05 meaningful successor/DECIDE/redemption/closure orders; detailed contract
  in PHASE8B_S1_EXECUTION_CONTRACT.md. Real expiry/rejection preconditions matter:
  do not force expired old DECIDE and successor both to succeed.0.2 closure cannot
  successfully close0.3 fence. Existing intent must never be duplicated/undone.
- S2: X06 applicable legacy/Refund both-order races, distinct valid fixtures.
- S3: T03 numeric versions/audit/idem pre-state plus actual kill/wait; T04 actual
  postcommit lost response and exact replay if raw compatibility cannot close it.
- S4: only residual exact-session/authority/event/key ordering, not all22 D reruns.
- S5: real failure after original audit INSERT and targeted runtime audit denial,
  on fresh schemas; existing helper-entry tests need not be rerun merely for totals.

Capture source freeze, full versions/counts/IDs, request key/body hashes, actual
OS and PG PIDs, lock/blocker/barrier/commit ordering, receipt/boot/fence lineage,
action-specific audits/idem/children and real exit/wait. Keep Payment SUCCEEDED,
old obligation/custody/three holds, ACK15s/physical60s/freshness15s and original TTL.
No fake physical/proof/custody SQL. Refund remains REQUESTED/inert REFUND outbox;
provider refund dispatch, B2–B5 and8C are outside scope.

## Business Adapter foundation: tested source and blockers

tools/g6_business contains Config/catalog admission, ExactTransport and Supervisor
for owned harmless mock controls. tests/test_g6_business_adapter.py: final37/37
Passed, exit0,1.32s, no warnings. Earlier37-pass run with regex warning retained.
HTTP controls use MockTransport; catalog controls use synthetic facts. Actual
harmless OS child validates base-interpreter PID/parent/wait. These are not real
database/network/business-process integration passes.

**launch_business must still hard-deny with PendingIntegration.** inspect_live
is a refusing scaffold, not an authoritative grant collector. Do not give runtime
pg_control_system/admin access just to pass it. Required remaining integration:

1. Separate trusted read-only cluster identity collector and exact effective
   table/column/schema/role/SECURITY DEFINER grant checks; actual dedicated runtime
   credentials, separate provisioning authority, fresh owned schema marker.
2. Reviewed child bootstrap and native psycopg/libpq plus raw socket/DNS/IPv4/IPv6
   coverage; explicit owned endpoint/process tree. Python hooks are not an OS sandbox.
3. Scenario route registry expanded from actual frozen method/path/operation/UUID
   bindings; current syntax validation alone is not scenario authorization.
4. Real Backend/worker/simulator/mock PID/parent/start/server/exit/wait records,
   scoped crash ownership, abnormal-exit handling and transaction/barrier linkage.
5. Focused real safety integration: protected endpoints denied without sending
   traffic; cross-schema grants independently denied; no redirects/proxies/native
   bypass; Refund provider permanently forbidden. Keep startup guard unchanged.

S5 storage-only probes may use an owned-schema admission path rather than the full
HTTP process stack. No integration prompt has been executed. Next action is to
review/authorize minimal REAL adapter integration on PC, not to start S1 yet.

Final37 evidence SHA256 (raw source bytes, no EOL normalization):

```text
75f5412277c7046058207708df0414c7b27d9fcd97c10ae22cccdd6ca7bb2154  tools/g6_business/__init__.py
cf747caeea037f62691eddf83b25231d2076a46c39f0dca5a8031588ff95c2e3  tools/g6_business/adapter.py
4e806b2825358147055e66dca1f45a8ea515444d9e140c0e9534359dd8b29930  tools/g6_business/mock_probe.py
a5a9e0e01209d7250ec2e94efe139f7471cd5eb3f18e5a182250f82b16c41e3b  tests/test_g6_business_adapter.py
b1766e04668ea8419bd243a3a4139d1b4b8e517b73c3b8058532dbd7c6ec5cf3  docs/PHASE8B_S1_EXECUTION_CONTRACT.md
```

## Laptop-only raw evidence and environment

Ignored paths relative to laptop checkout (not uploaded):

- .local/g6-laptop/business_adapter_20261127_01/: final XML/log/exit/source hashes,
  permission/safety matrices, exact diff and report; .local/business_adapter_controls/
  contains actual mock process journals.
- .local/g6-laptop/g7_historical_20261127_01/: consolidated gaps, guard/process/ledger
  review, private WAL-aware copies and report; g5_historical_20261127_01/ contains
  T/X timelines; deep_audit_20261127_02/ contains39-row private review. Earlier
  incomplete deep_audit_01/ and all failed runs remain untouched.
- .local/g6-laptop/provision_20261127_01/, diagnosis_20261127_01/,
  recovery_verification_20261127_01/, startup_recovery_20261127_01/ and original
  failed startup_20261127_01/: readonly startup evidence and preservation manifests.
- docs/PHASE8B_TESTS/b1b_guard_*_20261119_01 plus other40 raw bundles and .cache/
  runtimes/SQLite ledgers remain local/ignored. .local/preservation/
  b1b_sync_20261127_ae4608ae97/ records78 copies/218 ledger hashes.

Raw SQL, tokens/passwords/.env/private files, ledgers, WAL/SHM, logs and screenshots
are NOT portable Git evidence. Laptop is needed for independent verification of
these raw artifacts later. This sanitized summary never replaces them.

Laptop protected cluster5432 identity7699937118555680806 and G6 cluster5449
identity7712738307604140070 are laptop facts, not PC configuration. Existing
smoke phase5_test_ecfa77274ae3 is protected. PC may retain older cluster5448;
do not reuse/mutate it by assumption. Current adapter deliberately pins laptop
identity and denies business ports5432/5448/5449 in its generic socket policy;
future native DB authority must be separately verified. Moving execution to PC
requires environment inventory and an approved target binding; never replace
identity strings or relax checks to manufacture readiness.

## PC synchronization prerequisites / stop point

On PC first locate repository, read AGENTS, inspect branch/HEAD/index/dirty,
untracked/ignored evidence and local commits; verify GitHub WIP live SHA. Preserve
raw PC evidence before updates and detect incoming-path collisions. Fetch/ff-only
only when separately authorized and safe; no reset/restore/clean/stash/force.
Do not change main, EOL policy or attributes. Supported exact-byte checkout mode
remains core.autocrlf=input; verify the five hashes above after checkout. If any
source, environment or ownership condition mismatches, stop before integration.
No need to rerun37 simply to transfer identical bytes.

Do not auto-start Docker, API, workflows or provision test data when opening this
checkpoint. Inventory actual PC resources/credentials without exposing secrets,
then approve the integration/test-only target scope. Raw laptop evidence is not
present merely because this file was pulled. No B1b/G5/G6/G7/G9 acceptance is implied.
