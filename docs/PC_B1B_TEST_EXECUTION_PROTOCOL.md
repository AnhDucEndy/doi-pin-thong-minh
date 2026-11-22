# PC B1b supervised execution protocol

Tooling-only checkpoint, 21/11/2026 (+07). B1b remains WIP/not accepted. Original
HEAD is e005ef6f69f6e0b731315d94e6be29c0428326d2. Historical 803/12F laptop run
b1b_full_20261120_01 is INTERRUPTED/outcome UNKNOWN, never a pass.

## Explicit profiles

`python -B tools/run_phase8b.py LABEL --profile business [tests/MODULE.py::NODE]`
selects every top-level test_*.py business module, excluding only:

* tests/test_provision_database.py: separate compatibility launcher and run identity.
* tests/test_phase8b_tooling.py: separate synthetic tooling profile.

The exclusion reasons and exact collected node IDs are written to collected.json.
No skip/xfail, -k, --lf, deselection or arbitrary plugin arguments are introduced.
Targets must belong to the selected module set. Actual counts are measured, not
assumed to remain 803. `--profile tooling` selects only the new synthetic module
and uses --noconftest. `--profile compatibility` refuses and names its dedicated
launcher. Business keeps conftest and its audit assertions. Collection-only adds
--collect-only; it does not execute fixtures, migrations or test bodies.

## Output and process boundary

All run directories are exclusive `.local/pc-b1b/b1b-harness-LABEL` directories;
an absent label generates UUID hex. No reuse/cleanup/overwrite of an existing run.
Supervisor records RUNNING before preflight/tests, pins local PC URLs, snapshots
all existing non-system schemas (reference, development and retained fixtures),
data digests, ownership/ACL/column inventory/functions, roles/memberships/defaults,
source hashes and protected evidence hashes. No credentials/row contents are
included in snapshots. Existing source/fixture/evidence must be unchanged after.
New schemas are accepted only under explicit historical fixture prefixes; names
outside that set fail post-check. Existing schemas cannot be replaced by this rule.

One child runs pytest with plugin autoload disabled, cache disabled, fresh temp,
log and JUnit paths. In-process writes via Python builtins.open/io.open/Path.open
outside the run are denied; docs reports are redirected under run/reports. This
routes conftest PHASE5_TEST_ENVIRONMENT and recovery_audit_checks session output
without replacing accepted historical artifacts. Collection and per-node outcome
events are fsynced so a future failure can be mapped to its test ID/phase.

This is not an OS sandbox: direct OS syscalls, mkdir/deletion APIs, native modules
and independently launched subprocesses are not universally intercepted. Source
and protected-state post-checks detect drift, but do not undo damage. The current
authorization covers synthetic tests and one collection only. Before process-based
domain tests, review their outputs/child environment and use a dedicated supervised
adapter. Legacy `script smoke_phase8b_b1b.py` dispatch is deliberately refused by
this pytest-only supervisor; no physical/financial effects are added. No claim of
universal subprocess confinement is made.

## Journal semantics

Append-only journal_NNNN.json records are exclusive, flushed and fsynced. They
contain profile, timestamps, HEAD, exact child command/PID, stage and observed exit.
COMPLETED means child exited AND mandatory post-checks passed; passed is true only
for exit zero. A normal failed test can be COMPLETED with passed=false.
Post-check/preflight errors yield UNKNOWN; KeyboardInterrupt yields INTERRUPTED.
Owned child termination is bounded and never implies all descendants were cleaned.
Hard kill/power failure may leave RUNNING and no exit.json: `--status PATH` reports
UNKNOWN, never PASS, and never edits/reuses the stale directory. Filesystem fsync
is best-effort durability, not a guarantee against storage/controller power loss.
artifacts.json lists hashes excluding itself. Keep every partial log/schema/ledger.

## EOL portability

Only tools/validate_phase8b_b1b.py changes. A pinned list of 78 reviewed paths can
reproduce the original immutable SHA256 through LF/CRLF conversion in memory.
It reports RAW_MATCH, HISTORICAL_EOL_EQUIVALENT, APPROVED_CONTENT_DELTA or
UNEXPECTED_CONTENT_DELTA. Mixed EOL/lone CR refuses; UTF-8 decoding is strict;
BOM/whitespace/comments/content are never stripped. No disk normalization or
expected hash edits. Frozen normative contracts and prior overlays remain raw
strict, as do out-of-allowlist EOL differences. Explicit current tooling deltas are
reported as content deltas, not disguised as original source matches. Git status
must be entirely within approved paths plus the accepted incidental audit file.

