# Phase 8B — B1a independent acceptance review

17/11/2026, +07. **B1a INDEPENDENT REVIEW PARTIAL/BLOCKED.**

P8B-B1A-01 is independently confirmed **Fixed in the reviewed source/PG-session scope**. A different **Major P8B-B1A-IA01** was reproduced in a shared station-lock caller: a Technician mutation commits after its station assignment has been revoked and that revocation is already observable. No production fix was made in this review. Do not start B1b or mark B1a accepted by the user.

## 1. Scope, requirements and method

Expected behavior was derived from AGENTS, GD2 OpenAPI/invariants and frozen P8-REF-0.1/P8-REC-0.3/B0/D01/D02 before inspecting results: Admin-only request/reconcile, owning Customer read, strict ReasonAction, full verified DB charge, fixed refund identity, UNKNOWN query-only, FAILED no unpermitted retry, no SUCCEEDED downgrade, truthful atomic audit, and fail-closed without B1b eligibility. Existing Technician asset actions remain restricted to assigned stations; no generic unlock or physical/custody authority is added.

Read implementation/fix/design/test/decision/status documents, Refund application/domain/API/audit, migration0009/grants, Identity AssignStations/logout/role changes, station/resource/session locks, Recovery guards and all reported helper callers. Independently parsed source AST, runtime OpenAPI and actual test artifacts. Reran selected PG probes and migration tests on retained isolated schemas, then stopped acceptance expansion on the new Major. No543 rerun, provider effect, positive fake certificate, production edit, requirement change, credential/environment change, demo migration or cleanup.

Review evidence roots are unique:

- `PHASE8B_TESTS/b1a_independent_evidence_20261117_01/`: independent source/artifact/static verification.
- `PHASE8B_TESTS/b1a_independent_review_20261117_01/`: original deadlock/both ordering/migration/control + first novel probe (fixture precondition failures).
- `PHASE8B_TESTS/b1a_independent_review_20261117_02/`: corrected fixture precondition, actual new authorization failures.
- `PHASE8B_TESTS/b1a_independent_review_20261117_03/`: same failing assertions plus an Admin observation after revoke and before releasing the lock.

“Rerun” below means current reviewer execution. “Artifact verified” means prior execution whose XML/log/exit/hash/source was checked, not rerun. ASGI/TestClient with distinct native PostgreSQL sessions is not two OS FastAPI processes, Browser or provider E2E.

## 2. Verified source inventory

main/HEAD **de9b9288452f3c4e2b6703ed0ce641668ac8fc78**, no staged content. Current189 files in the completed543 source manifest match before/after and current contents. New review source is only `tests/test_phase8b_independent_review.py`; no production source changed in review.

| Source | Independent review result |
|---|---|
| `app/api/refunds.py` | Three original public operations, strict ReasonAction, no client money/actor/state, correct role dependencies |
| `app/application/refunds.py` | Station→sorted users/resources→Payment/Refund→exact caller session; current role/session/version recheck; unconditional missing-certificate refusal before business writes |
| `app/domain/refunds.py` | Five original states, ordinary allowed edges, terminal success, UNKNOWN query-only; positive permitted retry not implemented in B1a |
| `app/application/refund_audit.py` | DB-derived snapshot/allowlist, typed identity refs, creation-null, same caller transaction; no autonomous commit or new lock order edge |
| `alembic/versions/0009_refund_foundation.py` | Forward from0008; existing Refund reused, five relationship tables; no historical backfill/downgrade |
| `tools/provision_database.py` | New tables limited insert/select or certificate select-only; no new broad Refund identity UPDATE/DELETE |
| `app/application/assets.py:63` | Station mutex retained; station row NO KEY UPDATE, others FOR UPDATE retained |
| `app/main.py:185` / AssignStations | Target user FOR UPDATE before assignment replace/FK; user remains permission serialization point |
| `app/application/assets.py:313` / change_compartment | **Major: scope checked before waits, no actor user/session lock or revalidation before write** |
| Recovery/Payment/Device/Reservation callers | Source and selected historical regression checked; no inherited blanket authorization-safety conclusion for every caller |

