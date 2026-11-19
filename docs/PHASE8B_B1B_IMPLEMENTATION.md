# Phase 8B — B1b implementation checkpoint

## Checkpoint 19/11/2026 — final verification in progress

B1b remains PARTIAL; this is implementation authority, not user acceptance. Historical 18/11 tables below remain unchanged as evidence of the earlier checkpoint.

- Final targeted label `b1b_target_final_20261119_01`: **92 Passed, exit0**, source-before/after equal; demo eight-table fingerprint unchanged (schema doi_pin, revision0002).
- Current real-process results with valid exits: `b1b_real_c_reject_20261119_02`, `b1b_real_c_expiry_20261119_02`, `b1b_real_e_inbox_20261119_01`, `b1b_real_d_precommit_20261119_02`, `b1b_real_d_decide_same_20261119_01`, `b1b_real_d_decide_other_20261119_01`, `b1b_real_d_freshness_20261119_01`, `b1b_real_a_final_20261119_01`: exit0. XML/log/exit/source manifests are retained under PHASE8B_TESTS, not added to Git.
- C-expiry used the original real 120s TTL. The simulator had retained a QUEUED local receipt although the worker had already processed its immutable source. Two new regressions first failed, then passed after a bounded source-disposition refresh outside the SQLite writer. No source event/timestamp was rewritten; rejected/unknown sources still fail closed. Initial failed C-expiry evidence is retained.
- The C-reject runner originally asserted one total receipt after inspecting two operations. Corrected the tooling oracle to exactly one immutable receipt per operation, two total for successor chains. Original failure retained; no business expectation was relaxed.
- Windows venv redirectors use different PIDs from the real interpreter. The test launcher now runs the real interpreter with the verified venv launcher context; actual OS PID equals the process controlled by the test. The earlier precommit-kill run has insufficient kill provenance. Corrected `D-precommit_20261119_02` explicitly asserts the actual Backend PID, observes rollback and retries on the other Backend. Corrected B-kill-before/after likewise passed; their initial PID-mismatch failure is retained.
- Native proof negative additions passed: semantic tampering with valid wire shapes, durable rejected receipt replay/body conflict, wrong Device-Key station, cross-Customer ownership, role isolation, stage/reference mismatch, append-only REJECT, human audit failure rollback. Existing GET ownership convention is404, without revealing another Customer's resource. Schema-validation errors precede inbox insertion and are not cached receipts.
- Local ledger additions verify actual service crash UNKNOWN across reboot and an object delivered then returned by the real model: a present slot cannot erase its disqualifying delivery history. `b1b_local_complete_history_20261119_01`:20 Passed.
- Read-only audit/static validator `tools/validate_phase8b_b1b.py` now exists. `b1b_checkpoint_a_20261118_01/audit_validation_20261119_01.json`: all8 frozen actions observed across current C-expiry/E-inbox fixtures, exact before/after/version/child references and protected facts/redaction checks passed. This is read-only SQL, not an audit backfill.16 frozen files and25 prior references match; implementation-status documentation is tracked separately from normative freeze.
- New Backend uncertainty regression originally reproduced an unsafe202 when an accepted UNKNOWN ACK followed a historical NACK. The new adapter now validates all accepted sources, rejects that uncertainty and revokes eligibility on accepted contradiction. The unchanged failing assertion passed in `b1b_history_conflict_20261118_02` (see label inventory for precise historical names). No command was rewritten into NOT_EXECUTED.
- Frontend evidence `b1b_frontend_20261119_01`:39 Recovery tests,1 reporter/tooling test and TypeScript/Vite build exit0. No UI source or dependency change. Affected real Browser0.1/0.2 verification and full Backend run still pending here.
- First collection checkpoint:796 nodes,90 B1b tests, no duplicate or skip/xfail marker; two later local regressions add2 nodes. Final collection/delta and full Backend source-freeze/exits are still required. Do not reuse historical543/603 totals as B1b full regression.

Pending before independent-review handoff: remaining final E2E/race orders, final collection/full suite, affected legacy Browser, final scope/bytes/security review and G1–G9 allocation. No stage/commit/push, provider Refund, cleanup, demo migration or B2–B5 work.

18/11/2026 (+07). **B1b PARTIAL — implementation/verification in progress.**

User implementation authority: attachment `7cf962b2-d3bf-4664-94a7-b0c35ee83e28`, approving the reviewed 36-path proposal and checkpoints A–E. This is not user acceptance of B1b. B0 remains frozen, B1a remains ACCEPTED BY USER. No stage/commit/push, cleanup, demo migration, provider Refund effect or B2–B5 work.

## Baseline and environment

