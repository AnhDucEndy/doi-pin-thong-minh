# P8-REC-0.2 — conditional approval and implementation tracking

## Customer projection increment

See [CUSTOMER_PROJECTION_1](CUSTOMER_PROJECTION_1.md) and versioned
RecoveryConfirmationContext.schema.json. The integration request authorizes
owner-only GET swap enrichment and current stage/reference validation.
Original GD1/GD2 and the P8-REC-0.1 snapshot are retained.


## ER-01 and ER-02 approved

The user approved both decisions recorded in PHASE8A_IMPLEMENTATION.md.
On the existing Technician evidence endpoint, REINSPECT_OPERATION opens a
read-only successor referencing the expired operation and its authorization.
The RECONCILIATION_INSPECTION device observation describes current external
possession under the predecessor fence. Technician and Customer attest to
that observation on the successor. Chain settlement requires both the original
authenticated effect receipt and all three current sources.

CLOSE_NO_EFFECT requests a durable closure intent on the same endpoint.
The device returns NO_EFFECT_CLOSURE using the authenticated observations
endpoint. An inspection-time NEVER_PREPARED witness, actual model and complete
command ledger establish the past history. A durable disabled operation and
command deny set protect future effects. The simulator requires a matching
CLOSURE_COMMITTED task before releasing station exclusivity. Both receipts and
human requests retain their original identities across retries.

Forward migration 0008 adds the successor evidence stage, separate uniqueness
for the read-only chain and append-only closure intent and receipt storage.
See PHASE8A_IMPLEMENTATION.md for verified scope and test results.

## Staged foreign-object settlement increment — 06/11/2026

The user authorized Stage C settlement on the existing Technician-only
`POST /v1/swaps/{swap_id}/recovery/settle`, with StructuredSettlement,
expected_version and Idempotency-Key. No new input/schema, enum or endpoint.
The dedicated 0.2 branch validates the immutable inspection/intent/ACK/activation
chain and three POST sources, current actors/sessions/assignment, fresh same-boot
snapshot, complete command ledger and the original durable fence. PRE proof is
historical chain evidence, never refreshed or substituted for POST proof.

The only writes are operation.consumed_at, recovery case EVIDENCE_RECORDED with
version/note/current snapshot, and FOREIGN_OBJECT_RETURN_SETTLED audit, atomically
with existing request idempotency. It preserves old_pin_settled/new_pin_delivered,
swap state, Payment, both network-pin custody records and all three holds. The
foreign object is not registered as a network battery. The station fence is not
cleared by this decision. A separate VERIFY_OLD_POSSESSION remains necessary to
resolve the real old-pin obligation. No automatic custody deadline is bypassed.

Expiry, REJECT, superseded operations, old boot, contradictory or missing proof
remain fail-closed. Inspection-only successor reconciliation after expiry remains
a separate unfinished capability; no timestamp renewal or second action exists.
See PHASE8A_IMPLEMENTATION.md for actual acceptance results, not the older
checkpoint statements below.

## Human POST confirmations increment — 05/11/2026

The user explicitly requested implementation of the existing Stage C human
statements. `StageReference.stage` now accepts POST_ACTION_RECEIPT as well as PRE.
No endpoint, role, TTL or settlement permission is added. Technician uses the
existing evidence API (TECHNICIAN_ATTEST, actual_serial, CONFIRM/REJECT), Customer
the existing confirmations API (confirm=true/false). Both bind exact operation,
context, POST Simulator receipt ID/hash. Recipient and actual serial for Customer
are derived from immutable context/receipt, never user-controlled overrides.

The current operation must be live; source receipt must be accepted, immutable,
chronologically earlier, current-boot and fresh. Current accepted snapshot must
show the source empty and supply serial still present, with no conflicting command
history. Current actor/session and Technician assignment are rechecked under
station/user/session locks. One append-only statement per operation/stage/source;
same-key replay returns its result, a changed payload conflicts, new-key duplicate
cannot overwrite. Accepted receipt of a REJECT statement is NOT confirmed delivery.
No ownership claim follows from being the recipient of a foreign object.

Expired/stale/superseded or old-boot proof stays historical. Existing section7 of
the approved proposal requires inspection-only successor linked to the original
authorization and actual external holder/model; never another action. That
successor reconciliation and terminal settlement are not implemented by this
increment. Rejection keeps review, original receipt, original fence and three holds.
Human statements alone do not change custody/payment, consume operations or settle.

Previously wrong-stage authorization regression used HTTP422 because POST was not
an accepted input literal. It now expects409 for a PRE receipt referenced as POST:
syntax is approved, receipt stage is wrong. This preserves the refusal invariant.
The checkpoint sections below describe earlier increments and do not disable this
newly requested POST statement transport. See implementation report for actual tests.

## 05/11/2026 activation addendum — explicitly approved, in implementation

