# Phase 8B — Test plan và acceptance gates

## B0 checkpoint16/11/2026 — decisions approved,tests vẫn chưa chạy

D01 Option B/provider-authorized retry vàD02 VERIFY_NO_DELIVERY **APPROVED BY USER**. Normative contracts hiện hành: [P8-REF-0.1](implementation-contracts/P8-REF-0.1/README.md),[retry protocol](implementation-contracts/P8-REF-0.1/RETRY_PROTOCOL.md),[P8-REC-0.3](implementation-contracts/P8-REC-0.3/README.md). Các đoạn “pending D01/D02” trong review ban đầu bên dưới là lịch sử trướcB0,không phải trạng thái approval hiện tại. Static schema checks không phải runtime acceptance.

| B1–B5 scenario bổ sung bắt buộc | Expected / status |
|---|---|
| FAILED có provider permit+no-effect receipt vàdurable prior denial | Cùng refund/provider key;next generation=prior+1,one effect;**PLANNED / NOT RUN** |
| Denied/expired/consumed/mismatched permit | Không effect/generation sai;replay sameattempt nhận cùng receipt;**PLANNED / NOT RUN** |
| Two workers consume permit +same/different HTTP key | Unique attempt/consumption,one claim/effect;actual2OSprocess;**PLANNED / NOT RUN** |
| Permit issued nhưng Backend crash,dispatch marker commit nhưng POST chưa tới | UNKNOWN STATUS query-only;AdminSEAL_UNACCEPTED phảiatomicdeny/NEVER_PREPARED trướcFAILED;NOT_FOUNDđơnthuần chưađủ;**PLANNED / NOT RUN** |
| Callback generation cũ/future generation/FAILED sauSUCCEEDED | Historical disposition/conflict query,no downgrade/no attempt mới;**PLANNED / NOT RUN** |
| Provider effect lostresponse vàprocessrestart | Query exactattempt,một refund effect;**PLANNED / NOT RUN** |
| VERIFY_NO_DELIVERY positiveold_pin_settled=false | Current3source/fullhistory+fence→certificateNO;oldfalse,custody/Payment/holds không đổi;**PLANNED / NOT RUN** |
| UNKNOWNcommand/servicePREPARED,missing history,uncoveredcachedissuer | Không certificate/refund;UNKNOWN/fence giữ;**PLANNED / NOT RUN** |
| Oldboot/stalesnapshot/receipt mismatch/revokedwitness/session/assignment | Refusal saulockwait,trướcwrites;audit/version/proof khôngsuccess;**PLANNED / NOT RUN** |
| Cached tasks trướcfence vàfuture supplytasks | Durabledeny at finaleffect point;reboot/TTL khôngreset;**PLANNED / NOT RUN** |
| Certexpiry/supersede/reinspection vsAdminredemption | Staleversion/context bị từchối;successor readonly khônggây effect;**PLANNED / NOT RUN** |
| Refundsuccess vớiold obligation unresolved | oldfalse,custody/3holds giữ,khôngCLOSED_COMPENSATED;existingRecoveryrefund-presentguard khôngbịbỏqua;**PLANNED / NOT RUN** |
| NFR06 từng newevent ởB0auditmatrix | Exactvaluesbefore/after,afterINSERT failure rollback,replay/concurrency no duplicate;**PLANNED / NOT RUN** |

B0 chỉ có validation tĩnh **PASSED** theo [freeze report](PHASE8B_B0_CONTRACT_FREEZE.md),không có runtimeFAILED/PASSED để suy ra kết quả8B. Nếu B1 thiếu journal/fence hoặc phát hiện ambiguity mới thì **BLOCKED nhánh phụ thuộc**,không nới guards. Phần kế hoạch trước approval được giữ dưới đây để truy vết.

16/11/2026. **PLANNED / NOT RUN toàn bộ tests8B**. Không tạo TC số mới;giữ FR16/UC14/BR08/TC16/CT13.603 Backend/8 runners/Browser evidence là8A,kế thừa để định phạm vi regression,không Passed8B. [Readiness](PHASE8B_READINESS_REVIEW.md),[design/increments](PHASE8B_DESIGN_PROPOSAL.md).

## Requirement → Source → Tests → Evidence → Gate

Các module refund dưới đây là **dự kiến**,không giả file đã tồn tại. Test names là tên kỹ thuật đề xuất,không đổi baseline IDs.