Independent AST analysis found **26 call sites**, exactly matching the reported inventory; no additional literal `get_row(...,'stations',lock=True)` production caller was found. Full paths/lines/functions are in [independent inventory and artifact verification](PHASE8B_TESTS/b1a_independent_evidence_20261117_01/artifact_validation.public.json). This search was supplemented by route/schema analysis, not treated as a proof against all future dynamic SQL.

Runtime station paths: GET/POST `/v1/stations`, GET/PATCH `/v1/stations/{station_id}`; no DELETE. StationUpdate accepts only expected_version/name/address/state, not id/code. Therefore the writer-row compatibility argument is valid for the current non-key API; it is not approval of future station key-changing/deletion APIs or arbitrary owner SQL.

## 3. Migration0009 / runtime grants

Source review and **three current PostgreSQL migration tests Passed** in review run01: direct clean-head install;0008→0009 with historical Refund retained byte-for-field, repeated upgrade/no backfill; runtime grant/schema checks. Actual demo revision remains0002 and was not upgraded. There is one source head0009; down_revision0008 is correct, not an assumption that the live demo was at0008.

Verified design: original UNIQUE payment_id/provider_key/reference; immutable Refund id/payment/requester/key/amount/reason/creation; reference cannot change once present; UPDATE version advances exactly1, success cannot downgrade, ordinary edges are checked. Insert amount is tied to verified SUCCEEDED original Payment/VND. New attempts have unique refund+generation, immutable bindings and prior composite FK; permit/redemption identity, generation arithmetic, expiry and uniqueness are constrained. Certificate relationships bind same payment and original operation/proof rows, reject legacy protocols; runtime cannot issue/redeem certificates yet.

Runtime Refund UPDATE is limited to state/version/reference/verified_at, no DELETE; attempts/permissions/redemptions insert/select and append-only; certificate tables select-only. No old migration modified. Constraints alone are not authenticated provider permission/certificate verification: wire provenance, full positive eligibility, issued permit TTL/effect authority and permitted FAILED dispatch remain B1b/B2/B3 obligations. Current API cannot exploit a storage-only row as positive authority because it refuses all missing-capability writes.

## 4. API, RBAC and financial invariants

| Gate | Result / evidence basis |
|---|---|
| Strict DTO and immutable client-controlled fields | Source +43 historical B1a tests checked in verified543; no added amount/currency/custody/desired-state input |
| Admin-only request/reconcile; Technician denied | Correct dependency and under-lock Admin recheck; historical tests verified |
| Owning Customer GET | Role/swap owner checked before refund existence lookup; cross-owner403 follows approved convention; no raw Technician evidence |
| Expected version | Request uses Payment.version, reconcile uses Refund.version; correct source/fixtures |
| Idempotency | Existing principal/route/key advisory, body hash conflict after successful receipt, atomic successful response cache; failed certificate refusals do not create receipts or success audit |
| Certificate absent |422 REFUND_EVIDENCE_REQUIRED before intent/attempt/case/outbox/audit/redemption write; **expected B1a behavior**, not a defect |
| UNKNOWN / FAILED / SUCCEEDED | No dispatch exists; UNKNOWN application refuses rather than POST, FAILED refuses retry without consumer/permission, success no downgrade; positive refund/provider processing Not Run |
| Money/assets | Refund amount derives from DB; no API path modifies Payment SUCCEEDED, custody, old_pin_settled or three holds |
| Caller revoke/expiry | Refund rechecks current user and exact session after waits; current rerun both-ordering tests passed; additional prior logout/role/expiry native probes artifact-verified |
| Shared Technician asset scope | **Failed**, P8B-B1A-IA01; cannot infer all shared callers are safe from Refund-specific checks |

Idempotency same-key/body success/audit replay is currently storage/helper-level evidence; no positive Refund API is claimed. Late role/session/certificate revalidation and durable successful intent semantics still need end-to-end coverage when B1b is introduced.

## 5. Independent deadlock / lock graph review

### P8B-B1A-01 — confirmed fixed within scope