## Bounded verification in this checkpoint

Only syntax, synthetic tooling tests, controlled static verification and one
business collection are authorized. Every execution uses a new ignored evidence
directory. No domain/race tests, Browser, provider effects, migrations/seed or
full regression. Synthetic interruption uses a fake child, never kills a real
service. Collision tests use only temporary paths. Do not waive failures or
adjust domain assertions. Independent review and new authorization precede the
first contract/migration/ledger B1b diagnostic group. A later journal node_events
file is diagnostic evidence; it cannot retroactively diagnose the laptop's 12 F.

Preserve reference doi_pin at 0002, pc_dev_b1b at 0010, forty pcprov schemas,
all run01/run02/reference-init evidence, .env and incidental audit file. No Git
stage/commit/push/reset/restore/clean or automatic evidence/cache/schema deletion.

## Round 2: separately authorized physical PostgreSQL isolation

The later Round 2 authorization supersedes the collection-only execution limit
above for exactly the ten nodes in `MIGRATION_TARGETS`. Use the business runner
with `--isolation ABSOLUTE_INSTANCE_JSON` and all ten exact targets. No original
fixture, provisioning implementation, migration or business assertion changes.

Create a fresh Compose project/container/volume/network on 127.0.0.1:5434 with
independent random admin/migrator/runtime passwords in an ignored private.env.
The original protected instance stays at 5433. Pin the official postgres image
digest; keep private configuration separate from public test-run artifacts.
The identity JSON records container/network IDs, sole named data volume/source,
loopback binding, and authenticated pg_control_system system_identifier, distinct
from the protected cluster. The supervisor rechecks container/mount/network and
database identity before and after execution. A cluster with existing application
schemas is refused for a new batch. No reference/development schema is needed in
the test cluster: this supervisor fingerprints the original through read-only
connections and the migration fixture bootstraps only its fresh test schemas.

Only the supervisor receives original credentials for protected read-only
snapshots. Worker/provision subprocess environments start from an OS-key allowlist
and explicitly validated test URLs/passwords. All three URLs must use psycopg,
127.0.0.1:5434, doi_pin and the source-contract role. URL query overrides are
refused. Missing secrets fail closed. PYTHON_DOTENV_DISABLED=1 is present before
Python imports app.config, so its load_dotenv cannot refill values from .env.
PGCONNECT_TIMEOUT=5 and PGOPTIONS statement_timeout=15000/lock_timeout=5000 bound
connections/SQL without changing recovery or payment policies.

The worker also guards psycopg.connect against endpoint/credential redirection.
It permits only the fixture's exact Python executable + provision_database.py +
roles/grants commands, cwd=workspace, no shell or caller environment override.
Other subprocess.Popen calls are refused. Each provisioning call gets exclusive
start/result JSON and stdout/stderr files under run/subprocesses, a 60-second
timeout, observed PID/exit status and timeout evidence. The worker has a 600-second
supervisor deadline. Failed/refused/timed-out calls cannot yield a PASS journal,
even if pytest catches the exception. Existing output directories are refused.

Only phase5_test_<12 hex> and b1b_upgrade_<12 hex> fixture schemas (plus a distinct
bootstrap environment identity) are accepted. A roles call must target a schema
absent from the test catalog and unclaimed by this run. Grants require that same
run's claim. Claims are retained on partial setup failure; catalog snapshots
record owner, revision or PARTIAL, and row counts. No teardown drops schemas.

This adapter is not an OS security sandbox. The safety boundary is a separate
PostgreSQL cluster with separate credentials/data and reviewed trusted fixture
code. Do not extend the command/node allowlist or claim general subprocess
confinement. The selected tests exercise local schema/storage constraints and
reservation setup, without running charge/refund providers, browser or workers.
Retain the new container/volume, schemas, partial directories and all evidence;
there is no automatic cleanup or Round 3 execution.