| Requirement | Existing/reused → proposed source | Tests/probes cần tạo | Evidence/gate |
|---|---|---|---|
| FR16/UC14/TC16,BR08 | payments/auth/identity → refund API/service | Paidverified+positiveNO→Admin202;unpaid/PENDING/UNKNOWN/FAILED charge từ chối;fullamountDB;extra clientmoney/state/actor reject | HTTP+DB refundREQUESTED,outbox,audit/version/idempotency atomic;NOT RUN |
| RBAC/QD06,CT10 | principal/current roles+owned_swap → request/get/reconcile | Customerrequest403,Technicianrequest/reconcile403;ownCustomerGET200,otherCustomer404/403 không leak;Adminread/request;revoked Admin401 | Actual endpointsecurity/OpenAPI/requestschema;NOT RUN |
| BR09/Invariant6–7,CT08 | current_snapshot/quiet/servicefence → refundeligibility | new_pin_delivered UNKNOWN/YES reject;flagNO stale/mismatch reject;ACK/empty slot/EXECUTEDalone reject;UNKNOWN/PREPARED service reject | Before/after case/custody/holds/refund0/outbox0 on refusal;NOT RUN,D02 pending |
| BR08 old obligation riêng,CT07 | recoverycase/holds → refundcompletion only | Positive no-delivery với old_pin_settled=false;refundSUCCEEDED giữoldfalse,custody/3holds;không CLOSED_COMPENSATED | Positive fixture phải qua approved proofpath,D02 pending;không SQL UPDATE flags |
| Một full intent/payment,CT11 | DBUNIQUE+idempotency → refunds | Samekey/body replay;differentbody409;differentkey samepaymentconflict;lostresponse sameidentity;2Adminrace | Actual DBunique1,intent/key/ref stable,oneaudit/outbox;NOT RUN |
| TC16/CT13 refund ledger | Providerchargeledger → refundledger | Chargeexistsverified;wrongoriginalreference/payment/refund/key/money/currency;2simultaneousPOSTs;restart/replay | Separate providerprocess,SQLite durableeffect≤1,totalrefund≤charge;NOT RUN |
| SM-04 timeout | worker/outbox → refunddispatch/query | Timeout before/after effect,lostresponse,NOT_FOUND/PENDING/UNKNOWN query;workerrestartbeforeHTTP/afterclaim | Exact samekey;no automatic newPOSTafteruncertainclaim,no guessedFAILED;NOT RUN |
| FAILED→PENDING conditional | Adminreconcile/provider retryprotocol | Allowed retry vsdeniedretry;latefailurefrompriorattempt;replayretrypermit;2workers consumepermit | D01 approval prerequisite;sameintent/key;oneeffect;NOT RUN/BLOCKED design |
| Callbackvalidation,P6-A01/02 | payment_events andreceiptlock/savepoint → refunddispatch | Wrong source/refund/payment/key/reference/amount/currency;eventIDbodyconflict;sameIDreplay;crossrefundreferencecollision;uniqueviolation/savepoint | Badcallback khôngpoisonacceptedInbox;later validcallback processed;original charge không đổi;NOT RUN |
| Finalresult ordering | refundapplyresult | Callbacksuccess beforeHTTPresponse,query+callbackrace;SUCCEEDEDthenFAILED;FAILEDthenSUCCEEDED conflicting generations | Stable success,no downgrade;conflict audit/query;oneeffect/onefinalsuccessaudit;NOT RUN |
| NFR06/BR12 | actualaudit snapshots/appendonly → refundaudit | ExactBEFORE/AFTERvalues cho request/dispatch/UNKNOWN/reconcile/result/conflict;creationnull;failureafterauditINSERT;forbiddenfieldsredaction | Coverage matrix toànrefundmutations,rollback/replay/concurrency giá trị thật;NOT RUN |
| P6-A03/CT06 | workers/retry + simulatorledger | PostgreSQL55P03 same-schema contention,recoverwithinbudget,exhaustion/fatalfail;restartPREPARED/UNKNOWN no reeffect | Real PGbackendPID/logretry/recovery,rollbackbeforebackoff;NOT RUN |
| P7-A01/8AIA01/ER01/02 | Frozenlegacyguards | Existing currentboot,deadline60/freshness15,ordering,serviceclosure/successor+session revocation tests | Original expected assertions giữ;fullnewcollection/exits/hashes;NOT RUN trên8Bsource |

## PostgreSQL deterministic concurrency matrix

Chạy từng label tuần tự trên schema riêng,migration/runtime roles riêng;không DROP/TRUNCATE/reset volumes. Hai Backend **OS processes** độc lập khi cần,không gọi2TestClients là2processes. Barriers chỉ test tooling,không importproduction;ưu tiên quan sát pg_locks/pg_stat_activity blocker PID vàcommit order,không dựa sleep may rủi.

1. Hai Admin cùng payment,cùng key vàkhác key:thử cả thứ tự,exactoneintent/outbox/audit.
2. Requestrefund vsRecoverysettle/resume/authorization/successor/closure:refund lock trước thì không actiongiao pin mới;settlement trước cóYES/COMPLETED thìrefundreject;close no-effect không tự grantrefundeligibility. COMPENSATING không tự unblockold-pin workflows ngoài8C.
3. Requestrefund vsdeviceworker boot/snapshot/commandACK:phân biệt inbox unprocessed với acceptedprojection;workercommit trướcmâu thuẫn thìreject,snapshot sau chỉreview/conflict,chưa cho effects mới.
4. Adminlogout/rolechange vsrequest/reconcile;witnesssession/assignment revoke trong proofvalidation. Test revokecommit trước finaldecision vàsettlement/authorization lock trước revokewaits. Expiry/freshness qua lockwait dùngclockthật,mốc15s giữ nguyên.
5. TwoRefundworkers claim sameoutbox,callback-vs-query,callback-vs-retrygeneration;kiểm case/refundversions,audit,processed_at vàproviderledgerkhôngduplicate.
6. Audit/DB failure sauintent,afteroutbox,afterresult,afteraudit trướccommit:rollback trọnbộ. Crash OS trướccommit vàsaucommit trướcHTTPresponse,retryexactkey nhận cùngidentity,audit/effect không tăng.

