# Phase 8B — Refund mock design proposal

## B0 checkpoint16/11/2026 — current design baseline

**B0 CONTRACT FROZEN — READY FOR B1 IMPLEMENTATION REVIEW.** P8B-D01 Option B vàP8B-D02 VERIFY_NO_DELIVERY đãAPPROVED BY USER. [Decision record](PHASE8B_DECISIONS_APPROVED.md),[freeze/traceability/locking/audit/B1–B5 handoff](PHASE8B_B0_CONTRACT_FREEZE.md),[Refund overlay](implementation-contracts/P8-REF-0.1/README.md),[Recovery0.3 overlay](implementation-contracts/P8-REC-0.3/README.md) là baseline hiện hành. Staticvalidation exit0:2bundles/34definitions,77shapechecks,2standaloneOpenAPI vàmerged8A+8Bspec hợp lệ;legacyCharge/security/Recovery0.1/0.2 không đổi.179sourcehashes delta0.

Freeze chỉ chốt thiết kếB0,không runtime acceptance8B hoặc quyền tự codeB1. Runtime/PGconcurrency/crash/E2E/migrations **NOT RUN**;không refund/physical effects,production changes,stage/commit/push hoặc8C. Phase8A conditional acceptance giữ nguyên;NFR04/NFR07/CT14/NFR08 vẫn OPEN. Nội dung initial review dưới đây giữ lịch sử trước approval/B0,không dùng trạng tháipending/proposed cũ thay checkpoint mới này.

## Initial review — historical

16/11/2026. **PROPOSED / NOT APPROVED / chưa implementation**. Baseline gốc giữ nguyên; phụ lục đề xuất `P8-REF-0.1` chưa được tạo thành contract/runtime trong lượt này. [Readiness](PHASE8B_READINESS_REVIEW.md),[test plan](PHASE8B_TEST_PLAN.md).

## 1. Boundary và API gốc

| Operation | Route | Actor/input/response |
|---|---|---|
| requestRefund | POST /v1/payments/{payment_id}/refund | Admin,UserBearer+Idempotency-Key,ReasonAction{expected_version,reason};202 Refunds |
| getRefund | GET /v1/payments/{payment_id}/refund | Admin hoặc Customer chính chủ;200 Refunds,404 chưa có;Technician403 |
| reconcileRefund | POST /v1/refunds/{refund_id}/reconcile | Admin,UserBearer+Idempotency-Key,ReasonAction;202 Refunds |
| providerRefund | POST /mock/v1/refunds | Backend,X-Service-Key+Idempotency-Key;ProviderRefundRequest;202 ProviderResult |
| providerQueryRefund | GET /mock/v1/refunds/{provider_key} | Backend,X-Service-Key;200 ProviderResult |

Callback vẫn POST /v1/payment-events,Payment-Key,bắt buộc payment_id và refund_id cho branch refund;không refund_id là charge. refund_id:null tiếp tục invalid,không rơi xuống charge. Kiểm full identity trước inbox write. Không tự thêm public endpoint.

ReasonAction strict chỉ expected_version>=1 vàreason nonempty;amount/currency/desired state/custody từ client bị reject. Đề xuất mô tả expected_version của POST request là **payment.version** theo resource trong URL;reconcile dùng **refund.version**. Case/swap version đọc dưới locks không do client khai. Cần ghi mô tả này trong appendix trước tests,không thêm version field trái strict input.

Refunds schema gốc gồm id,payment_id,requested_by,provider_key,provider_reference,state,amount_minor,verified_at,reason,version,created_at. **Không có currency**:dùng original Payment.currency để provider call/UI hiển thị,không tự thêm field vào strict response. Customer chỉ GET đúng payment của mình,không truy cập Technician recovery proof/raw ledger. requested_by/reason là trường đã có trong contract;không ghi internal secrets vào reason;muốn giảm fields phải duyệt projection schema riêng,không âm thầm đổi response.

