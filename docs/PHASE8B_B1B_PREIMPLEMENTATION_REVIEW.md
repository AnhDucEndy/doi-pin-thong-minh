# Phase 8B — B1b pre-implementation review

18/11/2026 (+07). **B1b PRE-IMPLEMENTATION REVIEW PASSED — READY FOR USER IMPLEMENTATION APPROVAL.**

Đây là kết luận về thiết kế và kế hoạch kiểm thử, không phải quyền bắt đầu code, nghiệm thu B1b hoặc kết quả chạy B1b. Production, migrations, contracts và các baseline không được sửa trong lượt này. Tất cả tests B1b bên dưới vẫn **PLANNED / NOT RUN**.

## 1. Checkpoint và nguồn quyết định

- `main`; HEAD và local `origin/main`: `0024c5f2ddac4c1652e77dcff2acf48fd791b8e0`. Parent `f51ba7d37a04be4f2ebd80ce76f4a1f28a510ea1`; B0/B1a đã push theo `PHASE8B_HANDOFF/push_20261118_01/PUSH_REPORT.md`. Không truy vấn remote mới trong lượt thiết kế.
- Index rỗng; chỉ tracked modification có sẵn `docs/PHASE5_TEST_ENVIRONMENT.json`. 1888 untracked paths tại preflight được giữ nguyên.
- Kiểm chứng tĩnh mới: accepted191/191 và reviewer192/192 khớp raw HEAD blobs lẫn filesystem; prior-overlay25/25 và B0 frozen16/16 khớp. Tracked filesystem/config/attributes/exclude không delta so checkpoint push readiness.
- Alembic **source head**: `0009_refund_foundation`. Không khẳng định live/demo DB ở revision này; không kết nối DB, Docker hoặc chạy migration.
- Evidence: `PHASE8B_HANDOFF/b1b_preimplementation_20261118_01/source_checkpoint.json` và `review_validation.json`.

Thứ tự áp dụng: GD1/GD2 và QD01–09 approved; D01/D02 approved; B0 frozen normative README/schema/OpenAPI/retry protocol; B1a acceptance và source cuối. Những chữ “NOT IMPLEMENTED”/“NOT STARTED” trong hồ sơ cũ mô tả checkpoint lịch sử. Phase thực tế không đổi mã FR/UC/BR/TC/CT của handoff.

Nguồn chính đã đối chiếu:

| Nguồn | Phần dùng trong B1b |
|---|---|
| `AGENTS.md`, `doi-pin-giai-doan-2/CODEX_START_HERE.md`, `handoff/CODEX_HANDOFF.md` | Phạm vi mô phỏng, nguồn chuẩn, grants/transactions/test evidence |
| `doi-pin-giai-doan-2/handoff/DECISIONS_APPROVED_2026-10-23.md` và approved config | NETWORK ownership, Admin/Technician độc lập, full mock fee từ Payment; ACK15/physical60/freshness15 không đổi |
| `doi-pin-giai-doan-2/database/INVARIANTS.md`, `handoff/ACCEPTANCE.md`, `contracts/traceability.csv` | Invariants6–8; FR12/16, UC10/14, TC12/16, CT07/08/10/11/13 |
| `PHASE8B_DECISIONS_APPROVED.md`, `PHASE8B_B0_CONTRACT_FREEZE.md` | D01/D02; lock, audit, data và B1b boundary |
| `implementation-contracts/P8-REC-0.3/README.md` ``1–60 và 17 definitions | Purpose/stage/read-only transport, three-source proof, history/fence, certificate/successor/revocation |
| `implementation-contracts/P8-REF-0.1/README.md` ``5–60; `RETRY_PROTOCOL.md` | Admin authority, ReasonAction, atomic intent/redemption/outbox, financial separation; phần provider để sau |
| `PHASE8B_B1A_USER_ACCEPTANCE.md`, B1a implementation/deadlock/IA01/re-review, `IMPLEMENTATION_STATUS.md` | Foundation đã accepted; protected authority và FK lock compatibility phải giữ |

B0 freeze16 không gồm phép so sánh nội dung cũ của IMPLEMENTATION_STATUS đã cập nhật có phê duyệt; file đó được bảo vệ riêng bằng checkpoint hiện tại. Không sửa freeze để che delta.

## 2. Phạm vi implementation đề nghị phê duyệt

**Bao gồm:** strict runtime branch0.3 trên routes hiện có; current read-only simulator inspection và complete history/quiescence; Technician/Customer attestations; Backend certificate issue/revoke; read-only successor; Admin first Refund request, durable certificate redemption, initial attempt identity và outbox. GET projections tối thiểu theo frozen schema cũng thuộc transport, không phải UI mới.

**Không bao gồm:** provider Refund API/effect, retry FAILED/permit consumer, Refund worker/callback/query/reconcile execution, UI/Browser mới, xử lý pin cũ/compensation/release fence thuộc8C, B2–B5. Existing CHARGE setup có thể được runner Phase6 chuẩn dùng để tạo khoản thu đã verified; không dựng Payment thành công bằng SQL và không gọi provider refund.

B1b kết thúc ở `Refund.REQUESTED` với job `REFUND` chưa dispatch. Không gọi trạng thái này là “đã hoàn tiền”.

## 3. Gap analysis trên source hiện tại

