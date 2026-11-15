# Gap analysis và đề xuất Phase 8–10

Ngày 29/10/2026. Đây là phân tích source/hợp đồng, không triển khai hoặc nghiệm thu runtime mới. Git đầu lượt `main...origin/main`, HEAD `e4fb9f5` (sau `81ade59`), không tracked modifications/untracked do Git báo. Không suy diễn kết quả 415 pytest thành toàn bộ MVP hoàn tất. Không chạy suite, ghi DB, cài dependency, dọn dữ liệu hoặc thay baseline trong lượt này.

## Nguồn và cách đánh giá

Đã đối chiếu AGENTS; IMPLEMENTATION_PLAN/STATUS; PHASE7_IMPLEMENTATION/ACCEPTANCE/P7_A01_FIX; START_HERE, CODEX_HANDOFF; DOCX GĐ1 (BR, FR, UC, NFR), bảng truy vết/test case; DOCX GĐ2; approved decisions/config; API catalog/OpenAPI, schema, invariants, AD-04b, SM-03b/04; API/application/workers, simulator, các màn React và tests liên quan. QD approved được ưu tiên trước ghi chú chưa xác nhận trong handoff cũ.

“Hoàn thành” dưới đây nghĩa là chức năng trong MVP có source và bằng chứng kiểm thử đã được báo cáo/nghiệm thu; không phải chứng nhận phần cứng thật hoặc mọi NFR. “Một phần” gồm cả backend có nhưng UI/hay nhánh nghiệp vụ bắt buộc còn thiếu. Test được dẫn là bằng chứng source và kết quả lịch sử, không phải đã chạy mới ở lượt phân tích này. Nhãn phase thực tế 1–7 khác nhóm handoff; F1–F7 và FR/UC/BR/TC gốc giữ nguyên.

## Đối chiếu toàn bộ FR

Đường dẫn trong bảng tính từ root workspace. Các tests nằm trong `tests/`, API/application trong `services/backend/app/`, UI trong `apps/web/src/`.