## Round 2 config fix and one controlled rerun

The initial Round 2 run retained 2 passes and 8 fixture failures: the clean
worker environment omitted DEVICE_KEY_DERIVATION_SECRET. qr_token reads it in
the worker process and requires length >=32 without the REPLACE_ prefix. That
omission raised ConfigNotReady (HTTP 422) before the eight storage assertions.
Do not reinterpret that run as migration coverage or overwrite its evidence.

The separately authorized rerun uses a single new cluster on 127.0.0.1:5435,
database doi_pin_r2_rerun. The adapter refuses both original 5433 and retained
Round 2 5434 endpoints and verifies that system/container/mount identities differ
from both old clusters. The earlier 5434 protocol above is historical; it is not
a reusable target for this rerun. Keep both previous clusters unchanged.

Generate the new derivation secret with a cryptographic random source and store
only in the new ignored private.env, alongside independent database credentials.
isolated_environment validates the application contract and requires the key
explicitly, without reading it from the parent environment. Supervisor preflight
also refuses reuse of the original derivation secret. The worker receives the
key before any imports and verifies it matches the explicit private configuration.
Provision roles/grants children do not need this application key: validate it in
the worker and remove it from their minimal database-only environments. No other
application secret, payment provider URL or policy/timeout setting is added.

environment_contract.json records only key names and validation booleans, never
secret values. The passive HTTP 422 observer records status, test node and a
redacted response body. Only fixed public CONFIG_NOT_READY/VALIDATION_ERROR codes
and messages survive redaction; other values/unknown keys are redacted. It returns
the exact original response without replay, assertion or business changes.

Focused tests cover missing/invalid/minimum-valid secret, worker propagation and
real qr_token configuration, omission from provisioning children, no secret in
evidence/errors, old endpoint refusal, journal failure and evidence collisions.
If focused verification fails, stop before creating/running the migration batch.
After focused/isolation/protected preflight pass, run exactly MIGRATION_TARGETS
once through the business runner with a new journal/evidence directory. Retain
the new volume/schemas and all successful or failed evidence. No retries or Round 3.

## Round 3: separately authorized no-delivery/certificate batch

The next authorization permits exactly the 13 ROUND3_TARGETS in the runner:
5 no-delivery, 3 certificate, 2 initial redemption/revocation, 3 API authority
cases. Save selected/deferred IDs against the 803-node collection before running;
exclude the 30 PC cases already passed. Legacy old-obligation settlement,
adversarial terminal metadata and broad races remain deferred. No assertions,
business rules, proof clocks, migrations or provisioning source are changed.

Use `--profile business --execution-profile round3 --isolation INSTANCE_JSON`
plus the exact ordered 13 IDs. Round 2's default execution profile and pinned
ten-node allowlist remain intact. Round 3 refuses unisolated execution, arbitrary
IDs/modules, subsets, extra targets, reordering and mismatched identity/profile.

Round 3 derives host/port/database from its verified identity: host must be
127.0.0.1, port an available integer outside retained 5433/5434/5435, database
doi_pin_b1b_r3_<12 hex>. All three URLs must match that exact endpoint and role,
without URL query overrides. Identity records all three retained clusters;
container/data volume/source/network/system identifier must differ from each.
Keep a fresh private.env with independent random database/derivation secrets,
dotenv disabled and a pristine new PostgreSQL cluster for this single batch.

Fixtures still use only the exact Python provision roles/grants subprocesses;
Alembic/seed/API writes remain in that new cluster with fresh phase5_test schema
and per-test rollback. Physical-review cases explicitly create fresh tmp_path
Simulator ledgers with MockTransport to TestClient. Their verified charge setup
uses test_phase6.outcome as a pure in-process callback. The first Refund intent
only creates REQUESTED/redemption/generation-zero/inert REFUND outbox; it never
dispatches a Refund provider. No additional environment keys are needed.

In addition to unchanged subprocess/psycopg/output guards, Round 3 blocks real
httpx sync/async HTTPTransport and payment.provider_request. MockTransport and
TestClient remain available. Any blocked transport sets failed=true and appends
a secret-free refusal record, preventing a false PASS even if caught by a test.
This remains a reviewed-source boundary, not a universal OS/network sandbox.

