# Refund-only retry protocol — normative B0

## Identity and ledger invariants

Five distinct identities:one refund_id/payment;one immutable provider_key for that refund;attempt_id and integer generation0,1,…;HTTP Idempotency-Key for each public Admin operation or private command;provider permit_id for a single ordered successor attempt. None is a Service-Key or substitute for source authentication. No new provider identity or refund intent on retry.

Provider owns permissions,not Backend/Frontend. Under SQLite BEGIN IMMEDIATE,verify original charge/payment/reference/full amount/VND,refund master current generation andcumulative effect count. Every effect path first checks the same master and durable denied-attempt set. Money effect and terminal receipt/outgoing callback event are committed atomically in the simulator ledger;PREPARED is persisted before starting that effect transaction. PREPARED/UNKNOWN without authoritative resolution never executes again.

## Permission issuance/expiry/consumption

Admin FAILED reconcile stores a durable reconcile_request_id/outbox job under PostgreSQL locks;worker calls private POST command REQUEST_RETRY_PERMISSION outside locks. Its expected prior attempt must have authoritative FINAL FAILED,no-effect receipt (`NEVER_PREPARED`,effect total0,attempt durably denied). Unexplained FAILED or just missing receipt is insufficient. If masterSUCCEEDED,priorPREPARED/UNKNOWN,another active attempt or binding mismatch:refuse,no grant.

Grant creation atomically persists permit_id,next generation=prior+1,provider-generated canonical next attempt_id and RESERVED attempt row. Original prior is irrevocably denied before no-effect proof. One outstanding grant per successor generation;same reconcile_request_id/body replays same grant,conflictingbody409. It must never allocate two attempt IDs for the same generation.

**New permit TTL=15 seconds from provider issued_at** is a conservative transport design bound,not a change to command ACK15/physical60/freshness15 or charge timeout30. Expiry uses provider clock;Backend treats expiry conservatively andprovider rechecks immediately before consumption. No renewal of same grant/body,reference or old proof timestamps. Expired permission does not mean financial no-effect by itself.

Backend stores the authenticated grant/receipt append-only and CAS-registers next attempt under station/Payment/Refund/session locks. If versions/authority/eligibility changed,do not dispatch;grant stays unconsumed until safely sealed/reconciled. Once registered,claim changesRefundFAILED→PENDING and commits dispatch marker/outbox scheduling **before** private ATTEMPT_REFUND HTTP. Two workers use unique(refund,generation),uniquepermit consumption and the same canonicalattempt;onlyone claim. A second same-attempt HTTP request is replay,not another generation.

Provider accepts ATTEMPT_REFUND for generation>0 only with the exact unexpired permit_id/binding/current RESERVED attempt. Within one writer transaction:check master effect0,consume permit exactlyonce,append PREPARED marker. A duplicate after consumption returns that attempt's current result;never treats consumed permit as permission for a different attempt. Wrong/expired/consumed-by-other attempt409. It then completes at most one effect under the master effect guard. Permit may expire after valid consumption without invalidating a proven effect;it cannot authorize another effect.

## Ambiguous dispatch and durable negative reconciliation

Automatic UNKNOWN handling only GET STATUS for the exact provider_key/attempt/generation. NOT_FOUND is not FAILED or permission to POST. Restart reloads durable dispatch state,not an in-memory flag. No automatic redispatch after ambiguous claim.

Admin reconcile UNKNOWN can issue **GET mode SEAL_UNACCEPTED**,with complete QueryContext and a durable reconcile_request_id. It performs no financial effect. Provider must take the same writer/master lock as every effect handler and positively prove target was NEVER_PREPARED;atomically write a durable denial tombstone before issuing a no-effect receipt and FINAL FAILED for that exact attempt. This also handles initial generation0 whose HTTP never reached provider:verify original charge bindings,create the denial-bound master/attempt record if absent. A late cached HTTP arriving afterwards is rejected by the tombstone,not executed.

If a concurrent handler already committed PREPARED/UNKNOWN,seal must refuse/returnUNKNOWN;effect_count0 or row absence alone is not enough. If alreadySUCCEEDED,return that truth,not FAILED. STATUS does not secretly convert NOT_FOUND toFAILED;only explicit authenticated negative reconciliation with denial+journal proof can do so. Expired RESERVED attempts need this same seal,not expiry-based inference. A worker job authorized while refundUNKNOWN remains query-only even if responsebecomesFAILED;it must not immediately request a grant/POST. A subsequent fresh Admin FAILED reconcile may authorize generationN+1.

## Generation/result ordering

| Situation | Required result |
|---|---|
| Replay initial/attempt body | Same attempt identity/current durable result;effect count unchanged |
| Same HTTP key with changed attempt/body |409,no ledger effect |
| Query/callback current generation final |Apply only after binding/source/reference/money verification;settle once |
| Callback from generation<current |Persist/dispose as historical,not overwrite current;contradictorySUCCEEDED triggers authoritative master query/incident,no new refund |
| FAILED after masterSUCCEEDED |KeepRefundSUCCEEDED and originalPaymentSUCCEEDED;conflict audit/query,no downgrade |
| Future/unregistered generation callback |Reject/quarantine,no current-state mutation;do not invent an attempt from callback |
| Provider effect committed,response lost |Query sameattempt returnsSUCCEEDED;no secondPOST/effect |
| Permit persisted,Backend crash before storage |Provider grant remains RESERVED,exact reconcile replay gets same grant;expiry requiresseal before next generation |
| Backend dispatch marker committed,crash before HTTP |UNKNOWN query-only;Admin seal can positively deny unaccepted attempt;no speculative resend |

Master SUCCEEDED outranks contradictory late failure;verified prior-generation success inconsistent with an already granted no-effect certificate is a provider integrity incident. Do not silently accept incompatible ledger facts,reset reference or create another intent. Backend retains review/holds;financial truth is resolved by authenticated master/attempt evidence,not arrival order.

## Why two effects cannot occur under this contract

All provider POST/retry/seal/query result transitions serialize on one refund master,unique payment and key. A successor is granted only after prior terminal no-effect plus permanent denial. An attempt effect checks master total0 and its unconsumed exact permission;effect+receipt atomically set master total1/SUCCEEDED. Thereafter every generation refuses effects. Two workers can only replay one exact attempt or conflict;they cannot consume one permit for two attempts. Crash leaves a committed terminal receipt or PREPARED/UNKNOWN that cannot re-execute. This is a design safety argument under the specified durability/atomicity assumptions,**not evidence that unimplemented runtime passes crash tests**.

Runtime acceptance must demonstrate these assumptions with PostgreSQL/process/SQLite restart probes;schemas alone cannot enforce generation arithmetic,sourceauth,temporalordering or no-effect provenance.
