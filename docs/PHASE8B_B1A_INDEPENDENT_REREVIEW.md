# Phase 8B — B1a independent re-review

17/11/2026 (+07). **B1a INDEPENDENT RE-REVIEW PASSED — RECOMMENDED FOR USER ACCEPTANCE.**

P8B-B1A-01 and P8B-B1A-IA01 are independently confirmed Fixed in the reviewed technical scope. No new Major/Blocker was found in that scope. This is a recommendation for **Increment B1a foundation only**, not ACCEPTED BY USER, full Refund/Phase8B acceptance, or permission to start B1b–B5. Phase8A conditional acceptance and the OPEN final-MVP NFR gates are unchanged.

## 1. Scope, provenance and method

Read AGENTS, original independent review, IA01 and deadlock fix reports, B1a implementation, B0 freeze/approved D01/D02/test plan/status, P8-REF-0.1/P8-REC-0.3, GD2 OpenAPI/RBAC/invariants and the relevant audit, migration/grants, Identity and shared-caller source. Requirements were checked against the original operation semantics rather than treating reported pass counts as acceptance.

Production was **not modified**. Added one reviewer test file and an artifact-validation tool; created this report and updated only IMPLEMENTATION_STATUS among existing reports. Original tests, assertions, failed reports, raw evidence, ledgers and private environment remain intact. No migration against demo, physical/provider effect, fake certificate, cleanup, staging, commit or push.

Docker29.9.2/PostgreSQL container healthy and pg_isready accepting before the review run; no old Python/pytest runner observed. Tests used newly provisioned retained PostgreSQL schemas and actual Backend endpoints through ASGI/TestClient with distinct native PG sessions. **These are not two OS API processes, Browser or provider E2E.** Only reviewer SQL pauses and read-only/native row-lock diagnostics were added; no SQL authority/custody/proof or timestamp mutation.

Evidence distinction:

- **Verified historical artifacts:** final affected543, targeted37/42, old192 subset and preserved failing evidence; independently read XML/exit/log/manifests/current files, not rerun wholesale.
- **Independently rerun:** original IA01 probes/control, mutation-first ordering, original deadlock probe, both Refund/AssignStations orders, FK/station compatibility and migration/grants/upgrade.
- **New reviewer probes:** six cached replay/savepoint/sibling resource-wait scenarios below.
- **Not Run:** full Backend collection, Browser, two-OS-server E2E, positive Refund/certificate/provider processing.

## 2. Source-level review

| Boundary | Independent conclusion |
|---|---|
| `assets.station_lock` L63–76 | Transaction advisory retained; station SQL uses FOR NO KEY UPDATE, not a weakened/unlocked read. Non-key writers serialize, FK KEY SHARE remains compatible |
| `identity.idempotent` L68–89 | Optional callback runs **after** idempotency advisory wait, **before** cached response lookup/body-conflict handling. Existing callers with no callback retain their original execution and lock ordering |
| `assets.operator_mutation` L92–135 | Station → temporary resource savepoint/rollback → sorted actor user → target resources → exact authenticated session. No business/audit/cache write in preliminary phase; current authority checked after waits and held through outer transaction |
| `assets.operator_authority` L79–89 | Re-reads ACTIVE/current allowed role, token principal binding/revocation/expiry and station assignment. Does not trust body actor/role |
| Compartment route/actions | Uses protected helper before entering original `change_compartment`; original role/action/version/resource/evidence constraints retained |
| Battery actions | Same helper, Admin RETIRE vs Technician ACTIVATE/QUARANTINE/RESTORE maintained. RESTORE prelocks its existing relevant alert set before session/freshness validation |
| Alert ACK and RESOLVE | Both protected, Technician-only; ACK remains distinct from resolving/restoring an asset |
| Identity AssignStations/UpdateUser/Logout | Assignment and account changes serialize through target user FOR UPDATE; role/state change revokes sessions. Logout updates exact auth_session. These conflict with the protected authority locks through commit |
| Shared callers | Current AST27 station helper calls: old26 plus new helper. No new late user/station acquisition by the four protected public operations beyond already-owned reentrant station/resource locks |

The integration covers **four public mutation operations in three families**: compartment actions, battery actions, alert ACK and alert RESOLVE. Application business functions still assume a protected caller; current source call sites go through that wrapper. Future direct/background callers must not pass a cached user without equivalent locks. No universal certification of unrelated Admin-only endpoints, owner SQL or future callers is made.

### Decision and commit boundary

