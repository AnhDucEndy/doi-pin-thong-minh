# P8A-E01 — Đề xuất phụ lục P8-REC-0.2

Ngày 04/11/2026. **PROPOSED — DESIGN READY FOR APPROVAL.** Chưa được phê duyệt,
chưa triển khai. Đây là thiết kế kỹ thuật cho RETURN_FOREIGN_OBJECT, không sửa
baseline GĐ1/GĐ2, FR/UC/BR/QD, phụ lục P8-REC-0.1 đã duyệt hoặc source hiện tại.
P8A-E01 tiếp tục Major/BLOCKED cho tới khi implementation và kiểm thử đạt.

## 1. Cơ sở và root cause

Đã đối chiếu AGENTS.md; PHASE8A_IMPLEMENTATION.md; PHASE8_APPROVED_DESIGN_PROPOSAL.md;
overlay P8-REC-0.1; migration0003; api/recovery.py và recovery_schemas.py;
application/recovery.py, application/device.py, workers/device.py;
simulators/device/main.py và service.py; test_phase8a_service/command_reconciliation;
runner phase8a_branches nhánh E. Phạm vi truy vết giữ FR12/UC10/BR05/09/11/12,
invariants6–8; FR16/UC14/BR08 chỉ là dependency tương lai, không làm8B/8C.

Call graph hiện tại:

`BEGIN_OPERATION → quiet() → INSERT operation → GET recovery-tasks → quiet()
→ simulator.perform → receipt → human confirmations → settle → quiet()`.

UNKNOWN OPEN_RETURN + ledger EXECUTED bị chặn ngay BEGIN với409
RECONCILIATION_REQUIRED; bỏ guard tại đó vẫn bị chặn ở tasks và settle.
Ngoại lệ positive pickup hiện có chỉ dùng ở final VERIFY_NEW_DELIVERY, không
phải quyền thực hiện action mới. P8-REC-0.1 yêu cầu verified presenter/full ledger
nhưng current snapshot chỉ truyền slots/command ledger. service_presenters ở
SQLite simulator chưa có receipt độc lập trước action gửi về Backend.

Schema hiện chỉ có observation result/actual_serial/supporting_event_ids và
UNIQUE(operation_id,source_kind). Cùng một nguồn không thể ghi inspection rồi
receipt cho cùng operation; proof_errors còn yêu cầu human confirmation sau
simulator receipt. Không thể dùng confirmation trước action làm xác nhận sau
bàn giao. E02 có return UNKNOWN/ledger EXECUTED, review PRESENCE_MISMATCH,
3holds,chargeSUCCEEDED,oldCUSTOMER/newCOMPARTMENT; foreign task409,không service
effect. Đây là bằng chứng lịch sử, không phải test chạy trong lượt thiết kế.

Phân biệt sáu sự kiện: actuator đã chạy; vật lạ trong ngăn; serial đã quan sát;
người trình được xác minh; đủ lời chứng hai phía; custody pin cũ đã commit.
Không sự kiện nào tự suy ra các sự kiện còn lại. Vật lạ không có battery_id.

## 2. Phạm vi và các quyết định đề nghị duyệt

1. Giữ purpose RETURN_FOREIGN_OBJECT; thêm ba **stage của giao thức evidence**:
   PRE_ACTION_INSPECTION, ACTION_AUTHORIZATION, POST_ACTION_RECEIPT. Không thêm
   enum Swap/Payment/DeviceCommand hoặc vai trò nghiệp vụ.
2. BEGIN tạo inspection intent và durable station fence, không cấp service action,
   nên không cần chứng minh quiet cho action tại bước chỉ-đọc. Permission/scope,
   phiên review, slot binding và fence exclusivity vẫn bắt buộc.
3. Chỉ trả vật lạ cho **Customer chính chủ phiên**, đồng thời được ba nguồn xác
   minh là người đã trình vật đó; không mở quyền cho người thứ ba chưa có mô hình
   xác thực. Người trình không xác định/khác Customer → giữ review, không handover.
   Đây là giới hạn fail-closed của MVP, không phán quyết quyền sở hữu vật thể.
