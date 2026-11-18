# Phase 8B — B0/B1a curated Git handoff

17/11/2026 (+07). **B1a USER ACCEPTANCE RECORDED — CURATED COMMIT READY FOR USER REVIEW.**

Proposal only: **62 REQUIRED paths,10 OPTIONAL paths**. No staging/commit/push, clone, package install, migration or test execution occurred in this acceptance/handoff. B1a only is accepted; B1b–B5 remain NOT STARTED. See [acceptance/provenance](PHASE8B_B1A_USER_ACCEPTANCE.md).

## Integrity and content review

- main/HEAD `de9b9288452f3c4e2b6703ed0ce641668ac8fc78`, index empty. Accepted191 and reviewer192 hashes match current source; no production/contract/test delta.
- Re-review16/exit0 and affected543/exit0 were read from actual XML/exit/manifests;543 was not rerun during acceptance. Static77/34 remains valid; frozen normative B0 bytes unchanged.
- Every candidate was fully read as UTF-8: AST/JSON syntax, credential URI/token/private-key/hostname/user-directory patterns, binary/NUL/runtime extensions and size checked. No blocking content finding. Hash-only manifests are not credentials; synthetic non-login/redaction fixture literals are not live credentials.
- 72 unique existing candidates, no binary/raw-runtime file, each below250KB at scan. Local SHA256/size/status records: `PHASE8B_HANDOFF/candidate_scan_final.json`. That mutable scan output is excluded from the proposal. Automated scanning/manual classification is not an absolute guarantee against every possible secret.
- Tracked `docs/PHASE5_TEST_ENVIRONMENT.json` stays EXCLUDED: the only tracked modification outside REQUIRED. No data/evidence/private file was deleted.

## One local-ignore exception

`tools/phase6_acceptance_e2e.py` is a reviewed738-byte source wrapper, not runtime data. Old179 hash input used by the current runner/static validator requires it. It is absent from HEAD and ignored by local `.git/info/exclude` line7. REQUIRED includes it explicitly.

**Before later staging**, the user must approve handling this one exact ignored source path (a specifically authorized add or a separate local-exclude adjustment). Do not blindly feed the manifest to normal git add and ignore an error. No ignore rule/force-add was performed. This is a pending staging procedure; the proposed dependency set itself is complete.

## A. REQUIRED —62 explicit paths

Machine-readable proposal: `docs/PHASE8B_HANDOFF/B0_B1A_REQUIRED_PATHS.txt`. No other path is implicitly approved. The list includes itself and the optional-path index. Already tracked unchanged dependencies need no new staging.

| Path | Current Git classification | Reason |
|---|---|---|
| `docs/IMPLEMENTATION_STATUS.md` | tracked modification | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8A_TESTS/nfr06_fix_20261115_01/source_final_before.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_B0_B1A_COMMIT_MANIFEST.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B0_CONTRACT_FREEZE.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_DEADLOCK_FIX.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_IA01_FIX.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_IMPLEMENTATION.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_INDEPENDENT_REREVIEW.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_INDEPENDENT_REVIEW.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_B1A_USER_ACCEPTANCE.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_DECISIONS_APPROVED.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_DESIGN_PROPOSAL.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_HANDOFF/B0_B1A_OPTIONAL_PATHS.txt` | untracked | Exact proposal index; no staging authorization |
| `docs/PHASE8B_HANDOFF/B0_B1A_REQUIRED_PATHS.txt` | untracked | Exact proposal index; no staging authorization |
| `docs/PHASE8B_READINESS_REVIEW.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/PHASE8B_TESTS/b1a_deadlock_collection_20261117.json` | untracked | Exact543 collection input |
| `docs/PHASE8B_TESTS/b1a_deadlock_regression_20261117_06/source_before.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TESTS/b1a_ia01_affected_20261117_04/source_after.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TESTS/b1a_ia01_affected_20261117_04/source_before.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TESTS/b1a_independent_review_20261117_03/source_before.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TESTS/b1a_rereview_20261117_01/source_after.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TESTS/b1a_rereview_20261117_01/source_before.json` | untracked | Public source/hash input or accepted checkpoint |
| `docs/PHASE8B_TEST_PLAN.md` | untracked | Approval, finding history, implementation or handoff documentation |
| `docs/implementation-contracts/P8-REC-0.3/README.md` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REC-0.3/contract.schema.json` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REC-0.3/openapi.overlay.yaml` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/README.md` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/RETRY_PROTOCOL.md` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/contract.schema.json` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/freeze_manifest.json` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/openapi.overlay.yaml` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/source_baseline.json` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/validate_static.py` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/validation_20261116_03.json` | untracked | Frozen B0 contract/schema/static input |
| `docs/implementation-contracts/P8-REF-0.1/validation_20261116_04.json` | untracked | Frozen B0 contract/schema/static input |
| `services/backend/alembic/versions/0009_refund_foundation.py` | untracked | Forward migration0009; chain0001-0008 already tracked |
| `services/backend/app/api/assets.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/api/batteries.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/api/device.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/api/refunds.py` | untracked | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/application/assets.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/application/identity.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/application/refund_audit.py` | untracked | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/application/refunds.py` | untracked | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/domain/refunds.py` | untracked | Refund foundation or reviewed shared authority/lock fix |
| `services/backend/app/main.py` | tracked modification | Refund foundation or reviewed shared authority/lock fix |
| `tests/phase8b_deadlock_capture.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase1.py` | tracked modification | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8a_migration.py` | tracked modification | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_b1a.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_b1a_transactions.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_deadlock_fix.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_ia01_fix.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_independent_review.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_lock_graph_probe.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tests/test_phase8b_rereview.py` | untracked | Regression/reviewer source or native-lock diagnostic |
| `tools/phase6_acceptance_e2e.py` | ignored local source | Old179 hash-input source dependency; locally ignored |
| `tools/provision_database.py` | tracked modification | Runner/summary/static/artifact validation tooling |
| `tools/run_phase8b.py` | untracked | Runner/summary/static/artifact validation tooling |
| `tools/summarize_phase8b.py` | untracked | Runner/summary/static/artifact validation tooling |
| `tools/validate_phase8b_b1a.py` | untracked | Runner/summary/static/artifact validation tooling |
| `tools/verify_phase8b_ia01.py` | untracked | Runner/summary/static/artifact validation tooling |

