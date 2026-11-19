# Phase 8B — B1b test matrix and acceptance gates

18/11/2026 (+07). Đi kèm [pre-implementation review](PHASE8B_B1B_PREIMPLEMENTATION_REVIEW.md). **Tất cả cases B1b: PLANNED / NOT RUN.** Review này không chạy pytest/collection, PostgreSQL, simulator, Browser hay provider.

Các ID B1b-* dưới đây là nhãn matrix nội bộ, không thay TC01–TC19/CT/FR/UC/BR. Số dòng matrix không phải số pytest tests hoặc E2E checks.

## 1. Oracle chung và dữ liệu cần quan sát

Baseline: main `0024c5f2ddac4c1652e77dcff2acf48fd791b8e0`; B0 frozen; B1a accepted. Existing evidence543 affected / reviewer16 / static77 là lịch sử, không được dùng làm Passed trên source B1b.

Mỗi probe ghi pre/post:

- Recovery case.id/state/operation_id/version/new_pin_delivered/old_pin_settled; immutable operation/context/protocol/stage; accepted/rejected inbox disposition.
- Certificate IDs/hash/source refs/validated_at/valid_until, append-only revocations, redemption/payment/refund binding.
- Swap state/version/return/pickup/closed timestamps; Payment full identity/state/version/amount/currency/verified charge reference.
- Old/new battery location_kind/holder_user_id/compartment_id/version; ba active hold identities và released_at.
- Device current boot, accepted+processed source event/snapshot IDs/hash/seq/time; command/service full ledger identities/status/effects.
- SQLite ledger_id/fence generation/state/deny sets/journal and effect count; không đọc một scalar effects0 làm positive no-effect oracle.
- Refund/attempt/outbox rows, action-specific audit count và **giá trị before/after thật**, idempotency key/hash/result count.
- Native PostgreSQL backend PIDs, Backend OS PIDs, pg_blocking_pids/lock wait/commit order cho concurrency. Không chứa bearer/password/Device-Key/connection URL.

**VERIFY-only positive:** new_pin_delivered=NO; old_pin_settled giữ giá trị gốc (cảfalse/true); Payment/custody/holds/Swap/effects không đổi. **Admin-request positive:** đúng1 REQUESTED Refund/v1,1 generation0 registry,1 redemption,1 REFUND outbox, Swap COMPENSATING/version+1; không dispatch, Payment/custody/old obligation/holds/effects không đổi. Audit có các action khác nhau cần thiết, không “một tổng audit” mơ hồ.

**Refusal:** không new accepted proof/certificate/redemption/Refund/attempt/job/idem success/version/success audit. Ngoại lệ được phân biệt: authenticated structurally-valid SIMULATOR receipt bị semantic rejection có thể ghi **rejected inbox disposition** trong transaction riêng savepoint; accepted human REJECT là một lời chứng hợp lệ confirmed=false, có append/audit/version, nhưng không certificate/NO.

## 2. Contract, storage và provenance