4. Thêm inspection/receipt typed payload, human confirmations theo stage, một
   authorization bất biến cho mỗi operation và local durable fencing ở simulator.
5. Giữ TTL operation120s, freshness15s và ACK15/physical60 hiện tại. Authorization
   không có TTL mới: hạn bằng operation.expires_at. Không gia hạn/re-authorize cùng
   operation sau mất kết nối/boot đổi; chỉ đối soát kết quả cũ.

Các lựa chọn trên là **đề xuất xin duyệt**, không coi yêu cầu thiết kế là quyền
triển khai. Không còn quy tắc sở hữu/tài chính mới cần tự quyết để mô tả nhánh an
toàn; nhánh ngoài giới hạn này tiếp tục BLOCKED. Có thể duyệt trọn hoặc yêu cầu
đổi từng mục trước viết schema/migration/code.

## 3. Immutable context và trust boundary

Context gốc gồm version P8-REC-0.2,operation/case/swap/station/device IDs,
source slot,foreign serial,customer/recipient,Technician creator,case/swap versions,
created/expires,known command IDs và hashes. Serial lấy từ current physical
projection và được inspection xác nhận; không nhận serial/recipient override từ
client. Nếu actual khác context: receipt ghi sự khác biệt, không sửa context.
Context hash bất biến. Ledger/snapshot mới là evidence tham chiếu, không ghi lại
context hash theo từng telemetry. Command mới phát hiện phải tái đánh giá toàn bộ.

| Nguồn | Xác thực và chứng minh | Không được suy ra |
|---|---|---|
| Device snapshot | Device-Key→device/trạm,accepted+processed,current boot/seq,observed/received | Danh tính người cầm vật ngoài ngăn |
| Simulator inspection | Cùng Device-Key; đọc model/ledger thực trong local critical section; boot,ledger identity,fence generation | Expected serial hoặc command payload không phải actual observation |
| Presenter chain | Actual wrong-return event IDs/command hash,model presenter record đúng serial/swap/customer; Technician kiểm và Customer chính chủ xác nhận độc lập | customer_id trong command một mình không chứng minh người trình |
| Technician | Bearer,ACTIVE,assignment đúng trạm,creator; xác nhận actual serial và stage receipt cụ thể | Không được giả Customer hoặc chọn holder tùy ý |
| Customer | Bearer của chính swap,session chưa revoke; trước action xác nhận đã trình/đồng ý nhận; sau action xác nhận đã nhận | Hai confirmation có ý nghĩa khác nhau, không dùng lại |
| Post-action receipt | Durable ledger,authorization ID,actual source/destination/recipient và serial; fresh snapshot đối chiếu | Không đổi custody pin cũ hoặc chứng minh khách nhận pin cấp |

Sự kiện wrong-return có thể bị domain từ chối vì sai expected serial; vẫn là
lịch sử quan sát. Phải kiểm authenticity/schema/scope và lý do reject riêng:
chỉ mismatch serial nghiệp vụ được dùng làm supporting history, không nâng event
accepted=false thành true. Event giả nguồn/sai boot/order/stale không được dùng
làm current evidence. Current snapshot mới và inspection độc lập luôn bắt buộc.

## 4. Stage A — PRE_ACTION_INSPECTION, tuyệt đối không effect

Technician BEGIN dưới lock hiện có, tạo operation/fence bền vững; GET tasks trả
task INSPECT, không trả quyền handover. Simulator cài local fence trước đọc model:
SQLite BEGIN IMMEDIATE chung cho command.handle, service.perform và inspection.
Mọi process dùng cùng station ledger phải dùng critical section này. Không chỉ
khóa HTTP polling vì command có thể đã được nhận từ trước.

Trong cùng local transaction: xác định actual slot CLOSED/present/serial;
presenter mapping và supporting event IDs; toàn bộ command/service records có
thể tác động station; boot/ledger_id/fence generation; persist receipt/outbox.
Inspection không mở cửa/đổi holder/di chuyển vật. Command/service handler phải
kiểm durable fence ngay trước effect; command cũ nằm trong fence không được chạy
sau inspection dù đã có trong bộ nhớ. Process không dùng cùng ledger/fence
protocol không được coi là đã chứng minh quiescence.