Focused tests verify exact profiles, dynamic endpoints, old resource refusal,
unchanged child commands, mock-only transport, journal failure and retention.
Snapshot original/retained clusters plus source/evidence before and after;
preserve the new cluster, schemas, SQLite ledgers, every partial run and logs.
Run exactly one batch after focused/preflight PASS, without retry or Round 4.

## Round 4: separately authorized race and failure-recovery batch

Use `--profile business --execution-profile round4 --isolation INSTANCE_JSON`
with the exact 14 ROUND4_TARGETS. Preserve Round 2/3 profiles and all their data.
The batch selects all 14 previously unexecuted non-contract cases; the remaining
40 DTO cases are deferred. Previously verified Refund intent/outbox/replay tests
are not repeated or misrepresented as new coverage.

Round 4 requires a pristine new cluster with identity-derived loopback endpoint,
port outside 5433-5436 and database doi_pin_b1b_r4_<12 hex>. Identity must list all
four retained clusters; container, named data volume/source, network and system
identifier must be separate. Keep existing URL/credential/secret validation,
dotenv suppression, provider/HTTP refusal, output routing, journaling and exact
roles/grants subprocess guard unchanged. No xdist or additional API process.

The three race-module cases comprise one sequential uncertainty ordering probe
and two same-process native PostgreSQL/thread expiry probes. Each expiry case
uses race_environment to call the official environment generator for another
fresh schema, committed setup and independent real DB transactions. Main holds
the station lock; a single thread submits the API request; a readonly AUTOCOMMIT
observer records pg_blocking_pids/wait_event_type. Source default isolation is
READ COMMITTED. The existing source 8-second session, 1-second lock-observation
window, 10-second result deadline, 5-second connection lock timeout and 15-second
statement timeout remain unchanged; lock holding begins near expiry (~2 seconds
left). The supervisor keeps its 600-second deadline. No clock/TTL/retry edits.

Other cases exercise station fences despite untrusted terminal markers, native
SQLite replay/queued disposition/crash recovery, delivery-history conflict and
legacy old-obligation preservation. The delivered-and-returned model test
intentionally records one local service effect and one local command effect;
this is not provider dispatch or hardware execution. Report actual per-ledger
effect counts, not a blanket zero. Legacy old-possession verification itself is
read-only. All simulator HTTP uses reviewed MockTransport callbacks. No new
socket/provider/worker command is authorized.

Expect three fresh PG schemas (master fixture plus two native race fixtures),
14 fresh SQLite ledgers, and durable race diagnostics redirected from docs into
run/reports. Preserve committed race state as evidence; no schema/volume/ledger
cleanup. Save selected/deferred IDs before execution, run exactly one batch after
focused/isolation/protected preflight PASS, diagnose failures without retry or
business/assertion edits, and stop without another batch or Phase 8C.

## Round 5: pure contract completion and 97-case accounting

Reconcile the saved 97 original B1b IDs against JUnit, call outcomes and completed
passed journals from Round 1, Round 2 successful rerun, Round 3 and Round 4.
Preserve parameter identities exactly. Exclude the initial failed Round 2 from
PASS accounting. The union must establish 57 distinct passed IDs, leaving 40.
Record that reconciliation and exact selection before running; do not change
expected counts or historical manifests to force the result.

Use `--profile business --execution-profile round5` with all exact ordered
ROUND5_TARGETS and no --isolation. This profile permits only 12 round-trip,
20 forbidden authority/financial input, 4 strict positive integer and 4 literal
coercion cases. No API/lifespan/database fixture is requested. Imports define
DTOs/schema/example functions; app.create_app is imported but not invoked by
these selected bodies. The audit autouse fixture returns for this module;
its session report still routes under the fresh run directory.

No PostgreSQL cluster, credentials or SQLite ledger is created. Only the parent
supervisor uses original credentials for mandatory read-only snapshots. The
worker receives an OS-key allowlist, dotenv disabled before Python imports,
and no DB/application credentials. PureContracts refuses psycopg.connect,
SQLAlchemy engine creation, SQLite connections, native subprocesses and sync/
async real HTTP/provider transport. Refusals are recorded without arguments or
secrets, set failed=true and prevent PASS even when caught. Exact collection is
checked before execution and each node before fixture setup. Existing Round 2-4
profiles and negative guards remain unchanged. This is a reviewed-source guard,
not a universal OS sandbox.