| FR / TC gốc | Trạng thái | Source/test cụ thể và khoảng trống |
|---|---|---|
| FR01 / TC01 đăng nhập/quyền | Hoàn thành phần auth/RBAC; audit read thiếu riêng | main.py, application/identity.py; test_phase1::test_TC01_login_me_roles_no_secret, test_TC01_rate_limit_concurrent_process_sessions; audit GET thuộc API catalog FR01/18 chưa có |
| FR02 / TC02 tài khoản | Hoàn thành | main.py account/assignment routes, main.tsx; test_phase1::test_TC02_create_replay_conflict_and_pagination; có khóa/revoke/session và bảo toàn lịch sử |
| FR03 / TC03 trạm/thiết bị | Hoàn thành | api/assets.py, application/assets.py, Stations.tsx; test_phase2::test_TC03_station_device_crud_idempotency, test_TC03_scope_auth_and_not_found |
| FR04 / TC04 ngăn | Hoàn thành | assets.py, Stations.tsx; test_phase2::test_TC04_active_transaction_guards_and_device_review, test_TC04_create_maintenance_separate_door_and_terminal |
| FR05 / TC05 pin khả dụng | Hoàn thành | assets.py availability, domain/bms.py; test_phase2::test_TC05_supply_guards, test_TC05_latest_bad_sample_never_falls_back; ordering P4/P5 regression |
| FR06 / TC06 hồ sơ/vị trí pin | Hoàn thành cho luồng thường | application/batteries.py, swaps.py, Batteries.tsx; test_phase3 và test_phase7::test_TC11_full_custody_and_replay. Quyền giữ pin trong bù trừ chưa hoàn tất, tính ở FR12/16 |
| FR07 / TC07 BMS | Hoàn thành | domain/bms.py, workers/device.py, Batteries.tsx; test_phase3::test_TC07_seed_repeat_preserves_samples_and_no_proof; test_phase4_bms_ordering.py; không coi seed là verified |
| FR08 / TC08 cách ly/phục hồi | Hoàn thành | application/batteries.py::action, Batteries.tsx; test_phase3::test_TC08_quarantine_restore_atomic_alerts, test_TC08_restore_fails_closed_and_rolls_back; đúng Technician/trạm |
| FR09 / TC09 QR/RFID | Hoàn thành MVP mô phỏng | api/reservations.py, application/reservations.py, simulators/device/authenticate.py, Reservations.tsx; test_phase5.py QR replay/concurrency/revocation. Full Browser QR→reserve→consent chưa nghiệm thu |
| FR10 / TC10 giữ tài nguyên | Hoàn thành | reservations.py, swaps.py; test_phase5.py, test_phase5_acceptance.py, test_phase5_door_ordering.py; giữ pin+hai ngăn nguyên tử |
| FR11 / TC11 trả/cấp | Hoàn thành trong phạm vi nghiệm thu P7 | swaps.py, workers/device.py, SwapProgress.tsx; test_phase7::test_TC11_full_custody_and_replay; test_phase7_acceptance.py, test_phase7_deadline.py; 60s decision guard/freshness15 độc lập |
| FR12 / TC12 gián đoạn | Một phần — ưu tiên cao | swaps.py::review, payments.py::review, device worker tạo case/giữ holds; test_phase7::test_wrong_return_reviews_without_custody; test_phase7_postfix_acceptance::test_return_custody_survives_missing_pickup_and_reservation_expiry. Thiếu recovery read/evidence/settle, phân giải custody và đóng case có chứng cứ |
| FR13 / TC13 lịch sử | Hoàn thành API/UI cơ bản | api/reservations.py list/get, api/payments.py get, Reservations.tsx/Payment.tsx; test_phase5::test_TC13_roles_ownership_and_no_device_key_in_user_api. Chưa có lịch sử refund vì FR16 thiếu; không yêu cầu tự thêm export/lọc nâng cao |
| FR14 / TC14 thu phí | Hoàn thành phần charge | application/payments.py, workers/payment.py, simulators/payment/main.py, Payment.tsx; test_phase6::test_TC14_consent_intent_quote_and_outbox_atomic; P6 blocker regressions |
| FR15 / TC15 đối soát khoản thu | Hoàn thành phần charge | payments.py::reconcile, worker/query, Payment.tsx; test_phase6::test_TC15_timeout_query_lost_response_and_ten_duplicates, test_pending_timeout_reconcile_version_and_query_only. Không gộp recovery tài sản vào charge reconciliation |
| FR16 / TC16 hoàn phí | Chưa triển khai workflow | Có bảng refunds/enum/contract nhưng không API/service/provider refund/UI/test TC16. payments.py::receive hiện từ chối refund_id bằng INVALID_ACTION; không coi schema sẵn là đã làm |
| FR17 / TC17 IoT/lệnh | Hoàn thành giao tiếp MVP | api/device.py, application/device.py, workers/device.py, simulators/device/main.py; test_phase4::test_TC17_inbox_commits_before_worker_and_duplicate_receipts; test_phase7/ordering/deadline. Recovery interpretation sau reconnect còn thuộc FR12 |
| FR18 / TC18 giám sát | Một phần | api/device.py::dashboard, Devices.tsx có online/offline/open alerts/review/as_of; test_phase4::test_TC18_dashboard_scopes_online_offline_maintenance_and_review. GET /v1/audit-events và UI audit chưa có; chưa có đường mở/xử lý case từ dashboard |
| FR19 / TC19 cảnh báo | Hoàn thành luồng hiện có | device worker alert/dedup/quarantine; api/device.py ack/resolve; Devices.tsx; test_phase4::test_TC19_fault_quarantines_and_good_data_never_restores, test_TC19_alert_scope_resolve_does_not_restore_lifecycle. ACK không restore; không cần xây lại alerts engine |

Không FR01–19 nào được loại khỏi MVP. Một phần FR01 được nêu riêng theo catalog audit; auth hoàn thành không đồng nghĩa đã có giao diện nhật ký.

## Đối chiếu UC01–17

