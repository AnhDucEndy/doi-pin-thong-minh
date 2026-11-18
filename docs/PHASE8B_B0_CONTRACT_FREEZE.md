# Phase 8B — B0 contract freeze & B1 handoff

16/11/2026. **B0 CONTRACT FROZEN — READY FOR B1 IMPLEMENTATION REVIEW** trong phạm vi design/static validation ghi dưới đây. Không tự bắt đầu B1. Đây không là nghiệm thu implementation Refund hoặc full MVP.

## Decisions và inventory

[P8B-D01 Option B và D02 VERIFY_NO_DELIVERY đã APPROVED BY USER](PHASE8B_DECISIONS_APPROVED.md). Không còn quyết định nghiệp vụ chưa chốt cần cho B1 theo phạm vi này. Các lựa chọn giao vận mới là contract versioned,không sửa baseline. Phase8A conditional acceptance,IA01/NFR06 technical closure và final MVP NFR gates OPEN giữ nguyên.

| Artifact | Frozen scope |
|---|---|
| P8-REF-0.1/README.md | Public API/version/RBAC,dispatch,state/money,locking,grants,audit/error semantics |
| P8-REF-0.1/RETRY_PROTOCOL.md | Provider-issued permit,attempt generations,replay,expiry/consumption,queryseal,crash/result precedence và no-double-effect argument |
| P8-REF-0.1/contract.schema.json |17 named definitions:strict public request/refund,baseline provider shapes,tagged commands/permit/results/query/callback |
| P8-REF-0.1/openapi.overlay.yaml | Additive five refund operations+existing callback;embedded baseline schemas chỉ là standalone validation context |
| P8-REC-0.3/README.md | New read-only purpose/trust/provenance/quiescence/current3-source proof/certificate;no physical or financial authority |
| P8-REC-0.3/contract.schema.json |17 named definitions:context/task/observation/ledgers/proofs/attestations/decision/certificate/role projections |
| P8-REC-0.3/openapi.overlay.yaml | Existing Recovery API branch additions;no new Recovery public path;Customer projection type for existing GETswap field |
| P8-REF-0.1/validate_static.py | Offline schema/shape/OpenAPI composition/security/legacy/source validation,không HTTP/DB/lifespan |
| PHASE8B_DESIGN_PROPOSAL.md / PHASE8B_TEST_PLAN.md | B0 checkpoint hiện hành và planned B1–B5 acceptance;trước approval là lịch sử |

Định nghĩa có tên nằm trong `$defs` hai bundle,không phải34 endpoints. [Static result](implementation-contracts/P8-REF-0.1/validation_20261116_04.json) là nguồn actual counts. [Freeze manifest](implementation-contracts/P8-REF-0.1/freeze_manifest.json) ghi từng path/SHA256;không chứa credentials. Các JSON Schema field constraints không thay cross-table/session/time/ledger guards normative trong README.

## Compatibility contract

Giữ nguyên baseline GD1/GD2/OpenAPI/FR/UC/BR/TC/CT/QD vàcharge schema/result/security. PublicRefund body=ReasonAction như cũ;expected_version request làPayment.version,reconcile làRefund.version. No clientmoney/state/actor. Refund currency được derive từ Payment;strictRefunds output không tự thêmcurrency.

Private Refund branch chọn bằng X-Refund-Protocol/body protocol_version vàtyped commands. Không header=baseline unchanged,initial attempt0 only;không âm thầm cho baseline client retryFAILED. Tagged HTTP key=attempt_id hoặcAdminreconcile_request_id theocommand,không provider_keymới. Callback legacyrefund chỉ generation0 nếu không có latergeneration;charge no-refund_id semantics giữ.

Composition normative:chỉ thêm **prefixed P8RF/P8ND** schemas từ standalone overlays vào runtime spec;không replace embedded baseline components hoặc oldRecoveryschemas. UNION legacy0.1/0.2 vànew0.3 input/response/task-item branches,giữsecurity/roles/opIDs trước merge. Customer recovery_confirmation union thêmminimal0.3 projection,không expose Technician proofs. No source merge code được viết ởB0.