| Điểm hiện có | Khoảng trống B1b / xử lý đề xuất |
|---|---|
| `application/refunds.py::request` L53–64 | Hiện cố ý422 REFUND_EVIDENCE_REQUIRED. Chỉ thay nhánh dương sau full certificate/context guards; mọi negative foundation giữ nguyên |
| `refunds.py::lock_context` L29–50 | Mới khóa caller Admin session. Phải thu thập và khóa **toàn bộ exact witness/caller sessions**, không thêm user lock sau session |
| `main.py::mutation` L92–94; `identity.idempotent` L68–86 | Generic mutation không cung cấp protected authorization callback. Nhánh0.3 và positive Refund phải dùng authorize callback **sau idem wait, trước cache lookup**, kể cả replay; không đổi hành vi mọi route một cách toàn cục |
| `assets.operator_mutation` L92–130 | Tham khảo pattern authority/replay và savepoint rollback, không gọi nguyên xi: helper này mới biết một operator và status200, không đủ witness tập thể/Refund202 |
| `recovery.py::quiet` L103–131 | Predicate dùng snapshot ledger và purpose-specific exception của8A. **Không dùng làm sufficient proof0.3**, không nới UNKNOWN/EXECUTED exception. Tạo guard no-delivery riêng |
| `recovery_authorization.py::human/guards` | Có IA01 session/boot/final-time checks nhưng foreign-only0.2, có historical POST semantics. Reuse pure checks thích hợp qua adapter; không đưa0.3 vào historical exception |
| `recovery_inspection.py::receive/accept` | Durable inbox, rejected outcome và savepoint đã có; accept hiện foreign-only. Thêm dispatch0.3 riêng, không “mở” accept0.2 |
| `api/recovery_schemas.py` và `api/recovery.py` | Chưa có0.3 DTO/union/task/response. Dùng đúng17 frozen definitions; không thêm endpoints/enums/body fields |
| `recovery_projection.py::project` | Chỉ legacy/0.2. Cần exact CustomerProjection0.3 riêng, owner-only; không trả old internal view dưới nhãn0.3 |
| `0009_refund_foundation.py` L85–110 | Certificate/redemption tables đã có, append-only và FK/payment binding; runtime chỉ SELECT. Chưa có0.3 operation/stage support, issuer/revocation validation/grants |
| `simulators/device/recovery_fence.py` | Có durable active fence, writer mutex và immutable0.2 receipt; chưa có0.3 history/deny coverage/transport |
| `Simulator._handle`, `service.perform`, `recovery_handover.validate` | Có effect-point checks. B1b cần inventory/deny cả fetched/cached tasks và đầy đủ history across boots; không coi thiếu row là NEVER_PREPARED |
| `application/device.py::command_allowed/poll/enqueue_command` | Guard active recovery hiện chủ yếu theo swap. B0 yêu cầu station fence; cần narrow0.3 station-level predicate dùng cả pending inspection, certified và refund-bound fence, kể cả op hết hạn |
| `workers/payment.py::tick` L55–58 | Chỉ claim kind CHARGE. Giữ nguyên; kiểm chứng job REFUND không bị claim/ack/POST bởi worker này |
| `refund_audit.py` / `recovery_audit.py` | Actual snapshot/redaction foundation có; bổ sung allowlisted certificate/revocation/redemption/child và swap-version refs; giữ nghĩa21 action8A |

Đây là các dependency triển khai đã được B0 dự kiến, không phải findings mới về một positive workflow B1b đã chạy.

## 4. API, actors và representation

| Operation / route hiện có | Branch / actor / response |
|---|---|
| `POST /v1/swaps/{id}/recovery/evidence` | Assigned Technician; UserBearer + UUID Idempotency-Key.0.3 BeginRequest / TechnicianAttestation / DecideRequest;200 NoDeliveryResponse; expected_version=case.version |
| `GET /v1/device/recovery-tasks` | Station Device-Key; thêm task item `{protocol_version:"0.3",task_kind:"VERIFY_NO_DELIVERY_INSPECT",context:Context,effect_allowed:false}` |
| `POST /v1/device/recovery-observations` | Station Device-Key; strict0.3 Observation;202 receipt{id,accepted,duplicate}; không UserBearer thay thiết bị |
| `POST /v1/swaps/{id}/recovery/confirmations` | Own Customer; exact0.3 StageReference + confirm;201. **Không thêm expected_version** vào closed body0.3; server kiểm current operation/context/receipt dưới khóa |
| `GET /v1/swaps/{id}/recovery` | Admin / assigned Technician; response0.3 branch theo current operation |
| `GET /v1/swaps/{id}` | Existing ownership; thêm đúng CustomerProjection0.3 vào recovery_confirmation union; không cho Customer đọc full Recovery API |
| `POST /v1/payments/{id}/refund` | Admin; existing ReasonAction{expected_version,reason};202 Refunds. expected_version=Payment.version. Backend tự chọn certificate hiện hành của đúng Payment/case |
| `GET /v1/payments/{id}/refund` | Admin / own Customer; output cũ, không thêm ledger/certificate/raw witness/session |

`reconcileRefund` vẫn fail-closed theo B1a; không tạo job query/FAILED retry trong B1b. Không enable P8RF callback/provider branches chỉ vì chúng có trong standalone B0 overlay.

Composition: chỉ thêm prefixed `P8ND*` definitions và UNION branches vào runtime Recovery/input/response/task-items/Customer projection. Giữ path/opID/security/x-roles cũ, strict extra=forbid và các schema Charge. Không copy embedded baseline components đè runtime. Typed DTO phải phân biệt0.3 với legacy/0.2, không bắt nhầm0.3 qua legacy statement.

Customer reference là handle tới accepted facts, không là authority. Backend chọn stage/receipt/context từ DB rồi so request; caller không chọn holder, recipient, actor, NO, custody, amount hoặc terminal state. State AVAILABLE/UNAVAILABLE/CONFIRMED/REJECTED/EXPIRED/CONSUMED/REVOKED chỉ dùng khi facts tương ứng tồn tại; không invent WAITING_RECEIPT/CANCELLED cho closed0.3 enum. Một cancelled/noncurrent context không được trình bày AVAILABLE.