Keep exclusive run directory, fsynced journal/node events, output routing,
JUnit/logs, source/evidence snapshots and 600-second child deadline. Focused tests
must pass before the single authorized 40-case batch. No retry or domain edits.
Snapshot all five existing clusters read-only; retain every historical artifact.

After execution, publish a 97-row inventory with exact node ID, latest valid run,
PASS/FAIL/SKIP/NOT RUN, JUnit testcase/result and source checkpoint snapshot/hash.
97/97 means targeted cases across those recorded checkpoints only. It does not
replace full 803 regression, static acceptance, guard A-E, NFR04/NFR07/NFR08,
independent acceptance or authorize B2-B5/8C. Keep B1b WIP/not accepted and stop.

## Full business regression: separate execution authorization

`--profile business --execution-profile full --isolation INSTANCE_JSON` selects
all business modules from the saved collection, excluding only compatibility and
synthetic tooling modules. Collection-only is a separate preflight invocation;
execute once only after identity/static/focused/resource checks pass. Actual
collection must match all saved identities before fixtures run. Two parameters
in test_phase8a_contract create uuid4 values at import: preserve and report raw
old/new IDs, normalize only those two values for reconciliation. All other IDs
are exact; no skips, xfail, --lf, deselection or changed expected counts.

Use one fresh PostgreSQL17 cluster, loopback port outside5433-5437, database
doi_pin_full_<12 hex>, independent credentials and all five retained identity
proofs. Keep derivation/payment service/callback keys explicit, dotenv disabled,
fresh ledger paths and source business policies unchanged. Full-only migration
schema prefixes b1a_upgrade/b1a_clean are allowed because those reviewed tests
exercise old-to-head and clean installations; existing schemas cannot be claimed.

Native command allowlist adds only source --once payment/device workers and
single-process uvicorn app.main:create_app on loopback8005/8006, no reload/worker
forks. Validate exact argv/cwd/schema/new URLs/environment/output paths. Launch
the actual base Python with explicitly pinned venv site-packages to avoid Windows
venv redirector PID ambiguity. Each child has a public ticket/start/actual PID/
exit evidence; synchronous stdout/stderr is retained. Expected nonzero native
lock-exhaustion exits belong to two source assertions, not an automatic PASS.
Unexpected child failures/refused effects cannot produce a passed journal.

An owned in-process uvicorn CHARGE-only mock uses a new loopback port and SQLite
ledger; source authentication reads current synthetic test keys. No Refund
dispatcher exists. Real HTTP is limited to this mock's CHARGE routes and owned
8005/8006 API children. In-process TestClient/MockTransport callbacks stay intact.
Reviewed .cache payment-ledger/API-log UUID paths route into the exclusive run;
an existing cache directory cannot be claimed. Native SQLite writes outside run
are refused. Preserve every new schema, ledger and partial log.

Run one suite, no xdist, 4-hour supervisor ceiling with fsynced per-node start/end
events and 30-second RAM/disk/process resource samples. Check original protected
snapshot every5minutes and before/after. Stop on drift/resource exhaustion;
retain UNKNOWN/INTERRUPTED evidence. A process-scoped Windows execution request
prevents idle sleep only during the run and is released in finally; power policy
is never changed. Parent/native process identities and expected fixture-controlled
termination are distinct from assertions of business success.

After execution inventory targeted97, full regression, static-only gate, eight
audit actions/GuardA-E/inherited real-process scenarios, B0/B1a nonregression and
independent-review/NFR gaps separately. No automatic guard reruns or B1b acceptance.

## Fixture isolation and bounded catalog verification checkpoint

The failed full_run_a5e628ba31664511a49b7880911c720a stays immutable:
803 executed,790 passed,13 failed; journal UNKNOWN after PostgreSQL53200.
CT11 committed an unprocessed non-seed SNAPSHOT through an independent client
into the session fixture. The current no-delivery guard correctly refused that
shared history. Do not delete/process/accept the event to force a positive proof.