ProviderRefundRequest gốc:payment_id,refund_id,provider_key,original_provider_reference,amount_minor,currency=VND. ProviderResult gốc gồm key/reference/result/amount/currency;result NOT_FOUND/PENDING/SUCCEEDED/FAILED/UNKNOWN. Các errors giữ HTTP401/403/404/409/422/503 đúng contract;duplicate-event/body/version code cụ thể tái dùng conventions khi cùng nghĩa,code mới cần appendix. Không sửa x-roles/bearer allowlist toàn hệ thống để mở Refund.

## 2. Eligibility và transaction model

Admin yêu cầu hoàn **full original verified charge**,không phụ thuộc old_pin_settled=true như điều kiện tài chính (BR08/Invariant7). Nhưng phải có **positive no-new-delivery proof hiện hành** và mọi command/service không còn khả năng gây giao pin. FlagNO,holder DB,ngăn rỗng,ACK hoặc note không đủ. UNKNOWN/PREPARED,boot mismatch,missing/stale/conflicting evidence phải chặn,không default NO. D02 bên dưới là gap cần phê duyệt cho nhánh old unsettled.

Đường request đề xuất:

1. Principal+route+key advisory idempotency;return exact receipt nếu đã commit,khác body409. Đọc ID để tìm trạm,không dùng state đọc sơ bộ làm quyết định.
2. Shared station advisory/row lock → sorted participant users (Admin,Customer,Technician witnesses) → sorted swaps/compartments/batteries tương thích station_locks → payment → existing refund → exact caller/witness sessions theo UUID order. Nhánh device ingress giữ thứ tự hiện có,không thêm lock ngược;worker không lấy idempotency sau station.
3. Đọc lại role/state/session Admin,owner/scope/provenance witnesses,Payment SUCCEEDED/verified/reference và case/swap state. Existing refund khác key không tạo intent mới;đề xuất409 theo version/resource conflict hoặc replay cùng HTTP key;không dùng key mới đổi reason của intent cũ.
4. Đối chiếu toàn command/service ledger/current boot+snapshot+accepted evidence;require durable fence/quiescence bao phủ commands nhận trước fence,không chỉ queue mới. Recheck version/expiry/freshness **sau lock waits và trước writes**. Không network/HTTP dưới DB locks.
5. Trong cùng commit:refund REQUESTED amount=payment.amount,currency từ Payment,immutable provider_key;swap REVIEW_REQUIRED→COMPENSATING/version+1 theo SM-03b/AD-04b;outbox REFUND dedup;safe before/after audit;idempotent response. Không đổi Payment,custody,old settled,holds. Lưu proof IDs/hash/boot/fence generation đã quyết định;không tự nâng case UNKNOWN→NO khi proof thiếu.

Proof binding đề xuất có thể nằm server-built outbox payload+audit references tới immutable attestation/context,không nhất thiết bảng mới. Nếu cần persist certificate riêng cho D02,thiết kế append-only liên kếtcase/swap/version/boot/command+service digest;không duplicate recovery model. Bất kỳ quyết định NO mới phải có audit before/after của case và nguồn được duyệt.

Refund intent tồn tại phải chặn mọi path resume/authorization/task có thể giao pin mới,bao gồm cached commands đã nhận:Backend mutex ngăn writers mới;simulator durable fence ngăn external effects cũ. Transaction PostgreSQL không tự thu hồi task SQLite đã cache. Nếu không chứng minh durable fence+no-effect closure phù hợp hiện có thì **chặn request**,không gọi provider. Kiểm trước first POST nếu outbox đã chờ;không làm mới timestamp của proof cũ. Sau dispatch,financial result là bằng chứng provider,không được biến refund thực tế SUCCEEDED thành FAILED chỉ vì snapshot sau đó mâu thuẫn;giữ tài sản/review và audit conflict.

## 3. State machine / retry

| From | Event/guard | To |
|---|---|---|
| Không refund | Verified Admin request+eligibility | REQUESTED |
| REQUESTED | Durable dispatch claim cùng key | PENDING |
| REQUESTED | Không rõ dispatch đã thành công | UNKNOWN |
| PENDING | Verified provider final | SUCCEEDED hoặc FAILED |
| PENDING | Timeout/response loss/conflict | UNKNOWN |
| UNKNOWN | Authoritative query/callback final hợp lệ | SUCCEEDED hoặc FAILED |
| FAILED | Admin reconcile+provider cho phép retry,no previous refund effect | PENDING cùng intent/key,**chỉ sau D01** |
| SUCCEEDED | Duplicate hoặc late FAILED/PENDING | Không downgrade;conflict audit/query/review |

