# Phase 8A — Independent Acceptance

**Liên kết Round 2 (15/11/2026):** [PHASE8A_INDEPENDENT_ACCEPTANCE_R2.md](PHASE8A_INDEPENDENT_ACCEPTANCE_R2.md) đóng P8A-IA01 trong technical scope sau fix/regression, đồng thời ghi audit/NFR gaps còn mở. Nội dung và kết luận R1 bên dưới được giữ nguyên như lịch sử trước sửa, không đổi thành PASS.

Ngày review: 14/11/2026. HEAD **e4fb9f5**, main, working tree Phase 8A chưa commit. Đây là review source/evidence và probe bổ sung, không triển khai hoặc sửa production. Người review đã tham gia các lượt triển khai trước; tính độc lập ở đây là phương pháp expected-from-contract/probe mới, **không phải một tổ chức/người kiểm toán bên ngoài**.

## 1. Executive summary / decision

**PARTIAL/BLOCKED — chưa đề xuất nghiệm thu toàn Phase 8A.**

Đã xác minh full regression 587, Browser 15 và frontend 39 là bằng chứng thật theo snapshot phù hợp. Tuy nhiên probe mới trên PostgreSQL và simulator restart tái hiện **P8A-IA01 — Major: Technician ghi accepted PRE proof từ receipt boot cũ trong khi Customer/projection đã chặn cùng receipt**. Hai lượt độc lập đều trả Technician 200 thay vì refusal, tăng version, thêm attestation append-only. Không sửa expected/skip/xfail. Không chứng minh được authorization/custody bypass: downstream guard vẫn kiểm boot; protected battery/Payment/hold facts không đổi trong probe.

NFR tải và backup/restore đồng bộ vẫn thiếu số đo/drill theo baseline; kế hoạch dời Phase10 không phải bằng chứng đã đạt hoặc waiver đã được duyệt. Finding mới đủ ngăn PASS; việc phân bổ các NFR trước release phải được xác nhận rõ, không tự miễn yêu cầu.

## 2. Scope và nguồn yêu cầu

Đã đọc AGENTS, kế hoạch/trạng thái/báo cáo 8A và Browser manual; CODEX_START_HERE/handoff, QD approved/config; GD1/GD2 DOCX qua XML paragraphs, traceability.csv, INVARIANTS, AD-04b/SM-03b, API/overlay 0.1/0.2 và migrations 0003–0008. [Trích yêu cầu gốc dùng review](PHASE8A_TESTS/independent_evidence_20261114_01/baseline_excerpts.json).

8A gồm getRecovery/evidence/confirmation/settlement, authorized service, successor và durable closure. FR16/UC14/BR08/refund/outbox hoàn, CLOSED_COMPENSATED và compensation finalizer thuộc 8B/8C, không ghi TC12/CT07/08 toàn dự án hoàn thành chỉ từ 8A. Không đổi FR/UC/BR/QD, không thêm tài chính thật hoặc manual unlock.

## 3. Traceability

