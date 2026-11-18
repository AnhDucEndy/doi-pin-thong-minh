# P8-REC-0.3 — VERIFY_NO_DELIVERY evidence contract

B0 design-only,16/11/2026,**NOT IMPLEMENTED**. D02 approved at [decision record](../../PHASE8B_DECISIONS_APPROVED.md).0.1/0.2 and ER-01/02 remain unchanged;new purpose cannot be safely encoded as VERIFY_OLD_POSSESSION (would attest old custody),VERIFY_NEW_DELIVERY (opposite proposition),or RETURN_FOREIGN_OBJECT (physical handling). Therefore this narrowversioned overlay is necessary,not a replacement of prior protocols.

## Purpose,actors,transport

Purpose **VERIFY_NO_DELIVERY**,protocol_version **0.3**,stage **NO_DELIVERY_INSPECTION**. Physical read-only,effect_allowed=false,effect_count_delta=0. Database writes for operation,observations,human attestations,audit andcertificate are allowed;no financial/custody/hold/old-settlement mutation. No AUTHORIZE_ACTION/ACTIVATE/HANDOVER/task capable of opening or moving anything for this purpose.

Existing routes only:

| Route | Binding / permission |
|---|---|
| POST /v1/swaps/{swap_id}/recovery/evidence | Assigned Technician;UserBearer+Idempotency-Key;strict0.3 BeginRequest,TechnicianAttestation or DecideRequest;expected_version=case.version |
| GET /v1/swaps/{swap_id}/recovery | Existing Admin/assigned Technician scope;0.3 NoDeliveryResponse branch when currentoperation0.3 |
| POST /v1/swaps/{swap_id}/recovery/confirmations | Own Customer principal;strict0.3 CustomerConfirmation;actor inferred from session,not body |
| GET /v1/device/recovery-tasks | Correctstation Device-Key;new task_kind VERIFY_NO_DELIVERY_INSPECT branch only,no effect |
| POST /v1/device/recovery-observations | Correctstation Device-Key;strict0.3 Observation branch,monotonic authenticated device boot/seq/event identity |
| GET /v1/swaps/{swap_id} | Existing owner-only Customerprojection;use CustomerProjection0.3 in existing recovery_confirmation union,no Technicianraw proof/ledger |

No new public path. Tagged0.3 input branches are disjoint from old closed inputs. Runtime composition must UNION branches rather than replace old route schemas/responses/auth;task items also union with existing task types. The overlay GET/evidence response schemas describe **the0.3 branch only**,not a blanket replacement for oldRecoveryCases/0.2 views. The validator composes unions with current8A OpenAPI in memory without startup/DB. GETswap Customerprojection addition is to existing field only;ownership/security cannot change.

## Immutable context and trusted observation

Context bindsoperation/case/swap/station/device,Customer,Technician creator,newbattery/supply serial/two slots,basecase/swap versions,created_at/expires_at andcanonical context_hash. Backend constructs it from DB under station/resource locks;client selects no holder/recipient/NO flag. DefaultoperationTTL remains approvedRecovery120s. A predecessor link is immutable andpurpose0.3-only;cannot revive consumed physical operation or acquire0.2 action authority.

Simulator reads actual model serial/presence/closeddoor,never copies expected_serial to manufacture observation. Observation links an accepted+processed authenticated SNAPSHOT for same device/station/boot,with canonicalpayload hash andseq/provenance. Backend independently checks existing command rows against **complete** local ledger hash/body/identities,service operations/activation records,pending tasks and source device events;one scalarcounter or caller-supplied digest is not proof.

DeliveryHistory must cover retained swap history across boots,including real pickup/transfer events and any service effects for that new serial. Verify event IDs/hashes and gap-free journal coverage using durable simulator history and accepted processed Backend events;newbattery still in supply slot is only one conjunct. If history cannot demonstrate delivery_count0,or physical model/customer statement conflicts,leaveUNKNOWN. An incomplete snapshot/event inbox is not accepted evidence.

## Durable quiescence / cached effects

Before observation becomes eligible,simulator installs persistent station fence under the same SQLite writer mutex as command/service effects. It records a high-watermark/full command+service digest and durable deny entries for **already fetched/cached** commands,service activations and future incompatible supply tasks. Every effect path must check this fence at the final effect point,not only when polling. All writers/issuers must participate;missing issuer coverage is failure,not presumed quiet.

No new physical effect. For every potential effect provide terminal verified history or positive NEVER_PREPARED+durable denial. **Backend command UNKNOWN or service PREPARED/UNKNOWN/unresolved journal blocks certification**,even if a rawledger entry saysEXECUTED. Resolve via an approved purpose-specific reconciliation first;do not convert UNKNOWN→NOT_EXECUTED or mark expired commandsOBSERVED. A terminal OPEN_RETURN can be resolved history without proving newbattery delivery. OPEN_SUPPLY execution/ACK alone proves neither delivery nor no-delivery;complete no-delivery history and zero unresolvedeffects are still required.