Không thêm enum RETRYING/REFUNDED/CANCELLED. Payment charge **luôn SUCCEEDED** sau refund. RefundSUCCEEDED không CLOSED_COMPENSATED,không release holds;8C mới finalizer đủ refund và old settlement.

Worker:process inbox riêng charge/refund trước;claim outbox REFUND dưới station/payment/refund/outbox locks rồi commit;chỉ first unattempted REQUESTED được POST. Nếu crash sau claim trướcHTTP,không biết đã gửi nên UNKNOWN/query cùng key;**NOT_FOUND không tự cho gửi lần nữa** khi chưa có proof/capability an toàn. Tiếp tục UNKNOWN nếu chưa phân giải;không suyFAILED từHTTP503/timeout.

Call provider ngoài locks;apply result bằng transaction mới,kiểm identity/amount/currency/reference ownership,event provenance vàexpected state. callbacks có thể thắng HTTP response;đường REQUESTED→PENDING→final cùng transaction giữ SM-04. Provider reference collision dùng advisory ownership lock+UNIQUE+savepoint trước durable rejection để không abort inbox (P6-A01). Reject sai identity không poison inbox,event ID sai body409(P6-A02). Chỉ55P03 bounded retry ngoài transaction(P6-A03),không nuốt lỗi DB khác hoặc retry HTTP vô hạn. Outbox polling dùng durable schedule,không busy loop;UNKNOWN không có TTL tự release.

## 4. Provider ledger và callback

Mở rộng ledger SQLite riêng với refunds (unique key/refund_id/payment_id,original charge reference,canonical request hash,full amount/currency,stable refund reference,result,effect count);charge row phải SUCCEEDED/đúng amount,currency,identity trước effect. Một payment chỉ full refund1lần,tổng≤charge. Charges ledger giữ nguyên;không reset file/schema demo.

PREPARED/dispatch marker bền vững trước refund effect. Simulator ghi receipt/effect count/result/outbox atomically trong durable ledger khi effect có thể mô phỏng bằng cùng transaction;crash PREPARED không có terminal receipt phải UNKNOWN/query,không thực hiện effect lần hai. Callback dùng refund_id+payment_id+key+reference+money,service auth đúng;persist pending delivery/event ID trước gửi,replay cùng ID/body. D01 cần nhận diện retry attempt nếu hỗ trợFAILED→PENDING;không tạo provider key/refund intent thứ hai.

Inbox payment_events dùng cộtrefund_id sẵn có:validate refund.payment_id==payment_id/key/money rồi INSERT accepted event. Worker dispatch theo refund_id,không áp charge. Provider_event_id namespace phải global unique gồm loại đối tượng;giữ unique constraint hiện có. Callback/query race serialize bằng same station/payment/refund locks. Success receipt khác refund không được chiếm reference;savepoint rollback giữ outer event disposition.

## 5. Data/grants/audit proposal

Không tạo lại refunds/payment_events/outbox. Schema0001 đã unique payment_id/provider_key/provider_reference,amount>0,version>0 nhưng không tự enforce amount=charge,requested_by Admin,refund/payment link ởinbox hoặc full sum cross-table. Backend guards vàprovider ledger làbắtbuộc;forward migration có thể thêm immutable binding trigger cho payment_id/provider_key/amount/requested_by và CHECK result-time coherence sau kiểm tra data hiện có. Currency giữ trên originalPayment;không thêm mặc định tài chính mới.

Cần grant runtime SELECT/INSERT và UPDATE chỉ các cột chuyển trạng thái/reference/verified_at/version cần thiết trênrefunds;khôngDELETE,broadUPDATE audit/immutable payload. Kiểm grants mới và upgrade từ0008 trên test schema;chưa ấn định migration number trước khi kiểm head thật. Thêm attempt/permit table/certificate chỉ nếu D01/D02 duyệt và chứng minh existing columns không đủ,không thực thi migration ở lượt này.