| UC gốc | Trạng thái | Bằng chứng/thiếu (tham chiếu bảng FR cho test cụ thể) |
|---|---|---|
| UC01 đăng nhập | Hoàn thành | identity/main + TC01 |
| UC02 tài khoản/quyền | Một phần hợp đồng mở rộng | account/assignment TC02 có; audit read theo api-catalog FR01/UC02 thiếu |
| UC03 trạm/thiết bị | Hoàn thành | assets/Stations + TC03 |
| UC04 ngăn | Hoàn thành | assets/Stations + TC04 |
| UC05 tra cứu trạm có pin | Hoàn thành | public station projection + TC05 |
| UC06 hồ sơ pin | Hoàn thành | batteries + TC06 và custody TC11 |
| UC07 BMS | Hoàn thành | telemetry/worker/Batteries + TC07, P4 ordering |
| UC08 phục hồi pin | Hoàn thành | technician actions/atomic resolve + TC08 |
| UC09 QR/RFID | Hoàn thành MVP | reservations/device adapter + TC09 |
| UC10 thực hiện đổi pin | Một phần toàn use case | reserve/normal custody/cancel/review có; recovery/compensation nhánh ngoại lệ thiếu, TC10–12 chưa đóng toàn bộ |
| UC11 lịch sử | Hoàn thành cơ bản | list/get swap và payment, ownership TC13; thêm refund view khi UC14 có |
| UC12 thu phí | Hoàn thành | consent/intent/outbox/provider/callback TC14 |
| UC13 đối soát thanh toán | Hoàn thành charge | reconcile/query TC15; không đổi mã này để gọi refund |
| UC14 hoàn phí | Chưa triển khai | thiếu TC16 và refund APIs/worker/provider |
| UC15 đồng bộ thiết bị | Hoàn thành MVP | event/poll/boot/seq/ledger TC17 |
| UC16 giám sát vận hành | Một phần | dashboard có TC18, audit read/recovery drilldown thiếu |
| UC17 xử lý cảnh báo | Hoàn thành phần hiện có | ack/resolve/restore tách biệt, TC19 |

## Đối chiếu BR01–12

| BR | Trạng thái | Bằng chứng và phần thiếu |
|---|---|---|
| BR01 một active swap/exclusive holds | Hoàn thành cho workflow đã có | reservations.py, unique indexes; test_phase5 concurrency/acceptance; nhánh release mới phải kiểm lại |
| BR02 pin đủ điều kiện | Hoàn thành | assets/domain bms + P3/P4/P5 ordering, P6 freshness, P7 guard |
| BR03 QR/RFID | Hoàn thành | token hash/consumption transaction + test_phase5 |
| BR04 thứ tự thu/trả/cấp | Hoàn thành luồng chuẩn | payments/swaps + test_phase6/7; payment success tách custody |
| BR05 pin trả đúng, sai pin xử lý kỹ thuật | Một phần | chặn sai pin/review có; xử lý kỹ thuật/custody sau case chưa có |
| BR06 dedup lệnh/ACK khác physical | Hoàn thành | device worker/simulator ledger + test_phase4/7 và E2E; không suy ra manual recovery đã làm |
| BR07 UNKNOWN không thu lại | Hoàn thành charge | worker payment/provider ledger + TC15/P6 fixes; refund UNKNOWN còn thiếu |
| BR08 hoàn phí và pin cũ độc lập | Chưa triển khai trọn quy tắc | chỉ tạo case/giữ holds; chưa full refund và old_pin_settled có chứng cứ |
| BR09 không rõ đã giao giữ review | Một phần | nhánh fail closed có tests missing pickup/P7; thiếu luồng nhân sự xác minh và kết thúc |
| BR10 cảnh báo chặn, Technician restore | Hoàn thành | alerts/batteries actions + TC08/19; Admin không kế thừa Technician |
| BR11 online/fresh, mất mạng dừng | Hoàn thành bảo vệ hiện có | workers/device.py, assets, test_TC18_offline_reconnect_requires_snapshot_and_does_not_restore, ordering; giải quyết sau offline còn FR12 |
| BR12 giữ lịch sử, không sửa tay | Hoàn thành workflow hiện có | retirement/actions, grants audit append-only, version/audit; không cho human set state. Nhánh mới phải kế thừa |

