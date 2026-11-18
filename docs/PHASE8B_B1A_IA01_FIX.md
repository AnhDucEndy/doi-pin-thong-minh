# P8B-B1A-IA01 — protected current operator authority

17/11/2026 (+07). **P8B-B1A-IA01 FIXED — B1a READY FOR INDEPENDENT RE-REVIEW** in the verified scope below. All required targeted/affected checks completed on final source. This is not independent/user acceptance or permission to implement B1b. No staging, commit, provider effect or deployment occurred.

## Root cause and preserved evidence

The independent report and all three `b1a_independent_review_20261117_0{1,2,3}` runs remain unchanged. `assets.change_compartment` checked a cached Technician and assignment before station/compartment waits. AssignStations could commit a revoke during that wait, while the pending mutation subsequently wrote MAINTENANCE/version2 and a success audit. This was pre-existing in HEAD, not caused by the correct NO KEY UPDATE repair.

Two new native PostgreSQL/ASGI probes confirmed the identical source pattern in battery lifecycle (`QUARANTINE`) and alert acknowledgment. Before-fix `b1a_ia01_siblings_before_20261117_01`: **0 Passed, 2 Failed, exit1**, actual mutation200 after revoke200. These failures and JSON are retained. No unrelated caller is changed speculatively.

## Scope and caller inventory

| Caller | Before-fix classification | Disposition |
|---|---|---|
| Compartment SET_MAINTENANCE/RESTORE/RETIRE | Confirmed vulnerable: station and compartment wait probes | Protected route for both fresh execution and cached replay; original business checks retained |
| Battery ACTIVATE/QUARANTINE/RESTORE/RETIRE | Confirmed same root cause by QUARANTINE station-wait probe; common change route | Same authority gate; prelock existing RESTORE alert set before session/freshness checks |
| Alert ACK/RESOLVE | Confirmed same root cause by ACK station-wait probe; common transition | Same gate, Technician-only unchanged |
| Recovery record/confirmation/authorization/settlement/successor/closure | Assignment/role pattern protected by sorted participant user locks and scope recheck; staged human/settlement/closure also lock exact sessions | No source change; affected regression required. This does not certify every legacy evidence-write session race |
| Refund request/reconcile | Already protected station, participant users/resources, exact Admin session and final role/version | No source change, remains missing-certificate fail-closed |
| Device ingestion/poll, Device/Payment workers, swap worker | Not applicable to cached human Technician assignment; device/service provenance or existing customer guards | No source change; shared-lock regression required |
| Station/device/battery creation or station/device update | Admin-only, not a Technician assignment-bound mutation | Not included in this fix; no universal claim that all pre-existing Admin endpoints serialize role changes |
| Read-only station/device/battery lists | No state mutation or success receipt | Existing request-time scope; no write-authority extension |

Original shared-lock inventory contained26 call sites. The new protected helper adds one station-lock call. Inventory is source-level; it does not establish every possible future/dynamic SQL caller safe.

## Transaction and lock graph

`identity.idempotent` has one optional internal `authorize` callback. Existing callers do not change behavior. The three reviewed routes use `assets.operator_mutation` to invoke this callback **after idempotency advisory acquisition, before response-cache lookup**, so cache replay cannot carry stale assignment/session authority and lock order is not reversed to station→idempotency.

The helper retains station advisory mutex and **FOR NO KEY UPDATE**. Before taking authority it performs a read-only resource availability wait in a savepoint, then rolls that savepoint back. PostgreSQL releases those temporary row locks; no user/session lock or business/audit write exists in this preliminary phase. This preserves the original revoke-first compartment-wait scenario without introducing a resource→user lock edge.

Protected phase: **sorted actor user UUIDs → ordered target resource rows → exact authenticated session**. Current ACTIVE state, role, principal/session binding, revoked_at, real expiry and station assignment are checked after all waits. User/session locks remain held until the request transaction commits/rolls back. Current authority and wall-clock expiry are checked again after business/audit work and before successful idempotency receipt insertion. Business resource versions, state/evidence and existing freshness guards still execute under the protected resources/station.

AssignStations/UpdateUser take the same target user FOR UPDATE; Logout updates the exact session. Thus revoke-first is observed and refused; a mutation holding authority first forces revocation to wait. AssignStations FK KEY SHARE remains compatible with station NO KEY UPDATE. Login has no station edge; UpdateUser reference reads do not take resource writer locks. No HTTP/network waits, new transaction isolation, automatic retry, broader deadlines or session fabricated from request body are added.

All domain writes/audit/idempotency receipts remain in the original dependency transaction. Refusal/expiry/audit exception rolls the entire write back. No migration, grants, normative contract, custody, Payment, holds, physical effect, Recovery protocol or baseline is changed.

## Verification checkpoint

