# Final MVP integration — release-gate register

Checkpoint **15/11/2026**. Allocation R2-D01/D02/D04 **APPROVED BY USER** bằng câu trả lời **“Đồng ý”** cho câu hỏi chốt allocation và conditional acceptance riêng8A, theo provenance được người dùng xác nhận lại ngày16/11/2026. Không lấy tiêu đề prompt ghi nhận làm approval trực tiếp. [Biên bản](PHASE8A_CONDITIONAL_ACCEPTANCE.md) · [R3 và yêu cầu gốc](PHASE8A_INDEPENDENT_ACCEPTANCE_R3.md).

**Các gates dưới đây NOT RUN / OPEN, không PASSED hoặc WAIVED.** Phải kiểm chứng và được nghiệm thu trước full MVP acceptance/release. Không tự đóng gate bằng build, unit tests, Browser automation hoặc chỉ đổi tên Phase. Không bổ sung ngưỡng nghiệp vụ thay baseline.

| Gate | Allocation đã duyệt | Accountable/support đề xuất theo R3 | Người nhận việc | Test / evidence bắt buộc |
|---|---|---|---|---|
| R2-D01 / NFR04 | Final MVP integration acceptance | TV5 QA accountable;TV3 workload/API;TV1 sign-off | **Chưa xác nhận cá nhân**, nhóm cần chốt |20 authenticated sessions;1000 read requests đo sau warm-up; p95≤2s;2trạm×6ngăn. Ghi hardware,dataset,endpoint mix,warm-up,percentiles,error rate và samples/evidence redacted. Không chọn riêng endpoint dễ đạt hoặc dùng functional pass thay benchmark |
| R2-D02 / NFR07/CT14 | Final MVP integration acceptance | TV5 coordinator/QA;TV3 PostgreSQL/Backend;TV4 payment ledger;TV5 device/service ledger;TV1 sign-off | **Chưa xác nhận cá nhân**, nhóm cần chốt | Coordinated backup PostgreSQL và mọi durable ledger đang dùng;consistency/quiescence boundary;manifest/hashes/revisions/record counts. Restore vào runtime riêng;đối chiếu custody,Payment,holds,audit,idempotency,in-flight state;reconcile trước resume;không duplicate command/service effect/charge. Thêm refund ledger khi module đó thực sự có,không coi restore riêngDB là đủ |
| R2-D04 / NFR08 | Final MVP integration acceptance | TV1 accountable bàn giao;TV2/TV3 UI;TV5 record/QA;3 người dùng thật | **Chưa xác nhận cá nhân và3 người thử**, nhóm cần chốt | Ba người thật thực hiện đúng kịch bản MVP đã chốt,không sửaDB tay;UI rõ bước/phí/timeout/trợ giúp. Ghi role,success,error,help,timeout và kết quả từng người;không credentials. Browser automation hoặc smoke một người không thay trial |

## Quy trình đóng gate

1. Nhóm xác nhận người accountable/support cụ thể; ghi thời điểm và người nhận, không tự điền tên.
2. Chốt kế hoạch/dataset/workload/consistency boundary/scenarios theo tiêu chí gốc, không đổi ngưỡng để hợp thức hóa kết quả.
3. Chạy trên runtime kiểm thử riêng; giữ log/samples/manifests/hashes đã lọc secrets; ghi source revision và môi trường. Không phá demo hoặc ledger hiện có.
4. Reviewer đối chiếu actual results; ghi Passed/Failed/Blocked, evidence và người duyệt. Chỉ gate đạt và được nghiệm thu mới chuyển CLOSED.
5. TV1 tổng hợp trước full MVP release; gate OPEN/Failed/Blocked ngăn full release sign-off. Allocation approval không phải approval kết quả kiểm thử.

NFR06 Recovery8A đã đóng finding tại R3. Tổng audit/monitoring coverage các module MVP còn là nghĩa vụ release integration, không được suy từ21 Recovery actions thành coverage100% toàn hệ thống. Refund8B/Compensation8C và các module chưa hoàn tất có checklist riêng; register này không mở phạm vi hoặc tự triển khai chúng.