Future issuer attempts while fence active are denied and audited. Boot/reconnect/TTL does not clear fence or deny records. Old-boot inspection never counts as currentproof. Accepted certificate/Refund intent must retain control of this fence;operation expiry,certificate expiry or refundSUCCEEDED cannot release it. No-effect closure0.2 cannot close0.3 operation by bypassing this rule. Future8C owns a separately approved terminal release/old-obligation path.

## Three-source proof and decision

SIMULATOR observation,TECHNICIAN attestation andCUSTOMER confirmation must be distinctauthenticated sources for the exactoperation/stage/context/serial/currentreceipt. Customer is swapowner,Technician is creator with currentstation assignment;Admin cannot impersonate either. The human statement means “I confirm the stated no-new-pin-delivery observation/context”,not ownership of an unrelated foreign object or oldpin settlement. Confirm andReject stored append-only,unique(operation,stage,source),reference same SIMULATOR receipt;no overwrite or reuse PRE/POST0.2 proof. Human observed_at is server time after acceptedreceipt received_at.

At VERIFY_NO_DELIVERY_DECIDE,Technician asks Backend to evaluate,not submitsNO. Take existing station→sorted participant users→resources→sorted exact witness/caller sessions locks;re-read all permissions,caseversion,operationexpiry,deviceboot/current snapshot,complete history,denial fence andproof hashes. After waits use currentdecisionclock. All current source observations andhuman proofs must be≤15s old (observed/received,notheartbeat-only),no timestamp renewal. Validate recipient/principal from immutable context andDB,not user fields.

Only then appendEligibilityCertificate and audit,incrementcase.version,setnew_pin_delivered=NO/stateEVIDENCE_RECORDED. **old_pin_settled remains its actual prior value**,includingfalse;Payment,swap financial state,custody,holds,commands/service effects unchanged. Certificate.valid_until is minimum of source freshness deadlines andoperation.expires_at;never extends any timestamp. Certificate carries receipt/humanrefs,case/swapversions,boot/fence/digests. Issuance isnot Refund authorization or a capability to issue commands.

Admin Refund request revalidates certificate andcurrentphysicalcontext/fence/roles after waits and atomically redeems one certificate into the same refundintent;cannot use stale NO flag or certificate alone. On stale/conflict/boot change,collect a **new read-only inspection operation/certificate**,not refresh timestamps. If refund alreadyexists,a new certificate may only refresh eligibility for thatsameintent under explicitAdminreconcile;no newintent/physicalaction.

## Supersede/reinspection,expiry,rejection

Expired/rejected0.3 inspection may have a read-only successor withnewcontext/IDs/current3proofsources;oldREJECT/conflict remains attached andmust be resolved by realnewproof,not ignored or copied. Atomic station fence handover preserves union of olddenials;no gap where cachedoldtask canrun. Unique currentoperation perstation/case-version guard serializes successor vsAdminredemption/closure. If no-effect/quiescence cannot be proven,keepoldfence andUNKNOWN;do not cancel effect-capable0.1/0.2 operations to make room.

Concurrent CustomerCONFIRM/REJECT:one source winsappend-only;other409. Newaccepted contradictory observation invalidates certificate at nextdecision,revocation append-only/audit andcaseUNKNOWN whereappropriate;no financial rollback of proven provider effect. Inbox-only unprocessed events are not proof;stationworker serialization/fence prevents unprocessed event from being silentlytreated as acceptedcurrent state. Expiredwitness/session/role/assignment must refuse before mutation,no acceptedproof/version/successaudit from refusal.

Errors:reuse401/403/404,409VERSION_CONFLICT/RECOVERY_CONTEXT_MISMATCH/RECOVERY_ATTESTATION_EXISTS/RECOVERY_OPERATION_EXPIRED,422EVENT_STALE/EVIDENCE_REQUIRED,503CONFIG_NOT_READY/unavailable;appendixcode409QUIESCENCE_REQUIRED for incomplete durabledenial/history. No keys/rawproof in errorbody. ExacteventID/body replay retains outcome;differenthash409;rejected receipt cannot become accepted on replay.

## Proposed storage and audit

Reuse recovery_operations/attestations/inbox/case fields;forward-only widenpurpose/protocol/stage constraints **only for0.3 VERIFY_NO_DELIVERY**,not existing0.2 foreign-only mapping. Addappend-only eligibility certificates andcertificate redemptions withunique IDs/payment/refund bindings asneeded;immutable context/sourcehashes andlimited runtimegrants. Do not create parallelRecovery orwrite migration inB0. Serviceledger additions are fence/denial/history metadata,not aphysicaltransfer engine.

NFR06 events needed forBegin,acceptedinspection,humanCONFIRM/REJECT,certificateissue/revoke,successor/fencehandover andredemption:actualBEFORE/AFTER caseversion/NO flags andnew childabsence/presence;actor/device/time/correlation/context/source refs. Audit/mutation/inbox/idempotency atomic;rollbackno acceptedproof/cert/audit,replayno duplicates. Do not change meaning of existing21 Recovery audit actions;new purpose-specific eventnames are frozen in the audit matrix of PHASE8B_B0_CONTRACT_FREEZE.md for B1 implementation,never mislabelverification as physicalhandover.