| ID | Scenario | Expected / evidence | Layer |
|---|---|---|---|
| B1b-C01 | Frozen17 definitions0.3 và ReasonAction/Refund old schemas | Shape/strict extras/format union đúng; no new path/opID/security; old0.1/0.2/Charge unchanged | Static + actual OpenAPI/schema |
| B1b-C02 | Legacy/0.2,0.3 request/task/response và Customer projection unions |0.3 không parse thành legacy; task items mixed hợp lệ; Customer không raw ledger/session/Technician proof | API contract |
| B1b-C03 | Admin/Tech/Customer/Device roles + cross-customer/station/device key | Existing401/403/404 convention; Admin không ký hai nguồn, Tech không Refund; wrong Device-Key không poison inbox | API + PG |
| B1b-C04 | Missing/extra stage/protocol/receipt/actor/NO/custody/amount fields | Closed schema rejects; không extra field để giả stage/financial state; public Refund unchanged | Schema + API |
| B1b-M01 | New test schema clean install0010 và0009→0010 upgrade | Actual single head/FK/checks/trigger/index/grants; historical rows/0009 constraints semantics nguyên vẹn; không backfill cert/NO | Native PG migration |
| B1b-M02 | Stage/protocol/purpose/reference constraints |0.3 chỉ purpose/stage đúng, pin=new;0.2 foreign-only và legacy mappings vẫn enforced; cross-stage human receipt INSERT bị chặn | PG owner+runtime |
| B1b-M03 | Issuer/redemption/revocation FK/unique/immutable/grants | Runtime INSERT đúng quyền mới; UPDATE/DELETE forbidden; cross Payment/Refund/stage/source và expired redemption denied; owner trigger cũng bảo vệ identity | PG |
| B1b-M04 | Historical migration test compatibility | Giữ riêng0009 SELECT-only/no issuer assertions và new-head issuer assertions; không drop historical checks/test coverage vì head đổi | PG + collection diff |
| B1b-P01 | Trusted model supply actual serial/door/presence | Read actual model; mismatch không echo expected_serial; read-only delta0; không forge sensor event | Simulator + API |
| B1b-P02 | Same-boot/source/context positive; old boot, future/high seq hoặc hash mismatch | Chỉ current accepted+processed snapshot/projection; old/future/reordered/stale không làm mới facts | PG + real process |
| B1b-P03 | Snapshot mới chỉ inbox QUEUED / rejected / chưa worker processed | Không dùng làm accepted current proof; sau worker accepted mới xét; refused event không displace current projection | Worker + PG |
| B1b-P04 | DeliveryHistory complete/hash/count tự khai nhưng thiếu IDs/boot/journal/known issuer | Backend independent reconstruction fail-closed; current slot present không che past delivery | Pure negative + PG |
| B1b-P05 | Đã giao pin trong lịch sử rồi model lại present | Không certificateNO; history0 không tin từ client; Setup physical history qua simulator, không SQL custody | Simulator + real process negative |
| B1b-P06 | Complete retained history across boots và terminal OPEN_RETURN | Positive chỉ nếu current boot proof, lịch sử đầy đủ và delivery_count tự tính0; không quy OPEN_RETURN thành giao pin | Ledger + PG |
| B1b-P07 | Backend UNKNOWN + raw ledger EXECUTED hoặc NOT_EXECUTED | Không certificateNO, không rewrite command state/deadline; purpose-specific8A reconciliation phải giải quyết trước nếu có cơ sở | PG + legacy regression |
| B1b-P08 | Service PREPARED/UNKNOWN; missing receipt/issuer/witness | effects0/expiry/revocation không suy NEVER_PREPARED; giữ review/fence | SQLite restart + PG |
| B1b-P09 | Legacy ledger thiếu new coverage metadata | Không tự tạo complete genesis/no-effect;0.3 fail-closed,0.1/0.2 behavior vẫn đúng | Local ledger + API |
| B1b-P10 | Legacy command hash vs Recovery canonical hash | Golden vectors bảo toàn formatter/event body hiện có; command body tamper/hash scope mismatch bị chặn | Pure tests |
| B1b-P11 | Receipt/device event/ACK/closure seq interleaving, boot-before-task và restart | Stable high-watermark và immutable event IDs; không reuse seq/old boot, không nhầm service-count là current ordering | Ledger + PG + real process |
| B1b-P12 | Pin cũ chưa rõ custody/wrong serial nhưng mọi effect đã quiescent, new-pin proof đầy đủ | Không tự đặt old settled, không impose điều kiện cấp pin/BMS như Refund policy; contradiction hoặc unresolved effect riêng vẫn chặn | PG + actual-model fixture |

## 3. Fence, statements và certificate