User approved a separate immutable 1:1 activation referencing the existing intent
and durable ACK. Technician requests `AUTHORIZE_ACTION`, `phase=ACTIVATE`, exact
authorization/acknowledgment IDs, expected_version and Idempotency-Key on the
existing evidence endpoint. INTENT remains the default for backwards compatibility;
its immutable payload remains effect_allowed=false. No second intent or renewal.
Migration0007 records the activation separately with original expiry. ACTION tasks
are returned only for a live activation after the existing source/actor/fence
guards pass. They bind activation hash, intent hash and the canonical typed ACK
hash. PREPARED revalidation preserves the original evidence freshness deadline;
`proof_valid_until` is derived from original proof/snapshot time and the approved
telemetry_stale_seconds, never from time of delivery or retry.

Only an explicit service operator invocation may consume an ACTION task. Polling
or receiving ACK never performs an effect. The simulator writes PREPARED first;
an interrupted PREPARED stays UNKNOWN and cannot run again. Actual model movement,
source snapshot, OBSERVED entry and POST_ACTION_RECEIPT share one SQLite commit.
The fence remains ACTIVE. Receipt delivery waits for the source snapshot to be
processed; retries preserve event/body/boot/time. Authenticated historical receipts
may be stored after expiry/reboot with their original effect window validated,
but storage is never current proof, human confirmation, custody or settlement.

Human POST confirmations and staged settlement are intentionally still disabled.
The checkpoint sections below retain earlier implementation boundaries; they do
not supersede this user-approved addendum. PostgreSQL and real-process acceptance
for this increment are recorded in PHASE8A_IMPLEMENTATION.md: targeted91Passed,
follow-up2Passed (one overlap), real-process K03 nineteen checks Passed. This
does not approve or implement human POST confirmations or staged settlement.

## 05/11/2026 authorization transport addendum — approved, implementation in progress

User explicitly approved a transport acknowledgment on the existing observations
endpoint, bound to authorization ID/hash, operation/context, boot/ledger/fence,
append-only and idempotent, without custody or physical effect. This supersedes
the pending-handshake decision in the implementation log; it is not a new
physical evidence stage and does not modify GD1/GD2.

`AUTHORIZE_ACTION` is a Technician mutation under the existing evidence endpoint
and idempotency/version guard. Pre-stage Technician and Customer confirmations
reference the exact accepted inspection ID/hash. They do not satisfy post-stage
proof. One immutable authorization row represents the durable intent. Polling
returns `AUTHORIZATION_INTENT`, with `effect_allowed=false`; never ACTION in this
increment. Simulator validates the authenticated task and current local fence/
model/ledger in its SQLite transaction, persists `AUTHORIZATION_ACK` before HTTP,
and replays the original event/body after response loss. Acknowledgment means
stored transport intent, **not effect or handover**. Backend rechecks proof and
revocation before accepting it. No HTTP is awaited inside a PG transaction.

Migration0006 adds append-only recovery_authorization_acks with unique permit,
event and device/boot/seq. Existing immutable inspection inbox also records the
outcome of authenticated authorization-ack attempts, including semantic refusal;
the name of that table is historical. Accepted acknowledgment and audit commit
together. Authorization and acknowledgment are separate durable facts. Timeout
does not erase either, reset TTL, clear the fence or allow a replacement permit.
Replay of an accepted response is not a fresh action authorization.

No consumer can execute this increment's intents: effect_allowed is false in
the hashed payload and task, service only stores acknowledgment, default fence
remains ACTIVE, and staged settlement stays blocked. A future handover increment
must explicitly review this boundary and revalidate before PREPARED; it must not
treat a stored acknowledgment or this immutable no-effect payload as permission
to move. There is no post-action receipt/confirmation/settlement here.

Current conservative guard: any prior service_operations entry blocks issuing
a new foreign intent, since closure/reconciliation of service history is not yet
implemented. UNKNOWN or missing/conflicting command history also blocks. This
is a reported availability limitation, not a relaxation of quiescence.

The sections below preserve earlier checkpoints and are not current test results.

User approval: conversation **PHASE 8A — P8A-E01 FINAL DESIGN REVIEW &
IMPLEMENTATION**, subject to all constraints in that message. Design reference:
`../../PHASE8_P8A_E01_DESIGN_PROPOSAL.md`, sections 2 and 8–9. This record
preserves the proposed document and P8-REC-0.1; it does not modify GD1/GD2.

Status: **PARTIAL, NOT AN ACTIVE END-TO-END CONTRACT**. There is no public
AUTHORIZE_ACTION API yet. Do not send the internal local inspection receipt to
the legacy observation API or treat a storage row as a valid action permit.

## Inspection transport increment, 05/11/2026

Implemented write transport now accepts `PreActionInspection` on the existing
POST `/v1/device/recovery-observations` alongside the 0.1 union. The internal
fence receipt is converted into this typed envelope, not sent raw. The operation
created for RETURN_FOREIGN_OBJECT uses protocol_version0.2; GET
`/v1/device/recovery-tasks` returns only `task_kind=INSPECT` for it. No ACTION or
AUTHORIZE_ACTION is exposed. Legacy confirmations/attestations/settlement cannot
use a0.2 operation to bypass the staged protocol.