P8-REC-0.3 cần forward constraint/trigger branch:0.2 vẫn foreign-only,0.1 purposes giữ,0.3 chỉVERIFY_NO_DELIVERY;stageNO_DELIVERY_INSPECTION chỉ đúngpurpose/source/context. Không repurpose PRE/POST0.2 hayactual physical ledger entry thànhcertificate.

## State,authority và invariants

Refund states chỉREQUESTED/PENDING/UNKNOWN/FAILED/SUCCEEDED. Failed retry chỉprovider-authorized newgeneration,cùngintent/key/payment. UNKNOWN jobs query-only,không nâng thànhPOST khiquerytrảFAILED;phải cóAdmindecisionmới. SUCCEEDEDkhôngdowngrade. PaymentchargeSUCCEEDEDkhôngđổi,refundsuccesskhôngoldsettled/custody/hold release/caseclose/CLOSED_COMPENSATED.

Provider uses global payment/refundmaster uniqueness+writer lock,effect count0/1,uniqueattempt+generation/permitconsumption. PriorFailedno-effect phải có journal NEVER_PREPARED+durable denial;PREPARED/UNKNOWNkhôngđược suy từeffect_count0/expiry. Successor grant=priorgeneration+1,permit canonicalattemptid duy nhất. Newpermit validity15s là transport bound mới,không đổiACK15/physical60/freshness15/paymenttimeout30. Expiry không chứng minhnoeffect. Admin UNKNOWN reconciliation có thể querySEAL_UNACCEPTED để provider atomicdeny **trước** no-effectreceipt;cachedPOSTsau đó bịchặn. STATUS/NOT_FOUNDđơnthuần vẫnUNKNOWN.

VERIFY_NO_DELIVERY bắt buộc three-sourcecurrentproof,completeactual deliveryhistory,accepted/processed/provenance/hash/currentboot,closedserialmatching vàdurablequiescence allcachedissuers. Unknowncommand/servicePREPARED/UNKNOWN hoặcmissinghistory blocks. CaseNO được Backend kết luận bằngcertificate,khôngAdmin/Customer tự nhập. old_pin_settled=false đượcgiữ;no financial/physicaleffect. Fence/denial khônghếtvìTTL/certconsumed/refundsuccess;8C dependencyriêng mới xửlý terminal release.

## Transaction/linearization matrix

Common order:idem advisory→station advisory/row→sorted users→sorted swap/slots/pins→Payment→Refund→attempt/permit/outbox→sorted exactsessions. Existing device ingress order không đảo;không lấyuser/stationlockmới sau sessions. Snapshot/case/evidence writers serialize qua station mutex. Callbackprovider receipt owner mutex+UNIQUE/savepoint giữP6-A01;validateidentity beforeinboxP6-A02;55P03 boundedretry outside rollbackP6-A03.

| Scenario | Boundary và expected ordering |
|---|---|
| Admin request vsRecoverysettle | Cùngstation/resources;settle thắng códeliveryYES thìrejectrefund;refund thắng tạoCOMPENSATING/refund interlock,không giao thêm |
| Intent vsoldcacheddevice/service task | Chứng minh durablefence+denial trước cert/intent;Backendlock không thaySQLitefence. Không proofquiescence thìkhôngcommiteligibility/refund |
| TwoAdminrequests | Idemkey+station+uniquePaymentRefund serialize;oneintent/outbox,otherreplay/conflict |
| TwoWorkersdispatch/retry | Commitattemptclaim trướcHTTP;uniquerefund/generation+permitconsumption;secondworker chỉquery/replay,cùngattemptid |
| Callback vsquery | SamePayment/Refund/attempt locks;atomicresult/inbox disposition/audit;onefinalsuccess |
| Oldgenerationcallback | Historicaldisposition+authoritative masterquery nếuconflict;không overwrite currentgeneration/SUCCEEDED hoặcspawnattempt |
| RevokeAdmin/witness duringwait | GatherlocksessionsUUID;re-readrole/state/assignment/sessionexpiry+proof/freshness sauwait. Revocationcommittrướcdecision phải từchối;authorizedintent đãcommit khôngbịlogout sauđó sửafinancialtruth |
| CrashafterauditbeforeDBcommit | Mutation/audit/inbox/outbox/idempotency chungtxn rollback,no partialsuccess |
| Provider effect,response lost | Provider receipt/effectdurable;BackendUNKNOWNqueryexactattempt,khôngPOSTlại;restartkhôngeffect2 |
| RefundSUCCEEDED/oldunresolved | Financialresultverified,chargeSUCCEEDED,oldfalse/custody/3holds giữđúng;khôngfinalize8C |