| ID | Scenario | Expected / evidence | Layer |
|---|---|---|---|
| B1b-F01 | Command đã fetched/cached trước fence nhưng chưa effect | Exact receive/fetch register + durable deny; final effect-point guard từ chối; no new effect, không ACK thành proof | Two simulator processes/shared SQLite |
| B1b-F02 | Command UNKNOWN đã commit trước effect, inspection cạnh tranh | Không đổi UNKNOWN thành no-effect; không certificate; fence giữ và effect không tự retry | SQLite deterministic barrier/restart |
| B1b-F03 | Old service activation/task cached; new task thuộc swap khác cùng station | Station fence chặn cả old/future issuer; cross-swap station scope được kiểm; không chỉ polling filter | PG + SQLite + real process |
| B1b-F04 | Mỗi direct effect entry point và bypass dispatcher | Same SQLite writer/fence/deny guard được thực thi; không generic unlock; thiếu issuer coverage block | Call-graph tests + ledger |
| B1b-F05 | Fence install commit, HTTP receipt mất; simulator restart/reboot/TTL | Durable fence/deny/outbox giữ; replay immutable boot/time/hash; không effect mới hoặc auto close | Real process crash/restart |
| B1b-F06 | Successor readonly0.3 sau real expiry hoặc genuine REJECT | New IDs/context/current3proof; union-denial handover atomic/no gap; không old proof copy hoặc new action | PG + SQLite + real process |
| B1b-F07 |0.2 closure/activation/handover cố áp dụng vào op0.3 | Denied; no fence release/permit/effect; old foreign-only triggers không nới | API + PG + SQLite |
| B1b-H01 | Simulator + Tech creator + Customer owner CONFIRM độc lập | Same receipt/context/stage/new serial; server human timestamps sau receipt; no impersonation | PG/API |
| B1b-H02 | Tech wrong serial/creator/station; Customer khác chủ; session principal mismatch | Refusal không accepted child/version/audit; không tin actor ID từ payload | API + PG |
| B1b-H03 | Confirmation trước receipt, PRE/POST0.2 reference reuse hoặc wrong stage/hash | Refusal; current GET projection không cấp quyền vượt mutation guards | API + PG |
| B1b-H04 | CONFIRM/REJECT cùng nguồn; duplicate/replay/conflicting key/body | One append-only statement; same key/body historical replay, conflict409; REJECT không bị majority vote/overwrite | PG + race |
| B1b-H05 | Role/assignment/session revoked; exact khác session cùng user | Kiểm sau wait; đúng witness session, không revoke nhầm session khác; no stale cache success cho caller mất quyền | PG + two OS |
| B1b-E01 | DECIDE current3proof, old_pin_settled=false và true | One correct immutable certificate; case NO/EVIDENCE_RECORDED/version+1; old boolean/protected facts nguyên vẹn | PG + real process |
| B1b-E02 | Certificate wrong operation/case/swap/Payment/serial/boot/digest/fence/versions | Bound mismatch409/422; không NO chỉ do row/caller flag | PG |
| B1b-E03 | Proof freshness15/op TTL120/session expiry tại decision và lock wait | Dùng real clock; expired sau wait refuse. Equality tại valid_until không cấp certificate zero-life | PG deterministic |
| B1b-E04 | Accepted contradictory current observation sau issue | Append revocation + actual case UNKNOWN/version khi phù hợp; original cert/proof giữ; không financial rollback/hold release | Worker + PG |
| B1b-E05 | Rejected wrong-context/old-boot observation sau issue | Rejected disposition không trở thành accepted evidence hoặc revoke nhầm current valid context | PG/inbox |
| B1b-E06 | Two DECIDE requests cùng/khác key/version | Một certificate/issue action/version change; other cached response/conflict; UNIQUE là lớp cuối | PG + two OS |
| B1b-E07 | Certificate expire/supersede/revoke, replay issue request | Không renew timestamp/validity; exact replay không tạo cert/audit mới; next Admin decision vẫn reject stale | PG |

## 4. Admin request, rollback, replay và races