Không sửa command state để phân giải. Mỗi ledger entry có command ID/hash,
result, effect completion marker và relevant physical event IDs. Hash/count đơn
lẻ không đủ: Backend đối chiếu tập đầy đủ với command DB và records simulator;
entry thiếu/mâu thuẫn hoặc service PREPARED/UNKNOWN chưa phân giải → chặn action.

SIMULATOR receipt gửi trước; Technician và Customer xác nhận **receipt ID/hash
inspection** sau khi Backend đã nhận. Từ chối được lưu append-only. Ba nguồn đủ
chỉ có nghĩa inspection đủ cơ sở để xét authorization, chưa có handover.

## 5. Stage B — ACTION_AUTHORIZATION và quiescence theo mục đích

Technician chủ động yêu cầu AUTHORIZE_ACTION, với expected_version. Không cấp
quyền chỉ vì polling. Transaction theo graph hiện có: user-idempotency → station
→ sorted involved users → swap/slots/pins → operation/evidence/authorization;
recheck role/session/assignment,context,case version,TTL và ba nguồn pre-proof.
Không giữ transaction khi chờ HTTP/human. Dùng cùng serialization với worker.

Backend kiểm current snapshot boot đúng inspection và mới≤15s; foreign serial
vẫn ở return slot CLOSED; actual pin cấp còn ở supply và custody DB khớp,không
OPEN_SUPPLY/other possible delivery;old pin hợp lệ không bị giả nhận;3holds còn,
chargeSUCCEEDED verified,currency/amount khớp;không operation/fence khác mâu thuẫn.
Fence receipt còn đúng generation/ledger identity,không active service effect khác.
Recheck freshness ở điểm quyết định sau tất cả reads/locks.

| Command/service record | Có thể cho action? |
|---|---|
| UNKNOWN OPEN_RETURN + EXECUTED | Chỉ khi full inspection chứng minh effect đã kết thúc,wrong object đúng slot/chain/presenter,fence chặn mọi replay; không đổi command UNKNOWN |
| NOT_EXECUTED | Chỉ khi ledger chứng minh không có effect và local fence đã khóa/cấm command cũ; vẫn kiểm new-pin NO và mọi entry khác |
| ACK/EXECUTED không completion chain hoặc thiếu ledger | Không; không đủ quiescence |
| UNKNOWN có thể còn chạy / PREPARED service chưa rõ | Không; tiếp tục review dù qua TTL |
| OBSERVED/terminal nhưng current ledger mâu thuẫn | Không; không dựa riêng enum |
| Service cùng operation đã effect | Không cấp authorization mới; chỉ replay/query receipt |

Đối với ngoại lệ UNKNOWN OPEN_RETURN/EXECUTED, đề xuất giữ thêm điều kiện bảo
thủ hiện có: inspection/current snapshot phải quan sát sau created_at+physical60
của command gốc. Inspection sớm vẫn chỉ được ghi như evidence,không authorize;
cần inspection mới theo quy tắc supersede trước action. Không tính lại60giây
từ reconnect/ACK hoặc operation mới. Đây là guard manual action,không thay
automatic custody decision hoặc làm mới deadline P7-A01.

Đề xuất tách ba hàm policy thay blanket quiet bypass: inspect_read_allowed;
foreign_action_quiescent(full proof,fence); settlement_proof_complete. Default
quiet các caller khác,nhánh pickup và automatic Phase7 giữ nguyên. “Return đã
chạy” chỉ phân giải khả năng actuator tác động tiếp,không làm old custody đúng.

Commit một authorization ID duy nhất/op,hash chứa context+inspection receipt+
pre-confirmation IDs+boot/ledger/fence+command digest+source/destination/recipient+
expires_at. Không lưu bearer secret vào payload. GET tasks sau đó mới trả ACTION
với authorization đó; lặp polling không tạo authorization/capability mới.

