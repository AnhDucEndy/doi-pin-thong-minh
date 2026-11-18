# P8-REF-0.1 — Refund design contract

16/11/2026,B0 only; **NOT IMPLEMENTED**. D01 Option B được người dùng phê duyệt trong [decision record](../../PHASE8B_DECISIONS_APPROVED.md). Không đổi GD1/GD2/Charge. Nội dung normative của contract gồm README này,`contract.schema.json`,`openapi.overlay.yaml` và `RETRY_PROTOCOL.md`. Schema kiểm shape;guards chéo bảng/thời gian/provenance dưới đây bắt buộc dù JSON Schema không biểu diễn được.

## Public API/auth/version

Giữ nguyên POST/GET `/v1/payments/{payment_id}/refund`,POST `/v1/refunds/{refund_id}/reconcile`;Admin-only request/reconcile,Admin/own-Customer read,Technician403. UserBearer+UUID Idempotency-Key cho mutation. `ReasonAction` giữ nguyên strict{expected_version,reason},không money/actor/role/desired state do client gửi. Request version=Payment.version,reconcile version=Refund.version. Case/swap/fence/proof versions đọc lại dưới khóa,không client chọn. Cùng principal/route/key/body replay durable response,khác body409;khác key không tạo intent thứ hai.

Response `Refunds` giữ nguyên GD2,no currency field mới:currency lấy original Payment VND,amount bằng full charge đãverified;requested_by/reason/provider IDs là contract read gốc,không lộ keys/rawledger/Technician proof. Reason có thể customer-visible,không dùng làm kho notes/credentials. Chưa có refund404,ownership403/404 theo convention hiện có. Không mở API history cho Technician hoặc generic state/custody update.

## Provider compatibility và negotiation

Giữ POST `/mock/v1/refunds`,GET `/mock/v1/refunds/{provider_key}`,X-Service-Key. Overlay là **additive OpenAPI3.1 design document**,không tự nạp vào runtime. Baseline file và source schemas Charge không đổi.

| Mode | Request/result | Idempotency |
|---|---|---|
| Baseline,không X-Refund-Protocol | Original ProviderRefundRequest/ProviderResult unchanged;adapter chỉ initial generation0,không cấp retry | Header/body provider_key theo baseline;duplicate cùng payload giữ kết quả |
| Versioned | Header `X-Refund-Protocol:P8-REF-0.1`,body protocol_version cùng giá trị,strict tagged command/response | ATTEMPT_REFUND HTTP key=attempt_id;REQUEST_RETRY_PERMISSION key=reconcile_request_id. provider_key là intent identity,bất biến qua mọi attempt |

Header/body không khớp422. Không thêm properties vào original closed schemas;oneOf branch mới có protocol discriminator nên không overlap baseline. Worker8B dùng versioned mode;không gửi extensions vào Charge. Versioned GET gửi `context` query parameter encoded JSON `QueryContext`;không chứa bearer/Service-Key/token. Baseline GET không có context trả summary kiểu cũ,không là permission retry. Không query key mới để né UNKNOWN.

Provider master lưu negotiation mode bất biến khi initial request được chấp nhận. Baseline-only master không được nâng cấp ngầm sang retry0.1;tagged permit request cho master này phải conflict. Backend8B khởi tạo intent/attempt bằng0.1 ngay từ đầu. Embedded baseline component copies trong OpenAPI overlay chỉ phục vụ standalone validation;composition chỉ thêm P8RF-prefixed definitions,không replace các schemas baseline/8A đang có.

Callback POST `/v1/payment-events` giữ Payment-Key. Không refund_id là charge như cũ;refund_id:null invalid. Versioned refund callback bắt buộc protocol_version,payment_id,refund_id,key,reference,money,attempt_id,generation và unique provider_event_id. Legacy refund callback chỉ được map generation0 nếu chưa từng cấp successor generation;không dùng untagged event sau retry. Không route ambiguous refund vào charge.

## State table

| From | Accepted event | To |
|---|---|---|
| none | Admin+fresh no-delivery certificate+quiescence+verified charge | REQUESTED |
| REQUESTED | Durable first dispatch claim | PENDING |
| REQUESTED/PENDING | Uncertain dispatch/timeout/lost response | UNKNOWN |
| PENDING | Verified final provider result | SUCCEEDED/FAILED |
| UNKNOWN | Authoritative query/callback for exact current attempt,final result | SUCCEEDED/FAILED |
| FAILED | Fresh Admin reconcile+provider permit+no-effect/denial proof+eligible physical context,claim retry | PENDING,original intent/key |
| SUCCEEDED | duplicate/late failure/pending | Remain SUCCEEDED;conflict disposition/query/audit as needed |

