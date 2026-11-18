# Phase 8B — Baseline review & implementation readiness

## B0 checkpoint16/11/2026 — current design baseline

**B0 CONTRACT FROZEN — READY FOR B1 IMPLEMENTATION REVIEW.** P8B-D01 Option B vàP8B-D02 VERIFY_NO_DELIVERY đãAPPROVED BY USER. [Decision record](PHASE8B_DECISIONS_APPROVED.md),[freeze/traceability/locking/audit/B1–B5 handoff](PHASE8B_B0_CONTRACT_FREEZE.md),[Refund overlay](implementation-contracts/P8-REF-0.1/README.md),[Recovery0.3 overlay](implementation-contracts/P8-REC-0.3/README.md) là baseline hiện hành. Staticvalidation exit0:2bundles/34definitions,77shapechecks,2standaloneOpenAPI vàmerged8A+8Bspec hợp lệ;legacyCharge/security/Recovery0.1/0.2 không đổi.179sourcehashes delta0.

Freeze chỉ chốt thiết kếB0,không runtime acceptance8B hoặc quyền tự codeB1. Runtime/PGconcurrency/crash/E2E/migrations **NOT RUN**;không refund/physical effects,production changes,stage/commit/push hoặc8C. Phase8A conditional acceptance giữ nguyên;NFR04/NFR07/CT14/NFR08 vẫn OPEN. Nội dung initial review dưới đây giữ lịch sử trước approval/B0,không dùng trạng tháipending/proposed cũ thay checkpoint mới này.

## Initial review — historical

Ngày16/11/2026. **PARTIAL/BLOCKED cho triển khai đầy đủ8B**, chờ quyết định tại [design proposal](PHASE8B_DESIGN_PROPOSAL.md). Đây là review/design, không triển khai, không acceptance hoặc refund effect mới.

## Baseline và checkpoint

HEAD/main `de9b9288452f3c4e2b6703ed0ce641668ac8fc78`, origin/main local reference đồng bộ. Không liên hệ remote mới trong lượt review. Phase8A **CONDITIONAL ACCEPTANCE APPROVED BY USER** giữ nguyên; IA01/NFR06 Recovery closed technical scope.603 Backend Passed và179 hashes là evidence8A, không phải tests8B. NFR04/NFR07/CT14/NFR08 vẫn OPEN cho final MVP release; owner cá nhân cần nhóm xác nhận theo [register](MVP_RELEASE_GATES.md).

Nguồn: AGENTS; CODEX_START_HERE; CODEX_HANDOFF; approved decisions/config; baseline GĐ1 DOCX (FR16 paragraph321/323,BR08 paragraph109,UC14 và TC14–16 paragraph576); GĐ2 OpenAPI/schema/state-enums; SM-04,AD-04b,SM-03b; INVARIANTS6–8; handoff/ACCEPTANCE CT13/14; implementation plan/status,gap/design/approved proposals8A và các findings P6/P7/8A. Đọc DOCX bằng XML,không dùng bảng Passed làm yêu cầu.

FR16/F6→UC14→TC16 là hoàn phí,không đổi số khi tên Phase thực tế là8B. Handoff nhóm5 gộp recovery/refund/compensation; triển khai thực tế chia8A recovery,8B refund,8C compensation/UI tích hợp. FR12/UC10/TC12 và CT07/08 là dependency tài sản; không tuyên bố hoàn tất chúng chỉ từ refund thành công.

QD01–09 vẫn:2×6,một họ pin mạng lưới,mock/tài khoản cấp sẵn,Admin/Technician tách biệt,sai pin cần kỹ thuật,thu trước phí9.000VND từ cấu hình approved,ngưỡng80/80/40 là giả định demo và15/60/15 không đổi. Full-admin-reviewed refund trong MVP; không tiền thật,partial refund,ví,gói thuê bao hoặc pin ngoài mạng lưới.

## Inventory source thực tế