| Requirement | Implementation được review | Tests/evidence | Acceptance status |
|---|---|---|---|
| FR12 / UC10 / TC12 (slice recovery) | application/recovery.py, api/recovery.py | test_phase8a_api/evidence/settlement; E2E A–F | Partial: có workflow/guards nhưng IA01 mở; refund/cancel sau thu không thuộc slice này |
| BR05 sai pin/nguồn gốc | purpose RETURN_FOREIGN_OBJECT, recovery_settlement.py; simulator actual model | E/K/J + canonical Browser post, wrong-stage/reference | Custody không gán vật lạ vào mạng; proof PRE sau boot mới còn Major |
| BR09 UNKNOWN không suy delivery | quiet(), reconciliation/closure; service ledger | C/F, UNKNOWN/PREPARED tests, operator U/S | Passed trong evidence tương ứng; không đồng nghĩa mọi receipt guard đã đúng |
| BR11 online/current evidence | current_snapshot(), authorization.guards, projection | ordering/freshness, race snapshot, IA01 | **Partial**: Customer/settlement chặn old boot, Tech PRE chưa chặn |
| BR12 lịch sử bất biến | trigger append-only, operation/context immutable, audit | migrations/stage_storage; PostgreSQL rollback probes | Positive evidence; accepted sai cũng không thể overwrite, tăng tác động IA01 |
| AD-04b / SM-03b | settle A/B/D/manual; staged foreign return giữ review | E2E A–F, ER-01/02, foreign settlement audits | Đúng tách charge/custody; không hoàn toàn SM-04/refund |
| Invariant 6 | giữ 3 holds khi UNKNOWN/review | DB/ledger audit 15 fixture Browser mới | Verified scope, không tự phát command mới |
| Invariant 7 | chuẩn bị new_pin_delivered/guard refund; chưa refund engine | no-refund guards trong settle | Chỉ phần đầu vào 8A; 8B chưa nghiệm thu |
| Invariant 8 | old_pin_settled chỉ bằng proof; không CLOSED_COMPENSATED tự động | A/B/D/E DB facts | Recovery slice có evidence; final compensation thuộc 8C |
| P8-REC-0.1 | legacy evidence/settle, session locks sorted UUID | settlement tests + revocation ordering probes | Chưa thấy lỗi mới ở nhánh đã review; không tái chạy toàn bộ |
| P8-REC-0.2 | inspection→intent/ACK→activation→receipt→human→settle | Browser post/terminal-label, E/K/J | **Partial do IA01**, không dùng Browser happy path thay boot-negative |
| ER-01 | successor read-only + history chain | real-process K 26, Browser successor | Verified scenarios; không cấp effect mới |
| ER-02 | NEVER_PREPARED witness + permanent denies + commit ACK | real-process J 20; Browser closure | Verified scenarios; không coi expiry/revocation riêng lẻ là no-effect |
| CT07/08 | old obligation/new delivery độc lập, UNKNOWN review | A/B/C/D; Payment/holds snapshots | 8A evidence đủ nhiều nhánh; money/refund portion vẫn Not Implemented trong 8A |

Các đường dẫn application tương đối với services/backend/app; test names nằm dưới tests/. Đây là ma trận evidence cụ thể, không phải formal proof mọi interleaving.

## 4. Independent source findings

### P8A-IA01 — Major: PRE Technician acceptance không nhất quán current boot

**Điều kiện tái hiện:** schema PostgreSQL riêng; fixture setup_inspection tạo actual wrong-return model/operation; simulator gửi readonly inspection được Backend accepted. Đóng/restart simulator cùng SQLite ledger (boot UUID mới), gửi snapshot thật và xử lý worker. Không UPDATE custody/proof/clock/timestamp. HTTP adapter dùng FastAPI TestClient + httpx MockTransport cho **transport**, model/ledger và PostgreSQL thật; đây không phải OS-process E2E.

Customer GET `/v1/swaps/{swap_id}` lúc đó trả projection `UNAVAILABLE`. Customer POST confirmations cùng binding trả **409 RECONCILIATION_REQUIRED**. Technician POST `/v1/swaps/{swap_id}/recovery/evidence` lại trả **200**, case version **2→3**, accepted sources **SIMULATOR, TECHNICIAN**. Replay cùng key/body cũng 200/cùng body, không ghi lời chứng thứ hai. Protected battery/Payment/resource facts giữ nguyên.

Payload không chứa secret:

```json
{"expected_version":2,"note":"Independent old boot refusal","statement":{
 "kind":"TECHNICIAN_ATTEST","operation_id":"<fixture operation>",
 "context_hash":"<accepted context hash>","stage":"PRE_ACTION_INSPECTION",
 "receipt_id":"<old-boot accepted inspection>","receipt_hash":"<accepted hash>",
 "actual_serial":"SIMULATED-WRONG-BATTERY","observation":"CONFIRM"}}
```

Expected: từ chối current PRE attestation dựa boot cũ (409/422), không thêm proof/version/success confirmation audit. Actual: accepted proof/version tăng dù API Customer xác định cùng nguồn không còn current.

**Root cause:** `recovery.py::confirmation` có PRE boot/device check trước gọi human; `recovery_authorization.py::human` (khoảng dòng 26–72) chỉ kiểm reference/stage/hash/actor/serial và proof age, không kiểm current device boot cho Technician PRE. `recovery.py::record` gọi thẳng human cho TECHNICIAN_ATTEST. `authorization.guards` có kiểm boot muộn hơn, nên lỗi hiện chứng minh **cổng nhận evidence/workflow**, không chứng minh mở cửa/custody sai. Không gọi đây là QR/Device-Key bypass hoặc double charge.