## 5. Nguồn chứng cứ và complete-history design

### 5.1. Cùng một proposition, ba nguồn độc lập

SIMULATOR đọc supply slot thực: present, CLOSED, actual_serial từ model; expected_serial chỉ là interlock. Đối chiếu new_battery_id, supply/return slots, current device/station/boot, accepted+processed source SNAPSHOT và current projection. Không lấy heartbeat/seq cao làm độ mới vật lý.

Backend new-pin custody projection cũng phải nhất quán với history và supply slot; nếu nó đã ghi holder/delivery khác thì đó là contradiction, không “sửa lại” bằng verification. Tuy nhiên không đòi pin cũ đang ở đâu/old_pin_settled=true để chứng minh chưa giao **pin mới**. Không reuse nguyên xi `payments.resources_valid()`/`swaps.supply_ready()` hoặc predicate hai ngăn/old custody của `recovery.current_snapshot()`: các hàm đó có điều kiện cấp pin/settlement cũ ngoài proposition0.3. Tách source/provenance/currentness checks thích hợp; không tự thêm ngưỡng SOC/SOH/old-return-settlement làm chính sách Refund. Pending/unresolved old command vẫn chặn do quiescence, không phải do yêu cầu old obligation đã hoàn tất.

TECHNICIAN phải là creator witness, còn ACTIVE/TECHNICIAN và assigned station. CUSTOMER đúng swap owner. Backend suy actor/session từ session đã xác thực; human observed_at/received_at do server sinh sau receipt. Ba nguồn cùng operation0.3, stage NO_DELIVERY_INSPECTION, context hash, actual serial và receipt ID/hash; không reuse PRE/POST/successor0.2.

DECIDE là yêu cầu Backend đánh giá của assigned Technician, không là client gửi kết luận NO. Caller và Technician witness có thể dùng hai session khác nhau; collector không giả định session caller = session witness. Phải khóa/kiểm cả hai nếu khác nhau.

### 5.2. Delivery history phải kiểm được, không chỉ assert complete=true

Đề xuất serializer nội bộ0.3, cùng golden vectors cho Simulator/Backend:

1. Stable ledger_id; immutable journal genesis chỉ tạo cho **new model/ledger chưa có lịch sử**. Ledger cũ thiếu coverage/witness không backfill một lời chứng “chưa giao”; nhánh0.3 giữ UNKNOWN.
2. Journal append trong cùng SQLite transaction với mỗi command effect, service effect, actual source event và boot marker. Ghi register/fetch identity trước khi command/task có thể được effect handler dùng. Không xóa/truncate history qua reboot hoặc TTL.
3. Observation gửi **toàn bộ** command_entries và service_entries theo frozen shape; Backend kiểm exact identity coverage với command rows, operation/authorization/activation records và source receipts, không chỉ entries của swap hiện tại nếu fence bao trùm station.
4. DeliveryHistory.event_ids dùng thứ tự journal ổn định across boots, giữ event IDs/hashes gốc. Backend nạp các events đã accepted+processed, phục dựng envelope/hash bằng formatter gốc; đối chiếu boot_ids, command/swap/slot/serial bindings và tất cả nguồn có thể giao new serial. Thiếu nguồn, thiếu ID, duplicate identity, gap hoặc service receipt chưa được đối soát: từ chối.
5. Backend **tự tính** delivery_count từ actual pickup/transfer history và correlated terminal outcomes. Present(new serial) hiện tại không phủ định một delivery cũ. Command ACK/EXECUTED không thay delivery proof. History có giao/đưa pin ra rồi quay lại vẫn không được cấp certificate NO.
6. command_digest/service_digest canonicalize danh sách đầy đủ, không map loại bỏ duplicate trước khi kiểm. journal_hash nội bộ được chốt trong code/tests từ canonical object gồm binding ledger/swap/serial, ordered event ID + stored envelope-hash/boot/seq, command_digest và service_digest. Simulator và Backend tính độc lập từ local journal và accepted PostgreSQL facts; không thêm field vào wire schema.
7. Giữ nguyên hash formatter của **legacy command body** và DeviceEvent envelope. Chúng khác formatter `canonical_hash` của Recovery; không rehash/normalize dữ liệu cũ bằng formatter mới.

Event/receipt ordering cần một high-watermark adapter bền vững cho current boot và các channel mà0.3 sử dụng; không reset seq hoặc reuse event ID khi restart. Không lấy thẳng `next_sequence()` dựa service-count làm chứng cứ rằng seq đã mới hơn source SNAPSHOT. Chốt domain/canonicalization bằng tests source+receipt+ACK+closure interleaving; không thay timestamp hoặc diễn giải lại legacy accepted sequences. Simulator boot phải được Backend xác nhận qua processed snapshot **trước** khi dispatch task/evidence của boot đó.

“Độc lập” không có nghĩa tạo một cảm biến mới: nguồn thiết bị vẫn là authenticated simulator được tin cậy trong MVP. Backend không chấp nhận các scalar complete/digest/count do caller khai mà thiếu correlation/coverage. Không chứng minh chống một thiết bị có Device-Key hợp lệ cố ý làm giả toàn bộ physical model ngoài trust model MVP. Nếu không biểu diễn/kiểm được một coverage bắt buộc bằng frozen fields và retained facts, **BLOCK nhánh**, không tự thêm endpoint/proof semantics.

### 5.3. Matrix fail-closed