## B. OPTIONAL —10 separately selectable paths

Not implicitly approved for staging. Public filenames alone were not trusted; each candidate's content was scanned. Historical summaries retain their actual scope and do not replace source/tests or raw local evidence.

| Path | Purpose / limitation |
|---|---|
| `docs/PHASE8B_TESTS/b1a_deadlock_before_20261116_06/postgresql_deadlock.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_ia01_affected_20261117_04/summary.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_ia01_targeted_20261117_03/summary.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_independent_review_20261117_03/finding.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_rereview_20261117_01/summary.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_rereview_artifacts_20261117_01.public.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_rereview_static_20261117_01.json` | Content-reviewed public historical summary/evidence |
| `docs/PHASE8B_TESTS/b1a_rereview_validation_20261117_01.public.json` | Content-reviewed public historical summary/evidence |
| `docs/implementation-contracts/P8-REF-0.1/git_checkpoint.json` | Historical B0 branch/count metadata; no credential/hostname |
| `tools/review_phase8b_b1a.py` | Forensic old-artifact validator; needs excluded raw archive; not a clean-clone test prerequisite |

## C. EXCLUDED —preserve locally

- .env, credentials/passwords/tokens, private.json, browser profiles and private fixture metadata.
- SQLite/command/provider/service ledgers; .local/, .cache/, PostgreSQL data/snapshots/volumes; .venv/, node_modules, dist/build/cache/binaries.
- Raw XML/log/HAR/trace/screenshots, unselected duplicate summaries and unrelated older-phase artifacts.
- docs/PHASE5_TEST_ENVIRONMENT.json; local .git/info/exclude; local handoff scan/dependency/exclusion inventories.

`PHASE8B_HANDOFF/EXCLUDED_PATHS.txt` is a local-only exact inventory of remaining visible untracked paths plus the held tracked environment file. Ignored private/runtime trees remain excluded by category, not recursively dumped. All files remain on disk. REQUIRED source/hash inputs are explicit exceptions to broad evidence-directory exclusion; no whole evidence directory is proposed.

## Static clone/reproduction dependency review

- Proposed set plus HEAD covers66 local Python import dependencies; zero uncovered imports/old179 input/B0 frozen input. AST inspection did not execute fixtures or clone the repository. No new package dependency.
- 0009 is REQUIRED;0001–0008, Alembic config, .env.example, requirements.in/requirements.lock.txt, deploy/compose.yaml, tests/conftest.py and existing helpers already tracked. All9 revision/down_revision links are covered.
- Old179 snapshot and the ignored Phase6 wrapper prevent otherwise real runner failures after clone. Exact543 collection and original/final source manifests are REQUIRED public path/hash metadata, not runtime fixtures.
- Current static entry point: `tools/validate_phase8b_b1a.py`. Frozen B0 validate_static.py is retained/imported; its old standalone zero-delta assertion is historical and is not the current B1a gate.
- `tools/verify_phase8b_ia01.py collect` produces exact543 selection; verification mode reads a fresh run folder plus committed hash inputs. summarize_phase8b.py works on new runs. OPTIONAL review_phase8b_b1a.py needs hardcoded old raw XML/logs retained locally and excluded from Git: this forensic archive check is not a fresh-clone prerequisite.
- Historical report links to excluded raw artifacts may be unavailable after clone. Fresh public source runners, not copied private runtime files, are the reproduction path.
- Existing Windows/PowerShell layout is the reviewed target. Frozen baseline contains Windows-style relative paths. Linux portability and an actual clean-clone/install/execution are NOT RUN.