## Gap theo mức độ ưu tiên

1. **G1 bắt buộc, cao nhất: recovery + refund + compensation**. Hiện case chỉ là đầu vào, không có lối nghiệp vụ giải quyết chắc chắn. Giữ holds vô hạn là an toàn khi chưa rõ nhưng chưa hoàn thành UC10/14. Đây là khoảng trống đã dự kiến cho phase sau, không phủ định kết quả nghiệm thu an toàn Phase7.
2. **G2 bắt buộc: audit read và hoàn thiện UI vận hành**. Audit đã ghi và grants bảo vệ nhưng chưa có endpoint audit hoặc màn đọc; dashboard/alerts/Technician restore đã có, cần nối case và tài chính. Customer phải thấy charge và refund riêng.
3. **G3 bắt buộc nghiệm thu: NFR/restore/triển khai tái lập và Browser còn thiếu**. Có regression/E2E không thay đo tải, backup/restore DB+ledgers và 3 người dùng thử.

Chi tiết FR18: response dashboard hiện chỉ có online_stations,offline_stations,open_alerts,review_swaps,as_of; trạng thái bảo trì xem ở trạm/ngăn, không phải chỉ số riêng trên summary. TC18 baseline còn yêu cầu danh sách phiên cần xử lý; hiện summary đếm review, Admin có listSwaps nhưng Technician không được đọc lịch sử khách. Cần nối UI với recovery theo hợp đồng và giữ giới hạn dữ liệu kỹ thuật, không tự thêm API list case hoặc quyền đọc swap cho Technician. Nếu Dashboard schema hiện không hỗ trợ trường cần thêm, trình phương án hợp đồng trước khi triển khai, không âm thầm thêm field/count. Đây là phần FR18 còn thiếu, không được coi test summary đã thay thế đủ TC18 đầu–cuối.

Đối chiếu operation_id source với api-catalog và kiểm tra OpenAPI cho các nhóm thiếu: 9 operation chưa có gồm getRecovery, recordRecoveryEvidence, settleRecovery; requestRefund,getRefund,reconcileRefund; providerRefund,providerQueryRefund; audit. Đây là kiểm tra cấu trúc, không chứng minh các operation còn lại khớp mọi response/guard. Chưa gọi live API để phân biệt404/405 ở lượt này.

Schema nền đã có recovery_cases (new_pin_delivered YES/NO/UNKNOWN, old_pin_settled, evidence/version), refunds UNIQUE payment/provider_key, payment_events.refund_id, outbox, audit. Runtime grants hiện chỉ INSERT recovery_cases, chưa đủ cập nhật recovery/refunds. Không tạo bảng trùng hoặc chạy lại DDL; xác minh Alembic/live schema/grants trên DB test khi bắt đầu triển khai, chỉ migration nếu thiếu thật.

## Giới hạn MVP được chấp thuận

QD01/02:2×6, một họ pin mạng lưới, khách có pin ban đầu; QD03:thu trước9.000VND/mock; QD04:sai pin giữ review/kỹ thuật; QD05:QR một lần/RFID mô phỏng/tài khoản cấp sẵn; QD06:Admin/Technician độc lập; QD07:ngưỡng demo80/80/40 và TTL approved; QD08:kế hoạch5người/10tuần; QD09:duyệt FR/UC/BR cho mô phỏng. Không mở thêm chu kỳ10tuần hoặc coi thời gian thực đã đo bằng ước lượng gốc.

FULL_ADMIN_REVIEWED refund và xử lý quyền giữ pin **vẫn thuộc Must MVP**, không được loại vì chỉ là mô phỏng. Ngoài MVP: tiền thật/phần cứng thật, ví/gói thuê bao/đặt cọc, pin riêng/đa hãng, remote booking, AI/định tuyến, app mobile riêng, hóa đơn tài chính thật. Bản đồ/lọc nâng cao là Should, không ưu tiên trước G1–3. Mobile web cơ bản không đồng nghĩa phải xây native app.

## Đề xuất Phase8 — khép kín recovery, refund và compensation

