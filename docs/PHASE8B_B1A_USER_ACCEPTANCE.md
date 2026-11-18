# Phase 8B — Increment B1a user acceptance

**Decision: B1a ACCEPTED BY USER — 17/11/2026 (+07).**

## Approval provenance and boundary

The user explicitly approved “B1a ACCEPTED BY USER — ngày17/11/2026” in the attached request **PHASE8B — B1a USER ACCEPTANCE & SAFE GIT HANDOFF**, section “Người dùng đã chính thức phê duyệt”. This records approval in the collaboration session; it is not a lecturer signature, a whole-team sign-off or an approval inferred from a Codex-generated prompt/report.

Accepted scope: **Increment B1a Refund Foundation** on frozen B0/P8-REF-0.1/P8-REC-0.3, with D01/D02 approved. This includes schema/migration/grants, strict public Refund API/domain/audit foundation and reviewed shared station/Technician authorization fixes. Positive eligibility, refund processing/provider effects and full FR16/TC16/CT13 remain unfinished beyond this slice.

## Accepted source and evidence checkpoint

- Branch main/base HEAD`de9b9288452f3c4e2b6703ed0ce641668ac8fc78`; accepted work remains in the working tree, not committed by this decision.
- Final affected source:191 entries in `PHASE8B_TESTS/b1a_ia01_affected_20261117_04/source_before.json` and `source_after.json`, equal before/after/current. Historical179 is an older comparison input with explicitly reviewed deltas, not a claim of unchanged179 source.
- Independent re-review:192 entries in `PHASE8B_TESTS/b1a_rereview_20261117_01/source_before.json`/`source_after.json`: the same191 plus the new six-probe reviewer test. Current hashes rechecked without delta.
- [Independent re-review](PHASE8B_B1A_INDEPENDENT_REREVIEW.md): **PASSED — RECOMMENDED FOR USER ACCEPTANCE**, now followed by this explicit user decision. Prior FAILED/BLOCKED reports remain historical and are not rewritten.

## Accepted gates

| Gate | Evidence and status |
|---|---|
| B0 contracts / decisions | Frozen B0; D01 provider-authorized FAILED retry and D02 read-only VERIFY_NO_DELIVERY approved |
| P8B-B1A-01 | FIXED/CLOSED technical scope; original deadlock probe, FK compatibility and both transaction orders independently confirmed |
| P8B-B1A-IA01 | FIXED/CLOSED technical scope; original failures403/no mutation/audit/receipt, authority-first serialization, current role/session/scope protection |
| Independent reviewer |16 Passed,0 Failed/Errors/Skipped,exit0; six new probes, raw/redacted JUnit and exit present |
| Affected regression |543 Passed,exit0 on final source; exact543 IDs and old192 retained; artifacts verified by re-review, **not rerun in this acceptance/handoff** |
| Targeted remediation |37 final/42 earlier Passed, overlap explicitly preserved; not summed |
| Static contracts |77 checks/34 definitions,exit0, baseline/frozen overlays unchanged |
| Data and locks | No unauthorized mutation/audit/receipt or captured40P01 in verified scope; eight-table demo fingerprint and revision0002 unchanged |

Primary public references: [review validation](PHASE8B_TESTS/b1a_rereview_validation_20261117_01.public.json), [historical artifact reconciliation](PHASE8B_TESTS/b1a_rereview_artifacts_20261117_01.public.json), [review summary](PHASE8B_TESTS/b1a_rereview_20261117_01/summary.public.json), [affected summary](PHASE8B_TESTS/b1a_ia01_affected_20261117_04/summary.public.json), [static result](PHASE8B_TESTS/b1a_rereview_static_20261117_01.json). Raw logs/XML/fixture metadata remain local and are not automatically approved for Git.

## Residuals / not accepted

- B1b NOT STARTED; B2–B5 NOT STARTED. No positive no-delivery certificate issuer/redemption, Refund dispatch/provider effects/query/callback or permitted FAILED retry execution. Missing-certificate refusal remains intentional fail-closed B1a behavior.
- Full Backend collection/new Browser/two-OS-provider E2E were not run in re-review/acceptance; ASGI/native PG tests do not substitute for those labels. This approval does not complete full Phase8B, TC16/CT13, Phase8C or the MVP.
- No universal deadlock/authorization proof for arbitrary owner SQL, new direct/background callers, future station identity mutations or mixed binaries. New mutation entry points must preserve protected user/resource/session order and exact authority checks.
- Eight-table demo hashes are not whole-DB/ledger backup evidence. Phase8A remains CONDITIONAL ACCEPTANCE APPROVED BY USER. NFR04, NFR07/CT14 and NFR08 remain OPEN/NOT RUN before full MVP release, with existing owners/criteria unchanged.

## Conditions before B1b

The user must explicitly assign B1b; this acceptance/handoff does not start it. Preserve approved B0 semantics, charge/refund separation, custody/holds/fences, P6/P7/8A fixes and original failing evidence. Review B1b's positive/current no-delivery evidence/certificate, late role/session/boot/freshness/version guards and cross-module serialization before implementation. Add targeted native PostgreSQL/concurrency and real-process proof paths with actual model evidence; never turn UNKNOWN/PREPARED/empty-slot/ACK into no-effect or fake eligibility. Financial/provider work remains in its assigned later increment.

## Git handoff authorization

This turn authorizes documentation and read-only integrity/security/dependency checks only. [Curated manifest](PHASE8B_B0_B1A_COMMIT_MANIFEST.md) is a proposal for later user review. **No file is staged, committed or pushed by this acceptance.** No source, schema, ledger, volume, private file or evidence is removed or reset.