| ID | Scenario | Expected / evidence | Layer |
|---|---|---|---|
| B1b-R01 | Fresh valid certificate + Admin first request |202 REQUESTED/v1, full original amount/VND,1 redemption/attempt0/outbox, Swap COMPENSATING/version+1; old obligation cònfalse hợp lệ | PG + two OS E2E |
| B1b-R02 | Payment chưa verified/PENDING/UNKNOWN/FAILED, wrong Payment.version, missing certificate hoặc NO flag đơn lẻ | Giữ foundation refusal; zero partial writes | PG/API |
| B1b-R03 | Certificate stale/revoked/old boot/changed case/swap version hoặc contradictory source | First request từ chối sau final revalidation; không consume certificate/force failure | PG + two OS |
| B1b-R04 | Reuse certificate sai Payment/Refund, second intent/key khác |409/422; unique/payment/FKs bảo vệ; no second intent/attempt/job | PG |
| B1b-R05 | Same principal/key/body sau response loss; different body; caller revoked trong idem wait | Durable replay cùng result/IDs, no duplicate; conflicting body409; stale authority401/403 trước cached success | PG + actual backend kill |
| B1b-R06 | Đã REQUESTED, witness logout/cert expiry sau commit | Intent vẫn durable; replay của Admin hiện còn quyền không recertify/renew; không dispatch bằng quyền cũ | PG |
| B1b-R07 | Generation0/outbox tồn tại trong lúc Payment worker chạy | kind REFUND giữ attempts0/delivered_atNULL, no provider refund call; không UNKNOWN→FAILED/PENDING tự động | Worker transport spy + OS smoke |
| B1b-R08 | Existing Refund + new cert hoặc reconcile UNKNOWN/FAILED | Không second intent hoặc new generation/permit/query job trong B1b; reconcile vẫn fail-closed; FAILED retry reserved B2/B3 | API/PG |
| B1b-T01 | Fault sau certificate INSERT / case UPDATE / audit INSERT / success idem INSERT | Toàn txn rollback: no positive child/version/audit/idem; existing fence/proof giữ | PG fault runner |
| B1b-T02 | Fault sau Refund INSERT / attempt / redemption / Swap / outbox / từng audit | Refund/child/Swap/audit/idem cùng rollback; certificate chưa redeemed; no custody/Payment/hold write | PG fault runner |
| B1b-T03 | Real kill trước PG commit | Connection rollback; retry Backend khác an toàn, một committed result; fence không bị tháo | Two OS APIs + PG |
| B1b-T04 | Real kill sau PG commit trước HTTP response | Response mất thực; same key retry đúng stored202/cert result; one intent/attempt/redemption/job, action-specific audits không tăng | Two OS APIs + PG |
| B1b-X01 | AssignStations/UpdateUser/logout thắng trước decision, hoặc B1b authority giữ khóa trước | Cả hai ordering; revoke-first refuse, authority-first commit rồi revoke; native FK KEY SHARE compatible NO KEY UPDATE, no40P01 | PG barriers + two OS APIs |
| B1b-X02 | Caller Admin khác issuer/witness; issuer và witness cùng principal nhiều session; role/state đổi | Exact issuer/caller/witness IDs gathered trước khóa session; current permissions re-read; không một session hợp lệ “thay” session đã revoke; issuer storage-only thiếu provenance không eligible | PG + two OS APIs |
| B1b-X03 | Accepted contradictory observation/boot snapshot thắng trước Admin redemption và thứ tự ngược | Projection-first refuse; intent-first giữ historical intent nhưng invalidates future eligibility, không money/custody rollback | Worker + two OS APIs |
| B1b-X04 | Customer REJECT vs CONFIRM vs DECIDE/Admin request | Append-only source winner; REJECT thắng thì no certificate; CONFIRM+valid proof thắng chỉ one cert/intent. Late conflicting source không overwrite | PG + two OS APIs |
| B1b-X05 | Successor vs DECIDE/redemption/closure cả hai ordering | Current operation/version/fence lineage serialize; không consume stale context, renew authority hoặc release denies | PG + SQLite + two OS APIs |
| B1b-X06 | Recovery0.1/0.2 settlement/resume/authorization vs Admin request | Delivery YES/COMPLETED thắng → Refund refused; Refund thắng → existing refund-present/new station guards chặn cấp pin/resume; không reset P7 deadline | PG + real process |
| B1b-X07 | Hai Admin same key/body, same key/different body, different keys/sessions | One unique intent/payment và one physical delta0; cached202 hoặc409 đúng; exact action counts | Two OS APIs + native PG |
| B1b-A01 | Từng8 frozen B1b audit actions trong coverage matrix | Giá trị before/after/version/child refs đúng, creation before=null; Payment/old obligation/custody/holds facts unchanged | PG read-only SQL |
| B1b-A02 | Audit secret redaction, append-only, replay/concurrency và grant denial | Không raw reason/note/password/token/QR/headers; audit rollback atomic; no duplicate success hoặc backfill | PG + unit |

## 5. Deterministic concurrency method

Không gọi hai ASGI clients là hai Backend OS process. Native PG tests dùng ít nhất hai connections/backend PIDs riêng; matrix ghi loại bằng chứng. Critical positive redemption/revocation/idempotency/crash phải có **hai API OS processes** trên cùng fixture schema và cùng device ledger.

Barrier chỉ ở test runner, không import vào production. Trước khi nhả barrier ghi pg_blocking_pids, target lock, backend PID/OS PID và state transaction. Ghi rõ transaction nào commit trước; không dùng HTTP latency hoặc một lần không tái hiện làm proof.

Giữ isolation/lock_timeout/55P03 policy hiện có. Để freshness15s hết khi chờ khóa mà không cần lock lâu hơn lock_timeout5s: chờ proof thật gần deadline **ngoài DB locks**, bắt request lúc vẫn fresh, quan sát native wait ngắn qua deadline rồi release. Không sửa timestamps hoặc tăng lock_timeout để né lỗi. Expiry120 dùng đồng hồ thật và fresh receipt gần expiry; positive control commit trước deadline.