CT11 now selects committed_environment. It uses the unchanged official fixture
generator with a fresh test-scoped schema/settings/credentials and real independent
connections/two threads. The session environment remains separate. Teardown
retains the child schema and records public event metadata before/after, checks
the shared device history is unchanged, closes fixture engines and restores the
process DATABASE_SCHEMA. Historical CT11 assertions and all803 node identities
are unchanged. Other committed race/worker suites already use race_environment;
the Phase3 shared concurrency/seed cases are identified separately and do not
leave the pending device event responsible for these13 failures.

Two additional business fixture-regression identities live in
tests/test_phase8b_fixture_isolation.py: committed_ingress_does_not_leak_to_session_schema
and pending_snapshot_still_requires_quiescence (both prefixed test_). They prove
independent committed ingress stays in its retained schema and a valid pending
SNAPSHOT still causes QUIESCENCE_REQUIRED. They are not excluded or counted among
the historical803. The expected full collection is805, reconciled as803 historical
plus these2 new identities, with the same two import-UUID4 normalizations only.

For the separately authorized interaction verification, a full infrastructure
identity with selection_kind=fixture_interaction accepts exactly FIX_VERIFY_TARGETS:
CT11 first, the13 exact failed nodes, then the2 new fixture regressions. Collection
order is checked before fixtures. This is a16-case focused invocation, not a full
regression. Full native/output/environment safety stays enabled. A full identity
uses the entire805-case inventory instead. Both refuse protected ports5433-5438
and every retained endpoint; identities must enumerate at least those six preserved
clusters without duplicate ports. The later full rerun also preserves the focused
cluster, uses another fresh cluster, and cannot reuse its endpoint or data.

isolated_catalog now uses AUTOCOMMIT between finite per-schema READ ONLY,
REPEATABLE READ transactions. Each batch retains counts/digests, revision,
ownership/ACL, columns/constraints/triggers/functions. Namespace OID/name/owner/ACL
and authenticated cluster identity are rechecked before batches and after the scan;
other client backends cause mandatory pre/post checks to fail closed. This is
explicitly not an atomic global snapshot. Fixture-time inventory can coexist
with its owned pools and reports no quiescence guarantee; supervisor checks require
quiescence. Native actual PID/exit records and the stopped mock/worker manifest
must be complete before post-checks. SQLSTATE is retained on post-check exceptions;
errors still produce UNKNOWN, never warning-only success. No server setting changes.

The108-schema retained5438 cluster is used only for authenticated read-only live
verification. Its rows, ACL/catalog, ledgers and old UNKNOWN journal stay unchanged.
Focused tooling, live catalog, the16-case interaction, static/source/protected
checks must all pass before exactly one separately isolated full rerun. No retry
or code edits during execution. Proof ingress observation records only node/status
and approved public codes, never request bodies, headers or secrets.

The immutable static checker does not yet know these newly approved infrastructure
paths. Invoke its existing main through a recorded process-only overlay adding
exactly FIXTURE_SOURCE_SCOPE (conftest, Phase4 fixture selection, new module) to
APPROVED_TOOLING. No checker file, historical expected hashes/EOL allowlist or
frozen manifest is edited; unexpected deltas remain refused. Report this overlay
explicitly and retain all final source hashes for independent review.

## Independent Windows execution (separate restore/launch authorization)

The545/805 interrupted run and its RUNNING journal remain immutable/UNKNOWN.
Windows power-off at12:58:24 on22November2026 stopped the workload. Task Scheduler
and process-scoped idle prevention cannot protect against explicit shutdown,
logoff, power loss or OS failure. Keep Windows/user session/Docker running until
terminal evidence is verified; no global power-setting changes are made.

tools/launch_phase8b_windows.py wraps the unchanged business runner. Prepare an
exclusive windows-launch-UUID/request.json under.local/pc-b1b. It pins base
python.exe/pythonw.exe hashes, exact cwd/argv, current interactive user, HEAD,
all tracked/approved new source hashes (including the untracked launcher), and
business isolation/preservation manifest hashes. Task arguments contain only
request paths/digests. No credentials are stored in task arguments or XML.