Severity Major: API append-only nhận proof không đủ điều kiện làm lời chứng PRE hiện hành, gây bất nhất quyền thực hiện workflow và audit/version; happy-path UI không phát hiện. Chặn downstream giúp hạn chế hậu quả nhưng không làm receipt acceptance đúng. Nếu muốn cho phép lời chứng lịch sử sau reboot, phải biểu diễn/định nghĩa rõ theo contract; hiện không có phân loại historical ở response này, không tự suy đó là ngoại lệ đã duyệt.

Probe: [test_phase8a_independent_acceptance.py](../tests/test_phase8a_independent_acceptance.py). [Run 01](PHASE8A_TESTS/independent_review_boot_20261114_01/results.xml), [run 02 có Customer/replay](PHASE8A_TESTS/independent_review_boot_20261114_02/results.xml); run.log cùng thư mục có boot IDs/status/version/facts, không có token/password. **Mỗi run 1 Failed, exit 1**; là một scenario tái hiện hai lần, không cộng thành hai yêu cầu khác nhau. Assertion gốc giữ nguyên, không sửa production.

Đề xuất sửa tối thiểu cho lượt riêng: dùng cùng current-boot/provenance guard cho hai actor PRE trong shared human path, dưới station/device locks; recheck sau lock wait; giữ POST history/successor semantics tách riêng. Rejected mutation phải rollback version/proof/audit và không cache thành successful receipt. Thêm Technician old-boot, Customer counterpart, healthy same-boot, logout/expiry wait và replay regressions. Không broaden quiet(), reset deadline hoặc sửa receipt cũ.

### Các kết luận source khác

- Device receive wrapper `recovery_inspection.receive` khóa station rồi re-read/lock device/key trước dispatch closure/inspection/ACK/post; vì thế nghi vấn stale device dependency ở closure được giảm bởi wrapper, không ghi thành finding chưa tái hiện.
- Settlement 0.1/0.2 gom caller/witness sessions khóa UUID, revalidate revoke/expiry/role/scope; station/user/resource locks serialize evidence và role/assignment. Không có network wait trong domain settlement. Giới hạn: audit/commit vẫn có thời gian sau final guard; policy là decision linearization dưới khóa, không tự diễn giải thành deadline tại WAL commit.
- Staged settlement so khớp intent/activation/ACK hashes, receipt chronology, actual serial/recipient, 3 sources, current snapshot, verified charge/refund absence và 3 holds. Không đổi old custody khi trả vật lạ. Historical proof không thay current snapshot.
- Simulator PREPARED commit trước effect, transaction local serialize effect/deny set; UNKNOWN không retry, closure ACK mới release station exclusivity. Restart/command cached-before-fence có regression. Không mở rộng kết luận sang mất/corrupt ledger hoặc coordinated restore chưa kiểm.
- Migrations 0003→0004→0005→0006→0007→0008 nối 0002, grants/append-only trigger/stage uniqueness hỗ trợ pipeline. Downgrade destructive fail-closed; không gọi đây là migration rollback đã chạy. Không chạy migration trên demo.
- UI fix ưu tiên Backend terminal status; closed()/requestFor và role guards giữ nguyên. Không thấy cần sửa nhãn thêm từ review này. OpenAPI appendix dùng allowlist schemas/6 routes và giữ baseline security/roles bên ngoài; không thấy generic unlock API.

## 5. Evidence validation độc lập