UNKNOWN+PENDING/NOT_FOUND is unresolved,notFAILED or automaticPOST. A callback may win first HTTP response:record dispatch evidence transition REQUESTED→PENDING→final in same transaction. FAILED terminal for one attempt;new attempt requires permit,not replacement refund. Financial Payment staysSUCCEEDED;never change custody/holds/old settlement or close compensation on refund success.

## Eligibility/locking and cross-module fencing

Admin request must use current valid certificate from P8-REC-0.3 or equivalent fully validated existing proof;flagNO alone never sufficient. No positive certificate for UNKNOWN/PREPARED/unresolved task/command,missing history,conflict,old boot,revoked witnesses or stale15s. Never deriveNO from empty slot/ACK/EXECUTED/timeout. old_pin_settled is not a prerequisite and is not changed by verification/refund.

Lock order:HTTP idempotency advisory →station advisory/row →sorted participant users →sorted swap/compartments/pins (existing station_locks) →Payment →Refund →attempt/permit/outbox rows →exact sessions sortedUUID. Gather all participant/session IDs before locking;never acquire a new user/station lock after session lock. Device ingress retains its existing device/source locking order under the same station mutex;new audit helper adds no locks. Provider SQLite uses one writer/refund-master transaction;no PostgreSQL lock during HTTP/provider wait or human confirmation.

Caller/witness role/state/station assignment/session revoked/expiry and proof boot/context/version/freshness are revalidated after waits at acceptance decision. Accepted Admin request/reconcile is a durable authorization;later logout does not undo money already authorized/processed. A new retry permission/generation requires a fresh valid Admin decision;no stale request authority can be used to create a later generation. Provider callbacks/outcomes do not require an interactive session to record financial truth.

At first or retry dispatch,require current eligible physical context and compatible durable fence;revalidate current boot/snapshot after lock waits. If the certificate expired before dispatch,do not POST;keep intent/holds and require a new read-only inspection/certificate plus Admin reconciliation for the same intent. If eligibility changes after an effect could have happened,only query provider and retain asset review;do not fabricate FAILED to reverse a real refund.

Intent creation commits refundREQUESTED,swapCOMPENSATING/version,audit before/after,outbox and idempotency response atomically. It redeems one certificate by append-only unique reference and binds its still-active device fence to that intent. Backend REFUND-present guard prevents new supply/resume;device fence permanently denies cached commands/activations captured at decision,including tasks fetched before fence. Future tasks need same station epoch and see fence/refund interlock. No automatic fence expiration at operationTTL or refundSUCCEEDED.

Keep existing Recovery refund-present guards. Safe old-pin processing after refund is8C dependency;do not remove guards to demo it.8B may record refundSUCCEEDED while old obligation false and3holds remain;that is not CLOSED_COMPENSATED.

## Data/grants/audit

Reuse refunds,payment_events,outbox_messages,audit_events. Add only append-only refund_attempts (unique refund+generation,unique attempt_id),provider retry-permit receipts,permit consumptions uniquepermit,certificate redemption unique certificate when necessary. One refund/payment and immutable provider_key/amount/charge identity/requested_by;no new Refund/Payment states. Provider ledger has unique payment refund master,cumulative effect count0/1 and exact attempt/permission/journal bindings. Provider identity/refund reference are stable across generations. Original charge reference must match provider charges ledger SUCCEEDED/full amount/currency.

Forward migration proposal only:freeze immutable fields/checks/attempt generation FK+uniques,limited runtime grants,append-only permit/proof/audit records. Runtime may update only state/version/reference/verified_at and outbox scheduling fields,not rewrite money/identity or delete history. Payment currency remains the source;no extra Refund.currency column needed for MVP. Validate from actual head and isolated schema during B1,not demo.

NFR06 audits:actual before/after aggregate state/version and immutable proof/intent/attempt/outbox refs,Admin/provider/system actor,transaction time,swap/payment/refund/command correlation as applicable. Creation before=null;dispatch/UNKNOWN/permit grant/consumption/reconcile/final result/conflict have separate truthful events. No raw reason/receipt body/password/header/key/token/QR;allowlist metadata. Audit+mutation+idempotency/inbox disposition same transaction;failure after audit INSERT rolls back all;replay no extra success audit.

Errors:reuse baseline401/403/404,409 state/version/idempotency/reference conflicts,422 schema/evidence/config,503 unavailable. Versioned codes proposed for B1:REFUND_RETRY_NOT_AUTHORIZED,REFUND_ATTEMPT_CONFLICT,REFUND_PERMIT_EXPIRED,REFUND_PERMIT_CONSUMED,REFUND_EVIDENCE_REQUIRED,REFUND_RESULT_MISMATCH (all409 except evidence422). Authentication uses existing AUTH_REQUIRED/session codes. Never include private payload in errors. These are appendix codes,not edits to baseline enums.