- `b1a_ia01_original_after_20261117_01`: **5 Passed, exit0**, including the unchanged two original failing probes, their pre-revoked control and both confirmed sibling probes. Source stable; demo8-table fingerprint and revision0002 unchanged.
- `b1a_ia01_targeted_20261117_02`: **42 Passed,0 Failed/Errors/Skipped,exit0**,273.05s. Original probes/control3, new IA01 tests27, original deadlock1 and deadlock repair tests11. No40P01, hashes/demo unchanged.
- `b1a_ia01_targeted_20261117_03`: **37 Passed,0 Failed/Errors/Skipped,exit0**,215.81s. Original probes/control3 and final IA01 tests34. Adds explicit full custody/Payment/holds/commands comparisons, concurrent same/different-key mutations and cached replay waiting at idempotency. Production source identical to02; original assertions unchanged. Runs overlap; do not add42+37 or5+42+37.
- Static `b1a_ia01_static_20261117_01.json`: **77 checks/34 definitions, exit0**. Original GD2 and frozen B0/8A overlays unchanged; validator explicitly declares the four additional reviewed production file deltas against the old179-source snapshot, without replacing that baseline.
- Collection `b1a_ia01_collection_20261117.json`: exact original543 IDs, missing0/extra0. Final `b1a_ia01_affected_20261117_04`: **543 Passed,0 Failed/Errors/Skipped,exit0**,2336.70s (38:56), wrapper14:00:36–14:39:35 +07. Historical543 was not substituted for this result.

Tests use isolated retained schemas and distinct native PG sessions with observed `pg_blocking_pids` waits. ASGI/TestClient probes are **not two OS Backend servers or Browser tests**. There is no new physical fixture, provider call or fake certificate. Data protection evidence is scoped to the runner's8 demo tables/revision, not a whole-volume backup proof.

## Targeted matrix (final production source)

| Gate | Tests / observed result |
|---|---|
| Original revoke-first station / compartment | Both403 STATION_FORBIDDEN, old slot/version/audit unchanged, same original probe bytes |
| Sibling revoke-first | Battery QUARANTINE and alert ACK403; no row/version/audit/idempotency mutation |
| Role/state/session revoke-first |3 actions × logout/change-role/LOCKED =9 cases; real revoke endpoint200 and me401 before barrier release, mutation401, protected state unchanged |
| Mutation-first |3 actions × assignment/logout/LOCKED =9; successful mutation holds user/session, revoke visibly waits on PG blocker, old state remains externally visible until commit; then mutation200 and revoke200, subsequent action403/401 |
| Exact session | Logout of different session does not invalidate valid session; newly inserted short-lived auth fixture expires during observed native lock wait,401/no write; no historical timestamp or policy changed |
| Audit rollback/replay |3 actions; injected audit failure rolls back state/audit/receipt; same key retry succeeds once, exact replay unchanged, conflicting body409, revoked-scope replay403 |
| Concurrent mutation |3 actions × same/different keys =6;200/200 cached or200/409 VERSION_CONFLICT; one version increment, one audit and one receipt, unchanged custody/payment/holds/commands |
| Cached replay wait | Prior success exists; replay blocks at idempotency, revoke commits first, replay403; no stale successful cache response |
| RBAC / wrong station |3 cases: Customer403, Admin cannot use Technician-only battery/alert actions, Technician S02 action403; Admin's existing compartment rights retained by affected Phase2 coverage |
| Deadlock / resource guards | Original40P01 probe and11 repair regressions Passed in02, on the same production bytes; repeated within affected543 |

JSON evidence contains native blocker/waiter PIDs, before/after facts and response codes. The new mutation-first fixture has zero holds and no paid swap; it proves no added/changed resources, not a three-held-resource positive settlement. Separate affected Payment/Recovery tests protect those workflows. No new physical effect is attempted in IA01 probes.

## Source delta and reproduction

Against the completed prior543 source, only five production files differ: `app/application/assets.py`, `app/application/identity.py`, `app/api/assets.py`, `app/api/batteries.py`, `app/api/device.py`. Their actual code adds the shared protected gate, the optional idempotency callback and the three route integrations. The application business mutation functions still assume their protected route caller; future non-HTTP entry points must use equivalent authority locking rather than calling them with a cached user. No new public request/response field or permission is introduced.

New regression source: `tests/test_phase8b_ia01_fix.py` (34 final tests). The original `tests/test_phase8b_independent_review.py` is unchanged. `tools/validate_phase8b_b1a.py` declares the reviewed source delta; `tools/verify_phase8b_ia01.py` checks exact collection/JUnit/hash/probe/deadlock facts. The final run freezes191 files; five changed and two added against the old189 manifest (one addition is the already-existing independent-review probe). Additional tooling hashes are recorded separately because those new tools are outside the legacy source-manifest algorithm.

With the existing private local environment and healthy PostgreSQL, run sequentially, choosing **new unique labels** each time:

```powershell
.venv/Scripts/python.exe tools/run_phase8b.py NEW_TARGET_LABEL tests/test_phase8b_independent_review.py tests/test_phase8b_ia01_fix.py -p phase8b_deadlock_capture
.venv/Scripts/python.exe tools/verify_phase8b_ia01.py collect docs/PHASE8B_TESTS/NEW_COLLECTION.json
$paths = (Get-Content docs/PHASE8B_TESTS/NEW_COLLECTION.json -Raw | ConvertFrom-Json).test_paths
& .venv/Scripts/python.exe tools/run_phase8b.py NEW_AFFECTED_LABEL @paths -p phase8b_deadlock_capture
.venv/Scripts/python.exe tools/verify_phase8b_ia01.py NEW_AFFECTED_LABEL
.venv/Scripts/python.exe tools/summarize_phase8b.py NEW_AFFECTED_LABEL
```