Register a new on-demand task with no triggers, InteractiveToken/LeastPrivilege,
IgnoreNew, RestartCount0, StartWhenAvailable=false and PT5H execution ceiling.
Never update/reuse an existing task, request or run label. Submit only once.
The submitting terminal exits; the service starts pythonw.exe independently.
The launcher records PID/creation time/executable, request/command identity,
service-owned ancestry and the task submission receipt. It creates its Python
child suspended, assigns a unique Windows Job Object with KILL_ON_JOB_CLOSE,
then resumes. Children inherit this owned job; assignment failure prevents tests.
No unrelated Python or Docker process is terminated. Heartbeats are exclusive,
fsynced records; the existing runner retains its own journal/node/resource/JUnit
and subprocess/effect evidence. An unexpected launcher exit closes the owned job
and leaves UNKNOWN/partial evidence. There is no automatic retry after failure
or reboot and no completion of historical interrupted journals.

Read-only status:
`.venv/Scripts/python.exe -B tools/launch_phase8b_windows.py status REQUEST_JSON`
checks creation time/executable as well as PID. Stale identity and missing or
inconsistent terminal evidence cannot yield PASS. Final business PASS requires
all805 actual identities/call outcomes, final JUnit with no failures/errors/skips,
pytest/runner0, completed passed runner journal and mandatory post-checks.
The launcher separately verifies all eight retained clusters and frozen evidence
before/after via a pinned preservation manifest using bounded READ ONLY schema
transactions, and guards its own source hashes. These supplemental checks do not
claim an atomic global snapshot or create post-checks for the old run.

The5439 restored database has an exact pre-full comparator. The interrupted5440
database has completed provisioning inventory and CT11 event metadata; no full
data digest was taken at shutdown. Compare the retained evidence without calling
authorized test mutations corruption, record that historical limitation, then
freeze authenticated current catalog/ACL/data as the future protection baseline.
Any actual comparator mismatch stops the workflow.

Synthetic lifecycle verification uses this same task/job boundary with no DB or
provider imports/effects: normal completion, a deliberate nonzero child exit,
separate-terminal status, exclusive launch and stale/fake PASS checks. It is not
full pytest or domain verification. Only after recovery, synthetic lifecycle,
focused tooling/static/frozen/805/protected/resource checks pass may one fresh
cluster and one full invocation be admitted. All task/evidence records remain.
Static verification adds only the approved launcher to the previous process-only
scope overlay; checker source and historical hashes/manifests remain untouched.

### Effective Task Scheduler settings (validator checkpoint)

The scheduler can omit StartWhenAvailable and RunLevel in its returned XML.
Validate the effective COM properties at registration, immediately before
submission and inside the scheduled launcher before child creation. Require
StartWhenAvailable to be the boolean false and RunLevel the integer 0
(TASK_RUNLEVEL_LUA). An omitted StartWhenAvailable uses the schema's optional
default=false only together with this COM confirmation. An omitted RunLevel
does not establish privilege: COM must independently confirm least privilege.
Explicit XML true/HighestAvailable, disagreement, missing/unknown COM values or
unreadable COM fail closed. Explicit false/LeastPrivilege still require COM.

Validate exact task name/root path, resolved principal SID, owner SID and caller
SID against the requested current Windows account. Keep one InteractiveToken
user principal, one exact executable/arguments/cwd, no triggers, no restart,
IgnoreNew and the unchanged deadline. Check XML and COM independently; compare
the registered configuration again before submission. Credentials never enter
task arguments. Use TASK_CREATE only, with an exclusive registration reservation
before RPC, and exclusive submission reservation; collisions or failed attempts
cannot overwrite a task/evidence or automatically retry. Keep the previous
never-submitted task unchanged and use a fresh identity for lifecycle verification.

This checkpoint authorizes synthetic lifecycle only, after focused tooling PASS.
Observe service-owned ancestry, PID/creation identity, owned child job membership,
independent status, durable heartbeats and normal exit after the submitting
terminal ends. Preserve all evidence and eight database clusters. Full805,
domain tests, a fresh database cluster and acceptance guards are NOT authorized.

Primary references: [StartWhenAvailable schema](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-startwhenavailable-settingstype-element),
[Principal.RunLevel](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-runlevel),
[TASK_CREATE registration](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertaskdefinition).