Refund audit allowlist actual BEFORE/AFTER trong mutation transaction:refund state/version,amount/payment refs,swap state/version và case/evidence refs,protectedPayment/custody/holds facts;creation before-objectnull. ActorAdmin/device-provider/system,DBtime,swap correlation/payment/refund/outbox/event refs. Không logreason freeform toàn bộ,password,Service-Key,callback key,raw QR,payload/token. Audit action names mới là implementation appendix cần review;không đổi nghĩa action8A. Rollback/replay phải một hoặc không success audit,không ghost receipt.

## 6. Quyết định cần người dùng review — chưa approved

| ID | Gap/lựa chọn | Đề xuất và tác động |
|---|---|---|
| P8B-D01 | ProviderFAILED retry chưa có handshake trong strict schema. A:mock provider không cho phép retryFAILED,chỉquery/fail-closed theo conditional SM-04. B:hỗ trợ retry có explicit permit/attempt binding | Đề xuất B nếu muốn nghiệm thu nhánhFAILED→PENDING:private versioned refund-only request/result/callback appendix mang durable retry authorization/generation,Admin khởi phát qua reconcile hiện có;không đổi intent/key. Cần chốt representation/replay/late-attempt rules trước code. Không tự dùng network replay làm retrypermission. A an toàn nhưng không được báo đã kiểm positive retry khiprovidercho phép |
| P8B-D02 | Thiếu đường proof độc lập cho NO khi old_pin_settled=false;không yêu cầu Admin/Frontend tựdeclareno-delivery | Đề xuất narrow read-only Technician no-delivery inspection/evidence context,cócurrent simulator supply serial+allledgers/boot/fence và human attestations theo appendix được duyệt;chỉ Backend kết luậnNO,không custody/oldsettled/action. Cần chốt có tái dùng operation purpose hiện có đủ semantics hay bổ sung VERIFY_NO_DELIVERY qua overlay. Không tự thêm enum/API hoặc dùng fixtureNO giả. Nếu chỉ hỗ trợ existing8A NO thì phầnold-unsettled positive scenario vẫn BLOCKED |

Hai decisions là implementation/contract gap,chưa phải findings làm mất acceptance8A. Sau refund xuất hiện,existing8A settlement guard chặn;không gỡ guard để trả pin cũ sau refund trong8B. Thiết kế8C sau này phải xử lý riêng quyền giữ pin và finalizer;8B chỉ chứng minh refundsuccess giữ unresolved old obligation/holds.

## 7. Increment order và completion gates

| Increment | Nội dung khi được giao code | Gate hoàn thành |
|---|---|---|
| B0 | Chốt D01/D02,versioned appendix+error/version semantics và cross-module fence matrix | User approval rõ;không còn nhánh phải suy chính sách |
| B1 | Schema/grants tối thiểu,strict API/domain guards,Adminrequest/read,idempotency/audit,outbox,no provider effect | PostgreSQL migration/rollback/RBAC/2Admin race;positive proof không SQL fixturecustody |
| B2 | Durable provider refund+query,original-charge identity/full amount,dedup vàcrash boundaries | Separate process/ledger restart;effect≤1,payment charge không đổi;D01protocoltests |
| B3 | WorkerREFUND/callbackinbox/query/timeouts/reconcile+attemptbinding | P6-A01–03 regressions,NOT_FOUND ambiguity failclosed,callback/query race,OS crash before/after commit |
| B4 | Minimal Adminrequest/reconcile vàCustomerreadonly refund display theoAPI gốc | Backend RBAC directAPI,UIloading/error/UNKNOWN/reload/idempotency;không mở8Cscreen/finalizer |
| B5 | Full isolated real-process TC16/CT13,refund-vs-Recovery/device races,fullregression/validators/Browser affected | Evidence đủ,một refund effect;custody/holds/payment invariants;audit before/after;noMajor. Không dùng603 lịch sử thay fullsource8B |

Không bắt đầu increment trong lượt review này. Kết luận **PARTIAL/BLOCKED cho toàn8B implementation**,đủ hồ sơ để user review D01/D02 và giaoB0/B1;không chấp thuận tự động.