Các linearization points làtxncommit dưới sharedlocks;proof validation dùng freshdecisionclock trướcwrite sauwait,không claimdeadline tạiWALcommit. HTTP/provider vàhumanwait ngoàiPGlocks. Staticreview không là chứngminh thựcnghiệm mọiinterleaving;B1/B5 phải bổsungdeterministicPGbarriers/2OSprocess/pg_locks.

## Data/migration feasibility proposal — chưa thực thi

Không tạoRefundintent/inbox/outbox/auditbảngtrùng. Reuse refunds(uniquePayment/key/reference),payment_events.refund_id,outboxREFUND/audit. Newrefund_attempts FKrefund+unique(refund,generation)/attempt_id;permitreceipt+redemptionuniques;eligibilitycert FKexistingRecoveryoperation/attestation;redemption FKcertificate+refund sauintentinsert,tránhFKcycle cầninsertobjectchưa tồn tại. ProviderSQLitecómaster/attempt/permit/denial/journal/callbackoutbox;chargeledgerkhôngxóa.

Forward-only migration sau actualhead,khôngghi fileAlembicB0. WidenRecoveryprotocol/purpose/stage checks vàcrossstage reference triggers đúngversionbranch;giữimmutable8Acontexts/appendonly/history/grants. Limited runtimeINSERT vàUPDATEstate/version/reference/verified_at theo bảng,khôngDELETE hoặcUPDATEmoney/providerkey/proof/audit. Cross-tablefullamount,currency,role,certificate/callbackidentity vẫnserviceguards;DBuniqueslà lớpchốngduplicate cuối. MigrationPK/FK/grants/runtimeroles vàclean/upgrade tests **NOT RUN**,phải kiểmtrênschemariêngB1,khôngdemo.

## Audit coverage baseline cho implementation

New purpose/finance events không đổi nghĩa21 Recoveryactions hiện có:

| New events | Actual before→after vàrefs bắt buộc |
|---|---|
| REFUND_REQUEST_CREATED | Refundbefore-null→REQUESTED;swapReview→COMPENSATING/version;money/originalpayment/cert/outbox refs;protectedfacts giữ |
| REFUND_RECONCILIATION_REQUESTED | Intent/attemptstate/version trước→job/version sau;Adminauthdecision/ref |
| REFUND_PERMISSION_STORED / REFUND_ATTEMPT_REGISTERED | Permit/attemptabsent→immutablebinding,generation,no-effectreceipt;no moneyeffect |
| REFUND_ATTEMPT_CLAIMED / REFUND_PERMIT_REDEEMED | Dispatchmarker andpermitredemptionbefore/after;FAILED→PENDING chỉgrantvalid |
| REFUND_UNKNOWN / REFUND_RESULT_VERIFIED | State/version/verified_at/referenceactual before/after,currentattempt/sourceevent;charge/custody/holds unchanged |
| REFUND_RESULT_REJECTED / REFUND_CONFLICT | Disposition/refreasonmetadata,không audit success giả,không rawpayload |
| ND_OPERATION_CREATED / ND_SUCCESSOR_LINKED | Childabsence/context/currentref/fencehandover;caseversionactual |
| ND_INSPECTION_ACCEPTED / ND_HUMAN_ATTESTED | Sourceabsent→receipt/statementref;CONFIRM/REJECT metadata,nophysical/financialstate |
| ND_CERTIFICATE_ISSUED / ND_CERTIFICATE_REVOKED | CaseNO/UNKNOWN andversionactual,source/fence/proofrefs,append-onlycertificate/revocation |
| ND_CERTIFICATE_REDEEMED | Redemptionabsent→refundlink;cert/source identityunchanged,no duplicate |

Creationbefore-objectnull,allowlistsecretsredaction,actor/device/time/swap-payment-refund-op correlation. Tests phải kiểm values đúng,không chỉNOT NULL. FailureafterINSERT rollback,exactreplayno auditduplicate. Eventnames lànewappendixnames,cầnkhớpimplementationtestmatrixB1,không dùnghandover-success cho readonlyverification.

