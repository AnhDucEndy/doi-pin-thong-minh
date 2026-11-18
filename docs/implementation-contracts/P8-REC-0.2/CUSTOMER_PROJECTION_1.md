# P8-REC-0.2/customer-projection-1

Approved scope in the Customer Projection & Confirmation Integration request.
Additive owner-only GET /v1/swaps/{swap_id} response enrichment. No new endpoint,
role, custody transition, stage meaning, migration or Customer input field.
The GD1/GD2 files and P8-REC-0.1 snapshot remain unchanged.

RecoveryConfirmationContext retains the original fields and adds protocol_version,
stage, receipt_id/hash/observed_at, case_version and confirmation_status.
The stage is selected from the active immutable operation and accepted simulator
attestations. RECONCILIATION_INSPECTION takes precedence for a successor; otherwise
an accepted POST_ACTION_RECEIPT selects POST, else PRE. Legacy stays LEGACY.
Only the selected receipt identity/hash/time is exposed, never raw simulator
payload, command history, technician testimony, tokens or authorization secrets.
Closed/expired metadata is retained for the owning Customer.

confirmation_status is read metadata, not a new domain state or permission.
POST re-derives the active stage/reference under existing station/user locks.
Client stage/reference must match. Existing actor, freshness, provenance and
append-only guards still execute. Same-key replay uses existing idempotency.
case_version helps the frontend preflight refresh comparison; it is not an
additional CustomerConfirmation input or substitute for receipt validation.
Customer still cannot GET Technician recovery or mutate custody/Payment/holds.
