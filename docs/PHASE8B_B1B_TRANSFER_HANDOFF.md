# B1b PC transfer checkpoint — 19/11/2026 (+07)

**WIP / PARTIAL — NOT ACCEPTED.** User authorized only curated WIP branch/commit/push for transfer. Approved main remains 0024c5f2ddac4c1652e77dcff2acf48fd791b8e0. Target branch: wip/phase8b-b1b-transfer-20261119. Obtain exact transfer commit with git rev-parse HEAD after checkout; source hashes are in PHASE8B_HANDOFF/b1b_transfer_20261119/SOURCE_SHA256.json. No Refund provider dispatch or compensation is implemented.

## Implemented

Strict P8-REC-0.3 VERIFY_NO_DELIVERY DTO/API unions, migration0010 after0009, SQLite complete-history journal/fence/readonly receipt, current independent Simulator/Technician/Customer proof, certificate issuance/revocation, protected Admin first intent, generation0 registry, certificate redemption, inert REFUND outbox, atomic before/after audits. Charge stays SUCCEEDED; old obligation, custody and three holds are preserved. No UI or dependencies changed. Existing legacy internal Refund refusal method remains; public POST uses protected_request/first_intent.

## Actual verification

- Final targeted: b1b_terminal_fence_20261119_02 —97 Passed, exit0, unchanged source during run, unchanged demo eight-table fingerprint.
- Six final-source real-process runners: b1b_guard_a, b1b_guard_b, b1b_guard_c_expiry, b1b_guard_d_precommit, b1b_guard_e_inbox, b1b_guard_e_intent_first (all suffix _20261119_01) — all exit0. They cover A–E, actual OS precommit kill/rollback, successor at real120s expiry, inbox/projection ordering, durable fencing and zero new effects.
- Earlier real-process competing DECIDE, CONFIRM/REJECT, lost response after committed intent and authorization/logout/assignment orders passed separately. Do not add overlapping check counts. Older precommit kill evidence before Windows venv PID correction is insufficient; corrected runs explicitly matched actual interpreter PID. Test-only gates are confined to tools/smoke_phase8b_b1b.py.
- Audit validator observed all8 frozen B1b actions, exact before/after values and redaction on real isolated fixtures. Frontend39 Recovery tests +1 reporter test and TypeScript/Vite build exit0. Browser POST/settlement, successor and closure ran on real Chromium:3 Passed before final0.3-only fence correction; this is inherited legacy evidence, not final-source Browser execution after that correction.
- Collection before last two fence tests:801,95 B1b cases, all603 historical case identities retained (two UUID-generated parameter IDs need identity normalization). Last two tests imply a delta, but final collection must be rerun; do not assume its result.
- Full run01: deliberately INTERRUPTED for required fence correction; no final JUnit/exit, not a pass. Full run02 was launched after six E2E gates. Transfer preflight found no matching runner, no final JUnit or exit. Record **INTERRUPTED / final outcome UNKNOWN**, cause not established. No completed full Backend regression on this final B1b source. Historical543/603 are not current results.

All raw runs, credentials and ledgers remain only on the laptop. Fresh clone cannot inspect those local logs; reproduce using the committed runners. Portable static checker now references the curated tracked-source baseline, not laptop-private PHASE5 environment metadata. This tooling-only transfer delta has separate static verification; it does not turn earlier tests into new executions.

## Findings and remaining gates

Fixed during implementation: UTC context wire hash mismatch; retained SQLite UDF binding/sequence; UPDATE-privileged certificate row mark; immutable receipt dispatch before source processing; accepted UNKNOWN ACK after NACK; cached QUEUED source disposition after restart; station fence loss from consumed/cancelled metadata. Last finding reproduced in two unchanged failing assertions, then passed in97-test group. Backend now retains0.3 exclusivity without an approved durable release and prioritizes the current successor pointer. Unsupported terminal metadata was an adversarial storage fixture, not a legal release API or physical proof.

No known unresolved reproduced payment/custody Major in the verified subset. **G8/G9 and independent review remain OPEN:** rerun collection, targeted on transfer checkout, full Backend suite with final source freeze/JUnit/exit, validate all8 audit actions on newly generated fixtures, assess affected Browser after final guard, review complete G1–G9 matrix. Do not claim B1b accepted or begin B2–B5. B0 contracts remain frozen; Phase8A conditional acceptance and final-MVP NFR04/NFR07/CT14/NFR08 OPEN gates are unchanged.