## Traceability và implementation order

| Requirement | Contract | Planned acceptance |
|---|---|---|
| FR16/UC14/BR08/TC16 | PublicAPI/eligibility/fullamount/moneyseparation | Onefullrefund/Adminownercorrect,oldunsettledretained |
| CT13/SM-04 | Retryprotocol/attemptpermit/queryseal | Timeout/query/restart/replay,positiveFAILEDretry,denied/expired/consumedpermit,effect≤1 |
| FR12/BR09/CT07/08,Invariant6–8 | P8-REC-0.3 certificate+fence | UNKNOWNnotNO,no release/custody/refundduringVERIFY,8Cnotcompleted |
| P6-A01/A02/A03 | Inboxvalidation/receiptlock/savepoint/boundedretry | Crossreferencecollision,laterlegitcallbackafterreject,55P03recovery/exhaustion |
| P7-A01/BR11/IA01 | Currentboot/provenance/finaltimeguards | No deadline reset,oldboot/stale/revoked witnessrefusal,legacy/POST/successorregression |
| NFR06/BR12 | Auditmatrix+limitedgrants | Exactbefore/after,rollback/replay/concurrentauditcount,historyimmutable |

B1a:actualschemahead/grants+forwardmigration proposal implementation,strictDTO/API+state/repository/audit;B1b:read-onlyVERIFY_NO_DELIVERY transport/actualmodelhistory+fence+3proofcertificate,Adminrequest/outbox(no provider effect untilB2).B2:privateproviderrefundmaster/attempt/permit/queryseal/restart.B3:worker/callback/reconcile/resultassociation.B4:minimalAdmin/CustomerUI.B5:TC16/CT13/races/processcrashes/fullnewregression/Browser/validators. Các lần chuyểnincrement đều cầnusergiao riêng;không tự làmB1.

## Static validation evidence và residual risks

Final command:

```powershell
.\.venv\Scripts\python.exe docs/implementation-contracts/P8-REF-0.1/validate_static.py --output NEW_RESULT_PATH.json
```

Final `validation_20261116_04.json`: **exit0;2 bundles/34 definitions;77 static shape checks;2 standaloneOpenAPI documents vàcomposed8A+8B spec valid**. Actualgenerated8A spec chỉtạoinmemory,khôngenterlifespan/Database hoặcHTTP. Runtimepathsaddedđúng4refundpaths gốc,khôngnewRecoverypath;oldsecurity/Charge/legacyinputs vàprior0.1/0.2 filehashesunchanged;179 sourcefreeze delta0.

Validation01 exit1 vìexamplegenerator không hỗtrợpatternhash copiedtừbaseline;02 exit1 vìvalidator đoán schemaSwaps thay vì dùngactualGETschema `$ref`;sửa riêngvalidator,không nới contract guards.03 exit0/74checks trước khi thêmconditionalresult/sealconstraints;04 exit0/77 làsourcecontractcuối. Chưa cófinaloutput01/02 vì lỗi xảyra trước ghioutput,traceback nằmtoolhistory;không gọi chúngPassed. Runtime8B tests/migration/effects **NOT RUN**,77checks không phảipytest/PG/E2E. Existing603 chỉ8A.

Risks còn lại:distributedPG/SQLitedurability vàallcachedissuersfence phải được runtimeprobes chứngminh;no-effect sealing phải thực sự atomic với everyprovider effectpath;clock/skew/providerpermit15s/freshness15s có thể khiến happy path failclosed;missinghistoricalmodeljournal cấm certificate;oldpinsettlementafterrefund bịexistingguardchặn vàthuộc8C,không sửaởB0. Full MVP NFRload/restore/3usabilityvẫnOPEN. Khôngcòn decision tài chính/tài sản bắt buộc chưaapproved choB1 trongcontract này;runtimefindingmớithìdừngnhánhphụthuộc,khôngnới guards.

B1prerequisites:ngườidùngreviewB0/giaocode,sourcefreezeđượckiểmtrướcbranchwork,DockerPGtestroles/isolatedschema,readonlysimjournalfencecoverage,contractvalidation0 vàtestplanbarriers sẵn. Không giả liveDemoDB0008,khôngmigratedemo,khôngxóa/clean schemas/ledger/evidence hoặcstage/commit/push.