**Mục tiêu:** giải quyết phiên lỗi bằng bằng chứng và đúng thẩm quyền, không thu/hoàn/giao pin hai lần. FR12/16 chủ đạo; liên quan FR11/13–15/17–19; UC10/11/13/14/15/16/17; BR01/02/04–12. Giữ TC12/16 và CT07/08/13, không đổi chúng theo số phase.

Chia thành các lát trong cùng phase, chưa coi xong Phase8 chỉ vì refund gửi thành công:

- **8A Recovery evidence/read/settle:** GET /v1/swaps/{id}/recovery; POST /recovery/evidence; POST /recovery/settle. Technician đúng trạm thu thập snapshot/ledger, Backend suy ra kết luận; client chỉ gửi expected_version/evidence_event_id/note hoặc resolution_note theo OpenAPI, không tự nhập YES/NO,old_pin_settled,state hay vị trí pin. Tái sử dụng inbox/boot/order/evidence và khóa hiện có. Nhánh đã phát OPEN_SUPPLY chưa rõ không mở/cấp lại; nhánh chưa phát chỉ tiếp tục khi SM-03b và đủ interlock cho phép.
- **8B Refund mock:** POST/GET /v1/payments/{id}/refund, POST /v1/refunds/{id}/reconcile; hai provider endpoints /mock/v1/refunds. Một full refund intent mỗi payment, amount/currency từ DB, Admin-only request/reconcile. Refund worker/outbox/callback inbox xác minh refund identity, original charge/reference, key,amount,currency; ledger provider bền vững và query đúng loại. UNKNOWN chỉ query, FAILED retry cùng intent chỉ khi provider cho phép/xác nhận chưa hoàn. Payment vẫn SUCCEEDED sau hoàn.
- **8C Close compensation/UI:** COMPENSATING→CLOSED_COMPENSATED chỉ khi refund SUCCEEDED và pin cũ giải quyết có chứng cứ; release3holds và audit nguyên tử. Nếu chưa nhận pin cũ phải xác minh khách còn giữ đúng pin. Nếu xác minh đã giao pin mới, chỉ COMPLETED khi đủ cả hai custody+charge; không tự refund. Customer xem refund của mình, Admin yêu cầu/đối soát tiền, Technician thao tác evidence/settle đúng trạm. Không nút force-complete/force-release/unlock.

**Dependencies:** Phase1–7 và P6-A01–03/P7-A01; schema/grants hiện có; SM-03b/04, AD-04b, INVARIANTS6–8. Không giữ khóa khi chờ HTTP/người; thiết kế chung station/user/resource rồi swap/payment/refund theo thứ tự tương thích hiện tại, kiểm tra toàn call graph để tránh đảo khóa. Không chỉ áp thứ tự refund cục bộ bỏ qua worker dùng station lock.

**Database/API/UI:** ưu tiên bảng/enum có sẵn; cập nhật grants tối thiểu; không hứa không migration trước khi kiểm tra schema thật. Refund provider cần bổ sung durable refund ledger/uniqueness, tách charge/refund key và query. Mở rộng payment callback hiện từ chối refund_id bằng nhánh được kiểm tra đúng hợp đồng, không làm yếu guards charge. Recovery UI mới tích hợp Reservations/Payment/Devices; không xây lại login hoặc dashboard engine.

**Điểm cần làm rõ trước lát phụ thuộc:** OpenAPI evidence/settle chỉ nhận một evidence_event_id và ghi chú; không có API manual unlock hoặc payload tùy ý sửa custody. Thiết kế yêu cầu trả/quyết toán pin cũ nhưng chưa đủ căn cứ trong API để tự tạo hành động vật lý hay chính sách chuyển quyền sở hữu mới. Phải đặc tả trong tài liệu triển khai cách Backend đối chiếu chuỗi event/ledger và bằng chứng xử lý pin cũ theo schema hiện có; nếu không biểu diễn được hợp lệ, dừng nhánh đó để người dùng duyệt bổ sung hợp đồng, không fake evidence/UPDATE tay. Không để nhánh này lại phase xa hơn rồi tuyên bố UC14 hoàn tất.