Session expiry PG fixture có thể reuse **new short-lived auth record** pattern đã được B1a test, không UPDATE timestamp lịch sử/physical proof hoặc đổi web TTL production. Phân biệt fixture này với login3600s real-process case; real-process logout/role/assignment phải dùng API thật và observed ordering.

Không giữ PG transaction trong lúc HTTP/operator/human chờ. SQLite race dùng cùng writer DB, request thứ hai thực sự chờ writer/deny, không chỉ hai object riêng. Raw owner SQL chỉ dùng tạo lock barrier, storage/migration-negative fixtures hoặc đọc assertions; **không UPDATE custody/new_pin_delivered/old_pin_settled/accepted proof để dựng positive workflow**.

## 6. Real-process B1b runners đề xuất

Một `tools/smoke_phase8b_b1b.py` với scenarios tách fixtures/schema/ledger theo label, reuse startup/auth/charge/physical-model primitives từ runners8A sau khi kiểm dependencies; không copy toàn bộ implementation8A.

Warm Admin/Technician/Customer contexts trước receipt freshness window. Device boot handshake và source SNAPSHOT phải được worker processed trước task dispatch; không tạo Simulator object với boot mới giữa các bước rồi reuse task của boot cũ. Source/durable model phải đi qua adapter thật, không nguồn expected_serial hoặc SQL. Nếu timeline vượt freshness thật, giữ failed run và phân loại, không retry mutation nguy hiểm hay nới policy.

| Scenario | Workflow thật | End-state bắt buộc |
|---|---|---|
| B1b-E2E-A | Charge Phase6 verified setup → existing review có new pin chưa giao → Begin0.3 → processed SNAPSHOT → readonly inspect/fence → Tech/Customer confirmations → DECIDE → Admin request | CertificateNO với oldfalse và đúng1 REQUESTED/attempt0/redemption/job; financial Refund effects0; full invariants |
| B1b-E2E-B | Cached command/service task; durable UNKNOWN/PREPARED; restart Simulator | Fence/denial tồn tại, no cert/intent/effect mới; snapshot không biến UNKNOWN thành NO |
| B1b-E2E-C | Old boot/stale receipt; real operation expiry hoặc genuine REJECT → readonly successor với new current3proof | Old evidence giữ nguyên; no history reset/second effect; nếu coverage đủ mới issue certificate; otherwise report fail-closed |
| B1b-E2E-D | Hai API OS processes: competing Admin/DECIDE, revoke-first/authority-first; actual crash precommit và postcommit/pre-response | Exact one or zero committed result theo ordering; no partials, no duplicate audit/job/redemption |
| B1b-E2E-E | Current projection contradiction/inbox processing boundary cạnh tranh redemption; legacy8A action interlock | Accepted projection quyết định đúng ordering, no early release/second supply; no automatic compensation |

Không yêu cầu full Refund financial success/FAILED retry/query/callback trong B1b; các tests đó thuộc B2/B3/B5. Không gọi operator/API-only runner là Browser Passed. Không dùng Browser0.3 mới để mở rộng B4; nếu shared response composition ảnh hưởng8A, chạy affected Browser0.1/0.2 trên final source hoặc ghi Blocked có lý do, không lấy build thay Browser.

## 7. Regression và thứ tự chạy sau approval/code