Simulator kiểm authorization qua Backend/device auth,Technician còn quyền và
local fence/boot/model/ledger đúng **ngay trước PREPARED**. Kiểm TTL bằng clock
thực; thay đổi thực tế → từ chối,không sửa timestamp. Authorization không chứng
minh action đã chạy. Revocation xảy ra sau authorization phải chặn request mới;
không hứa có thể thu hồi hồi tố action đã được local transaction chấp nhận.
Nếu không xác định action đã nhận trước revocation hay chưa: review/query ledger,
không reissue. Offline hoặc boot đổi không được bắt đầu action từ cached permit.

## 6. Stage C — POST_ACTION_RECEIPT và settlement

Adapter ghi durable PREPARED trước effect. Một operation/authorization chỉ một
effect; khóa local chung chặn hai caller. Sau PREPARED nếu process chết mà không
có terminal receipt: giữ UNKNOWN,không tự thực hiện lại. Trong mô hình SQLite,
effect cập nhật slot/foreign external holder,presenter linkage,effect counter và
post receipt cùng transaction. Không gửi DOOR/ACK giả hoặc thay command outcome.

Receipt ghi actual serial từ model,source slot,destination CUSTOMER,actual
recipient,authorization ID/hash,context hash,fence generation,boot và seq,
effect_started_at/completed_at,ledger digest và result. Nếu không quan sát được
recipient hoặc serial: UNKNOWN, không điền expected thay actual. Crash sau commit
local trước HTTP: flush replay **cùng event/body/timestamp**,không chạy perform lại.
ACK cho inbox không thay PostgreSQL settlement.

Technician và Customer xác nhận receipt hậu-action cụ thể. Mỗi stage một lời
chứng/source; pre-confirmation không thỏa post-proof. Backend recheck role và
session hiện hành,quyền tại trạm,chronology và full post-proof,current fresh
snapshot mới chứng minh source trống,pin cấp vẫn có,no conflicting command/effect.
Giữ inspection lịch sử làm chain,không refresh observed_at để biến nó thành mới.

Settlement dưới cùng locks+version+idempotency: consume operation,ghi riêng
FOREIGN_OBJECT_RETURN_SETTLED audit với inspection/authorization/receipt IDs,
case version và kết luận trong một transaction. Không thêm battery record vật lạ,
không UPDATE custody pin cũ hoặc pin cấp,PaymentSUCCEEDED không đổi,giữ3holds và
REVIEW_REQUIRED/COMPENSATING. **Không tự old_pin_settled=true.** Muốn xử lý nghĩa
vụ pin cũ phải operation VERIFY_OLD_POSSESSION ba nguồn riêng; không dùng receipt
vật lạ làm proof cho serial pin cũ. Không tự finalise/refund8B/8C.

## 7. Expiry, supersede và khôi phục

- TTL120 không reset theo stage/ACK/reboot. Hết hạn trước authorization: không
  cấp action; có thể inspection operation mới sau khi local fence cũ được chứng
  minh không có outstanding effect. Không chỉ đánh cancelled do TTL.
- Hết hạn authorization trước action: simulator đóng permit no-effect dưới local
  lock,emit receipt mới xác nhận permit không thể dùng lại;Backend cần receipt
  đó trước supersede/release fence. Expiry phía server đơn lẻ không đủ.
- PREPARED/UNKNOWN: không supersede thành operation action mới,không retry effect.
  Read-only reconciliation có thể liên kết predecessor nhưng không hủy fence.
- Effect đã xảy ra/receipt đến sau TTL: nhận lịch sử authenticated kể cả expired,
  không tự settle operation expired. Tạo inspection-only successor liên kết
  predecessor và authorization; lấy proof mới đúng holder/context và snapshot
  current. Chỉ consume predecessor+successor atomically khi chain phân giải đủ;
  không cấp lại action. Cần cùng typed inspection cho vật ngoài ngăn đọc actual
  external model và recipient,không suy từ slot trống.
- Rejected/mismatched proof không overwrite. Trước authorization chỉ supersede
  sau durable no-effect/fence closure. Sau authorization phải giữ predecessor
  tới receipt no-effect hoặc reconciliation effect đã hoàn tất. Boot đổi luôn
  vô hiệu hóa quyền *bắt đầu* action cũ; history receipt vẫn giữ provenance.
