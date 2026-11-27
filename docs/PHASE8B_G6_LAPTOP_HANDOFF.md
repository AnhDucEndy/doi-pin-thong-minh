# Phase 8B B1b — G6 laptop handoff

27/11/2026 (+07). **WIP, not Accepted. G5/G6/G7/G9 OPEN.**

Parent checkpoint: `393de5d64cae9b8c7f19669bb8267ea7b049c447`.
The portable checkpoint is the commit adding this document; use its SHA from the
PC handoff result and verify `git rev-parse HEAD` after synchronization. Remote:
`AnhDucEndy/doi-pin-thong-minh`, branch `wip/phase8b-b1b-transfer-20261119`.

## Scope and provenance

`tools/g6_acceptance/` contains explicit Windows guard controls and read-only API
startup tooling. Importing the package, coordinator, API helper or process probe
does not launch an API, a database or a business workflow. No Docker/provisioning
command is implemented by this package. It is **not a G6 business runner**.

Portable verification on PC27/11: 9/9 focused guard controls PASS, exit0, guard
enabled, zero API/DB/business executions; 10 syntax/import/configuration/path/
provenance checks PASS. Raw verification remains ignored on PC. These results do
not verify actual API startup or G6 acceptance on the laptop.

The socketpair and process-exit repair originated in the PC ignored recovery
harness. Its accepted guard SHA256 was
`a460dcd8c63b557cf203f46adb5a0deed5701101bc1ef1ddfc3c9224d971446d`.
The PC focused result was 9/9 PASS with guard enabled. Earlier ERROR/TIMEOUT
development probes remain separate, preserved evidence. Portability changes
parameterize paths/DB identity/protected ports and add explicit CLI configuration;
the exact stdlib caller, socket identities, scoped socketpair permission, network
denials, readonly DB policy and exit checks remain required. A different Python
socketpair implementation fails closed and needs review.

Historical Backend805/805, IPC and Browser A–E evidence remains historical. The
real API startup smoke has **NOT RUN**. C-expiry failed at fixture startup before
business execution; E-inbox has **NOT RUN**. No completed G6 business workflow.
The API helper/health-only supervisor is prepared source, not a readiness PASS.

## Laptop prerequisites and entrypoints

1. Inspect laptop Git status, branch, dependencies and existing Docker projects,
   volumes, schemas and ledgers. Preserve old laptop data/evidence. If dirty or
   diverged, stop; do not reset, clean, rebase or overwrite files.
2. With a safe working tree, fetch the WIP branch and use a fast-forward-only
   update. If the local branch does not exist, create a tracking branch from the
   remote after inspecting existing branches. Verify the exact handoff SHA.
3. Use Windows CPython3.12 and the project `.venv`/`requirements.lock.txt`; verify
   `pip check`. The PC control run used CPython3.12.10 and Uvicorn0.54.0.
   Node/Playwright/Browser are not needed for these controls or startup.
4. Inventory protected ports explicitly. All outputs must be **new**, Git-ignored
   directories under the checkout's `.local/`; collisions fail closed.

Focused controls use fresh synthetic DB URLs and never connect to PostgreSQL:

```powershell
.venv/Scripts/python.exe -B tools/g6_acceptance/coordinate.py controls --help
# Repeat --protected-port for the actual protected database ports discovered here.
# Select a NEW output directory; no automatic retry or overwriting old evidence.
```

For the separately authorized API startup, copy
`tools/g6_acceptance/config.example.json` to a **new ignored** local configuration
file. Fill every null and the complete protected-port inventory from laptop
inspection. `env_file` is relative to the checkout root and must be Git ignored;
it supplies explicit test-only `DATABASE_ADMIN_URL`, `MIGRATION_DATABASE_URL` and
`DATABASE_URL`, matching postgres/migrator/runtime roles and the chosen database.
Never copy PC credentials or use the original laptop database as a test target.

An already approved isolated `phase5_test_<12 hex>` fixture at revision0010 must
exist. Prepare a separate test environment only with explicit authorization after
checking old resources. The harness does not migrate, seed, start or create it.
The template deliberately fails closed until configured. The API entrypoint is:

```powershell
.venv/Scripts/python.exe -B tools/g6_acceptance/coordinate.py api --help
# After startup-only authorization and configuration:
# ... coordinate.py api --config .local/g6-laptop/config.json --output .local/g6-laptop/NEW_STARTUP_ID
```

API mode verifies the configured PostgreSQL system identifier/schema revision
read-only before one actual `app.main:create_app`/Uvicorn invocation. Child
connections force transaction-read-only and the selected test search_path.
The supervisor checks only its owned `/health`, writes an identity-bound stop
record, waits for the real exit and compares audit counts. The server has a 30s
deadline; process failures are retained and not automatically retried. A health
response/controller exit alone cannot establish G6 acceptance. This is a scoped
startup check, not a whole-database backup or a firewall against malicious Python.

## Eight-action matrix and next business batch

| Action | Existing accessible PC rows | G6 status / proposed workflow |
|---|---:|---|
| ND_OPERATION_CREATED | 4 | PARTIAL; retain existing proof |
| ND_SUCCESSOR_LINKED | 0 | MISSING; C-expiry |
| ND_INSPECTION_ACCEPTED | 4 | PARTIAL; retain existing proof |
| ND_HUMAN_ATTESTED | 8 | PARTIAL; retain existing proof |
| ND_CERTIFICATE_ISSUED | 0 | MISSING; C-expiry / E-inbox |
| ND_CERTIFICATE_REVOKED | 0 | MISSING; E-inbox |
| ND_CERTIFICATE_REDEEMED | 0 | MISSING; C-expiry |
| REFUND_REQUEST_CREATED | 0 | MISSING; C-expiry, REQUESTED/inert outbox only |

Two legitimate workflows can produce the five missing action names; that does
not close G6 until raw before/after, child/version/actor/correlation, redaction,
append-only and transaction/replay evidence is independently validated. Reuse
the 16 retained rows and 13 compatible historical tests where provenance permits.
Laptop does not inherit PC raw evidence merely by pulling Git.

Already tracked and unchanged: `tools/smoke_phase8b_b1b.py`,
`tools/validate_phase8b_b1b.py`, `tools/provision_database.py`,
`tools/run_phase8b.py`, B1b tests, migrations and frozen contracts. Do not duplicate
them. Future business execution needs separate approval and an isolated runner
with fresh schemas/ledgers; do not disable the startup guard to run business APIs.
Do not rerun Backend805/Browser/IPC or begin G5/G7/G9 automatically.

## PC resources and evidence stay on PC

PC cluster `127.0.0.1:5448`, system identifier `7712160968488140838`, is **not a
laptop prerequisite and does not exist there by default**. Do not reuse a prompt
to restore PC container5448 on the laptop. Never copy/mount its database through
Git, and do not assume a laptop port/container/volume has the same identity.

Keep all retained PC clusters/volumes and `.env`/private configuration unchanged.
Preserve the ignored G6 audit/recovery directories, all historical Backend/IPC/
Browser evidence, failed probes, raw JUnit/logs, hashes and ledgers. None is part
of this Git handoff. Incidental `PHASE8A_NFR06_AUDIT_COVERAGE.json` stays untracked
and is not B1b G6 coverage PASS. No ZIP, raw evidence, credentials or DB dump is
published. **Next task: authorized API startup smoke against a laptop test DB.**