| Tình huống | Kết luận0.3 |
|---|---|
| Backend command UNKNOWN, dù ledger EXECUTED/effects1 | Không certificate; dùng reconciliation đã duyệt trước, không chuyển UNKNOWN thành NOT_EXECUTED |
| DISPATCHED/ACKNOWLEDGED/QUEUED còn có thể gây effect | Không certificate khi chưa có terminal verified result hoặc positive never-prepared + permanent denial đủ scope |
| Ledger UNKNOWN / service PREPARED/UNKNOWN / missing journal | Không certificate dù effects=0, hết hạn hoặc hiện slot có pin |
| OPEN_RETURN terminal với verified history | Có thể là lịch sử trả pin; không suy thành delivery/new-pin NO; các điều kiện khác vẫn bắt buộc |
| OPEN_SUPPLY EXECUTED/ACK đơn lẻ | Không đủ; unresolved block, delivered history block |
| Old boot/high seq hoặc snapshot chỉ QUEUED trong inbox | Không current proof; rejected input không làm mới current projection |
| Một source REJECT, sai serial/context, hoặc contradiction | Không majority vote; giữ UNKNOWN/review/fence; lời chứng hợp lệ REJECT vẫn append-only |
| Missing legacy coverage | Giữ fail-closed; không “migrate” absence thành positive proof |
| Full actual history delivery0 + all terminal/never-prepared/denied + current3proof | Có thể issue certificate tại final decision, bất kể old_pin_settled=false/true |

Frozen Observation chỉ biểu diễn positive OBSERVED/present/complete/delivery0. Khi inspection thực tế không đủ điều kiện, Simulator giữ factual journal/fence/local diagnostic và không manufacture một packet positive. Không thêm UNKNOWN branch vào frozen schema. Schema refusal khác một structurally-valid receipt đã được inbox disposition; retry receipt đã bị semantic rejection không được rehabilitate.

## 6. Durable fencing và non-atomic PG/SQLite boundary

Không có distributed transaction PostgreSQL+SQLite. Thứ tự an toàn:

1. PG BEGIN operation0.3 commit dưới station/user/resource/session locks; station-level Backend interlock có hiệu lực từ operation pending.
2. Ngoài PG locks, simulator re-fetch/authenticate exact task; SQLite BEGIN IMMEDIATE dùng **cùng writer mutex** với effect paths. Install persistent fence, register permanent denials cho đã fetched/cached command IDs/activation IDs và future incompatible tasks; capture actual model/history. Commit fence/denial kể cả khi không thể phát positive certificate observation. Không biến UNKNOWN/PREPARED thành no-effect.
3. Transport receipt outbox bền vững gửi qua API. Backend chỉ accept khi full provenance/coverage kiểm được. Crash giữa2/3 chỉ để lại fence chặt hơn và pending/rejected receipt; không mở đường effect.
4. Issue certificate ở PG không tháo fence. Admin redemption liên kết certificate→Refund bằng append-only record, qua certificate chứa ledger_id/fence_generation/digests. Không cần HTTP ACK riêng để “bật” Refund fence: physical fence đã installed và không tự đóng.
5. Refund-bound fence và union deny history sống qua TTL, cert expiry, restart, redemption hoặc Refund result sau này. B1b không có release path.

Phải inventory mọi issuer và final effect point: `Simulator._handle/_execute_command`, legacy `service.perform`, staged `recovery_handover.validate/perform`; Backend `device.command_allowed/poll/enqueue_command` và `recovery.tasks/settle(RESUME_SWAP)`. Cached task phải kiểm **trong writer transaction sát effect**, không chỉ lúc poll. Direct call bypassing adapter phải bị từ chối hoặc không có quyền đi vào effect engine. Mixed binaries chưa được chứng minh phải coi là thiếu all-issuer coverage.

Backend predicate0.3 phải theo **station**, kể cả khác swap ở cùng trạm và kể cả certificate đã redeem/op đã terminal. Reuse durable operation/receipt/certificate/redemption links; không tạo một bool RAM “fence active” hoặc một shadow mutable physical truth. Consumed/cancelled metadata không tự chứng minh fence CLOSED. Không cấm read/query hoặc sửa legacy physical semantics khi không có0.3 fence.

Successor chỉ từ eligible expired/rejected readonly0.3 predecessor: new context/IDs/current3proof; PG station/case serialization trước, local SQLite chuyển owner fence dưới một transaction và giữ union denials. Không dùng0.2 ER-02 CLOSURE_COMMITTED để đóng0.3 fence. Stale proof không được làm mới timestamp; nếu cần successor mà precondition frozen chưa thỏa thì chờ/giữ review, không tự cancel/renew để tạo happy path.

## 7. Certificate authority, binding và durable redemption

**Issuer là Backend service**, do assigned Technician yêu cầu evaluate. Chứng cứ Technician/Customer không tự là certificate và Admin không được ký thay hai nguồn. Đề xuất lưu `issued_by`/`issuer_session_id` ở private storage và audit để giữ exact caller của quyết định issue (có thể khác session của Technician witness); không tự thêm issuer field vào closed public EligibilityCertificate. Collector của first Admin decision bao gồm provenance này cùng caller/witness IDs, không chỉ user_id trùng nhau mà bỏ sót session.

Certificate theo đúng schema: operation/context/case+post-issue case.version, swap+current swap.version, payment/station/device/current boot/new serial, exact Simulator receipt và hai human attestation IDs, ledger_id/fence_generation/command+service digests, validated_at/valid_until, new_pin_delivered=NO và effect_count_delta=0. payload_hash dùng canonical body bất biến. References/actor sessions truy ra từ attestations/context; không caller-supplied credential.