- Hai Backends: unique authorization/op +row/advisory locks+idempotency. Same
  key/body replay response;different key/version cũ409;không double authorization,
  audit hoặc consumption. Hai simulators chung ledger:BEGIN IMMEDIATE+unique
  authorization ID;hai ledger độc lập cho cùng device không phải cấu hình hỗ trợ,
  ledger identity mismatch chặn chứ không coi là reboot an toàn.

## 8. Đề xuất contract P8-REC-0.2 tối thiểu

Không tạo endpoint mới. Dùng discriminated union phiên bản mới trên path hiện có,
giữ0.1 cho purpose khác. Foreign operation0.2 bắt buộc staged payload;không cho
legacy request thiếu stage rơi xuống đường action. additionalProperties=false.

| Operation hiện có | Payload/response đề xuất mới | Quyền/status |
|---|---|---|
| POST recovery/evidence | BEGIN_OPERATION chọn foreign0.2;TECHNICIAN_ATTEST thêm stage,receipt_id/hash;AUTHORIZE_ACTION thêm operation/context/expected_version | Technician assigned,Idempotency-Key;200;không thêm quyền Admin |
| POST recovery/confirmations | stage,receipt_id/hash,operation/context,confirm | Own Customer,Idempotency-Key;201;không recipient override |
| GET device/recovery-tasks | INSPECT hoặc ACTION,protocol_version,context,fence/authorization refs;chỉ ACTION có permit | Device-Key đúng trạm;200;GET không cấp quyền mới |
| POST device/recovery-observations | Typed PreInspection hoặc PostReceipt;exact event hash/boot/seq;historical expired receipt được lưu nhưng không làm current | Device-Key;202 durable receipt;phân biệt stored/eligible/duplicate |
| GET recovery | stage proof matrix,authorization summary,missing/conflict reasons;không expose raw keys | Admin/assigned Technician;200 |
| POST recovery/settle | Same operation/version/note;server suy proof stage và kết quả | Assigned Technician,Idempotency-Key;200 hoặc409/422 |

Envelope device: protocol_version literal0.2;stage enum PRE_ACTION_INSPECTION hoặc
POST_ACTION_RECEIPT;event_id/operation_id UUID,context_hash SHA256,boot_id UUID,
seq positive int,observed_at aware datetime,simulation_only=true. Stage B là
authorization record,không phải Simulator attestation.

Pre payload bắt buộc actual_serial nullable,slot observation,source slot,
snapshot_event_id,ledger_id,fence generation,command_entries/service_entries đầy
đủ cho station đang fenced,wrong_return_event_ids,presenter record (actual mapped
customer/swap/serial hoặc null),result,read_only=true,effect_count_delta=0.
Đề xuất chỉ scope một station/2×6,không pagination làm mất pending entries.
Post payload bắt buộc authorization refs,actual serial/source/destination/
recipient nullable,start/completion times,full relevant ledger/result/effect
count;không nhận new_pin_delivered/old_pin_settled/desired_state từ client.
Unknown/null không vượt validation thành OBSERVED đủ proof.

Human stage assertion buộc receipt_id/hash đã tồn tại đúng operation/stage;
server lấy actor/session từ auth. Pre CUSTOMER là “tôi là người trình và đồng ý
nhận vật này”;post là “đã nhận vật này”. Rejection bền vững,không thay thế bởi lần
confirm khác. AUTHORIZE_ACTION không cho client chỉ định actuator/target tùy ý.

Giữ401/403/404/409/422/503 và error envelope. Tái dùng RECONCILIATION_REQUIRED,
EVIDENCE_REQUIRED,EVENT_STALE/OUT_OF_ORDER,IDEMPOTENCY_CONFLICT,version errors.
Đề xuất409 RECOVERY_STAGE_CONFLICT,RECOVERY_FENCE_CONFLICT và422
RECOVERY_PRESENTER_UNVERIFIED cho hai trust boundary mới;chỉ bổ sung vào overlay
được duyệt,không sửa baseline enums. Detail không chứa bearer/device key.

## 9. Database, constraints và grants — chỉ thiết kế

Không sửa0003 đã tồn tại. Sau duyệt mới forward migration với revision chọn từ
HEAD thực,thử schema riêng trước demo. Không chạy schema.sql/backfill custody.