**Acceptance Criteria:** TC12/16 và CT07/08/13 đạt cả nhánh chưa nhận pin cũ/đã nhận/chưa rõ pickup/đã giao; người sai quyền/trạm và evidence stale/replay/mismatch bị chặn; refund không vượt charge; duplicate callback không đổi kết quả cuối; refund SUCCEEDED không release trước custody settlement; ledger/inbox/audit/release rollback đúng; không lệnh còn có thể tác động khi kết luận chưa giao để hoàn. Source/contract/schema validations, full regression và Browser ba vai trò có bằng chứng. Chưa đủ evidence thì giữ review, không đoán NO.

**PostgreSQL concurrency bắt buộc:** hai Admin refund khác key/hai process; refund cạnh tranh closing pickup event; recovery evidence cạnh tranh telemetry/boot mới; settle cạnh tranh callback/refund worker/timeout; hai Technician settle/version conflict; rollback sau writes pin/refund/holds/audit. Kiểm DB trước/sau và số intent/holds/audit, không chỉ HTTP. Không khóa riêng in-memory.

**Real-process E2E:** Backend2process+worker+provider+2simulators/test schema: đã thu/chưa trả→refund; đã trả/chưa pickup→refund trước settlement vẫn giữ3holds rồi settlement mới đóng; pickup UNKNOWN→không hoàn/cấp lại; xác minh delivery→complete đúng; provider đã hoàn nhưng mất response→restart/query cùng key/1refund; callback trùng/sai identity/receipt conflict; crash sau ledger/trước DB và sau DB/trước ACK. Không dùng trạng thái vật lý giả để vượt deadline P7-A01. Recovery sau deadline phải là luồng đối soát có thẩm quyền và bằng chứng theo SM-03b, không nới deadline luồng thường.

**Rủi ro cao:** snapshot vắng pin không tự chứng minh ai nhận pin; replay bằng chứng cũ để refund; charge/refund reference collision; hai worker double refund; deadlock; callback cuối trái thứ tự; user/assignment bị thu hồi; tiền đã hoàn nhưng pin cũ chưa giải quyết. Giữ P6 savepoint/receipt rejection/inbox atomicity, freshness decision guard, 55P03 bounded recovery và P7 decision deadline trong regression bắt buộc.

## Đề xuất Phase9 — audit, hoàn thiện vận hành và UI nghiệm thu

Mục tiêu khép G2, không thêm business mới: FR01/12/13/16/18/19, UC02/10/11/14/16/17, BR08–12. Phụ thuộc8A–C.

- API GET /v1/audit-events theo contract: Admin toàn mạng, Technician chỉ xử lý của mình; redact, paginate và ownership; không trả private payload/token. DB dùng audit hiện có, chỉ thêm index/grants nếu đo và thực sự thiếu.
- UI liên kết review trên dashboard với recovery case, charge/refund và audit đúng quyền; giữ freshness/as_of/offline và phân biệt service_state/cửa; hoàn thiện lịch sử tài chính từ hai bảng. Không cho Technician lịch sử Customer toàn mạng hoặc Admin phục hồi pin.
- Hoàn tất Browser QR→adapter verification→reserve→consent→swap; thông báo sai pin trước offline; mobile/accessibility cơ bản/loading/error/forbidden. Không nhúng Device-Key vào bundle để tiện Browser.

AC: TC13/18/19 + scope/role/audit mới đạt, full Browser luồng thường/lỗi ba vai trò, stale không hiển thị live, audit không tiết lộ credential. PG concurrent pagination/state changes và authorization sau revoke; E2E recovery/alerts/dashboard cuối cùng sau Phase8. Rủi ro lộ dữ liệu/audit quá rộng, UI suy đoán thành công, bỏ mất lý do lỗi ban đầu; dùng lịch sử evidence/audit thay vì ghi đè hoặc xóa kết luận cũ.

## Đề xuất Phase10 — NFR, backup/restore và bàn giao MVP

