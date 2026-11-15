# P8-REC-0.1 — Recovery evidence & settlement

Technical appendix approved by the user on 29/10/2026, with the additional
conditions in “PHASE 8A — FINAL DESIGN APPROVAL & IMPLEMENTATION”. It does not
modify the GD1/GD2 baseline, FR/UC/BR identifiers or QD01–09.

Implementation is **in progress**, not ready for acceptance. See
[PHASE8A_IMPLEMENTATION](../../PHASE8A_IMPLEMENTATION.md) for the actual scope
and test evidence. Schema files describe inputs; their presence does not imply
that all endpoints or transitions are implemented.

## Traceability and trust boundaries

- FR12, UC10, BR05/09/11/12, AD-04b, SM-03b, invariants 6–8: recovery preserves
  last-known custody and the three resource holds until a justified decision.
- FR16/UC14/BR08/SM-04 are dependencies for 8B/8C only. No refund or compensation
  finalizer is implemented by this appendix's 8A slice.
- A payment charge remains independent from custody. ACK, timeout, an empty
  slot, a note, or DB holder alone cannot prove a handover.
- Automatic ACK15/physical60/freshness15 guards and P7-A01 remain unchanged.
  Historical recovery attestation may remain evidence; a current authenticated
  snapshot must still pass freshness at the final manual decision.

## Approved operation purposes

| Purpose | Intended behavior and safety gate |
|---|---|
| VERIFY_OLD_POSSESSION | Observe correct customer's actual old pin outside the cabinet; no transfer; three independent sources |
| RETURN_OLD_TO_CUSTOMER | Explicit Technician service action, correct old pin/recipient, positive no-new-delivery proof and no possible command effect; never automatic on poll |
| VERIFY_NEW_DELIVERY | Observe positive new-pin possession; never grant another pin; combine with return history and verified charge |
| RETURN_FOREIGN_OBJECT | Separate foreign-object handling for the verified presenter; never register it as a network battery; does not settle the real old pin |
| RESUME_SWAP | Explicit intent only; backend derives permitted step from history and interlocks; no duplicate OPEN_RETURN/OPEN_SUPPLY |

## Input contracts

The six JSON Schema 2020-12 files are generated from
`app/api/recovery_schemas.py`. They forbid additional fields, including
client-selected custody, desired state and actor overrides. They preserve the
legacy evidence/settlement request shapes. The structured variants do not
accept a mixture of legacy evidence and a statement.

| Operation | HTTP | Role | State of implementation |
|---|---|---|---|
| getRecovery | GET `/v1/swaps/{swap_id}/recovery` | Admin; Technician assigned to station | Read API present |
| recordRecoveryEvidence | POST `/v1/swaps/{swap_id}/recovery/evidence` | Assigned Technician only | Legacy snapshot receipt and structured operation/attestation receipt present |
| confirmRecovery | POST `/v1/swaps/{swap_id}/recovery/confirmations` | Own Customer session | Confirmation/rejection receipt present |
| settleRecovery | POST `/v1/swaps/{swap_id}/recovery/settle` | Assigned Technician only | A/B/D, UNKNOWN rejection and guarded resume implemented; remaining A–F gates tracked in implementation report |
| recovery tasks | GET `/v1/device/recovery-tasks` | Station Device-Key | Scoped polling; does not execute service actions |
| recovery observations | POST `/v1/device/recovery-observations` | Station Device-Key | Durable receipt, source/boot/sequence validation and exact replay |

Mutating user APIs require UUID `Idempotency-Key` and reuse the existing durable
idempotency record in the same transaction. Same key/different body is 409
`IDEMPOTENCY_CONFLICT`. A second source attestation for an operation is 409
`RECOVERY_ATTESTATION_EXISTS`: a recorded rejection cannot be overwritten.
Read-only inspections may be superseded with a new operation after rejection
or expiry, retaining old context/attestations/audit. Effect-capable operations
remain fenced until their effect is positively reconciled.

Other current errors: 401 auth/session; 403 `FORBIDDEN`, `STATION_FORBIDDEN`,
`RECOVERY_CONTEXT_FORBIDDEN`; 404 `RESOURCE_NOT_FOUND`; 409 version/state,
`RECOVERY_OPERATION_ACTIVE`, `RECOVERY_OPERATION_CLOSED`,
`RECOVERY_OPERATION_EXPIRED`, `RECOVERY_CONTEXT_MISMATCH`; 422
`VALIDATION_ERROR`, `EVIDENCE_REQUIRED`, `EVENT_STALE`, `EVENT_OUT_OF_ORDER`.
Error codes are an implementation appendix, not edits to baseline error enums.
Typed response schemas cover tasks, receipts, operation/context and Customer
confirmation context. The baseline schemas and security remain authoritative
outside the explicitly approved appendix. API error/recovery matrices still
require complete A–F acceptance coverage.

## Storage and configuration

`0003_recovery_evidence` follows verified live head `0002_user_approval`.
It creates `recovery_operations` and `recovery_attestations`, plus nullable
`recovery_cases.operation_id`. It does not fabricate/backfill physical evidence.
Operation identity/context is immutable; only consumption/cancellation timestamps
can be changed. Attestations are append-only, enforced by trigger and grants.
Device boot/sequence and event identity have unique constraints. API validation
must additionally enforce cross-table identity and current authorization.

`RECOVERY_OPERATION_TTL_SECONDS` defaults to 120 and must be a positive integer.
It does not alter approved command, physical-step or telemetry freshness values.
Expiry never proves that an external effect did not happen.

Runtime gets SELECT/INSERT attestations, not UPDATE/DELETE; operation UPDATE is
limited to `consumed_at`/`cancelled_at`. Destructive downgrade is deliberately
disabled. A rollback of application deployment must preserve evidence and holds.

## Locking and remaining gates

User idempotency lock precedes station lock. Recovery gathers involved users
before taking sorted user row locks through the shared `station_locks` helper;
the existing swap/slot/pin order follows. No external HTTP/human wait belongs in
the transaction. The new optional actor list does not change default worker
behavior. This still requires the approved multi-process lock-order tests;
passing input/receipt tests alone is not a concurrency guarantee.

Service actions are explicit via `--service-operation`; durable UNKNOWN is not
re-executed. After an expired old-pin handover, a new VERIFY_OLD_POSSESSION may
reference it without removing its fence. Positive three-source proof consumes
both operations atomically with custody/audit. An UNKNOWN inspection still
cannot settle. This does not authorize a second handover or clear uncertainty
merely because time elapsed.

Before acceptance: complete remaining A–F paths and their real-process evidence,
full lock-order/revocation/concurrency coverage, Browser checks and final full
regression. UI exists but is not Browser-accepted. See the implementation report
for separate historical and newly executed results.
No TC16/CT13 completion claim is made before 8B exists.
