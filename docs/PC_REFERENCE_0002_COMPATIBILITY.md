# PC reference 0002 provisioning compatibility

Implementation checkpoint, 21/11/2026 (+07). **Awaiting independent review.**
Original transfer HEAD: `e005ef6f69f6e0b731315d94e6be29c0428326d2`, branch
`wip/phase8b-b1b-transfer-20261119`. The provisioning delta is distinct from that
transfer baseline. No historical manifest/hash or frozen contract is updated.

## Scope and interface

Only `tools/provision_database.py`, `tests/test_provision_database.py`, and this
document change. Migration 0001–0010, seed, runner, environment files, business
logic, EOL policy, and contracts are unchanged. Real `doi_pin` reference creation
and changes to `pc_dev_b1b` are not authorized by this checkpoint.

Existing CLI remains `python tools/provision_database.py roles|grants`.
`grants` defaults to `--profile runtime`. The new explicit
`grants --profile reference-readonly` is restricted to revision
`0002_user_approval`. Both use the selected `DATABASE_SCHEMA` and the local
`DATABASE_ADMIN_URL`; connection parameters and driver exceptions are not printed.
The `roles` stage preserves existing credentials, checks ownership/role authority,
and never grants runtime schema CREATE or role membership.

## Revision/object/privilege plan

All table targets and column inventories are explicit constants, independent of
catalog discovery. Every supported plan includes SELECT on its known tables and
`alembic_version`. No blanket ALL TABLES/ALL PRIVILEGES/default ACL grants are used.

| Revision | Objects and runtime changes |
|---|---|
| 0002 | 24 baseline tables plus `alembic_version`; policy `approval_evidence`, audit append-only trigger. No `recovery_cases.operation_id`. |
| 0003–0008 | Historical introduction of Recovery operations/attestations, authorizations, inbox, ACKs, activations and closure tables. `operation_id` starts at 0003. These intermediate revisions are deliberately not supported grant targets in this checkpoint. |
| 0009 | Baseline + all eight Recovery tables + refund attempts/permissions/permit redemptions and two certificate tables. Runtime certificate/redemption SELECT only. |
| 0010 | Adds certificate issuer columns and revocations. Runtime certificate/redemption/revocation SELECT+INSERT, never UPDATE/DELETE. |

Runtime plans preserve the prior effective 0010 table-level INSERT/UPDATE grants
for identity/assets/device/QR/swap/payment/outbox tables; the earlier narrow UPDATE
statements on swaps/alerts were already covered by full-table UPDATE. Assignments
retain DELETE. Telemetry and audit retain INSERT only beyond SELECT. Recovery cases
retain INSERT and an explicit UPDATE column list (adding `operation_id` only in
0009/0010 plans); operations only update `consumed_at/cancelled_at`; authorizations
only update `revoked_at`. Refunds from 0009 have INSERT and UPDATE only on
`state/version/provider_reference/verified_at`. Immutable proof/permit tables retain
INSERT only beyond SELECT. `demo_policies` and `alembic_version` remain SELECT only.

The reference-readonly plan grants runtime only schema USAGE and SELECT on the 25
known 0002 tables (including Alembic). It grants no table or column writes,
TRUNCATE, REFERENCES, TRIGGER, MAINTAIN, grant options, ownership or DDL. Seed does
not use runtime; it uses the migrator/owner through official `app.seed`.

## Preflight and failure behavior

Before the first GRANT, the selected schema must belong to `doi_pin_migrator`.
Application roles must be LOGIN, non-superuser, without CREATEDB/CREATEROLE,
REPLICATION, BYPASSRLS or inherited role memberships. The schema-qualified
`alembic_version` must contain exactly one supported revision.

Table names, ordinary-table kind, table ownership, and exact column-name sets must
match the revision allowlist. Extra tables/views/sequences and missing/extra columns
refuse provisioning. Constraints must be validated and FKs stay within the schema.
The enabled audit row BEFORE UPDATE/DELETE trigger must bind the local
`reject_audit_change` function. Owner default ACL entries at global/selected-schema
scope are refused for explicit review rather than silently changed.

Effective table and column privileges (including PUBLIC/inherited rights and grant
options) must be subsets of the selected plan. Runtime schema CREATE and owner
authority are refused. Missing allowed privileges can be added; excess privileges
cause refusal without REVOKE. In particular, switching an existing writable schema
to reference-readonly refuses drift instead of downgrading rights silently.

Caller-owned transaction encloses validation and all GRANTs. The CLI uses
`engine.begin()`; errors roll back the whole stage. Revision row/table locks protect
the operation from competing row/DDL changes. Local administration must still be
serialized: this tool is not a security boundary against a concurrent database
superuser or migrator intentionally changing privileges/functions.

Catalog checks validate grant compatibility, not every SQL type, constraint body,
index definition, or trigger function body against source. Frozen migration/source
integrity and independent review remain necessary; this does not certify arbitrary
manually modified databases as equivalent to official migration history.

## Isolated verification

The test module requires `PC_PROVISIONING_REVIEW=1`, explicitly validates the PC
database endpoint `127.0.0.1:5433/doi_pin`, and uses only fresh `pcprov_<uuid>` names.
It does not request the repository `environment` fixture and therefore does not
create `phase5_test_*` schemas. All schemas and sanitized stage logs are retained.

Coverage includes official Alembic migrations to 0002/0009/0010; official owner
seed/idempotency and runner `demo(schema)` fingerprint reads at 0002; runtime real
permission refusals with SQLSTATE 42501; audit row trigger enforcement as owner;
effective 0010 table/column comparison with unchanged development; 0009 certificate
write refusal; idempotent grants; malformed/unknown revision and profile refusal;
missing/renamed columns/tables, wrong owners, extra table, disabled audit trigger,
table/column/PUBLIC/grant-option/schema CREATE drift; and real PostgreSQL GRANT
failure injected after prior successful statements to verify transaction rollback.