1. Bounded environment readiness: Docker/pg_isready/runtime SELECT1, explicit schema khác demo, actual migration head, không duplicate pytest/runner. Không sửa business code khi Engine mất kết nối.
2. Static/schema/pure-ledger tests trước; PG migration/grants rồi issuer/redemption tests; sau mỗi substep lưu unique labels.
3. Native PG concurrency và two-OS-process E2E ở`6. Chạy suites **tuần tự**: advisory station/user keys có thể collide xuyên search_path do seed IDs giống nhau. Không đổi production namespace chỉ để tests đỡ contention.
4. Re-run B1a affected regressions: foundation/transactions, original deadlock and remediation, IA01 originals/fix/re-review; P6-A01/A02/A03, P7-A01,8A IA01/NFR06,0.1/0.2 PRE/POST/settlement/revocation, ER01/ER02/fence/ledger/successor/closure.
5. Baseline/overlays hashes, runtime OpenAPI actual unions/authorization allowlist, JSON schemas, migration/grants/runtime roles, dependencies and legacy frontend/build checks nếu relevant. Không sửa frozen B0 validator/shape/security checks; validator B1b khai báo versioned source delta thay vì cập nhật hash lịch sử.
6. Vì shared Device worker/station interlock/API Backend thay đổi, trước handoff B1b independent review chạy **một full Backend collection và suite trên source cuối**, actual count/delta, không --lf/deselect/skip/xfail để ép Passed. Đây là regression cho delta B1b, không thay B5 full Phase8B provider acceptance. Không mặc định count543/603/599; giữ đầy đủ historical nodes hoặc giải thích legitimate versioned migration-test delta.

Commands dự kiến (files mới **chưa tồn tại**, không chạy trong lượt review):

```powershell
.venv/Scripts/python.exe tools/run_phase8b.py B1B_LABEL_MOI tests/test_phase8b_b1b_contract.py tests/test_phase8b_b1b_migration.py tests/test_phase8b_b1b_no_delivery.py tests/test_phase8b_b1b_certificate.py tests/test_phase8b_b1b_refund.py tests/test_phase8b_b1b_races.py tests/test_phase8b_b1b_ledger.py
.venv/Scripts/python.exe tools/validate_phase8b_b1b.py OUTPUT_MOI.json
```

CLI real-process/full-suite chỉ chốt sau runner được viết/review; không viết một lệnh giả đang được đảm bảo chạy. `run_phase8b.hashes()` phải bổ sung **new simulator files, smoke/static tooling, protocol adapters** vào manifest; glob backend/test8b hiện có chưa đủ cho new simulator source. Không sửa accepted191/reviewer192 manifests; ghi before/after B1b riêng, exact intended delta.

## 8. Evidence / preservation

- Mỗi run: unique schema/runtime/ledger/label; logs, JUnit/XML, exit code, UTC timestamps, source SHA256 before/after, collection IDs/delta/warnings, JSON scenario output, DB/ledger snapshots/counters.
- Rejected and failed/interrupted runs giữ nguyên; không suy Passed từ progress hoặc gộp overlapping runs. Counts API checks, pytest tests, Browser và static definitions tách riêng.
- Credentials chỉ private local; không headers/tokens/raw reason/receipt body trong public audit/log report. Public summary đỏ bỏ hostname/user-dir; raw logs vẫn giữ local.
- Runner phải giữ ledgers/schemas/evidence sau fail; chỉ quản lý đúng process nó tạo. Không đụng fixture Browser khác.
- Fingerprint demo read-only trước/sau ghi đúng8-table scope/revision như runner; không gọi nó là whole DB/ledger backup. Không migration demo, reset volumes/schema, delete ledger/cache/evidence.
- Exact-byte source provenance: giữ bytes cũ/EOL; supported checked mode core.autocrlf=input. Không normalize/đổi attributes hoặc update approved hash để làm tests hợp lệ. Mọi B1b intended source delta được review và freeze mới trước long regression.

## 9. Acceptance gates

| Gate | Điều kiện bắt buộc | Trạng thái tại review |
|---|---|---|
| G0 | User approves B1b scope/file proposal/migration và strict frozen semantics | PENDING APPROVAL |
| G1 | Migration clean+upgrade/grants/immutable binding; old0.1/0.2 unchanged | NOT RUN |
| G2 | Complete actual history + current3proof + cached/future effect fence; zero effect during VERIFY | NOT RUN |
| G3 | Correct certificate issuer/binding/validity/revocation; old obligation independent | NOT RUN |
| G4 | Atomic Admin REQUESTED/redemption/attempt0/outbox with replay/rollback | NOT RUN |
| G5 | Deterministic both-ordering PG/two-OS races, actual pre/postcommit crashes, no deadlock/double effect | NOT RUN |
| G6 | Frozen8 action audit coverage, exact before/after, secrecy, idempotency and append-only | NOT RUN |
| G7 | Real-process A–E final source; read-only DB/ledger/fence facts and demo fingerprint | NOT RUN |
| G8 | Affected/full final Backend regression, actual collection delta/exits/hashes; schemas/OpenAPI/dependencies; relevant legacy frontend/Browser where affected | NOT RUN |
| G9 | Zero unresolved Major/Blocker; implementation/test/traceability handoff for independent review | NOT RUN |

G0 design approval không đồng nghĩa G1–G9 Passed. Các thiếu history/UNKNOWN phải tiếp tục review/fence đúng expected, không waive để tạo positive demo. B1b nghiệm thu không hoàn tất TC16/CT13 provider end-to-end, B2–B5,8C hoặc final-MVP NFR04/NFR07/CT14/NFR08.

**Dừng trước implementation.**