### Safe fresh test setup —instructions only, not executed

Prepare a **new dedicated PostgreSQL17 test instance/database**, fresh secrets and project .venv using requirements.lock.txt. Never run bootstrap against current demo or overwrite existing .env. In a clean checkout only, configure private .env from the tracked example with matching fresh URLs/role passwords and required service/session keys.

Required variable names include DATABASE_ADMIN_URL, MIGRATION_DATABASE_URL, DATABASE_URL, MIGRATOR_PASSWORD, RUNTIME_PASSWORD, DEMO_ADMIN_PASSWORD, DEMO_CUSTOMER_PASSWORD, DEMO_TECHNICIAN_PASSWORD, DEMO_DEVICE_KEY_S01/S02; use the example for other required keys. No values belong in Git/logs. Verify the private URLs target the new TEST database.

Runner fingerprinting needs a fully initialized **fresh anchor schema** before tests create separate schemas. Initial seed is unverified simulation data, not physical-success proof. Do not use old README demo-migration commands without isolation.

```powershell
$env:PYTHONPATH = "services/backend"
$env:DATABASE_SCHEMA = "handoff_anchor_UNIQUE_LABEL"
# Only after verifying all private URLs target a newly prepared TEST database:
.venv/Scripts/python.exe tools/provision_database.py roles
.venv/Scripts/python.exe -m alembic -c services/backend/alembic.ini upgrade head
.venv/Scripts/python.exe tools/provision_database.py grants
.venv/Scripts/python.exe -m app.seed
# Always use NEW labels, never historical evidence folders:
.venv/Scripts/python.exe tools/validate_phase8b_b1a.py docs/PHASE8B_TESTS/NEW_STATIC.json
.venv/Scripts/python.exe tools/run_phase8b.py NEW_TARGET tests/test_phase8b_independent_review.py tests/test_phase8b_ia01_fix.py tests/test_phase8b_rereview.py -p phase8b_deadlock_capture
.venv/Scripts/python.exe tools/verify_phase8b_ia01.py collect docs/PHASE8B_TESTS/NEW_COLLECTION.json
$paths = (Get-Content docs/PHASE8B_TESTS/NEW_COLLECTION.json -Raw | ConvertFrom-Json).test_paths
& .venv/Scripts/python.exe tools/run_phase8b.py NEW_AFFECTED @paths -p phase8b_deadlock_capture
.venv/Scripts/python.exe tools/verify_phase8b_ia01.py NEW_AFFECTED
.venv/Scripts/python.exe tools/summarize_phase8b.py NEW_AFFECTED
```

Do not reinstall dependencies or mutate the current environment for this handoff. Fresh secrets are required locally, not historical private.json from Git. Retain unique runtime ledgers/evidence; never reset them to retry.

## Decision and remaining gates

**B1a USER ACCEPTANCE RECORDED — CURATED COMMIT READY FOR USER REVIEW.**

The62-path default plus any separately selected OPTIONAL files and the exact local-ignore exception require approval of a later staging action. This is not READY TO PUSH or automatic commit. No missing dependency in the proposed set, no blocking content finding, and no technical B1a acceptance blocker is reopened.

B1b requires a separate user task, positive current3-source no-delivery/certificate guards, preserved station/user/resource/session/fence order, no custody/Payment/holds/deadline change and increment-specific PG/race/real-process verification. Final MVP NFR04/NFR07/CT14/NFR08 stay OPEN. No next increment started.

## Final Git checkpoint

main/HEAD remains `de9b9288452f3c4e2b6703ed0ce641668ac8fc78`;11 tracked modifications,1396 untracked paths after creation of the final local scan report,0 staged. The only tracked modification outside the62-path proposal is `docs/PHASE5_TEST_ENVIRONMENT.json`. Accepted191/reviewer192 hashes remain unchanged; only acceptance/handoff documents were added/updated in this task. Read-only diff checks pass; no source change means no pytest rerun. The local scan JSON records per-path SHA256/size/Git status; approve explicit path sets before any later Git mutation.
