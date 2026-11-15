# Biên bản nghiệm thu có điều kiện Phase 8A

Checkpoint quyết định **15/11/2026, Asia/Bangkok**.

**PHASE 8A — CONDITIONAL ACCEPTANCE APPROVED BY USER**

Nguồn phê duyệt: người dùng trả lời **“Đồng ý”** cho câu hỏi chốt R2-D01/D02/D04 và CONDITIONAL ACCEPTANCE riêng Phase 8A. Provenance này được người dùng xác nhận lại trong yêu cầu “PHASE 8A — FINAL PRE-STAGING REVIEW” ngày16/11/2026; không dùng tiêu đề prompt Codex làm lời phê duyệt trực tiếp và không suy thêm nguyên văn câu hỏi hoặc ID message chưa có trong repository. Đây là phê duyệt của người dùng trong phiên cộng tác, không phải chữ ký hoặc approval của giảng viên/nhóm. Chỉnh provenance không thay phạm vi nghiệm thu hoặc trạng thái release gates.

## Phạm vi được chấp thuận

- Recovery Evidence & Settlement P8-REC-0.1/0.2, ER-01/ER-02 trong phạm vi đã kiểm chứng.
- P8A-IA01 và R2-NFR06-01 **FIXED/CLOSED trong technical scope** theo [Independent Acceptance R3](PHASE8A_INDEPENDENT_ACCEPTANCE_R3.md).
- Evidence đã được R3 xác minh: Full Backend603 Passed,0Failed/Errors/Skipped,exit0; giữ599 tests cũ+4 audit tests; targeted PostgreSQL86; coverage Recovery21/21 actions;8 real-process runners exit0;8 audit fixtures/63 committed rows; Browser affected3 Passed,frontend39 và TypeScript/Vite đạt. Browser canonical15/IA01 affected6 là evidence kế thừa đúng scope, không cộng trùng.
-179 source hashes khớp freeze trước/sau verification và tại R3; lượt ghi nhận quyết định không chạy lại tests hoặc đổi production.

## Quyết định được phê duyệt

| ID | Quyết định allocation | Trạng thái test/gate |
|---|---|---|
| R2-D01 | **APPROVED BY USER**: NFR04 performance/load đo tại final MVP integration acceptance | **NOT RUN / OPEN**, bắt buộc trước full MVP acceptance/release |
| R2-D02 | **APPROVED BY USER**: NFR07/CT14 coordinated PostgreSQL+durable-ledger restore tại final MVP integration acceptance | **NOT RUN / OPEN**, restart Recovery không thay coordinated restore |
| R2-D04 | **APPROVED BY USER**: NFR08 three-person usability tại final MVP integration acceptance | **NOT RUN / OPEN**, Browser automation không thay người dùng thật |
| R2-D03 | Audit fix đã được giao rõ và R3 xác nhận khép finding Recovery8A | **FIXED/CLOSED technical scope**, không chứng nhận audit/monitoring toàn MVP |

[Release-gate register](MVP_RELEASE_GATES.md) giữ nguyên criteria gốc, owner đề xuất theo TV1–TV5 và yêu cầu nhóm xác nhận cá nhân nhận việc. Phê duyệt allocation không có nghĩa gate đã Passed, đã được miễn, hoặc đã có người nhận việc.

## Điều kiện và giới hạn

Không kết luận FULL MVP ACCEPTANCE PASS. NFR04, NFR07/CT14 và NFR08 vẫn bắt buộc được kiểm và nghiệm thu trước phát hành toàn MVP; TV1 phải kiểm release checklist và không sign-off khi còn gate OPEN. Không tự gán sang Phase10 hoặc miễn trừ vì lịch triển khai.

Không coi toàn bộ FR12/UC10/TC12 hoặc FR16/UC14/TC16, refund/compensation đã hoàn thành. Không tự triển khai8B/8C. Không thay baseline FR/UC/BR/QD/MVP, deadlines, custody,Payment,holds hoặc fence.

Kết luận R1/R2/R3 tại thời điểm review được giữ nguyên; quyết định này là **checkpoint mới sau R3**, không biến các báo cáo lịch sử thành PASS hồi tố. Các biên bản fail/fix, interrupted runs, audit lịch sử thiếu before-state và credentials/ledgers/schema đều giữ nguyên.

## Bàn giao Git

Chỉ chuẩn bị [Git staging proposal](PHASE8A_GIT_READINESS.md). Không git add/commit/push; việc stage/commit cần một lượt người dùng giao tiếp theo. Không xóa artifacts hoặc dữ liệu. Các thư mục build/cache tái tạo chỉ xét dọn trong lượt riêng; `.cache` runtime và `.local` ledgers không được coi là rác.
