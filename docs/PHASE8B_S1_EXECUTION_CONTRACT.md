# B1b S1 — successor concurrency execution contract (not executed)

27/11/2026 (+07). Planning artifact for B1b-X05, not a normative overlay change.
Business adapter is PARTIAL and launch is locked; no S1 permission is implied.

## Authority and prerequisites

- `docs/PHASE8B_B1B_TEST_PLAN.md:95`: successor versus DECIDE/redemption/closure,
  both meaningful orders, current operation/version/fence serialization.
- P8-REC-0.3 README supersede/reinspection: only expired/rejected predecessor,
  immutable new context and independent current three-source proof; preserve
  denials through atomic local fence ownership handover. Never renew timestamps.
- P8-REC-0.3 README explicitly forbids using 0.2 no-effect closure to close a 0.3
  fence. A rejected closure is not a competing successful terminal transition.
- Backend `no_delivery.begin` checks current station/case predecessor and
  consumed/cancelled/expired/rejected conditions; allows REVIEW_REQUIRED and
  COMPENSATING. Successful existing Refund does not imply a new intent is allowed.

Before execution: actual cluster5449 identity7712738307604140070; isolated newly
owned schema and ledgers, dedicated runtime role with no privileges on historical
or smoke schema; read-only identity/ACL admission and revision0010; exact grant
plan, explicit owned process/endpoints and complete child guard integration.
Provisioning authority must be separate, never inherited by business children.
Existing smoke `phase5_test_ecfa77274ae3` is forbidden as business fixture.

## Exact operations and route compilation

Technician: `POST /v1/swaps/{swap_id}/recovery/evidence` with approved 0.3 BEGIN
(predecessor_id) or VERIFY_NO_DELIVERY_DECIDE payload. Customer confirms through
existing confirmations endpoint; Admin first request is
`POST /v1/payments/{payment_id}/refund`. Closure uses existing 0.2 statement flow
only as a negative cross-protocol control. Inspect actual API schemas/operation
IDs and expand each selected fixture UUID into exact method/path pairs before
admission. No wildcard pattern may be passed to transport. Setup/login/device
ingress/task/command/charge routes must be separately enumerated from current
routers and original C-expiry primitives. This route registry is still PENDING;
the current Config validates syntax but is not an approved scenario registry.

## Meaningful combination matrix

Each row is a fresh independent fixture/ledger where terminal or REJECT state
would invalidate reuse. Both Backend APIs must be actual base interpreter OS
processes, never two TestClient instances.

| Pair / order | Oracle |
|---|---|
| Successor commits before old DECIDE | Old operation/context/version cannot issue certificate; new operation is current, immutable predecessor link, version increments only for committed successor |
| Old DECIDE holds station lock, eligibility expires/rejects before final decision; successor waits | Revalidate after lock wait: old decision refuses, then successor may proceed if legitimate preconditions remain; do not force both operations to succeed |
| Valid DECIDE commits before predecessor becomes expired/rejected, successor later eligible | One immutable old certificate remains historical; successor creates new current context and proof, old certificate does not become fresh/current or authorize another intent |
| Successor commits before Admin redemption of old certificate | Old binding/case version fails current validation; no new intent/redemption/outbox/audit success; preserve existing physical fence |
| Valid Admin redemption commits first; successor later legitimately eligible | Keep exactly the original REQUESTED intent and inert outbox. Successor, if permitted for the same recovery, cannot create a second Refund or undo committed intent; preserve COMPENSATING/payment/custody/holds |
| Successor and invalid 0.2 closure attempt against 0.3 operation, each lock order | Closure remains refused in both orders; no CLOSURE_COMMITTED/fence removal. Do not invent a valid 0.3 closure or assume generic unlock |
| Two successor requests sharing predecessor/version | One current successor at most; loser stale version/context/active-operation conflict, no extra accepted proof/audit/idempotency success |

An expired predecessor implies its old DECIDE/certificate cannot remain eligible
past its approved expiry. A REJECT prevents certificate issuance. Therefore a
test demanding two simultaneously valid positive decisions from those states
would be an invalid oracle. Time-bound ordering uses the real clock, not UPDATEs
to timestamps or renewal. If a pair cannot be constructed under frozen semantics,
retain the rejection oracle and document applicability rather than adding rules.
The exact success/refusal business code must be derived from actual guards at
implementation, not guessed or changed to satisfy this plan.

## Deterministic synchronization and evidence

Reuse C-expiry setup/three-source/readonly inspection primitives and existing
station/user/resource/session lock order. New test-only barriers must be local
to a reviewed runner; no production fault switches. Capture actual child/server
PID+parent and exact PostgreSQL PID at barrier, pg_blocking_pids, wait event,
transaction ID, barrier identity, request ID, hashed idempotency key/body and
server-handled process. Barrier must be reached under the same transaction
protecting the mutation. Do not infer overlap from HTTP timing or sleeps.

Capture independent pre/post numeric case/swap versions, operation metadata and
successor links, certificate/redemption/Refund/attempt/outbox/accepted-proof/audit
IDs and counts, idempotency state, actual receipt/hash/boot/seq, local ledger ID,
fence generation/owner and union denials. Keep original raw source/receipt hashes
and all failed/interrupted artifacts. Do not infer missing pre-state from final
DB or self-reported audit snapshots alone.

Every branch preserves old obligation, custody/assets, Payment SUCCEEDED and
three holds unless its approved existing transition explicitly changes a named
field. All S1 branches have zero new command/service physical effects and zero
provider Refund dispatch. Exactly one initial mock charge is setup evidence,
not a real provider interaction. Inert REFUND outbox: attempts0/delivered_atNULL.

## S2–S5 reuse / stop conditions

The evidence journal and exact admission/transport/process controls can support
S2 legacy-vs-Refund, S3 actual pre/postcommit crash, S4 residual authority/projection
and S5 audit storage probes after separate approval. Do not implement all runners
now. S5 SQL-only probes may use a separate owned-schema verifier without the
HTTP/process adapter; still require real grant/identity admission and fresh data.

Stop on admission/ownership/privilege mismatch, stale authority/proof, absent
process exit evidence or unowned endpoint/ledger. Preserve fail-closed business
results. No retries to obtain PASS, no source/contract/deadline/custody guard changes.
Current adapter lacks child/native transport and grant-collector integration;
all above combinations remain NOT RUN / PENDING INTEGRATION APPROVAL.