## Fresh PC setup and commands (PowerShell)

Use core.autocrlf=input for the verified byte mode. No dependency installation or migration occurs merely by cloning.

```powershell
git -c core.autocrlf=input clone --branch wip/phase8b-b1b-transfer-20261119 --single-branch https://github.com/AnhDucEndy/doi-pin-thong-minh.git
cd doi-pin-thong-minh
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r services/backend/requirements.txt
cd apps/web
npm ci
cd ../..
```

Read AGENTS.md, doi-pin-giai-doan-2/CODEX_START_HERE.md, handoff/CODEX_HANDOFF.md, B1b review/test plan and frozen overlays first. Use .env.example and README for fresh local configuration. Required private names include DATABASE_URL, MIGRATION_DATABASE_URL, DATABASE_ADMIN_URL, DATABASE_SCHEMA, DEMO_ADMIN_PASSWORD, DEMO_CUSTOMER_PASSWORD, DEMO_TECHNICIAN_PASSWORD, DEMO_DEVICE_KEY_S01/S02, PAYMENT_MOCK_URL, PAYMENT_SERVICE_KEY, PAYMENT_CALLBACK_KEY and PAYMENT_LEDGER_PATH. Verify actual names in config/.env.example before provisioning. Generate new local values; never paste laptop secrets into Git. Install Docker Desktop/PostgreSQL using the repository dev compose instructions; do not copy live PostgreSQL volume files as a backup.

Migration head in source is0010_no_delivery_eligibility; laptop demo stayed0002_user_approval. Test runner generates isolated phase5_test schemas and routes PHASE5 reports. Never migrate demo just to run tests.

```powershell
.venv/Scripts/python tools/run_phase8b.py PC_UNIQUE_TARGET tests/test_phase8b_b1b_contract.py tests/test_phase8b_b1b_migration.py tests/test_phase8b_b1b_ledger.py tests/test_phase8b_b1b_no_delivery.py tests/test_phase8b_b1b_certificate.py tests/test_phase8b_b1b_refund.py tests/test_phase8b_b1b_races.py
.venv/Scripts/python tools/run_phase8b.py PC_UNIQUE_A script tools/smoke_phase8b_b1b.py --scenario A
.venv/Scripts/python tools/validate_phase8b_b1b.py PC_UNIQUE_STATIC.json
.venv/Scripts/python tools/run_phase8b.py PC_UNIQUE_FULL
```

Run PostgreSQL suites sequentially: advisory locks may contend across schemas. Labels/output must be new. Real runner scenarios are enumerated in smoke_phase8b_b1b.py; retained fixture labels can be supplied to the static validator for read-only8-action audit checks. Full run must not use --lf, skip or xfail to force success. Evidence/raw runtime is retained, not auto-cleaned.

Backend command after explicitly selecting a fresh configured development schema: .venv/Scripts/python -m uvicorn app.main:create_app --factory (set PYTHONPATH=services/backend). Workers: python -m app.workers.device and python -m app.workers.payment with the same schema. The charge worker never processes REFUND jobs. Frontend: npm run dev under apps/web. Prefer smoke_phase8b_b1b.py for authenticated simulator/charge setup; it creates isolated ledgers and performs lawful model/API steps. Never SQL-update custody/proof/NO to stage success. See Browser manual for optional legacy regression; managed Chromium may need installation on the new PC, without reusing another user's Browser profile.

## Resume prompt for the new Codex account

Continue B1b from this WIP branch. Read this handoff and AGENTS.md. Do not redo implementation or alter frozen contracts. Verify source hashes, dependencies and fresh PostgreSQL readiness. Recover/reproduce the97 targeted tests and six A–E guard runners; collect actual test count (last two fence tests were added after801 collection). Run one complete Backend regression on final source and validate audit/Browser impact. Full laptop run02 has no final result and must not be called Passed. Preserve payment/custody/holds/deadlines/fence and all evidence; no provider Refund, B2–B5, commit/push or user acceptance without separate authorization.

## Local/private material not in Git

Back up separately only if needed: .env, .local, .cache runtime private.json/ledgers, docs/PHASE8B_TESTS raw logs/XML/JSON/screenshots and other historical test evidence, local PHASE5_TEST_ENVIRONMENT.json modification, Docker/PostgreSQL data via an approved coordinated backup. Never publish credentials or copy a running volume as a valid backup. Build/cache such as dist/node_modules/__pycache__ can be regenerated; .cache contains durable evidence and must not be blanket-deleted.