Mục tiêu G3: áp dụng xuyên FR01–19/UC01–17/BR01–12 và TC01–19/CT01–14, không thêm feature ngoài MVP. Phụ thuộc8/9 ổn định.

| NFR | Hiện trạng và nghiệm thu còn cần |
|---|---|
| NFR01 quyền | Test role/scope nhiều nhóm có; cần matrix cuối bao gồm recovery/refund/audit |
| NFR02 xác thực | QR120/login5/900 approved và đã test; hồi quy session/revoke/replay cuối |
| NFR03 nhất quán | Phase1–7 có PG/E2E; thêm refund/settle và CT13 mới đủ |
| NFR04 hiệu năng | Chưa có bằng chứng load test: đo p95 đọc≤2s,20phiên đồng thời,1000request sau warm-up,ghi cấu hình máy/dữ liệu/endpoint; đây là tiêu chí baseline, không tự đổi SLA |
| NFR05 freshness | Guard/order/timeouts có test; đo trễ event→UI dưới tải và recovery, không thay measurement time bằng heartbeat |
| NFR06 quan sát | Audit/log/correlation có nền; cần kiểm coverage mọi mutation, endpoint read/redaction và báo cáo thiếu trước-sau nếu có |
| NFR07 khôi phục | Process restart có; backup/restore DB+device/payment/refund ledgers CT14 chưa chứng minh |
| NFR08 sử dụng | UI đã kiểm một phần; cần3người chạy kịch bản đúng không sửa DB tay |
| NFR09 bảo trì/test | Tách provider/simulator và tests có; đóng traceability TC/CT cuối, review độc lập và mọi FR có evidence |
| NFR10 an toàn mô phỏng | Guard đã có; hồi quy recovery/refund không bypass và thông báo simulation |

DB/API/UI: không dự kiến business schema/API mới; scripts backup/restore/runbook, health/process supervision và trạng thái vận hành phù hợp contract. Compose hiện chỉ có PostgreSQL; Backend/workers/provider/simulator/frontend chạy bằng tooling dev, chưa phải deployment tái lập trọn stack. Chọn đóng gói MVP local theo ARCH-01, không tự thêm broker/Kubernetes/cloud/public exposure. HTTPS ngoài local và thời hạn retention chưa có quyết định đầy đủ: ghi cần duyệt khi triển khai tương ứng, không tự purge audit/idempotency/ledger (approved idempotency retention72h không tự cho phép xóa bằng chứng).

Restore thử ở database/volume/ledger test riêng, cần kế hoạch dung lượng và quyền tạo tài nguyên; không đè volume hiện tại. Snapshot backup nhất quán DB+ledgers, manifest/hash/revision, xác minh audit/idempotency/custody/holds và không thực thi lại command/refund sau restore. PG concurrency trong lúc drain/backup/restart; real-process CT14 sau restore và charge/refund UNKNOWN tiếp tục cùng key. AC: báo cáo NFR có số đo, TC/CT đầy đủ, restore drill, hướng dẫn startup/shutdown/worker retry exhaustion không mất dữ liệu, báo cáo giới hạn Browser cuối. Không lấy backup DB đơn lẻ làm CT14 Passed.

## Kết luận và thứ tự triển khai đề nghị

**Phase8 nên làm recovery evidence/settlement trước, tiếp đến full refund mock và đóng compensation có UI tối thiểu.** Xác minh chắc chắn chưa giao pin mới là dependency của refund; một nút hoàn phí riêng không thể giải quyết custody hay release holds. Đóng cả8A–C mới nghiệm thu phase này.

Phase9 dành audit read, nối dashboard/lịch sử/UI vận hành và bù Browser gaps; Phase10 dành performance/restore/NFR/deployment/bàn giao. Đây là chia nhỏ khối lượng Must còn lại của kế hoạch cũ, không thay phạm vi hay mã yêu cầu. Không đẩy an toàn tài sản/tiền sang một phase tùy chọn. Chưa cho phép bắt đầu code bởi báo cáo này; không commit/push/dọn dữ liệu. Chỉ tạo tài liệu gap analysis, không sửa source/baseline/IMPLEMENTATION_STATUS.