Read the actual pre-fix PostgreSQL server excerpt and structured DETAIL/CONTEXT in `b1a_deadlock_before_20261116_06`: PID38937 held station FOR UPDATE and waited for user/XID589357; PID38920 held user FOR UPDATE and its assignment INSERT/FK waited for station/XID589358. DETAIL lists both waits and client statements; CONTEXT is locking tuple(0,4) in users. A transaction ShareLock in DETAIL is not a station table SHARE lock.

Current helper keeps the transaction station advisory and a **NO KEY UPDATE writer row lock**. Parent FK KEY SHARE is compatible, breaking the backward wait edge. NO KEY UPDATE still excludes station writers/stronger identity-changing operations; user/resource/exact session locks and READ COMMITTED remain. There is no catch40P01, altered status mapping, lowered isolation or network call in the helper.

Current reviewer rerun01: **original unmodified probe Passed**, plus **both full Refund/AssignStations route ordering probes Passed** on independent PG sessions. The original SQL-assignment probe rolls back its participant; the API variants commit a real assignment and exactly one Identity audit/receipt. Native diagnostics captured **zero40P01**. Original before/fix evidence and assertions retained. Station key-change/delete are not exposed and were not silently inferred safe.

The source repair removes a conflicting FK edge rather than forcing every implicit FK read into identical textual acquisition order. Assignment-first commits before Refund obtains target user; writer-first retains the user lock so assignment waits. This is compatible with the reviewed Refund/Recovery writer ordering, but it cannot repair callers that never lock/revalidate their actor.

### New shared-caller issue

`change_compartment` calls scope at315, waits at station318 or compartment319, then writes356/audits358 with the initially authenticated user. No sorted actor-user lock, exact session lock or current scope recheck protects the interval. AssignStations can commit revoke while the request waits. This is the distinct Major below, **not a recurrent deadlock**.

## 6. Audit / transaction review

Refund audit snapshot reads actual fields, including immutable payment/swap references and charge state/currency; reason/raw provider body/headers/tokens/QR are excluded. Before data is allowlisted, creation has no fictitious prior object, after snapshot is read in the same transaction. References are UUID-typed; actor/correlation are explicit. Caller owns locks/commit, so the helper does not establish financial proof or independent authority.

Verified historical tests assert exact REQUESTED→UNKNOWN/version1→2, full amount/original charge SUCCEEDED, atomic audit failure/rollback and idempotent no-repeat. Existing Recovery21-action helper/source is unchanged; selected audit/settlement/IA01/authorization/POST/successor/closure tests within543 remain artifact-supported. No backfill or immutable-policy change.

New finding produces one **unauthorized** compartment success audit with truthful state values. It is not a ghost from transaction rollback: the unauthorized mutation actually commits. Correct payload values do not make that audit legitimate. Audit created_at uses transaction time, so commit order is established by HTTP completion, PG row waits and post-revoke Admin read, not by comparing audit timestamps alone.

## 7. Evidence verification and actual test runs

Historical artifacts independently checked, **not rerun wholesale**:

- 543 unique JUnit testcase IDs,0 failures/errors/skipped,exit0; exact collection match and no missing original192 IDs.
- 189 source hashes before/after/current match. Only a new review test file was added outside that historical manifest; production files were not edited.
- Old run05 has neither final XML nor exit and remains **INTERRUPTED**, not part of Passed.
- Demo fingerprints agree for exactly8 tables plus revision0002; not a whole DB/volume/ledger proof.
- Native lock capture has0 deadlocks, writer/FK SQL counters; current AST inventory matches26 call sites.
- Static validator was **rerun by reviewer**,77 checks/34 definitions,exit0, OpenAPI valid, baseline/prior/frozen normative overlays unchanged. Expected source delta is the declared B1a files plus assets.py, not a replacement of the old freeze.