| Gate | Đã kiểm artifact | Kết luận / giới hạn |
|---|---|---|
| Full Backend run 03 | results.xml, run.log, full_source_resume/exits.json | Đủ **587 testcase**, 0 failure/error/skipped, exit 0; 587 collection node IDs khớp sau normalize riêng UUID params; không chạy full mới |
| Historical 493→587 | collection_normalized.json, source/grants metadata | 493 cũ +94 mới, removed=0; run 01 exit1/run02 interrupted không dùng làm Passed |
| Source | terminal_ui_fix/source_after.json, SHA256 actual | 257 file manifest khớp current lúc review; probe mới ngoài manifest được ghi riêng. Backend/migrations/overlay không đổi từ freeze; không có claim byte-identical frontend trước/sau UI fix |
| Browser sau UI fix | 15 terminal_fix_*_browser XML/exit.txt | **15 Passed, 0 Failed/Errors/Skipped**, mọi exit0; assertion terminal-label cũ có trong source, không skip/xfail |
| Frontend | frontend.log, build.log, exits.json | **39 Passed**, noEmit/Vite exit0; SSR unit không gọi là Browser |
| A–F / ER01/02 | final_source verified_summary + per-run reports/exits | A5+B restart7+CD8+E28+F8=56; J20+K26=46; tổng **102**, thay B6 bằng B7, không cộng cả hai |
| Final races | implementation race table + linked process JSON/PID/lock waits | 17 scenarios là evidence kế thừa của interleavings đã mô tả; không phải mọi proof/actor path đều covered (IA01 minh họa khoảng trống) |
| Operator E/K/J/U/S | five runner scopes và source snapshots | Positive/negative service evidence có giá trị tầng device/API, không Browser |
| Validators | validation_exits, runtime_schema_security | Exit0 contracts/deps/build; OpenAPI và 22 schemas đã kiểm; không chạy validators lặp vì source contract không đổi |
| DB/ledger | terminal_ui_fix/db_ledger_audit.json | 15 fixture read-only scope, đúng custody/hold/charge/effect; fingerprint **8 bảng**, không toàn DB |
| Probe mới | boot run01/run02 | **1 scenario Failed hai lượt**, 0 Passed mới; không gộp vào 587 hoặc Browser15 |

[Independent counts/source/exit validation](PHASE8A_TESTS/independent_evidence_20261114_01/verified.json), [collection comparison thực sự](PHASE8A_TESTS/independent_evidence_20261114_01/collection_validation.json), [E2E counting](PHASE8A_TESTS/independent_evidence_20261114_01/e2e_count_validation.json). Không có full pytest mới; current full suite bao gồm probe mới chưa được chạy toàn bộ, không gọi current full suite all-green.

## 6. Browser variants — independent assessment

| Variant | Assessment độc lập |
|---|---|
| Reboot/old-boot | **Chưa đủ evidence để đóng gate kỹ thuật**: existing E2E/Browsers không phát hiện IA01. Cần bổ sung/fix PRE Technician ở PG/API; Browser old-boot riêng Not Run. Không ép thử hàng chục Browser lỗi thiết bị khi core validation chưa đúng |
| UNKNOWN/PREPARED closure negative | Evidence tầng local ledger/operator J/U/S + PG là đúng tầng bắt buộc; Browser positive closure đã có. Browser negative variant Not Run, không tự đổi nhãn |
| Witness role/assignment races | PG barriers/two OS processes phù hợp linearization tốt hơn Browser timing; 17 probes và session revoke fix là evidence. Không cần bắt Browser tái tạo mọi race để chứng minh DB locking |
| Legacy 0.1 confirmation | API regression + frontend guard/backward-compatible request model có evidence; Browser riêng chưa có. Không thấy baseline bắt Browser cho mọi protocol; giữ regression compatibility bắt buộc, không dùng staged15 nói legacy Browser Passed |
| Settlement response-loss | J/K/E OS crash trước/sau commit và replay là evidence đúng crash window; Browser confirmation-response-loss và settlement replay không phải Browser drop-settlement-response. Variant sau Not Run |
| Full mobile staged | Không có nghiệp vụ mobile riêng trong baseline; responsive smoke đã có, full staged mobile là coverage mở rộng deferred. NFR usability 3 người không được thay bằng headless smoke |

Không có waiver yêu cầu business từ bảng này. Việc một lớp đã test không đủ để miễn guard của lớp khác (điển hình IA01); dừng nhánh phụ thuộc finding, không chạy thêm Browser/full suite để che nó.

## 7. NFR, security và vận hành

Baseline GD1 **NFR04**/handoff ACCEPTANCE nêu p95 đọc ≤2s, 20 phiên, 1000 request sau warm-up, quy mô 2×6. **Not Run/thiếu benchmark có hardware/dataset/percentiles/error rate**. NFR07/CT14 yêu cầu restart và backup/restore; restart có evidence nhưng **coordinated restore PostgreSQL + device/payment/service ledger chưa chứng minh**. Không thể thay restore drill bằng restart SQLite/worker. Đây là yêu cầu MVP cuối; gap analysis đề xuất Phase10 chưa đủ làm waiver. Nếu cần nghiệm thu 8A chức năng riêng, phải chốt phạm vi NFR bàn giao rõ với người dùng; report này không tự coi SLA/restore đạt.