Mỗi probe ghi OS/PGPID,barrier+lockwait,requeststatus/businesscode,commitorder,refund/payment/case/swapversions,consumed/timestamps,evidencecontext,custody/holds/effects/audit/inbox/outbox/idempotency. Không rawpassword/token. Expected refusal khôngpartialwrites. Nếu phát hiện Majorlocking/custody:dừngnhánhphụthuộc,lưu failingevidence,reviewbảnsửa riêng.

## Real-process E2E plan

PostgreSQLschema mới,2APIs+paymentworker+mockprovider+deviceworker/simulators có ledgersriêng. Customer/Technician/Admin auth thật;testmodelactualevidence,không SQL UPDATE custody/proof/expiry. Warm browsercontexts trước freshreceipt;không nới deadlines để demo.

- Happy path:chargeSUCCEEDED→technical no-delivery verified→Adminrefund→outbox→provider→callback/query→RefundSUCCEEDED;GETCustomer đúngowner. Kiểm chargeSUCCEEDED riêng,không releaseholds/oldpinfalse tự thànhtrue.
- Fault path:providerpersist effect rồi mấtresponse;killworker trướcDBapply;restartquerysamekey;ledgerrefundeffect1. Callbackretry durableidentity;callback sai trước/sau validkhôngpoisonreceipt.
- UNKNOWN path:không có authoritative final,workerrestart/query giữUNKNOWN/3holds;không tạo khoản hoàn hoặc cấp pin khác;NOT_FOUND sau ambiguousdispatch không interpreted no-effect.
- FAILED path:theo D01 đã duyệt,nếu provider không cho phép thìfailclosed;không báo positive retryPassed khi chưa có protocol.
- Race path:Adminrequestrefund vssettle/newdeviceevidence,callback vsotherworker,revocationbeforefinaldecision;không financial success giả hoặc doublephysicaleffect.
- Old obligation path:D02approvedpositiveNO dùoldunsettled;refundSUCCEEDED vẫnneeds8C,3holds/custody giữđúng. Không cố demoCLOSED_COMPENSATED trong8B.

Providereffectcount dựaSQLledgersđọc saukill/restart,khôngchỉlog. Fingerprintdemo trước/sau ghi rõtablescope (không gọi8bảnglàtoànDB). Giữ schema/runtime/ledgerfailedruns;chỉstoptestprocesses do runner tạo,khôngfixtuređangdùng.

## Regression/contract/UI và acceptance

Sau targetedPassed:runrealprocess,bổsungAdmin/CustomerBrowseraffectedflow,response loss/reload/duplicateclick/403/409/503. Customerrefunddisplay đọcGETgốc,khôngunknown→success,không tin amountclient. Customerreadschema/rolefilterkhông lộrawledger/proof.

Validators:baselinehashes/OpenAPI/strictJSONschemas/migrationgrants/pipcheck/frontendtests/TypeScript/Vite. Newrefundroutes vàcallbackunion đượcallowlist đúngoperationIDs;chargeschemas/PaymentProviderResult không tự mở rộng theorefundretryfields. Regression test_phase6::test_TC14_callback_identity_money_and_source vẫngiữ negative randomrefund/nullrefundeffects0;validknownrefund cầntestmới,không đổiexpectedđểné lỗi.

Chạy **một full Backend suite hoàn chỉnh trênsource8Bcuối**,collectactualcountvàso historical603nodes,no --lf/deselect/skipđểépPassed. LưuJUnit/log/exittimestamps,sourcehashbefore/after,collectiondelta,warnings;khôngsuy sốmới từ603. Full frontend/Browser khôngđượcthay bằngAPI-only/SSR/build. PhânloạiPassed/Failed/Errors/Skipped/Blocked/NotRun riêng,không cộngE2Echecks vàopytest.

8B acceptance chỉđềxuất sau:D01/D02approved;TC16/CT13 vàmatrixpositive/negative/rollback/replay/OSprocessracesđạt;providerrefundeffect≤1;charge/custody/holds/fence/P6/P7/8A khônghồiquy;NFR06beforeaftercomplete;contract/migrations/build/fullnewregression vàBrowserđủevidence;khôngMajor/Blocker. NFR04/NFR07/CT14/NFR08 tiếp tụcfinalMVPreleasegates,không tựmiễn hoặcPassed. KhônggọifinancialrefundPassedlàPhase8C/finalMVPhoànthành.

**Lượt này không chạy tests,không infrastructure/refund mutations.** Tất cảtest8Bởtrên **NOT RUN**,D01/D02phụthuộcthiếtkế. Dừngđểngườidùngreviewhồsơtrướccode.