| Cấu trúc | Delta tối thiểu đề xuất |
|---|---|
| recovery_operations | Nullable protocol_version cho lịch sử,0.2 context chứa stage protocol;không thêm business purpose;context trigger bất biến giữ nguyên |
| recovery_attestations | Thêm stage:LEGACY cho0.1,PRE_ACTION_INSPECTION/POST_ACTION_RECEIPT cho0.2;thêm nullable reference_receipt_id FK cùng operation/stage kiểm bởi service/trigger |
| Unique nguồn | Thay UNIQUE(operation_id,source_kind) bằng UNIQUE(operation_id,stage,source_kind);không bỏ giới hạn nguồn hoặc cho overwrite |
| Event ordering | Giữ event_id UNIQUE và(device_id,source_boot,source_seq) UNIQUE xuyên stages;simulator dùng durable counter monotonic,không reset seq cho từng stage trong cùng boot |
| recovery_action_authorizations mới | id UUID PK,operation_id UNIQUE FK,context_hash,inspection_id FK,pre-attestation IDs,device/boot/ledger/fence,authorized_by,issued/expires,authorization_hash;immutable;revoked_at nullable monotonic có audit |
| Indexes | attestations(operation_id,stage,received_at);authorization(station/device qua operation,expires_at);FK index receipt reference;unique active station fence trong durable simulator ledger |
| Runtime grants | SELECT/INSERT evidence+authorization;không DELETE;chỉ UPDATE revoked_at authorization và consumed/cancelled operation;append-only triggers+cross-operation/stage checks;không grant direct custody APIs |
| SQLite simulator | Durable ledger_id,station fence generation,closed/active status;unique permit/op;stage receipts append-only,outbox sent flags riêng;service effect linked authorization;PREPARED-before-effect protocol |

Existing append-only trigger cấm UPDATE/DELETE evidence: migration phải thêm
default LEGACY không viết lại payload/hash,không sửa timestamp hoặc accepted
status. Nếu cần trigger thay đổi để migration metadata,phải review riêng trong
schema test;không tắt audit protection khi runtime đang chạy. FK stage/role
semantics không chỉ dựa JSON validation. Existing0.1 không tự trở thành staged
proof; foreign case chưa effect có thể mở operation mới0.2,các case UNKNOWN còn
effect chỉ read-only reconciliation,không auto-migrate thành no-effect.

## 10. Ma trận quyết định

| Trường hợp | Authorization/action | Settlement và bảo toàn |
|---|---|---|
| 1 Correct inspection,presenter/chain đủ,command phân giải,fence installed | Một authorization;explicit Technician action duy nhất | Chờ post3nguồn,current proof;object handled riêng,old settledfalse,3holds/charge giữ |
| 2 Inspection đúng,UNKNOWN có thể còn effect | Chặn;không task ACTION | Review,không custody/refund/release |
| 3 Sai serial/presenter/recipient hoặc không biết | Record mismatch/reject,không authorization | Không tự điền context values;giữ vật và nghĩa vụ old |
| 4 Human reject hoặc revoked role/session | Recheck ở authorize,perform,settle;không action mới | Đã possible effect thì query/reconcile,không hủy lịch sử hoặc giả rollback vật lý |
| 5 Crash trước action | No authorization:inspection replay;đãpermit:query ledger | Không cấp permit khác;PREPARED chưa rõ giữUNKNOWN |
| 6 Crash sau effect,trước Backend receipt | Replay durable receipt cùng ID/authorization | Không effect lần hai;DB chưa settle giữreview/3holds |
| 7 Operation expired,effect đã xảy ra | Không renew/action mới;inspection-only successor | Historical receipt retained,new current proof;consume chain nguyên tử,nếu thiếu giữreview |
| 8 Hai Backend authorize/settle | Lock/unique/version:chỉ một permit/decision;idempotent replay | Một audit/object settlement,no duplicate effect,rollback toàn phần |

## 11. Acceptance/test plan sau khi duyệt — CHƯA CHẠY