| Current review run | Passed / Failed / Error / Skipped | Exit / interpretation |
|---|---|---|
| independent_review_20261117_01 |7 /2 /0 /0 |exit1; original deadlock1, ordering2, migration3, pre-revoked control1 Passed. The two new cases stopped at an incorrect fixture assumption ACTIVE vs approved seed BLOCKED; not security evidence yet |
| independent_review_20261117_02 |1 /2 /0 /0 |exit1; fixture accepts the two contract-allowed SET_MAINTENANCE source states ACTIVE/BLOCKED, no DB mutation to prepare success; expected403/no-write unchanged. Both security cases reproduce200 |
| independent_review_20261117_03 |0 /2 /0 /0 |exit1; same assertions, adds Admin old-state observation after revoke/before lock release; both authorization failures confirmed |

These overlap; do **not** add7+1 as unique eight passing cases or count the two reproductions as four distinct findings. The final reviewed matrix has seven completed passing gates and two failing interleavings of one Major. Source of the initial fixture probe is retained in run01; source before the stronger observation is retained in run02. All runs kept log/XML/exit/hash/fingerprint; no skip/xfail or production bypass.

Latest [finding evidence](PHASE8B_TESTS/b1a_independent_review_20261117_03/finding.public.json), [redacted JUnit](PHASE8B_TESTS/b1a_independent_review_20261117_03/results.redacted.xml), [public summary](PHASE8B_TESTS/b1a_independent_review_20261117_03/summary.public.json). Detailed per-case before/after JSON in that run's `reports/PHASE8B_TESTS/independent_scope_*.json`. All actual runs use isolated retained schemas; demo8 fingerprint unchanged, no provider effects.

## 8. Findings

### P8B-B1A-IA01 — Major OPEN: Technician scope revoke loses against a waiting shared-caller mutation

**Location:** `services/backend/app/application/assets.py:313` (`scope`315 → station318/compartment319 wait → UPDATE356 → audit358); route `POST /v1/compartments/{compartment_id}/actions` (`changeCompartment`).

**Contract:** FR04/UC04 original OpenAPI says “Đúng trạm”; Technician acts only on assigned stations. Current review gate requires checking authorization through lock waits and no committed mutation under revoked authority. No durable authorization intent is committed before the lock wait.

**Reproduction (actual API, payloads contain no secret):**

1. Fresh isolated seed: Technician assignedS01, slot1 BLOCKED/version1, no active swap/holds; SET_MAINTENANCE is valid if authorized.
2. Separate PG transaction holds either station mutex/row or compartment row. Technician starts POST with `{expected_version:1,action:"SET_MAINTENANCE",reason:"Kiểm tra F2"}` and passes initial scope; `pg_blocking_pids` confirms it waits.
3. Admin PUT `/v1/users/{technician_id}/station-assignments` with `{station_ids:[]}` returns200; an independent connection sees0 assignments. Technician GET compartments returns403 STATION_FORBIDDEN.
4. **Admin GET after revoke, before releasing lock returns old BLOCKED/version1.** Thus there was no prior durable asset mutation/accepted intent to linearize before revoke.
5. Release test lock. Pending Technician POST returns **200**, slot becomes **MAINTENANCE/version2**, one `SET_MAINTENANCE` success audit attributed to Technician.

**Expected:**403 STATION_FORBIDDEN, slot/version unchanged, no mutation success audit/idempotency receipt.

**Actual evidence:**

| Boundary / isolated schema | Holder / waiter PG PID | Revoke / current scope / mutation HTTP | Slot before→after / audit delta |
|---|---|---|---|
| station / `phase5_test_770ec0127d02` |16271 /16288 |200 /403 /200 |BLOCKED v1→MAINTENANCE v2; +1 |
| compartment / `phase5_test_9b790c5b501c` |16321 /16338 |200 /403 /200 |BLOCKED v1→MAINTENANCE v2; +1 |

No random sleep; ordering is an observed DB wait, committed Admin endpoint, independent scope/old-state read, then release. Financial tables/outbox/holds counts remain unchanged (this fixture has **zero holds**, not a paid three-hold swap); seeded battery count11 unchanged. No physical proof/certificate, custody update or device/provider effect is created. Consequence is unauthorized asset availability change and success audit, a security Major even without demonstrated monetary/custody loss.

