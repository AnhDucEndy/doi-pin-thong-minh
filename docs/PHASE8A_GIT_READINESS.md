# Phase 8A — Git readiness proposal

Checkpoint15/11/2026. **Chỉ đề xuất; không stage/commit/push.** [Conditional acceptance](PHASE8A_CONDITIONAL_ACCEPTANCE.md), [release gates](MVP_RELEASE_GATES.md). Không chạy lại603 pytest khi179 source hashes không đổi.

## Include manifest và phân loại

[STAGING_PROPOSAL.txt](PHASE8A_HANDOFF/STAGING_PROPOSAL.txt) là danh sách path chính xác, hợp nhất126 paths của R2 và các bổ sung IA01/NFR06/R3/decision/register. Source IA01 và failing probe archive đã có trong126; không tạo bản sao probe. Files tồn tại/size/hash/secret flags và category từng path trong [candidate_scan.json](PHASE8A_HANDOFF/candidate_scan.json). Manifest cũ giữ nguyên; approval không tự stage bất kỳ file nào.

- A: production Backend/Frontend/simulators, gồm audit helper và payments/swaps handoff; không đổi chúng trong lượt này.
- B: tests, browser specs/config, runners/tooling tái hiện, original IA01 probe source. Package manifest/lock là frontend dev-tooling thay đổi từ các lượt trước.
- C: migrations0003–0008, overlay0.1/0.2, thiết kế/traceability/approval và reports; approved baseline QD đã tracked và không đổi, không sao chép lại hoặc sửa baseline.
- D: chỉ các **public derived evidence summaries** được liệt kê rõ trong manifest (R2/R3 query/inventory/diff/validation). UUID fixture,version/hash và test names là metadata; không có credentials/raw HTTP/ledger. Đây không phải log/XML/trace runtime.
- E: mọi file không nằm trong manifest **không được stage trong proposal này**. Đặc biệt .env/private.json/credentials,.cache/.local/.venv/.vs,node_modules,dist,pycache,DB/volumes,SQLite ledgers,-wal/-shm,raw logs/XML/HAR/traces/screenshots/video/browser profiles và test runtime artifacts. Giữ nguyên trên máy.

## Kiểm tra trước khi stage ở lượt được giao sau

Manifest chỉ là allowlist đề xuất, không phải lệnh git add tự động. Kiểm lại SHA256 từng candidate khi stage; nếu khác scan cần review lại. Không git add -A. Không đưa credential vào response/body, kể cả file ignored. Mẫu literal password/token trong playwright-reporter.test.mjs là dữ liệu synthetic để kiểm redaction, không token đăng nhập; flag được ghi rõ theo file/line và không in giá trị.

File trên1MiB hoặc binary sẽ được gắn cờ riêng; threshold này là heuristic review, không thay tiêu chí dự án. Secret scan là heuristic trên từng candidate, không chứng nhận toàn bộ workspace. Public summaries có paths tham chiếu local artifacts chưa commit; các tests/runners/hướng dẫn được giữ để tái hiện, không hứa clone chứa toàn bộ logs lịch sử.

Tracked docs/PHASE5_TEST_ENVIRONMENT.json là environment artifact tích lũy, **exclude**, không restore/xóa tự động. Các raw evidence p7a01/PHASE7_TESTS/PHASE8A_TESTS không được bulk stage. Danh sách excluded actual untracked/tracked-outside-manifest được ghi trong [exclude_inventory.json](PHASE8A_HANDOFF/exclude_inventory.json), không xóa chúng.

Git/readiness/source freeze cuối trong [workspace_state.json](PHASE8A_HANDOFF/workspace_state.json). NFR04/NFR07/CT14/NFR08 vẫn OPEN trước full release. Bước tiếp theo chỉ do người dùng giao; không tự bắt đầu8B/8C.