The verification tool's source input is the public original collection `PHASE8B_TESTS/b1a_deadlock_collection_20261117.json` (paths/IDs, no runtime credentials); keep it with reproducible tooling in a future curated handoff. Raw reports/credentials/database snapshots are not substitutes for that source and are not staging candidates. Runner creates isolated schemas and preserves historical artifacts; it does not migrate demo, drop schemas or reset rate limits. Redacted summaries are new copies, never edits to old raw evidence.

## Final evidence / safety decision

Final [redacted JUnit](PHASE8B_TESTS/b1a_ia01_affected_20261117_04/results.redacted.xml), [summary](PHASE8B_TESTS/b1a_ia01_affected_20261117_04/summary.public.json), [artifact validation](PHASE8B_TESTS/b1a_ia01_affected_20261117_04/validation.public.json) and raw `run.log/results.xml/exit.json/source_before.json/source_after.json` coexist in the unique run folder. XML and exit were actually parsed; no inference from progress dots.

- 543 unique completed IDs exactly equal the original affected selection, no missing/extra, failures/errors/skips0. This retains the original192 subset. **This is the affected selection, not the entire Backend collection.**
- 191 source hashes agree before/after/current. Original independent probe bytes agree with its failing run03 manifest. Static77checks/34definitions remain valid; no subsequent production/contract/test source edit.
- 0 captured SQLSTATE40P01. Actual lock counters:6027 station NO KEY UPDATE,4011 user FOR UPDATE,56 assignment FK INSERT;2 stronger station modes come from explicit diagnostic tests. AST inventory27 calls (the original26 plus the protected helper).
- Original two post-fix schemas were queried read-only separately: mutation403, success audit0, successful idempotency receipt0. See [two-fixture SQL verification](PHASE8B_TESTS/b1a_ia01_original_after_20261117_01/original_no_success_receipt.public.json).
- New final targeted facts compare exact custody columns and full Payment/Refund/holds/commands/outbox rows. Successful battery lifecycle changes are not misreported as custody changes. Both revoke and authorized-mutation winning orders were observed through native PG blockers, not guessed from timing.
- Demo fingerprint is unchanged for exactly8 tables and revision`0002_user_approval`; no demo migration. It is not a whole-DB or volume consistency proof. No new refund, certificate, provider/physical command or hold release was implemented.
- Three non-blocking warnings in affected run: one Starlette/httpx deprecation and two existing `validate_spec` deprecations. No dependency was installed or changed.

| Final gate | Status |
|---|---|
| Original station/compartment failures, unchanged expected403/no write | Passed |
| Same-root sibling battery/alert failures | Passed after fix; pre-fix failures retained |
| Reverse order, role/session/scope/expiry | Passed |
| Rollback, success replay/conflict, cached-response wait, concurrent mutations | Passed |
| Original deadlock, FK compatibility, AssignStations/Refund both orders | Passed, repeated in final543 |
| Relevant assets/P6/P7 deadline/8A current-boot, authorization, settlement, closure/audit/migration/grants | Passed in final543; module counts in summary |
| Exact collection/source/probe hash, static contracts, diff check | Passed |
| Full Backend collection, new Browser or two OS API servers | Not Run in this remediation; not claimed by ASGI/native-PG evidence |
| Independent re-review/user acceptance B1a | Pending; this report only recommends readiness |
| B1b–B5 positive eligibility/Refund provider effect, Phase8C | Not implemented; missing-certificate refusal remains intentional |

No new Major/deadlock was found in this verified scope. The caller inventory is not a universal authorization certificate for unrelated Admin-only endpoints, arbitrary owner SQL, future key-changing station APIs, mixed-binary rollout or untested legacy session races. Phase8A conditional acceptance and final MVP NFR04/NFR07/CT14/NFR08 OPEN gates remain unchanged.

## Git / preservation handoff

main/HEAD remains`de9b9288452f3c4e2b6703ed0ce641668ac8fc78`,0 staged;11 tracked modifications, including the preserved PHASE5 environment artifact. Final read-only check:1360 untracked paths (the earlier JSON count1359 precedes creation of that checkpoint file itself). No reset/restore/clean, deletion, staging, commit or push.

Keep the five production edits, regression source34 tests, unchanged original independent probe, both verification tools and these reports for review. Existing B0/B1a migration/contracts/tests/source must also remain; none are replaced. Preserve all prior and new raw evidence, isolated schemas, `.local`/`.cache` ledgers and private environment. Raw XML/logs/runtime credentials and binary ledgers are **not** future staging candidates. Ordinary `__pycache__`/`.pytest_cache` can be regenerated in a separately authorized cleanup; no cleanup was done here.