**Attribution:** AST of `change_compartment` matches HEAD de9b928 ignoring line numbers; this is a **pre-existing shared-caller flaw discovered by this review**, not evidence that NO KEY UPDATE caused it or that P8B-B1A-01 remains unfixed. It still blocks this acceptance because the requested independent gate includes shared callers and prohibits open authorization Majors. Phase8A's historical conditional acceptance is not rewritten/revoked by this report.

**Required repair proposal, not implemented:** protect current actor user in the common sorted user-lock phase after station and before resource/session locks; carry exact actor session context where necessary; re-read role/state/session expiry/revocation and station assignment after waits at the protected decision. Hold the authority lock through mutation/audit/commit so revoke-first refuses and mutation-first forces revoke to wait. Do not merely repeat an unlocked scope query immediately before UPDATE, remove Technician permissions, bypass authorization or revert the valid FK-compatible lock fix. Review sibling Technician mutators for the same pattern; then add both winning orders, role/session revoke, rollback/replay and resource/deadline regressions.

**Affected tests/gate:** preserve `tests/test_phase8b_independent_review.py` failing assertions and all three evidence runs; broaden Phase2/shared-caller security regressions for the authorized fix. Other suspected caller patterns are **not dynamically confirmed** and are not additional counted findings. Do not start B1b or accept B1a until this Major is reviewed/fixed/verified.

## 9. Residual risks / Not Run

- Positive B1b certificate issuance/redemption, provider permit authentication/FAILED dispatch, refund effects/query/callback, full TC16/CT13 and compensation remain out of B1a; no pass or waiver.
- No full Backend or full543 rerun in review; no new Browser/OS provider E2E. Existing543 supports its exact selected scope, not all possible races.
- No universal authorization/deadlock-safety conclusion for every sibling caller. Key-changing station APIs, arbitrary owner SQL and mixed old/new binary deployment require their own reviewed graph/rollout.
- Audit helper/storage reference tests are not positive financial authority. No actual provider result verification was demonstrated by storage-only fixtures.
- Final MVP NFR04/NFR07/CT14/NFR08 remain OPEN; Phase8A conditional acceptance unchanged.
- Raw logs/XML have local metadata; only redacted public copies are handoff candidates. No credentials, runtime ledger, DB data or raw evidence should be staged.

## 10. Decision and B1b handoff

**B1a INDEPENDENT REVIEW PARTIAL/BLOCKED.** P8B-B1A-01 technical fix is confirmed; migration/API fail-closed/audit foundation has the evidence stated above. **P8B-B1A-IA01 Major OPEN** prevents recommendation for user acceptance. Acceptance gate expansion stopped; no production fix was made in review, no B1b implementation or provider effects.

Next user decision: review the proposed shared-caller authority repair, retain original assertions, implement only the approved fix in a separate task and rerun the failing probes plus affected callers. Then resume independent acceptance; do not mark ACCEPTED BY USER or full Phase8B/TC16/CT13/MVP Passed here.

## 11. Files / Git / data preservation

New source: `tests/test_phase8b_independent_review.py` (test-only). New report: this file. Evidence is under the unique roots above, including snapshots of earlier probe revisions. No production/migration/approved contract/requirement edit, no credential/environment change. No delete/clean/restore/reset, demo migration, stage/commit/push/tag/release. Preserve PHASE5_TEST_ENVIRONMENT.json and all previous untracked files. Final Git/security inventory is recorded separately after report completion; this is not a staging approval.

Final read-only Git checkpoint: main/HEADde9b928, **7 pre-existing tracked modifications,1214 untracked files,0 staged**. This review changes only IMPLEMENTATION_STATUS among tracked files, as a factual review checkpoint; previous production edits remain exactly at the verified189-file snapshot. `git diff --check` and cached check exit0. [Review handoff/source/privacy inventory](PHASE8B_TESTS/b1a_independent_evidence_20261117_01/handoff.public.json) records no production delta or blocking content pattern and zero hostname/user-directory remnants in new public redacted log/XML. This is not a scan/approval of all1214 local artifacts. Cache/ledgers/evidence are retained, not classified for automatic deletion.