| Thành phần | Source/test cụ thể | Hiện trạng và tái sử dụng |
|---|---|---|
| Khoản thu/consent | application/payments.py,api/payments.py;test_phase6.py TC14/15 | Đã có một charge/phiên,quote DB,outbox,idempotency,RBAC;không phải refund implementation |
| Provider mock | simulators/payment/main.py::Ledger | Chỉ bảng charges/callback_deliveries,POST/GET charges;key/hash dedup,WAL,BEGIN IMMEDIATE,lost-response. Không có refund endpoint/ledger/effect |
| Worker | workers/payment.py::tick/process_events/provider_request | Chỉ chọn outbox kind CHARGE;mọi inbox event apply như charge. Tái sử dụng transaction-before/after HTTP nhưng phải dispatch rõ refund_id/kind,không route refund vào charge |
| Callback | api/payments.py::PaymentCallback;application/payments.py::receive | Schema có optional refund_id không nhận null;service hiện **422 INVALID_ACTION** nếu có refund_id. Shared Payment-Key/inbox/hash/replay có,refund verification chưa có |
| Callback conflict | payments.apply_result/reject_receipt | Receipt owner advisory lock+UNIQUE+savepoint giữ P6-A01;P6-A02 validation trước insert;test_phase6_blocker_fix/acceptance. Không copy charge transitions cho Refund một cách máy móc |
| Worker55P03 | workers/retry.py;test_phase6_worker_recovery.py | Bounded backoff1s/2s ngoài transaction,exhaustion không bị nuốt;giữ nguyên contract P6-A03,không retry HTTP trực tiếp |
| Refund storage | alembic0001_baseline.py;database/schema.sql::refunds | Có REQUESTED/PENDING/UNKNOWN/SUCCEEDED/FAILED;UNIQUE payment_id/provider_key/provider_reference,amount>0,version. Chưa có service/workflow/grants ghi refunds |
| Inbox/outbox/audit | payment_events.refund_id,outbox_messages kind REFUND,audit_events | Baseline đủ cấu trúc gốc;không tạo bảng intent/inbox trùng. Cần thêm validation/check/grants/immutability thực sự thiếu bằng forward migration khi được giao |
| Recovery | recovery.py::settle/quiet,current_snapshot;authorization.guards;closure/reconciliation | Đã có proof,locks,fences,old_pin_settled,new_pin_delivered. UNKNOWN/ACK/EXECUTED không delivery proof;không dùng một flag NO cũ thay current evidence |
| Cross-module guard | recovery.settle khoảng578;authorization.guards khoảng166 | Các paths này **chặn khi tồn tại bất kỳ refund**. Đây là guard an toàn hiện hữu,không lỗi8A.8C cần đường xử lý pin cũ sau refund có thẩm quyền;không âm thầm gỡ trong8B |
| Custody deadline | swaps.py;test_phase7_deadline.py;P7-A01 fix | Automatic custody decision60s,freshness15s độc lập;manual refund không gọi advance với deadline giả |
| Audit | recovery_audit.py,recovery.audit;test_phase8a_audit.py | Reuse nguyên tắc actual before/after,allowlist,atomic rollback vàno duplicate audit;helper hiện chỉ đọc scope Recovery,chưa phải Refund audit helper |
| Web | apps/web/src/Payment.tsx | Charge/consent/Admin charge reconcile có;không refund view/request/reconcile. Customer GET refund phải dựa Backend;UI không suyeligibility |
| OpenAPI/allowlist | main.py,recovery_contract.py,test_phase1_contract | Chỉ allowlist operations đã triển khai. Chưa thêm refund APIs vào runtime. Mở đúng5 operations gốc và dispatch callback,không nới security của endpoint khác |

Migration files hiện đến0008_recovery_reconciliation. Chưa truy vấn live schema/grants ở lượt này,không suy demo DB đã ở0008. Schema nền/migration0001 có refund table không có nghĩa runtime đủ quyền hoặc đã có testsTC16. Không chạy Docker/migration/tests/refund effect để lập inventory.

## Gaps cần chốt

1. **FAILED retry handshake**: SM-04 cho phép FAILED→PENDING chỉ khi provider cho phép. Strict provider schema hiện không có attempt/retry permit. POST cùng key/hash trả cached result của ledger charge hiện có;không thể mặc nhiên biến replay thành retry refund mới. Cần chốt phạm vi/cơ chế D01.
2. **No-delivery khi pin cũ chưa settle**:8A positive NO thường đi cùng VERIFY_OLD_POSSESSION/RETURN_OLD_TO_CUSTOMER và old settled=true;foreign0.2 giữ UNKNOWN. Cần đường proof độc lập cho NO trong khi old obligation chưa giải quyết,không dựng fixture SQL để vượt requirement. RESUME_SWAP có thể ghi NO nhưng tạo command mới,không là refund eligibility certificate. D02 đề xuất tối thiểu,chưa approved.
3. **Durable quiescence cho refund**: quiet() xử lý commands,không tự chứng minh mọi service operation/future cached task vô hiệu. Phải kiểm toàn bộ ledger/fence và giữ COMPENSATING/refund-intent interlock. Không mở generic unlock hoặc giải phóng fence/holds bằng refund success.
4. **8C dependency**:refund SUCCEEDED vẫn Payment SUCCEEDED,holds/custody không đổi. Existing Recovery refund-present guard không có workflow giải quyết pin cũ sau refund;ghi rõ cần8C được giao riêng,không coi đây là compensation8B đã hoàn tất.

## Implementation readiness

Có thể tái sử dụng baseline enum/storage,auth/idempotency/inbox/outbox,audit pattern,provider process vàtest harness. Cần xây refund domain/service/API,provider durable refund ledger,worker dispatch/callback/reconcile,eligibility adapter và read projection. Thiết kế/test plan có thể review ngay; **chưa READY FOR toàn bộ8B implementation** cho đến khi D01/D02 được chốt và overlay tối thiểu được duyệt. Không tự suy approval từ việc giao review.

Chỉ tạo ba tài liệu8B;không sửa production/requirements/contracts/migrations/acceptance8A hoặc environment artifact. Không pytest mới,không commit/push,xóa/clean hoặc8C/9/10. [Test plan](PHASE8B_TEST_PLAN.md) phân biệt rõ planned với Passed.

## Git và kiểm tra cuối lượt

HEAD vẫn `de9b9288452f3c4e2b6703ed0ce641668ac8fc78`,main...origin/main;index rỗng. Tracked modification duy nhất vẫn `docs/PHASE5_TEST_ENVIRONMENT.json`,không sửa/reset/restore. Git liệt kê966 untracked files:963 có trước lượt này và ba tài liệu8B mới;không xóa evidence cũ. `git diff --check` exit0 (cảnh báo CRLF→LF của environment artifact không phải lỗi check). Tính lại SHA256 của179 frozen source files:delta rỗng. Không có migration/API/refund effect hoặc test execution mới; không dùng603 Passed lịch sử làm nghiệm thu8B.