The input is strict (`additionalProperties=false`), stage literal
PRE_ACTION_INSPECTION, with device boot/sequence, original observation time,
snapshot event ID, actual model slot/serial, optional observed presenter, complete
local command/service entries, wrong-return event IDs, ledger identity and fence
generation. read_only=true/effect_count_delta=0 express observation only.
Unknown ledger entries and a missing presenter remain unresolved information;
accepted inspection never means verified delivery or authorized transfer.

Migration0005 adds immutable `recovery_inspection_inbox` to remember the hash and
outcome of validly parsed receipt attempts, including semantic refusals. Same ID
and different payload conflicts; identical rejection remains rejected. This is
necessary because raising a domain exception would roll back refusal evidence.
Successful attestation + audit + inbox are committed together. No custody,
payment, holds or delivery conclusion is changed. Unauthorized Device-Key and
invalid JSON/schema are rejected before the authenticated receipt service.

Simulator outbox persists the transport envelope and a shared durable service
sequence before HTTP. Replay retains event ID/body/boot/time; reboot or TTL does
not remove the station fence. Post-action receipt and human stage confirmations
remain unimplemented. `tools/smoke_phase8a.py --branch I` is inspection-only
real-process coverage; it must not be counted as successful E handover.

| Approved decision | Current implementation | Remaining gate |
|---|---|---|
| Foreign-only staged protocol; other purposes remain 0.1 | Migration 0004 has nullable protocol version, restricted to RETURN_FOREIGN_OBJECT | Strict staged write schemas, versioned API dispatch/overlay |
| Read-only pre-inspection with actual serial | Internal `recovery_fence.inspect`, actual slots/presenter/events/full command and service rows; immutable replay body/time | Authenticated INSPECT task and receipt ingestion, snapshot link, durable receipt sequence/outbox |
| Fence covers cached commands, not only polling | Shared SQLite writer transaction for inspection and full command model effect; legacy physical service checks same fence | Backend fence authorization and proven closure/reconciliation |
| Customer is verified presenter and recipient | No new authorization route enabled | Three-source identity/receipt checks; neither task.customer_id nor presenter mapping alone is proof |
| One authorization/op; current scope/version/expiry | DB unique operation; pre-stage receipt/actor/device/context binding; limited grants | Domain eligibility, freshness, revocation, audit and idempotency transaction |
| Separate pre/post human confirmations | DB unique(operation_id,stage,source_kind), same-stage same-operation SIMULATOR reference and chronology trigger | Typed API and hash binding; post-effect confirmation workflow |
| Durable PREPARED before effect, at most once | Existing legacy service logic retained; UNKNOWN never rerun; fenced legacy actions blocked | Authorized staged action and durable post receipt; crash/restart E2E |
| Settlement preserves payment, custody obligations and holds | No new settlement exception enabled; default quiet guard retained | Staged terminal proof and expiry successor reconciliation |

No business decision conflict was established in this review. Missing code/test
gates are implementation work, not a new request to approve weaker rules.

## Storage delta (forward only)

`0004_recovery_stages` follows `0003_recovery_evidence`. Existing attestations get
LEGACY metadata, without rewriting payloads, hashes, actors or timestamps.
Source uniqueness now includes stage; event/device-boot-sequence uniqueness is
unchanged. The insert trigger prevents crossing protocol, operation, stage,
receipt source or receipt chronology. Append-only protection remains.

`recovery_action_authorizations` has one row per operation. Its trigger binds the
pre-action trio, context, device/boot, creator and original expiry. Runtime can
insert and revoke once; it cannot change context/expiry/permit or delete history.
These are storage defenses, not a substitute for domain authorization. No
existing operation is promoted to 0.2 and no permit is seeded.

Read-only API views can represent the added metadata. Write API schemas,
allowlist/authentication and legacy quiet policy remain unchanged. No new
endpoint, enum, role, timeout, refund, custody update or generic unlock is added.

## Local fence implementation boundary

`inspect` is an internal primitive pending authenticated task integration. It
installs one ACTIVE fence under BEGIN IMMEDIATE and persists actual model
evidence. Reboot/expiry/replay never renew its timestamp or clear it. It cannot
authorize physical action. Unknown command/service entries remain in the receipt
and are not converted to NOT_EXECUTED. Missing presenter stays null.

Command handling commits UNKNOWN before attempting effect, then acquires the
same SQLite writer lock, checks the fence and commits model/events/completion
atomically. A command fetched earlier cannot cross the fence. An exception
rolls back that effect transaction and retains UNKNOWN. Legacy physical service
also checks the fence; no blanket EXECUTED exception is introduced in Backend.

The fixture tests for these primitives are **not real-process recovery E2E**.
Storage fixture rows are constraint probes, never physical evidence or successful
settlement. No success claim is permitted until the remaining API/domain/action
workflow and PostgreSQL + real-process branch E checks are complete.