`valid_until = min(operation.expires_at, observed_at+15s và received_at+15s của mọi current proof/snapshot được dùng)`. Nếu không còn khoảng hợp lệ dương thì từ chối, không kéo dài. At issuance/redemption phải `decision_now < valid_until`; op/session expiry cũng strict. Freshness equality không được tạo certificate có valid_until==validated_at.

Issuance atomic: append certificate + case state EVIDENCE_RECORDED / new_pin_delivered=NO / version+1 + truthful audit + idempotency response. **old_pin_settled giữ nguyên giá trị trước**, không thay Swap/Payment/custody/holds/commands/effects. Mỗi operation chỉ một immutable certificate (UNIQUE đã có).

Không cần tự đổi consumed_at/cancelled_at để issue hoặc redeem: certificate redemption là nguồn chống tái dùng; operation không được dùng cho physical authorization vốn bị cấm theo purpose. Nếu implementation muốn thêm operation-consumption transition ngoài những gì frozen yêu cầu, phải review riêng thay vì ngầm thêm.

Admin request chọn certificate của đúng current case/operation/payment/version; kiểm source/session/authority/boot/history/fence hiện tại, không chỉ row có NO. Fresh valid certificate không phải bearer capability. Row revoked/expired/superseded hoặc binding khác: từ chối. Certificate một lần; composite FK bảo vệ Payment/Refund binding; không redeem sang intent khác.

Accepted contradictory current projection phải append certificate revocation (unique certificate), audit thật, case UNKNOWN/version khi phù hợp; giữ receipt/certificate cũ bất biến. Input bị từ chối không được dùng để “revoke” facts hợp lệ của người khác. Refund đã REQUESTED vẫn là durable Admin decision: không xóa/đổi tiền/giả FAILED; future dispatch B3 phải revalidate và dừng khi eligibility không còn.

Existing Refund không tạo intent thứ hai. Certificate mới chỉ có thể refresh cùng intent qua **explicit Admin reconcile** ở increment được giao sau; B1b không implement positive reconcile hoặc provider retry.

## 8. State / lock / transaction design

### 8.1. State changes được phép

| Bước | Database transition | Facts giữ nguyên |
|---|---|---|
| Begin / successor | Immutable operation/context/current case ref/version; case UNKNOWN; append audit/idem | old obligation, Payment, custody/holds/effects |
| Accept inspection / human CONFIRM hoặc REJECT | Append receipt/attestation; case.version tăng cho accepted mutation; không đặt NO | Payment/Swap/custody/holds; invalid input không accepted proof/version/success audit |
| DECIDE eligible | Certificate append; case EVIDENCE_RECORDED + NO + version+1 | old_pin_settled như trước, tất cả protected asset/finance facts |
| Contradiction accepted | Append revocation; case UNKNOWN/version appropriate; fence giữ | Không financial rollback/custody/hold release |
| Admin request đầu | Refund REQUESTED/v1 + generation0 identity + certificate redemption + Swap COMPENSATING/version+1 + outbox + audits + idem | Payment SUCCEEDED/version/money, old_pin_settled/custody/ownership/holds, physical count |
| No evidence / authority lost / audit exception | Full transaction refusal/rollback | Không partial accepted state, success audit, redemption, job hoặc receipt |

NO chứng minh chưa giao pin mới, **không giải quyết pin cũ**. Không đòi old_pin_settled=true để cấp certificate/refund. Không đánh RESOLVED/CLOSED_COMPENSATED, không release ba holds dù case có NO.

### 8.2. Lock graph và final decision

User mutation:

`idempotency advisory → station advisory + station FOR NO KEY UPDATE → sorted participant users → sorted swap/compartments/batteries → Payment → Refund (nếu có) → operation/certificate/revocation/redemption/attempt/outbox rows theo thứ tự cố định → exact auth_sessions sorted UUID`.

- Dùng station_locks hiện có, không đảo resource→user. Collect caller + Customer + mọi Technician witness/creator và exact session IDs từ immutable proofs **trước** khóa session; gather lại dưới station mutex. Không discover thêm user sau session lock.
- Case/evidence/operation writers cùng station mutex; nếu thêm explicit row lock thì lấy trước exact sessions, không lazy FOR UPDATE sau final clock. Foreign-key implicit locks được đưa vào lock review/migration probes.
- Giữ NO KEY UPDATE của B1a. AssignStations giữ target user rồi FK station KEY SHARE; FK reference read tương thích với station writer mode này. User ownership serialize role/state/assignment; Logout dùng exact session row. UpdateUser user→sessions không phải station writer.
- Device ingress giữ existing station→device/source ingress order; sau đó users/resources cần thiết. Không đưa Admin network wait hoặc SQLite write vào bên trong PG locks.
- Re-read current caller user/session (principal binding, ACTIVE/role/expiry/revoked), witness roles/assignment/exact sessions, case/Payment/Swap versions, current operation, receipt hashes, boot/source projection, full ledger/history/fence sau mọi wait.
- Lấy final wall-clock sau blocking DB reads và capture audit-before; kiểm freshness/expiry ngay trước business writes. Giữ authority locks đến commit; last authority/time validation trước success receipt hoàn tất. Nếu cuối transaction không còn hiệu lực theo guard thì rollback cả write/audit/idem.
- Linearization cho competing mutations = transaction commit dưới shared locks; deadline được kiểm tại decision, **không đổi thành policy “WAL commit phải trước15s”**. Không reset P7 deadline hoặc giả precision vượt runtime.

Revoke-first commit được quan sát và từ chối; authority-first giữ locks khiến revocation đợi rồi commit sau. Hai thứ tự phải được test bằng barriers/PIDs, không chỉ một sequential negative.