NFR06 audit/correlation có source, append-only grants và rollback evidence; chưa có tổng kiểm kê 100% mutation trước–sau/alerting/supervision. Cần phân biệt audit trong DB với monitoring vận hành hoàn chỉnh. Không tự bổ sung purge/retention hoặc deployment production. NFR08 ba người dùng thực hiện kịch bản chưa chứng minh; manual smoke user-reported chỉ phạm vi cơ bản.

Security review: RBAC owner/assignment và guards server hiện hữu; .env/.local/.cache/node_modules/dist được gitignore, git ls-files không chứa các vùng đó. package-lock chỉ thêm Playwright dev tree, không production gateway. Raw HAR/trace bị tắt, credentials private local; scan trước 143 artifacts không có secret là bounded evidence, không chứng minh toàn repo không thể có secret. Danh sách untracked đã lưu và phân loại; trước commit phải scan lại staged contents/selected artifacts, không git add -A. Probe mới không in password/key/token hoặc đổi limiter.

## 8. Open findings / risks

| ID | Severity | Trạng thái |
|---|---|---|
| P8A-IA01 | **Major** | Reproduced twice, chưa sửa; cổng nhận Technician PRE old-boot không nhất quán |
| NFR04 / NFR07 / CT14 | Acceptance gaps, không phải production failure tái hiện | Load/restore chưa có evidence; cần chốt phase gate/hoàn tất trước release, không tự waiver |
| NFR06/08 | Coverage/operations gaps | Audit coverage/monitoring/usability chưa đầy đủ; báo cáo/plan cần bổ sung |
| Historical CONSUMED/EXPIRED | Minor **Fixed** | 39 frontend +15 Browser source mới; không mở lại do IA01 |

Không có Blocker double charge/custody được chứng minh trong lượt này. Không đồng nghĩa không tồn tại; chưa benchmark corruption/lost disk/power-loss toàn hệ thống hoặc restore mismatched snapshots. Historical 503 chưa đủ bằng chứng root cause vẫn giữ Unknown, không biến contention diagnostic thành giải thích chắc chắn.

## 9. Recommendations trước commit

**Chưa đề xuất commit tuyên bố hoàn tất 8A** khi Major mở. Sửa IA01 trong lượt được giao riêng, giữ failing tests/evidence, xác minh same-boot/old-boot/actors/replay/rollback, sau đó cập nhật acceptance. Không sửa nghiệp vụ trong lượt này.

Nhóm cần giữ cho commit sau: tất cả source Recovery Backend/domain/API/schema/contract composer; migration 0003–0008 và grants/config tích hợp; simulator service/fence/handover/reconciliation + integrations; Frontend Recovery/projection/main/styles cần thiết; package/lock/dev Playwright; tests Phase8A, độc lập mới, regression P6/P7 còn liên quan; runners điều phối/audit/fault chỉ test; overlays versioned 0.1/0.2 + ER approvals, design/implementation/manual/acceptance/status docs. Phải review từng diff tích lũy so HEAD, không chỉ tracked stat (đa số source 8A hiện untracked).

Chọn commit curated public evidence summary/manifests nhỏ nếu cần; log/XML/JSON intermediary/screenshot full batches giữ local, không bulk stage docs/PHASE8A_TESTS. Không commit .env, private.json, runtime SQLite/provider/device ledgers, profiles, binaries/cache/.vs/.local/.venv/node_modules/dist/DB volumes. `.cache` chứa cả dữ liệu không tái tạo được nên không đề xuất xóa toàn thư mục. Không xóa bất cứ file nào trong review.

## 10. Git / handoff

HEAD e4fb9f5/main, dirty tree tích lũy, index trống. [Inventory trước review](PHASE8A_TESTS/independent_evidence_20261114_01/git_inventory.txt). Lượt này chỉ thêm probe + evidence review + báo cáo độc lập và cập nhật status; không đổi production/migrations/contracts, không chạy migration/demo mutations hoặc dọn schema/ledger. Source manifest actual khớp tại validation; new probe nằm ngoài manifest cũ, không che điều đó.

**Decision: PARTIAL/BLOCKED.** Đề nghị người dùng xem xét Major và NFR gate allocation, không đề nghị chuyển sang 8B/8C hoặc chốt nghiệm thu toàn 8A. Dừng sau báo cáo; không stage/commit/push, không thực hiện sửa lỗi.