- Branch main, HEAD `0024c5f2ddac4c1652e77dcff2acf48fd791b8e0`, index empty at implementation preflight. Original accepted/reviewer hashes were verified before intended B1b deltas; historical manifests are not rewritten to hide those deltas.
- Initial Docker pipe outage/recovery was an environment block. After user opened Docker, read-only checks returned Engine 29.9.2, container healthy, pg_isready accepting, runtime account doi_pin_runtime SELECT 1 = 1. No reset/restart/volume deletion was performed.
- Demo remains schema doi_pin, revision `0002_user_approval`. Migration 0010 is applied only to new test schemas. Runner fingerprints cover eight tables, not a whole-database proof.
- Baseline byte inventory: `PHASE8B_TESTS/b1b_checkpoint_a_20261118_01/baseline.json`. The pre-existing PHASE5_TEST_ENVIRONMENT.json bytes are protected by report routing. Git config, attributes, ignore rules and frozen normative sources are not changed.

## Implemented scope so far

| Checkpoint | Actual implementation | Verification state |
|---|---|---|
| A | Strict 17-definition 0.3 DTOs; additive API/OpenAPI unions; forward 0010 constraints, issuer fields, append-only revocations, narrow grants | Local/schema/OpenAPI and isolated PG migration tests passed; final full regression pending |
| B | Native SQLite journal/genesis, fetch inventory, immutable denials, station model-write fence, readonly receipt/outbox, reboot retention, source high-watermark | Local tests passed; legacy activated handover/closure regression passed before latest transport gate; real-process A initial run failed and is retained |
| Transport/human | Authenticated Device-Key ingress with durable rejected inbox outcomes; independent Backend inventory/hash/source checks; exact Technician/Customer statements; protected caller/session checks after waits; minimal owner projection | PG/API actual-model positive and old-boot/replay tests passed; broader races still pending |
| Certificate | Backend issuer with exact witness sessions, source/role/station checks, current boot, short immutable validity, case NO/version transition; accepted projection contradiction revocation | Positive, REJECT, revoked sibling-session and audit rollback tests passed; full concurrency/expiry matrix pending |
| First intent | Protected Admin authorization before cached replay; atomic REQUESTED, attempt0, redemption, COMPENSATING, inert REFUND outbox and two audit actions | PG targeted positive/rollback/replay and new-boot revocation passed; no provider dispatch |
| E | Reproducible isolated runner with real Backend/worker/Simulator/charge processes | Initial A failed; subsequent transport-gate verification running. B–E/two-OS races/full final Backend suite NOT RUN |

No old obligation is settled by NO. Charge, custody and three holds remain independently protected. No automatic fence release is added. Legacy physical/ACK/freshness deadlines stay unchanged. Existing positive reconcile, provider Refund, callback/retry and UI remain outside this increment.

## Source and lock design

- New production: `api/no_delivery_schemas.py`, `application/no_delivery.py`, `domain/no_delivery.py`, migration `0010_no_delivery_eligibility.py`, `simulators/device/no_delivery.py`.
- Recovery routes dispatch only explicit strict 0.3 branches. Old 0.1/0.2 unions and authorization remain; a legacy input cannot mutate a 0.3 operation. GET swap provides only the frozen owner projection, not raw ledgers or Technician evidence.
- New user mutations use idempotency advisory → station mutex/FOR NO KEY UPDATE → sorted participant users → resources/Payment → children → sorted exact sessions. Current principal, role, station scope and expiry are read again after waits. No HTTP/Simulator waits occur while PostgreSQL locks are held.
- Immutable certificates have SELECT/INSERT only. They are protected by the station mutex and uniqueness/FKs, not an UPDATE-privileged row mark. Cached Admin success rechecks current Admin authority; it does not renew witness proof or grant provider dispatch.
- All model effects remain behind the SQLite writer/fence. A new ledger can record genesis; an existing uninstrumented ledger remains incomplete. UNKNOWN/PREPARED/missing provenance refuses certification, rather than becoming NOT_EXECUTED or NO.
- Audit snapshots include actual case/operation/proof/certificate/revocation/redemption facts. Full frozen eight-action before/after audit coverage still requires dedicated final validation.

## Test evidence — runs are separate and overlap

Every listed run has run.log, results.xml, exit.json and before/after source hashes unless explicitly noted. Do not sum overlapping groups as unique coverage.