### 8.3. Atomic Admin first intent

Trong cùng transaction, sau guards:

1. Snapshot BEFORE thật (Refund chưa tồn tại; Swap/case/protected facts có thật).
2. INSERT one Refund bound verified full Payment SUCCEEDED/VND; id/provider_key server-generated UUID ổn định, requested_by=Admin principal, reason theo contract.
3. INSERT immutable generation0 attempt identity, permit_id=NULL; đây là registry, **không dispatch claim/PENDING**.
4. INSERT certificate redemption unique certificate và exact payment/refund FK; giữ fence binding qua immutable certificate chain.
5. UPDATE Swap REVIEW_REQUIRED→COMPENSATING/version+1 (hoặc versioned approved current COMPENSATING context), không đổi Payment hoặc old obligation. Không fake case resolve/old settlement; child-only redemption không bắt buộc bịa case version change.
6. INSERT outbox kind REFUND / aggregate refund / unique dedup identity generation0. Payload nội bộ có exact frozen AttemptInitial command và riêng eligibility refs; không gắn secrets hoặc thêm extra fields vào provider command body.
7. Audit REFUND_REQUEST_CREATED và ND_CERTIFICATE_REDEEMED với actual before/after; INSERT successful idempotency response202. Commit cùng nhau. Audit/constraint/inbox/idem lỗi rollback toàn bộ.

Job còn attempts0/delivered_atNULL. Payment worker CHARGE-only phải bỏ qua; không chạy Refund worker tạm hoặc sửa scheduler để demo effect.

### 8.4. Replay và lost response

Same principal/route/key/body: sau protected **caller authority** recheck, trả stored response; không new certificate/intent/attempt/redemption/audit/job. Key khác cùng Payment:409. Cùng key body khác:409; dùng cached error không được thành accepted receipt.

Receipt đã accepted giữ nguyên thời gian/hash trên exact replay. Certificate expiry/witness logout sau một Admin intent đã commit không hủy authorization lịch sử; replay không được recertify/renew hay tạo quyền dispatch mới. Caller Admin hiện tại vẫn phải có quyền đọc replay; caller revoked trong idem wait không được trả cached success. New first decision/reconcile mới phải kiểm mọi witness/freshness hiện hành.

Crash trước commit: zero committed partials. Crash sau commit trước HTTP: cùng key tìm đúng stored response; một intent/attempt/job/redemption và đúng audit action counts. Hooks fault injection chỉ nằm trong runner test, không import/enable ở production.

## 9. Database / grants proposal — chưa tạo migration

Đề xuất **một forward migration `0010_no_delivery_eligibility` sau0009**, kiểm lại actual source head trước khi viết. Không sửa0001/0003/0004/0008/0009, không migration/backfill demo.

| Phần | Delta cần review/kiểm |
|---|---|
| Operation constraints |0.3 chỉ VERIFY_NO_DELIVERY, pin_id=new battery đúng context; legacy NULL purposes và0.2 foreign-only vẫn giữ. Không đưa0.3 vào reconciliation_only/permit/action mappings0.2 |
| Attestation constraints/trigger | Thêm stage NO_DELIVERY_INSPECTION chỉ operation0.3; same operation/stage SIMULATOR receipt reference, source/actor/chronology/append-only/unique giữ nguyên |
| Certificate table0009 | Reuse, không bảng certificate thứ hai. Thêm private issued_by/issuer_session_id refs cho quyết định issue; không bịa/backfill caller cho historical row, row thiếu trusted issuer không eligible. Strengthen insert validation: source roles/stage/reference/context/version/payment/boot bindings và positive validity interval; service vẫn chịu trách nhiệm auth/current-time/full history |
| Certificate redemptions0009 | Reuse unique/composite FKs; trigger kiểm valid/revoked/binding, timestamps và immutable owner. Không reuse permit redemption làm certificate redemption |
| Revocation | Thêm append-only refund_certificate_revocations (unique certificate, server decision time, allowlisted reason/context/source ref và issuer audit link nếu cần); không UPDATE payload hay backfill revocation giả |
| Fence storage | Reuse PG operation/proof/certificate/redemption refs; local SQLite forward metadata cho stable journal/fetch/deny/history và immutable0.3 receipt outbox. Không xóa/rename ledger cũ hoặc bịa coverage |
| Runtime grants | Chỉ SELECT/INSERT issuer/redemption/revocation và field-limited mutations đã duyệt; không UPDATE/DELETE evidence/certs/revocations. Không broad GRANT ALL, không quyền UPDATE custody để dựng workflow |

Binding/quiescence có thể kiểm thêm bằng trigger nhưng không nhầm DB owner SQL với authenticated issuer. Runtime là service account, không cấp cho HTTP caller SQL hay signing key mới. Public certificate không thêm trường ngoài frozen schema.

## 10. Audit matrix B1b

| Frozen action | BEFORE → AFTER bắt buộc |
|---|---|
| ND_OPERATION_CREATED | operation absent→immutable context; case current ref/version thực; no protected change |
| ND_SUCCESSOR_LINKED | predecessor/current refs và fence-handover bindings; new operation, union-denial lineage; không chứng nhận lại old proof |
| ND_INSPECTION_ACCEPTED | Simulator child absent→receipt/provenance/hash; actual case version; effect delta0 |
| ND_HUMAN_ATTESTED | source/stage child absent→CONFIRM/REJECT + receipt/session refs; actual version |
| ND_CERTIFICATE_ISSUED | certificate absent→exact binding/validity; case UNKNOWN→NO/version+1; old boolean unchanged |
| ND_CERTIFICATE_REVOKED | revocation absent→immutable fact; actual case NO→UNKNOWN/version nếu transition xảy ra; original certificate giữ |
| ND_CERTIFICATE_REDEEMED | redemption absent→intent/cert/fence refs; no money/custody effect |
| REFUND_REQUEST_CREATED | Refund before=null→REQUESTED; Swap before/after COMPENSATING/version, attempt/job refs; protected Payment/holds/custody facts |