| Gate | Test bắt buộc và evidence |
|---|---|
| Input/compatibility |0.1 purpose khác không đổi;foreign legacy không thể action;cross-stage receipt giả,wrong context/station/device/actor/serial đều reject;OpenAPI allowlist/security không broaden |
| Inspection |Actual model mismatch/absent/presenter missing hoặc wrong swap/customer;không slot/holder/effect change;full-ledger missing/conflict;read-only restart replay cùng receipt |
| Authorization |Snapshot mới boot/serial đúng;EXECUTED nhưng không completion chain bị chặn;UNKNOWN có thể effect bị chặn;human reject/revoked;freshness15 boundary sau final read |
| Temporal stages |Pre confirmations không pass post guards;receipt cùng source ởhai stage hợp lệ nhưng duplicate stage khác body409;expired evidence chỉ historical;không refresh timestamps |
| Local fencing |Command đã poll nhưng pause trướceffect cạnh tranh inspection;service effect đang PREPARED;reconnect khácledger;hai simulatorprocess cùngSQLite;không generic unlock/reissue |
| PostgreSQL |Hai OS Backends authorize kháckey cùngop,chỉ một auth;settle cùng/differentkey;race worker heartbeat/snapshot/late event;revocation/assignment;không deadlock hoặc staleversion bypass |
| Rollback |Fail sau authorization INSERT/trước audit;fail saucase consume/trướcaudit;idempotency rollback;Payment,custody,3holds không partial write |
| Durable crash |TrướcPREPARED,sauPREPARED,trongeffect,sauSQLitecommit/trướcHTTP,sauinboxcommit/trướcsettle,sauPGcommit/mấtresponse;đếm effect/audit/authorization/receipts |
| Real-process E |Wrong-return→inspection3nguồn→authorize→service→post3nguồn→settle;2Backends,worker,simulators,durableledgers,PGschema riêng;actual model serial/presenter;foreign không networkbattery;oldsettledfalse/PaymentSUCCEEDED/3holds giữ |
| E refusal/recovery |Sai/unknownpresenter,missingproof,oldboot,contradictorynewsnapshot,expiry-before/aftereffect,UNKNOWNrestart;không effectlầnhai;demo fingerprint trước/sau không đổi |
| Regression |PickupUNKNOWN/EXECUTED11tests;serviceledger11;P7-A01 auto deadline/freshness,replay,rollback/concurrency;P6 worker/callback guards khi chạy full8A cuối |

TC12/CT07/CT08 phần8A chỉ đạt khi các gate trên có bằng chứng. Không tuyên bố
TC16/CT13 hoặc toàn8A đạt từ thiết kế. Thực thi sau phê duyệt: schema/input
compatibility → inspection/fence → authorization/local interlocks → receipt/
settlement → targetedPG → realE → full8A cuối. Nếu bất kỳ gate an toàn thất bại,
dừng action,giữreview/holds,không sửa expected để pass.

## 12. Bàn giao, Git và kết luận

Lượt này chỉ tạo **docs/PHASE8_P8A_E01_DESIGN_PROPOSAL.md**; không thay overlay0.1,
source,migration,tests,DB hoặc ledgers. Trước lượt:HEAD e4fb9f5,
main...origin/main,13tracked paths dirty (PHASE5_TEST_ENVIRONMENT chỉ line-ending
warning trong diff);nhiều untracked8A gồm overlay,source,tests,runners/evidence
được giữ nguyên. Danh sách thực tế từ git status đã đối chiếu,không reset/restore.
Không stage/commit/push. Không kiểm thử implementation chưa tồn tại; các số
11service/56targeted/20E2E trước đây là lịch sử. Kiểm tra mới chỉ tài liệu và
git diff --check; không khởi động services hoặc ghi DB. Tài liệu nhỏ,không thêm
cache/build/dependency/image;giữ mọi .local và PHASE8A_TESTS evidence.

**DESIGN READY FOR APPROVAL.** Đề nghị duyệt P8-REC-0.2 đề xuất tại các mục2,
8–9,đặc biệt stage-specific confirmations,authorization duy nhất,fence local
bao phủ cached commands và mô hình presenter chính chủ. Sau duyệt mới tạo
overlay0.2 machine-readable và forward migration. Đây chưa là approval triển
khai,không phải P8A-E01 fixed hoặc Phase8A ready for acceptance.