Permission failures use valid targets/columns and assert privilege SQLSTATE rather
than relying on missing rows or constraint violations. Negative DDL/catalog mutations
are confined to the newly created test schemas and retained for review.

Legacy run01 evidence on this PC is preserved at
`.local/pc-b1b/reference-compat-implementation/`. It is never a new-run output
target. Its 20 Passed result is inherited evidence, not a new independent execution.
The incidental `docs/PHASE8A_NFR06_AUDIT_COVERAGE.json` was explicitly accepted for
retention only; it does not demonstrate NFR06/B1b coverage PASS.

### P1/P2 evidence isolation correction (static-only checkpoint)

The supported **future, separately authorized** invocation is the module launcher:

```powershell
# Do not execute until a new verification run is explicitly approved.
$env:PC_PROVISIONING_REVIEW = '1'
.venv/Scripts/python.exe -B tests/test_provision_database.py
```

The launcher reserves
`.local/pc-b1b/reference-compat-runs/<uuid-hex>/` using exclusive `mkdir` before
opening a log, writing snapshots, connecting to PostgreSQL, or invoking pytest.
An optional `--run-id <32 lowercase hex characters>` permits reproducible selection;
an existing directory or UUID collision is an error, never a request to reuse it.
The launcher prints the exact run ID/path and stores `run.json` with creation time,
Git HEAD, source hashes and a per-invocation token. Timestamps are provenance, not
the uniqueness mechanism. No reservation happens during import or collection.

`pytest.log`, `results.xml`, `pytest-tmp`, protected snapshots and all fixture
artifacts belong to that exclusively reserved directory. Every application-owned
JSON/log write uses exclusive creation, not `write_text` replacement. The JUnit
path is passed only after reserving the fresh directory; the fixture validates the
path and absence of a prior result. A claim file permits only one fixture binding.
Direct ad-hoc pytest invocation is not the supported evidence path: arbitrary CLI
output destinations cannot be protected by this module against deliberate bypass.

The launcher starts only this module with `--noconftest -p no:cacheprovider`, disables
third-party plugin autoload, clears `PYTEST_PLUGINS`/`PYTEST_ADDOPTS`, and passes the
validated local `.env` values to its child. The fixture requires these isolation
conditions, a fresh run claim and the launcher's new protected snapshot. It has no
dependency on repository conftest fixtures. The launcher never calls Compose or
starts/stops database services.

Before each schema CREATE, an immutable numbered event records the candidate UUID,
run ID, intended revision/profile and pending state. The fixture performs exclusive
`CREATE SCHEMA ... AUTHORIZATION doi_pin_migrator` **without IF NOT EXISTS**. Only
successful completion grants current-run ownership. The official roles/migration/
seed/grants commands run only for such confirmed schemas. Duplicate schema errors
are marked not-created; ambiguous connection loss stays unknown and must not be
interpreted as ownership. There is no collision adoption, retry against an existing
schema, or cleanup path.

Numbered event files are exclusive, flushed and fsynced before proceeding. Stage
failures record secret-free error types and partial state immediately, even before
fixture teardown. A hard process kill may leave only the event prefix: a pending
candidate requires manual catalog review and cannot be adopted automatically.
`schemas.json` is written once during finalization from this invocation's records.
`retained_schemas.json` contains only its confirmed owned names, exact-name catalog
observations and separately labelled unknown candidates. No prefix-wide query
assigns schemas from run01 or another invocation to the current run.

All schemas are retained, including partial/negative fixtures. Teardown never
drops, recreates, truncates, or repairs schema contents; it only reads exact names
and writes new-run evidence. Existing negative-privilege and atomicity assertions
remain in place. The launcher additionally compares protected development data/
effective privileges, application role attributes, `.env`, incidental audit hash,
and every legacy run01 file before/after the future run.

This correction is syntax/static review only. No reservation, launcher execution,
pytest collection/test, failure injection, schema creation, migration or seed is
performed in this checkpoint. Collision handling, partial-failure behavior and
end-to-end launcher integration remain **NOT VERIFIED by execution**, pending
independent review and explicit rerun approval.

## Future reference initialization — not executed

After separate authorization: verify `doi_pin` absent; use `roles` with process-local
`DATABASE_SCHEMA=doi_pin`; run Alembic `upgrade 0002_user_approval` as migrator; seed
with `python -m app.seed`; apply `grants --profile reference-readonly`; verify runtime
read-only fingerprint twice, revision, counts, privileges, and unchanged development.
Set `PYTHONPATH=services/backend` and load local environment without printing secrets.
Do not change the default `.env`, use `upgrade head` or `tools/dev.ps1 migrate` for
reference, invent revision rows, or alter migration history.

Keep reference out of API/worker mutation targets. Development processes explicitly
select `pc_dev_b1b`; test fixtures select their own schemas before provisioning.
The official runner fingerprints only eight tables, not all reference data. For
broader preservation, compare all reference-table data digests and catalog snapshots
before/after. Admin/migrator credentials remain able to mutate owned schemas if
misrouted; shared roles are not complete isolation between schemas.

## Unchanged gates

No real reference schema has been created or seeded. No full Backend/Browser tests,
Refund provider effects, B2–B5, independent review, Git staging/commit/push or cleanup.
The 78 EOL hash differences, Node24/Chromium gaps, and incomplete interrupted laptop
803/12F evidence remain separate unresolved gates. No cache/evidence/schema is
automatically deleted. Preserve `.env`, existing volume, test schemas and evidence.