Không dùng RECOVERY_HANDOVER/COMPLETED audit cho inspection. Không raw notes/reason/headers/keys/password/token/QR/payload; allowlist source IDs/hash/versions/boolean và actor/device/time/correlation/swap/payment/refund/op/command refs. Không sửa21 audit actions8A hoặc backfill audit lịch sử.

## 11. Implementation sequence và file proposal

Thứ tự sau khi người dùng phê duyệt:

1. Storage/DTO/composition + migration clean/upgrade/grants.
2. SQLite journal/fetch-denial/fence và0.3 readonly transport; legacy effect regression trước khi nối issuer.
3. Human statements, current projection, full validation, certificate/revocation và audit.
4. Protected Admin first-request/redemption/attempt0/outbox; reconcile/provider vẫn off.
5. Deterministic PG races → two-OS-process E2E → affected regression/contracts và handoff. Không tự chuyển B2.

**Danh sách explicit proposal, không phải staging allowlist và chưa có permission edit:**

| Action | Paths dự kiến |
|---|---|
| NEW production | `services/backend/app/api/no_delivery_schemas.py`; `services/backend/app/application/no_delivery.py`; `services/backend/app/domain/no_delivery.py`; `simulators/device/no_delivery.py`; `services/backend/alembic/versions/0010_no_delivery_eligibility.py` |
| MODIFY routing/schema composition | `services/backend/app/api/recovery.py`; `services/backend/app/api/recovery_contract.py`; `services/backend/app/api/refunds.py` |
| MODIFY narrow dispatch/projection/audit | `services/backend/app/application/recovery.py`; `recovery_projection.py`; `recovery_audit.py`; `refunds.py`; `refund_audit.py` (cùng application directory) |
| MODIFY station interlock/invalidation | `services/backend/app/application/device.py`; `services/backend/app/workers/device.py` |
| MODIFY simulator integration | `simulators/device/main.py`; `service.py`; `recovery_fence.py`; `recovery_handover.py`; `recovery_reconciliation.py` (cùng simulators/device) — chỉ metadata/final deny guards; physical action semantics cũ giữ |
| MODIFY runtime provisioning | `tools/provision_database.py` |
| NEW tests | `tests/test_phase8b_b1b_contract.py`; `test_phase8b_b1b_migration.py`; `test_phase8b_b1b_no_delivery.py`; `test_phase8b_b1b_certificate.py`; `test_phase8b_b1b_refund.py`; `test_phase8b_b1b_races.py`; `test_phase8b_b1b_ledger.py` (cùng tests) |
| MODIFY version-specific test/tooling | `tests/test_phase8b_b1a.py` (migration-related assertions only); `tests/test_phase8b_b1a_transactions.py` (0009 versus new-head contract split); `tools/run_phase8b.py`; `tools/summarize_phase8b.py` |
| NEW reproducer/static checker | `tools/smoke_phase8b_b1b.py`; `tools/validate_phase8b_b1b.py` |
| Docs after implementation | `docs/PHASE8B_B1B_IMPLEMENTATION.md` mới, `docs/IMPLEMENTATION_STATUS.md` checkpoint mới; report/tests mới, không ghi đè evidence |

`main.py`/`identity.py`/`assets.py`/Payment worker/Swaps custody engine không cần sửa theo design này: dùng existing idempotent callback và station_locks. Nếu lúc implementation cần đổi shared lock primitives/custody/financial transitions thì dừng review dependency, không tự mở scope. Tests migration hiện hardcode0009/SELECT-only certificate phải tách rõ “frozen0009 behavior” và “new head issuer grants”; giữ lịch sử/assertions0009, bổ sung expectation versioned cho0010, không lược constraints hoặc đổi negative để ép pass.

Không sửa `docs/implementation-contracts/P8-REF-0.1/*`, `P8-REC-0.3/*`, prior overlays0.1/0.2, GD1/GD2, approved decisions/config, frozen manifests hoặc EOL policy. Validator B1b mới phải giữ frozen shape/security/hash checks và báo rõ allowlisted source deltas sau implementation; không sửa B0 validator để phủ nhận source freeze lịch sử.

## 12. Decisions, risks và approval boundary

| Mục | Trạng thái / cách xử lý |
|---|---|
| D01 provider-authorized FAILED retry | APPROVED BY USER; để B2/B3, không implement/claim ở B1b |
| D02 readonly VERIFY_NO_DELIVERY độc lập old obligation | APPROVED BY USER; áp dụng nguyên vẹn |
| Full amount/original Payment/VND, one intent, Admin authority | Frozen; không quyết định phí/refund policy mới |
| Current3proof/freshness15/TTL120/boot/complete history/fence | Frozen; thiếu proof thì UNKNOWN; không cần approval mới để giữ fail-closed |
| Proposed adapters/migration0010/journal encoding/protected replay/tests | **PENDING USER IMPLEMENTATION APPROVAL** cho increment này; lựa chọn kỹ thuật dưới frozen semantics, không đánh dấu đã approved |
| Known missing-history legacy ledger | Thiếu điều kiện chạy nhánh dương, không waive. Chứng minh bằng negative tests; fixture mới tạo history trước effects |
| Không biểu diễn được bắt buộc provenance/coverage bằng frozen contract | Stop affected branch + exact gap/decision request; không tự thêm API/enum/financial/physical policy |
| Early successor trước frozen expiry/rejection, additional operation consume/close, fence release/old compensation | Không tự thêm; nếu cần thì review riêng; không phải dependency để happy path B1b chuẩn hoạt động |