Initial principal/route scope checks are admission hints. Effective authority is established by `operator_authority` after station/user/resource/exact-session waits. The user row protects assignment, role and state; the exact session row protects logout/revoke. Protected execution rechecks authority/real expiry after business/audit work and before success receipt insertion. The request dependency commits afterward and rolls back on any exception (`main.py` L61–68).

Revoke-first therefore sees current committed revocation and refuses; authority-first holds the conflicting locks so revocation cannot commit in that interval. Real wall-clock expiry is not frozen by a lock: the final check must still pass, otherwise the business write/audit/cache rolls back. Current business evidence/version guards execute under their existing station/resource locks; no deadline/freshness change or HTTP wait is introduced. Read-only cached replay still holds current authority through request completion; it does not create a new business effect.

### Savepoint semantics and lock graph

The preliminary step is a locking read, **not a read-only SQL transaction**. PostgreSQL may write tuple lock metadata, but there is no domain mutation. Its rollback must release only the locks acquired inside that savepoint; outer station locks remain. PostgreSQL17 documents both savepoint lock release and NO KEY UPDATE/KEY SHARE compatibility in [Explicit Locking, §§13.3.1–2](https://www.postgresql.org/docs/17/explicit-locking.html).

The new native probe independently confirms this: paused immediately after actor user lock, a different PG session can acquire compartment FOR UPDATE NOWAIT, while user and station FOR UPDATE NOWAIT each fail55P03; station KEY SHARE NOWAIT succeeds. Old state/audit/cache remains unchanged before release. Thus no temporary resource→user edge is retained. The production protected phase follows user→resources→session; idempotency is acquired first, avoiding station→idempotency inversion. Parent station lock/mutex are not removed to obtain these results.

AssignStations' user→FK station KEY SHARE edge is compatible with the retained NO KEY UPDATE. UpdateUser only reads custody/reference rows while holding its user; Logout has no station/user acquisition after its session update. Existing shared station writers serialize before acquiring station resources. No40P01 catch/retry, lowered isolation, TTL change, network call under locks or in-memory authority workaround was found. This is a reviewed lock graph, not proof that every possible application transaction is deadlock-free.

## 3. Independent execution — 16 Passed

Unique run: `PHASE8B_TESTS/b1a_rereview_20261117_01/`.

**16 Passed,0 Failed/Errors/Skipped,exit0**,87.33s pytest; wrapper16:01:08–16:02:37 +07. The run includes six new probes and ten rerun cases; do not add these numbers to historical543/37/42 as a new total. One existing Starlette/httpx deprecation warning, no dependency change.

| Scenario | Actual result / evidence |
|---|---|
| Original station waiter | Revoke200/me-scope403/Admin still sees old state; mutation403 STATION_FORBIDDEN, state/version unchanged |
| Original compartment waiter | Same original assertions, same403/no write; native holder48500/waiter48529 |
| Pre-revoked original control |403/no write |
| Mutation-first compartment | Existing unchanged ordering test: AssignStations visibly blocked by mutation transaction; one mutation/audit/receipt then revoke200 and subsequent request403 |
| **New:** cached replay, logout commits first | Replay waits on idempotency after admission auth; real logout200 and me401 before release; replay401 SESSION_REVOKED, cache/business/audit unchanged. Holder48607/waiter48586 |
| **New:** cached replay, role revoke commits first | Real assignment removal then PATCH role200/session revoke before release; replay401, no stale cached success. Holder48666/waiter48645 |
| **New:** cached replay holds authority first | Paused at actual cache SELECT after authorization; logout PG48725 waits on replay48703. Replay200 equals original body, logout200 afterward, subsequent replay401; no extra audit/receipt |
| **New:** savepoint/outer locks | Winner48761; compartment row lock independently available, user/station strong locks55P03, station KEY SHARE available; no preliminary domain writes; final valid action200 once |
| **New:** battery resource wait vs logout | Assignment remains in place; logout commits while QUARANTINE waits on pin row, then401/no lifecycle/version/audit/receipt mutation. Holder48839/waiter48818 |
| **New:** alert resource wait vs logout | Same valid assignment, actual logout and native alert-row wait; ACK401/no mutation. Holder48897/waiter48876 |
| Original deadlock probe + both HTTP orders |3 Passed; Refund remains422 missing certificate, assignment200, no40P01 |
| Native FK/writer compatibility | Passed; FK/KEY SHARE can finish while station writer held; other station writers/mutex users wait |
| Clean-head/runtime grants and0008→0009 historical retention |2 Passed; isolated schemas, no demo upgrade/backfill |

The two original schemas were additionally queried read-only: **zero SET_MAINTENANCE success audits and zero successful idempotency receipts**, not just HTTP403. Current reviewer facts compare exact before/after rows, versions, audits, request receipts, custody columns and Payment/Refund/holds/commands/outbox. Positive action/replay produces exactly one original mutation/audit/receipt. No new financial/physical effect was attempted. These fixtures have zero holds; they do not pretend to demonstrate a positive three-hold settlement. Relevant paid-flow preservation is separately supported by the verified affected regression.

[Reviewer redacted JUnit](PHASE8B_TESTS/b1a_rereview_20261117_01/results.redacted.xml) · [run summary](PHASE8B_TESTS/b1a_rereview_20261117_01/summary.public.json) · [native PG/SQL validation and six detailed references](PHASE8B_TESTS/b1a_rereview_validation_20261117_01.public.json). Raw log/XML/exit/hash files coexist in that new folder. Intentional NOWAIT55P03 refusals are diagnostics, not unexpected40P01 or failed tests.

## 4. Overall B1a foundation review / traceability

| Requirement | Source / evidence | Scoped disposition |
|---|---|---|
| FR04/UC04 assigned compartment operations, QD06 | Protected assets route/helper; unchanged original probes, reviewer ordering and savepoint | Passed; IA01 closed technically |
| FR06/08, UC06/08 lifecycle | Battery protected route, original business constraints; affected Phase3 and new resource/logout probe | Passed in scoped foundation/asset regression; no custody authority added |
| FR19/UC17 assigned alert ACK/RESOLVE | Protected routes/transition; affected Phase4, reviewer sibling ACK | Passed; ACK is not physical recovery proof |
| FR16/UC14 RBAC/ownership/strict DTO | Refund API/application source;43 B1a tests within verified543 | Admin-only request/reconcile, owning Customer read, no client money/state/actor; exact session after waits |
| BR08/09, invariants6–8 | Refund no-certificate fail-closed, immutable original charge, separate old obligation | Foundation Passed. Full refund eligibility/provider/compensation remains outside B1a, not declared complete |
| Refund state/idempotency/version | Five-state pure policy + migration identity/version/transition guard, same intent/payment uniqueness | Foundation Passed; FAILED retry still forbidden until future approved permit consumer; UNKNOWN never POSTs here |
| Migration0009 / grants | Immutable refund binding, append-only attempts/permissions/redemptions, certificate SELECT-only; runtime column-level UPDATE | Source reviewed and two reviewer PG tests Passed; no new positive certificate authority |
| BR12/NFR06 audit | Refund allowlisted DB snapshots, creation-null, actual before/after version/state, typed references; rollback/replay tests in543 | Foundation Passed; no historical backfill, no raw headers/token/password/QR/provider body in helper |
| P6-A01–A03 / P7-A01 / Phase8A IA01/ER01/02 | Relevant original modules in543, source guards unchanged | Historical final-source artifacts verified, not a new OS E2E or full-project rerun |
| B0/P8-REF-0.1/P8-REC-0.3 | Independently rerun static validator77/34 and immutable normative hashes | Frozen contracts unchanged;0.3 issuer/runtime remains future B1b |

Source review confirms all B1a financial refusals precede intent/attempt/certificate redemption/outbox/case/audit writes. Request checks DB verified SUCCEEDED full charge and Payment.version; reconcile checks Refund.version/state. Storage-only tests are not provider permission or physical no-delivery proof. Refund audit before-data is allowlisted from a prior DB snapshot and after-data read in the same caller transaction; the helper itself cannot establish authority or call commit. Future positive provider-result audits/dispatch/callbacks require their own acceptance.

## 5. Historical evidence independently reconciled

[Independent artifact reconciliation](PHASE8B_TESTS/b1a_rereview_artifacts_20261117_01.public.json) was generated from raw artifacts/current files, independently of the remediation's summary labels:

- Final `b1a_ia01_affected_20261117_04`: raw and redacted JUnit each543 unique IDs,0 failure/error/skip; exit0, complete log. IDs exactly equal original543 collection; actual original192 JUnit subset has no missing case. **Not rerun in re-review.**
- 191 before/after/current source hashes match. Five production changes against the old189 are precisely assets application, identity and assets/batteries/device API. No unexpected production delta. Reviewer run has192 stable hashes: the same191 plus the new reviewer test.
- Original IA01 probe bytes match its failing run03 manifest; expected403 and equality assertions were not changed. Original old deadlock source/assertions remain and were rerun successfully.
- Targeted37 and42 XML/exit were read, not added together; they overlap and new assertions were added to the final37's test version. No reuse of old543 as a current rerun.
- Original review01 remains7Passed/2fixtureFailed;02 remains1Passed/2authorizationFailed;03 remains0Passed/2authorizationFailed. Sibling-before remains0Passed/2Failed. Their files/statuses were not rewritten.
- Historical affected capture0 SQLSTATE40P01; reviewer capture also0. Reviewer actual SQL counters:56 station NO KEY UPDATE,72 user FOR UPDATE,17 assignment FK INSERT;3 stronger/different station modes come from native diagnostic tests.
- Demo fingerprints before/after agree for exactly users/stations/compartments/batteries/swap_transactions/payments/refunds/audit_events, plus revision0002. This is neither whole-DB nor volume/ledger backup proof.
- Static rerun [77 checks/34 definitions](PHASE8B_TESTS/b1a_rereview_static_20261117_01.json), exit0: runtime/design OpenAPI and frozen baseline/prior overlays agree. Expected source delta is explicit; normative contracts were not weakened to pass.

## 6. Findings and residual scope

| Finding | Re-review disposition |
|---|---|
| P8B-B1A-01 — station/User/FK deadlock | **FIXED, independently confirmed again.** Original server40P01 evidence retains the two-XID wait cycle; current compatible parent lock and real rerun orders break that edge without removing serialization |
| P8B-B1A-IA01 — stale Technician scope | **FIXED/CLOSED in reviewed technical scope.** Original failures now403/no version/audit/receipt; protected authority/commit order, new cached-session/role and sibling tests consistent with source/contract |
| New Major/Blocker | None found in this B1a re-review scope |

Residuals are not silently waived: positive no-delivery certificate verification/redemption, provider retries/permission/effects/query/callback, full TC16/CT13 and B1b–B5 remain Not Implemented/Not Run; no compensation8C. This review is not a global authorization or deadlock proof for unrelated Admin endpoints, arbitrary SQL, future station key changes/deletions, mixed old/new binaries or new non-HTTP callers. Full Backend/Browser/two-OS-provider E2E were not rerun because production matches the verified freeze and no substantive new suspicion required expanding the suite.

NFR04 load, NFR07/CT14 coordinated restore and NFR08 real-user usability remain OPEN before final MVP release, with their previously approved allocation unchanged. No full MVP PASS or user/lecturer signature is asserted.

## 7. Reproduction, changes and Git

New tests: `tests/test_phase8b_rereview.py` (six probes). New read-only artifact tool: `tools/review_phase8b_b1a.py`. Existing production, migrations, tests, original review/fix reports and B0 files unchanged. Only IMPLEMENTATION_STATUS receives a new review checkpoint; no old acceptance conclusion is overwritten.

Actual reviewer command used the standard isolated runner with a unique label and explicit nodes: original independent file; new reviewer file; `test_mutation_authority_first_revocation_waits[assignment-compartment]`; original lock-graph probe; full HTTP Refund/AssignStations both orders; station FK compatibility; clean migration/grants;0008→0009 historical retention. Exact testcase IDs are in JUnit. To reproduce choose a **new label**, not an existing evidence directory:

```powershell
.venv/Scripts/python.exe tools/run_phase8b.py NEW_REVIEW_LABEL tests/test_phase8b_independent_review.py tests/test_phase8b_rereview.py -p phase8b_deadlock_capture
.venv/Scripts/python.exe tools/review_phase8b_b1a.py docs/PHASE8B_TESTS/NEW_ARTIFACT_REVIEW.public.json
.venv/Scripts/python.exe tools/validate_phase8b_b1a.py docs/PHASE8B_TESTS/NEW_STATIC_REVIEW.json
.venv/Scripts/python.exe tools/summarize_phase8b.py NEW_REVIEW_LABEL
```

First command reruns the original control/probes plus six new cases; add the explicit regression nodes above to reproduce the complete16-case selection. Requires the existing private local environment and PostgreSQL; never publish passwords/tokens/connection URLs. All new evidence is retained. Redacted copies are additional files; raw files/private fixture metadata/ledgers/cache are not staging candidates. No cleanup was done; ordinary bytecode/pytest cache is regenerable only in a separate authorized cleanup.

Branch main/HEAD`de9b9288452f3c4e2b6703ed0ce641668ac8fc78`, index empty. Final read-only status:11 tracked modifications,1388 untracked,0 staged; initial1360 untracked and PHASE5 environment artifact preserved. `git diff --check` exit0 (only existing CRLF normalization notices). Final191 current hashes still match; no production delta during review. No Git mutation or automatic next increment. **Decision to accept B1a belongs to the user.**