| Label under PHASE8B_TESTS | Actual result | Meaning |
|---|---|---|
| b1b_a_local_20261118_01 | 48 Passed, exit0 | DTO/schema/OpenAPI, before PG readiness |
| b1b_a_pg_20261118_01 | 2 Passed / 8 Failed, exit1 | New storage fixture used nonexistent reason_code; log retained |
| b1b_a_pg_20261118_02 | 10 Passed, exit0 | Fixture column corrected; assertions unchanged |
| b1b_a_compat_20261118_01 | 92 Passed / 2 Failed, exit1 | Two refusal snapshots accidentally included a later setup LOGIN audit |
| b1b_a_api_20261118_02 | 3 Passed, exit0; 48 deselected by explicit API target | Login moved before before-snapshot; includes the two fixed cases and one overlapping API test |
| b1b_b_ledger_20261118_01 | 25 Passed / 8 Failed, exit1 | New journal formatter not bound early enough on retained DB restart |
| b1b_b_ledger_20261118_02 | 33 Passed, exit0 | Restart initialization fixed without changing original assertions |
| b1b_b_ledger_20261118_03 | 37 Passed, exit0 | Readonly receipts/current actual model/UNKNOWN/reboot local tests |
| b1b_b_staged_compat_20261118_01 | 11 Passed, exit0; 344.84s | PG/API actual activated 0.2 handover, crash/rollback and closure; real 60s waits |
| b1b_b_sequence_20261118_01 | 1 Failed, exit1 | New receipt seq1 followed actual source seq5 |
| b1b_b_sequence_20261118_02 | 38 Passed, exit0 | 0.3 allocator includes source/receipt high-watermark; old packets unchanged |
| b1b_transport_20261118_01–04 | Failed development runs retained | Missing lawful RESTORE/worker setup, then a real new context hash serialization defect |
| b1b_transport_20261118_05 | 2 Passed, exit0 | Actual model/API three-source transport + durable old-boot refusal |
| b1b_certificate_20261118_01 | 5 Passed, exit0 | Three-source transport, certificate issue/rollback/replay, REJECT, exact revoked witness session |
| b1b_intent_20261118_01 | 3 Passed / 2 Failed, exit1 | UPDATE-privileged certificate row mark caused runtime permission errors |
| b1b_intent_20261118_02 | 2 Passed, exit0 | Same two Admin cases passed after removing unnecessary row mark; grants unchanged |
| b1b_real_a_20261118_01 | exit1, NOT PASSED | Durable 409 QUIESCENCE_REQUIRED because trailing source snapshot was not yet processed |

Latest pending run: `b1b_transport_gate_20261118_01`. Its result must be recovered before another run; do not assume Passed.

Local SQLite/mock transport tests and same-OS TestClient/PG tests are not labeled real-process E2E. Historical 543/603/587 results are not final B1b regressions.

## Confirmed development defects and corrections

1. Storage fixture reason_code did not exist. Used actual resolution_note field for a storage-only OPEN/UNKNOWN case. No SQL positive physical/financial proof was introduced.
2. API refusal before-snapshot preceded setup login. Moved only login setup; refusal still must leave proof/version/success audit unchanged.
3. Retained SQLite triggers referenced nd_journal_hash before connection binding. Bind before any retained model write; restart does not reinsert existing slots.
4. 0.3 sequence initially used only legacy service count. New allocator includes actual current-boot sources/receipts; it never rewrites old timestamps or sequences.
5. New Context hash used +00:00 while typed wire serialization emitted Z. Construct stable wire timestamps before hashing; legacy hash formatter and actual clock remain unchanged.
6. Admin certificate SELECT FOR UPDATE conflicted with deliberately absent UPDATE grant. Removed this redundant row mark under station serialization, rather than granting UPDATE.
7. Real-process transport submitted immutable receipt after flushing a trailing unprocessed snapshot. Backend correctly refused; failed inbox outcome stays final. Simulator now waits for processed source dispositions and retains accepted/refused receipt disposition without recapturing evidence.
8. The first script runner compared the fixture schema as demo-after because generator close skipped environment restoration. `demo_original_recheck.json` independently verified original doi_pin unchanged/revision0002. Runner now pins the original fingerprint schema and restores local schema environment; historical exit.json is not overwritten.

## Gates still open

G0 approval is explicit. G1–G4 have partial implementation/evidence; do not mark the entire gates complete from the positive subset. G5 deterministic two-OS races/actual process crashes, G6 full eight-action audit validation, G7 complete real-process A–E, G8 final collection/full suite/static/freeze and G9 independent-review handoff remain OPEN/NOT RUN.

Required next evidence includes missing/contradictory history, actual pending service/cached tasks, real successor expiry/REJECT lineage, source/freshness lock waits, both revoke/authority commit orders, rollback and lost-response crashes, and final legacy/Backend regression.

## Preservation and Git

No commits or staged changes. Source edits are within the approved 36-path proposal; it is not a staging allowlist. The original proposal/approval history is preserved. Final tracked/untracked inventory and byte hashes must be refreshed at handoff.

Keep new regression source/runners and all historical failed evidence. Raw logs/XML may expose temporary fixture sessions through pytest assertion rewriting; treat them as private local artifacts, never stage them. Credentials stay in private.json/.env, runtime SQLite files/WAL and .cache are excluded. Generate public summaries separately; do not overwrite historical raw files. No cleanup is authorized, including rebuildable cache.


## User-approved WIP transfer checkpoint — 19/11/2026

B1b PARTIAL / NOT ACCEPTED. Final targeted97 Passed and six b1b_guard_* real-process runners exit0. Full01 deliberately Interrupted for terminal-metadata fence correction; Full02 has no final JUnit/exit and no runner found at transfer preflight: Interrupted/outcome UNKNOWN, cause unconfirmed. Browser3 legacy scenarios ran before final0.3-only fence correction; do not call them new final-source runs. User authorized a curated WIP branch/commit/push for PC transfer only; main checkpoint unchanged. See PHASE8B_B1B_TRANSFER_HANDOFF.md for exact resume gates and portable tooling delta.