Rủi ro chính: missing historical coverage; issuer/effect path ngoài shared mutex; legacy formatter mismatch; final freshness hết trong lock wait; session/assignment authority stale; operation/schema collision; immutable chain bị thiếu khi crash; callbacks/provider vô tình enable quá sớm; invalidation race với Admin redemption; source EOL thay vì logic bị normalize. Mỗi rủi ro có mandatory gate trong test plan.

Không có quyết định **nghiệp vụ tài chính hoặc custody proof mới bắt buộc chưa được phê duyệt** được phát hiện trong đường B1b frozen đã giới hạn trên. Runtime feasibility vẫn phải chứng minh; review pass không là bằng chứng journal/fence/certificate đã chạy.

## 13. Requirement → source → test → gate

Các source proposed chưa tồn tại/chưa thay đổi; tests dưới đây trỏ tới matrix đi kèm, không là evidence Passed.

| Requirement / scope | Source hiện có → proposal | Tests / bằng chứng phải có | Gate |
|---|---|---|---|
| FR12/UC10/TC12; D02/P8-REC-0.3 | recovery routes/inspection/projection → no_delivery application/domain/DTO + simulator adapter | C01–04,P01–12,H01–05,E01–07; current3proof, exact schema/DB refs | G2/G3 |
| FR16/UC14/TC16,BR08 | refunds.request fail-closed/0009 → protected positive first intent + certificate redemption | R01–08,T01–04;202/PG one full intent, no provider effect | G4 |
| BR05,QD02/QD04 | preserved old-pin custody/service guards → independent NO-new-pin validator | P05/P12,F07,E01; foreign/old object không trở thành network new pin hoặc old-settled proof | G2/G3 |
| BR09,CT08,Invariant6 | quiet/current snapshot/command ledger → strict0.3 history + quiescence | P02–09,F01–07; UNKNOWN/PREPARED/missing history/stale stay review/fenced | G2/G5 |
| BR08,CT07,Invariants7–8 | recovery case/Payment/holds/refunds → certificate + atomic redemption | E01,R01,R03,T02; oldfalse hợp lệ, unchanged custody/Payment/three holds, no CLOSED_COMPENSATED | G3/G4 |
| QD06,CT10; B1a IA01 | identity.idempotent authorize callback/assets locks → protected0.3 and Admin request adapters | C03,H02/H05,R05,X01/X02; ownership/current authority/exact sessions/both orders | G5 |
| CT11,one Refund/payment | UNIQUE/idempotency/inbox → certificate/redemption/attempt0/job dedup | H04,E06/E07,R04–06,X07; one append-only outcome, exact lost-response replay | G4/G5 |
| BR11,P7-A01,8A IA01 | unchanged automatic custody/shared current proof → purpose-specific0.3 final-time validator | P02/P11,E03,X03/X06 + original guards; no ACK15/physical60/freshness15 reset or historical POST reinterpretation | G3/G8 |
| BR12/NFR06 | refund_audit/recovery_audit/append-only storage →8 frozen B1b action snapshots | A01/A02,T01–04; exact before/after, true creation absence, no secret/ghost audit | G6 |
| ER01/ER02/P8-REC-0.1/0.2 | unchanged closure/successor/physical functions →0.3-only readonly successor + no-permit isolation | F05–07,X05/X06 +8A legacy suites; never close0.3 via0.2 receipt | G5/G8 |
| CT13/SM-04 (partial) | refund domain/CHARGE-only worker → stable initial registry and inert REFUND outbox | R05/R07/R08,T04; **không** cover provider timeout/permit/retry/refund financial success còn B2/B3/B5 | G4/G7 |
| Runtime/DB append-only invariants |0009/provisioning →0010 narrow constraints/grants/revocation | M01–04; clean+upgrade+runtime+owner FK/trigger/mutation denial | G1 |

Raw source hashes trong source_checkpoint.json cho phép reviewer đối chiếu các source hiện có; source proposal mở rộng path đầy đủ trong FILE_CHANGE_PROPOSAL.json. Không sửa traceability baseline để gán TC16/CT13 “hoàn thành” chỉ vì B1b đầu vào đã có.

## 14. Acceptance gates / bàn giao

[B1b test matrix, ordering probes, runner/evidence plan](PHASE8B_B1B_TEST_PLAN.md) là phần đi kèm của design này. Mỗi gate runtime hiện NOT RUN. Chỉ đề xuất nghiệm thu B1b sau positive real-proof path, no-delivery/old-obligation separation, durable redemption, same-key lost response, both-ordering revoke/race/rollback và legacy regressions có XML/log/exit/source hashes hợp lệ; zero Major/Blocker. Không cộng E2E checks vào pytest, không dùng historical543 như suite B1b.

Lượt review này chỉ thêm hai tài liệu và local static checkpoint/validation. Không chạy test, migration, Docker/provider effects, UI/Browser hoặc network; không stage/commit/push, không bắt đầu B1b implementation. NFR04/NFR07/CT14/NFR08 vẫn OPEN cho final MVP release.

**Kết luận thiết kế: B1b PRE-IMPLEMENTATION REVIEW PASSED — READY FOR USER IMPLEMENTATION APPROVAL. Dừng chờ phê duyệt implementation scope; chưa lập trình.**
