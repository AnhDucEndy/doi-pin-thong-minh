# Phase 8B — Approved decisions for B0

16/11/2026. Nguồn: yêu cầu người dùng đính kèm **“PHASE 8B — INCREMENT B0 / Approve Decisions, Finalize Versioned Contracts & Freeze Implementation Baseline”**, mục2 ghi rõ hai quyết định đã được người dùng phê duyệt. Đây là approval của người dùng trong phiên cộng tác,không giả chữ ký/approval giảng viên hoặc thành viên nhóm. Chỉ cho phép documentation+contract+static validation B0,không tự bắt đầu B1.

| Decision | Approval | Giới hạn bất biến |
|---|---|---|
| P8B-D01 | **APPROVED — Option B: provider-authorized FAILED retry** | Một refund intent/payment;provider key và charge binding bất biến;durable permit+ordered attempt generation;HTTP replay không tạo generation;UNKNOWN chỉ query/reconcile;provider phải chứng minh past no-effect và future denial;effect≤1;SUCCEEDED không downgrade |
| P8B-D02 | **APPROVED — VERIFY_NO_DELIVERY** | Read-only vật lý/tài sản/tài chính;operation/evidence/audit writes append-only/versioned được phép;current simulator+Technician+Customer proofs,boot/hash/ledger/current projection và durable quiescence/cached-task fence. Backend mới kết luậnNO,old_pin_settled có thểfalse;không custody/holds/refund/compensation hoặc cấp lệnh mở cửa |

Không thay FR/UC/BR/TC/CT/QD01–09,MVP,fee hoặc role model. ACK15s/physical60s/freshness15s không đổi. Phase8A CONDITIONAL ACCEPTANCE và IA01/NFR06 technical closures giữ nguyên. NFR04/NFR07/CT14/NFR08 vẫn OPEN trước final MVP release.

Thiết kế chi tiết và lựa chọn transport kỹ thuật được cụ thể hóa tại [P8-REF-0.1](implementation-contracts/P8-REF-0.1/README.md),[P8-REC-0.3](implementation-contracts/P8-REC-0.3/README.md) và [freeze report](PHASE8B_B0_CONTRACT_FREEZE.md). Freeze không là acceptance implementation hoặc quyền tự triển khai B1–B5.
