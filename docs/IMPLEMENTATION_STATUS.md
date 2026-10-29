# Trạng thái triển khai hệ thống đổi pin thông minh

**29/10/2026 — Người dùng chốt nghiệm thu Phase7 PASS trong phạm vi đã kiểm chứng và yêu cầu commit riêng P7-A01 cùng bộ nghiệm thu độc lập.** Bằng chứng415pytest và các E2E được đối chiếu, không chạy lại khi source không đổi. Giữ hai giới hạn Browser: full QR→Reservation→Consent và thông báo sai pin trước DEVICE_OFFLINE chưa xác minh. Bộ bàn giao gồm source fix, regression/acceptance tests, runners và hướng dẫn tái hiện trong PHASE7_ACCEPTANCE.md; raw artifacts/ledger/credentials giữ local. Không push hoặc triển khai Phase8. Các đoạn chờ duyệt/không commit phía dưới là lịch sử của lượt trước.

**29/10/2026 — Đề xuất chốt nghiệm thu kỹ thuật Phase7: PASS trong phạm vi đã kiểm, không có Blocker/Major được xác nhận còn mở.** Full415/0/0/0 và E2E17, hai real-deadline return/pickup,2probes kế thừa có bằng chứng; không chạy lại full. Bổ sung E2E thiếu pickup4checks, restart đúng sau RETURN_ACCEPTED5checks đã Passed. Browser sau sửa đã thấy AWAITING_PICKUP/Payment riêng/timeout REVIEW_REQUIRED (ảnh lượt trước), COMPLETED có hai mốc custody (DOM chạy mới), Admin/Technician và mobile cơ bản. API trực tiếp7checksPassed, không dựa menu để chứng minh RBAC. Hai fixture phục hồi Browser chạy mới mỗi4checksPassed,exit0,demo không đổi. Một lần setup bị PostgreSQL recovery được giữ log riêng. Full Browser QR→reserve→consent và thông báo sai pin trước offline chưa xác minh, ghi Not Run; không coi mọi Browser scenario Passed. Source production không sửa thêm, không đổi policy decision-vs-commit, không commit/push/Phase8. Danh sách file cần giữ/đề xuất commit và ngoại lệ nghiệm thu: [PHASE7_ACCEPTANCE.md](PHASE7_ACCEPTANCE.md), mục cập nhật29/10. Các kết luận trước bên dưới là lịch sử.

**28/10/2026 — Nghiệm thu bổ sung sau P7-A01:** E2E đầy đủ Backend/worker/provider/hai simulator chạy mới17checksPassed (4scenarios);2probe độc lập mớiPassed về thiếu pickup+expiration và late callback sau COMPLETED. Full415, targeted40 và hai E2E deadline được kế thừa, không chạy lại. Không phát hiện Blocker/Major mới trong phạm vi kiểm; chưa chốt toàn bộ Phase7 vì Browser/mobile, E2E thiếu pickup và restart chính xác giữa hai bước cònNotRun. Lỗi serializeUUID trong lượt probe đầu được giữ bằng chứng, sửa harness không sửa expected result/source. Xem mục bổ sung trong PHASE7_ACCEPTANCE.md. Không commit/push/Phase8.

**28/10/2026 — P7-A01 đạt kiểm chứng bản sửa, sẵn sàng TIẾP TỤC nghiệm thu độc lập; chưa nghiệm thu toàn bộ Phase7.** Full mới `p7a01_full_03`:415Passed/0Failed/0Errors/0Skipped, exit0,910.56s; targeted40Passed và hai probe gốc Passed được kế thừa có log. E2E deadline trả pin Passed từ lượt trước; cấp pin chạy mới Passed:60.428641s, evidence tối đa7.228998s, REVIEW_REQUIRED/3holds/custody và Payment bảo toàn/no success audit/no extra command/demo fingerprint không đổi. Lượt full_01 bị ngắt thiếu XML; full_02 có24Passed/391setupErrors do Docker chưa chạy, giữ riêng bằng chứng. Validator/build/dependency Passed từ lượt sửa trước; Browser và E2E đầy đủ hai simulator sau sửa NotRun. Không sửa thêm source/test khi tiếp tục; không migration/dependency/timeout change, không commit/push/Phase8. Chi tiết [PHASE7_P7_A01_FIX.md](PHASE7_P7_A01_FIX.md). Trạng thái blocker trước sửa bên dưới là lịch sử, báo cáo nghiệm thu gốc được giữ nguyên.

**28/10/2026 — Nghiệm thu độc lập Phase7 CHƯA ĐẠT: P7-A01 Blocker.** Hai probe PostgreSQL deterministic tái hiện custody return/pickup vẫn chuyển sau deadline60s ở điểm quyết định;18 regression Phase7Passed,2probeFailed. E2E trì hoãn thật và phần còn lại của ma trận nghiệm thu chưa chạy. Không sửa source/commit. Xem [PHASE7_ACCEPTANCE.md](PHASE7_ACCEPTANCE.md); kết luận cổng triển khai bên dưới là lịch sử, không thay thế nghiệm thu độc lập.

**28/10/2026 — Phase7 đạt cổng kỹ thuật, sẵn sàng nghiệm thu độc lập.** Full XML393Passed/0Failed/0Errors/0Skipped =375Phase1–6+18Phase7; targeted22Passed; SwapE2E17checks; hồi quy chạy mới Payment12/receipt5/IoT8/Reservation8/HTTP28Passed. Validator/hash/dependencies/TypeScript/VitePassed. Browser thật trên fixture kiểm chờ trả/chờ lấy/hoàn tất/ACK-timeout-review và quyền menu Admin/Technician; full QR→consent bằng UI, mobile, thông báo riêng sai pin trước offline còn NotRun. Custody/inbox/audit nguyên tử, giữ tài nguyên khi review, timeout15/60s và freshness15s theo phê duyệt. Không migration/dependency mới; không sửa baseline/demo/ledger, không Phase8/push. Source/tests/runner/docs sẽ commit theo yêu cầu sau staged review. Xem [PHASE7_IMPLEMENTATION.md](PHASE7_IMPLEMENTATION.md) và tổng hợp/hash PHASE7_TESTS/FINAL_VERIFICATION.json. Các kết luận Phase6 trở về trước bên dưới là lịch sử.

Cập nhật: 26/10/2026 (Asia/Bangkok).

**Người dùng đã chấp thuận nghiệm thu bản sửa Phase6 trong phạm vi kỹ thuật đã kiểm chứng và yêu cầu tạo commit riêng.** P6-A01/A02/A03 đã đạt kiểm chứng; 375 pytest/0Failed, targeted12, E2E12/5/8/8 và HTTP28 Passed. Browser NotRun, giới hạn retry cạn vẫn được giữ rõ. Bản gốc P6-A02 và bằng chứng trước sửa được bảo toàn; ca regression hiện hành vẫn chạy hai thời điểm, không skip/xfail. Xem [bằng chứng chọn commit](PHASE6_FIX/COMMIT_EVIDENCE.md). Không tự push hoặc chuyển Phase7; các trạng thái chờ duyệt bên dưới là lịch sử.


**Bản sửa P6-A03 đã đạt kiểm chứng kỹ thuật; chờ người dùng nghiệm thu/duyệt commit.** Retry chỉ PostgreSQL55P03 ở ngoài tick sau rollback/close, tối đa3 lần với backoff1/2s; lỗi khác hoặc hết budget dừng có log, giữ inbox/outbox. Hai worker cùng schema tự phục hồi trong cùng process; timeout sau dispatch chỉ query cùng provider key. Kết quả chạy mới sau sửa: **375 pytest Passed/0 Failed**, targeted12Passed, Payment E2E12, receipt-conflict5, IoT8, Phase5 E2E8, HTTP28 Passed; validators/baseline/dependencies/TypeScript/Vite Passed. Không cộng targeted vào full. P6-A01/A02 không hồi quy, archive probe gốc/characterization và log lịch sử được giữ. Không còn blocker nghiệp vụ được xác nhận trong phạm vi đã kiểm; Browser NotRun, chưa thử tải dài hạn/supervisor/mọi crash boundary. Hết retry budget vẫn cần xử lý vận hành, không retry vô hạn. Đề xuất nghiệm thu bản sửa Phase6, chưa tự chuyển Phase7. Không commit/push hoặc xóa DB/ledger. Xem [PHASE6_BLOCKER_FIX.md](PHASE6_BLOCKER_FIX.md), mục10; kết luận trước sửa bên dưới là lịch sử.


**Nghiệm thu bổ sung Phase6: full pytest chạy mới 370 Passed/0 Failed, nhưng CHƯA đóng nghiệm thu vì P6-A03 (Major).** Theo yêu cầu mới, đã lưu nguyên probe P6-A02 lịch sử + SHA256 rồi chỉnh regression kiểm hai thời điểm: receipt sai → UNKNOWN; callback hợp lệ → SUCCEEDED đúng một lần. P6-A01/A02 đã đạt kiểm chứng. Full run gồm 332 regression cũ +13 acceptance +23 regression bản sửa +2 characterization timeout (không cộng targeted). Hai probe cùng schema tái hiện Payment/Device worker exit1 khi advisory-lock timeout5s; dữ liệu/inbox/3holds bảo toàn, Payment hoàn tất sau restart thủ công, nhưng chưa có tự phục hồi. Đây là lỗi khả dụng thực, không chỉ cross-suite contention; cần sửa và kiểm chứng recovery trước nghiệm thu đầy đủ. Targeted mới16Passed; timeout characterization2Passed. E2E/HTTP/validators/build kế thừa, Browser NotRun. Không sửa thêm source nghiệp vụ, không commit/push/Phase7. Chi tiết và bằng chứng mới: [PHASE6_BLOCKER_FIX.md](PHASE6_BLOCKER_FIX.md), mục9. Các kết luận 367/1 phía dưới là lịch sử.


**Bản sửa Phase 6 P6-A01/P6-A02 đã kiểm chứng hành vi, chưa commit; chưa tuyên bố nghiệm thu toàn bộ.** Freshness được kiểm lại tại điểm quyết định; receipt conflict bị từ chối bền vững, không làm nghẽn callback hợp lệ. Full pytest sau sửa **367 Passed, 1 Failed** (332 regression cũ đạt, acceptance gốc 12/1, regression mới 23 đạt). Failed duy nhất là assertion lịch sử P6-A02 sau callback hợp lệ, giữ nguyên theo chỉ đạo người dùng; không skip/xfail hoặc tính thành Passed. Payment E2E 12, receipt E2E 5, Phase 5 E2E tuần tự 8 và HTTP 28 Passed đã đối chiếu bằng chứng; resume chạy mới IoT E2E **8 Passed**. Validator/hash/dependency/build Passed từ lượt sửa trước; Browser Not Run. Lượt E2E chạy song song từng lỗi advisory-lock timeout do các schema dùng cùng station key; chạy tuần tự đạt, nhưng worker chưa tự phục hồi lock timeout là giới hạn vận hành cần review. Hai blocker đã được khắc phục trong phạm vi kiểm chứng; sẵn sàng nghiệm thu lại bản sửa, **chưa chuyển Phase 7**. Không sửa thêm source khi resume, không xóa bằng chứng/DB/ledger, không commit/push. Xem [PHASE6_BLOCKER_FIX.md](PHASE6_BLOCKER_FIX.md). Kết luận trước sửa bên dưới được giữ làm lịch sử.


**Nghiệm thu độc lập Phase6 tại `81a8acd`: CHƯA ĐẠT, chưa đủ điều kiện chuyển Phase7.** Xác nhận hai blocker chưa sửa: **P6-A01** dùng mốc freshness đã cũ khi Payment xử lý chậm, consent/settlement có thể cho qua evidence quá hạn; **P6-A02** receipt thuộc Payment khác làm callback worker IntegrityError lặp, hai subprocess restart đều exit1 và chặn callback hợp lệ phía sau. Kết quả trước gián đoạn được đối chiếu JUnit/log: regression332Passed/0Failed; probe10Passed/3Failed; Payment E2E12Passed; validators/buildPassed. Browser nghiệm thu mới NotRun. Ngày26/10 chỉ hoàn thiện review/báo cáo, không chạy lại test, không sửa nghiệp vụ, không commit/push/Phase7. Xem [PHASE6_ACCEPTANCE.md](PHASE6_ACCEPTANCE.md). Các số hoàn tất triển khai phía dưới là lịch sử, không thay thế kết luận nghiệm thu này.

**Phase6 F6 Mock Payment hoàn tất cổng kỹ thuật:332 pytest Passed/0Failed (270 hồi quy+62 F6),12 E2E Payment,8 E2E Phase5,8 E2E IoT và28 HTTP smoke Passed.** FR14/UC12/TC14, FR15/UC13/TC15: consent nguyên tử, một Payment intent/outbox, provider ledger bền vững, callback xác thực/idempotent, UNKNOWN chỉ query cùng key, recheck evidence trước AWAITING_RETURN. Validator/hash baseline/build/pip/npm Passed. Không migration cấu trúc/dependency mới, head0002; grants F6 đã cập nhật. Browser phần đọc ba vai trò Passed; ba nhóm thao tác Browser đầy đủ Not Run. Đủ điều kiện nghiệm thu độc lập, dừng trước Phase7; không push. Xem [PHASE6_IMPLEMENTATION.md](PHASE6_IMPLEMENTATION.md). Base29f4352 đã được commit/push trước Phase6; các đoạn Phase5/4 dưới đây là lịch sử.

**Bản sửa P5-A01 đã đạt kiểm chứng kỹ thuật, ở working tree, chưa commit/push.** Bốn failing probes đã Passed; toàn bộ pytest mới **270 Passed,0 Failed =227 hồi quy+18 acceptance+25 ordering**. E2E tiến trình thật Phase5 **8 Passed**, IoT **8 Passed**, HTTP **28 Passed**, validator/build Passed. Guard thời điểm quan sát qua boot chặn snapshot cũ/cùng timestamp; bảo vệ projection và cả ngăn nhận/cấp. Không migration, không sửa demo/baseline/ledger; Browser Not Run trong lượt sửa (nghiệm thu trước Blocked429). Phase5 đủ điều kiện kỹ thuật để người dùng nghiệm thu bản sửa và quyết định Phase6; chưa triển khai Phase6. Dữ liệu/reservation lịch sử bị phiên bản cũ tác động cần đối soát, không tự sửa/hủy. Xem [PHASE5_P5_A01_FIX.md](PHASE5_P5_A01_FIX.md). Kết luận CHƯA ĐẠT bên dưới được giữ làm lịch sử trước sửa.

**Nghiệm thu độc lập Phase5: CHƯA ĐẠT, chặn chuyển Phase6 (P5-A01).** HEAD8a29636; regression chạy lại227 Passed nhưng18 probe độc lập có14 Passed/4 Failed: snapshot cửa cũ/cùng timestamp với seq cao ghi đè OPEN thành CLOSED và cho reserve3tài nguyên. Resume đã xác nhận timestamp cũ hơn đúng1s cho cả ngăn nhận/cấp. E2E tiến trình thật8 Passed; Browser Blocked tại login429, không reset counters. Không sửa nghiệp vụ/commit/push. Xem [PHASE5_ACCEPTANCE.md](PHASE5_ACCEPTANCE.md); phần hoàn tất triển khai bên dưới giữ làm lịch sử, không thay kết luận nghiệm thu mới.

**Phase5 hoàn tất trong phạm vi QR/RFID và reservation trước thanh toán.** Base a18e64f đã commit/push được xác minh lúc bắt đầu; bản sửa BMS không còn là thay đổi rời. Regression mới **227 Passed =175 cũ+52 Phase5**, HTTP28, E2E Phase5 thật8 (TTL120s/worker restart), E2E IoT hồi quy8, build/contracts và Browser phần QR/giữ/hủy/RFID/role đều Passed như báo cáo. Không migration mới/seed lại/reset DB; grants Phase5 đã áp dụng. Clipboard OS/camera/full Browser scenarios không tuyên bố Passed; không có API per-QR revoke trong baseline. Chi tiết [PHASE5_IMPLEMENTATION.md](PHASE5_IMPLEMENTATION.md). Dừng trước Phase6; các đoạn Phase4/BMS bên dưới giữ làm lịch sử.

**Bản sửa P4-A01 ở working tree, chưa commit:** hai probe lỗi và toàn bộ bảy probe nghiệm thu đã Passed; 21 ca timestamp/sequence Passed. Regression sau sửa trước gián đoạn đã hoàn tất **175 Passed**; lượt tiếp tục chạy lại 2/7/21 ca và E2E tiến trình thật **8 Passed**, không sửa source/test/fixture. Mẫu SOC cũ bị EVENT_OUT_OF_ORDER, availability giữ false. Không migration, không sửa demo/baseline, chưa Phase5; chờ người dùng xem xét commit. Chi tiết [PHASE4_BMS_FIX.md](PHASE4_BMS_FIX.md). Ghi nhận Failed dưới đây được giữ làm lịch sử trước sửa.

**Nghiệm thu độc lập Phase 4 sau commit a8a1d48: chưa đủ điều kiện chuyển Phase 5.** Bộ cũ chạy lại 147 Passed; 7 probe mới có 5 Passed / 2 Failed cùng phát hiện P4-A01: telemetry measured_at cũ hơn nhưng seq tăng có thể thay mẫu SOC mới10 bằng mẫu cũ90 và làm X-Battery-Available false→true. E2E8, HTTP13+14+16, build/contracts và Browser đọc ba vai trò Passed phần đã kiểm. Không sửa nghiệp vụ; xem [PHASE4_ACCEPTANCE.md](PHASE4_ACCEPTANCE.md). Những dòng hoàn tất/bằng chứng bên dưới là trạng thái bàn giao trước nghiệm thu bổ sung, không phải kết luận mới.

**Phase 4 – IoT Simulator & Device Communication hoàn tất trong phạm vi đã giao; dừng trước Phase 5.** Phase 0–3 được kế thừa, không xây dựng lại. P0-01/02/03 giữ nguyên theo IMPLEMENTATION_DECISIONS.md.

## Tiến độ

| Phase | Trạng thái | Bằng chứng |
| --- | --- | --- |
| 0 Baseline/hợp đồng | Hoàn tất | 15 static checks ban đầu; validator chuẩn chạy bổ sung ở Phase 1 |
| 1 Nền tảng/định danh | Passed | 18 tests, build web, 5 HTTP smoke checks; bằng chứng bên dưới |
| 2 F2 Trạm/thiết bị/ngăn | Passed | 55 Passed / 0 Failed; build + 14 HTTP checks Passed; xem PHASE2_IMPLEMENTATION.md |
| 3 F3 Pin/BMS (phần còn lại của nhóm 2 handoff) | Passed trong phạm vi F3 | 103 tests Passed: 18 Phase 1 + 37 Phase 2 + 48 F3; build, 16 HTTP checks, UI đọc ba vai trò |
| 4 IoT/thiết bị/bằng chứng | Passed trong phạm vi giao tiếp | 147 tests = 103 hồi quy + 44 IoT; 8 E2E tiến trình thật; 13 HTTP checks local; GUI ACK trên schema test |
| 5 QR/RFID và reservation | Passed phạm vi đã giao | FR09/10, phần cancel/read FR12/13; 52 tests mới, tổng227; HTTP28, E2E8+IoT8; Browser phần đã mô tả |
| 6 Payment Mock | Not Run | Chưa triển khai |
| 7 Quy trình đổi pin | Not Run | Chưa triển khai |
| 8 Exception/Reconciliation | Not Run | Chưa triển khai quy trình đối soát tổng thể |
| Tích hợp/nghiệm thu toàn hệ thống | Not Run | Không suy ra từ kiểm thử từng module |

## Kết quả mới nhất: Phase 2 – F2

**Cập nhật Phase 4:** [PHASE4_IMPLEMENTATION.md](PHASE4_IMPLEMENTATION.md), PHASE4_TEST_RESULTS.xml, PHASE4_E2E_RESULTS.json, PHASE4_HTTP_SMOKE_RESULTS.json và PHASE4_UI_RESULTS.json. Snapshot/heartbeat/BMS, event inbox, command polling/ledger, timeout và cảnh báo đã kiểm. Không migration mới, head 0002_user_approval; chỉ thêm grants. Chưa có API tạo swap/payment/reservation hoặc chuyển custody. Năm probe nghiệm thu Phase 3 đã được người dùng dọn, không nằm trong 103 ca hồi quy hiện có. Bằng chứng Phase 4 không thay thế hay sửa baseline; các phần Phase 1–3 bên dưới là lịch sử.

**Cập nhật Phase 3:** xem [PHASE3_IMPLEMENTATION.md](PHASE3_IMPLEMENTATION.md), [JUnit](PHASE3_TEST_RESULTS.xml), [HTTP smoke](PHASE3_HTTP_SMOKE_RESULTS.json), [validator](PHASE3_CONTRACT_VALIDATION.json), [DB check](PHASE3_DATABASE_CHECK.json). Không có migration cấu trúc mới, head 0002_user_approval; seed thêm 10 mẫu BMS chưa xác minh, bảo toàn hồ sơ/vị trí có sẵn. TC06 chuyển custody qua quy trình đổi và TC07 nhận telemetry qua thiết bị vẫn Not Run ngoài phạm vi F3. Các bảng/mục Phase 1–2 dưới đây là lịch sử nghiệm thu; Phase 3 dùng số thứ tự theo yêu cầu mới, không sửa mã module trong handoff.

Chi tiết API, file, lệnh, kiểm thử và giới hạn: [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md). Bằng chứng: [JUnit](PHASE2_TEST_RESULTS.xml), [HTTP smoke](PHASE2_HTTP_SMOKE_RESULTS.json), [validator](PHASE2_CONTRACT_VALIDATION.json), [môi trường test](PHASE2_TEST_ENVIRONMENT.json), [dung lượng](PHASE2_DISK_USAGE.json). Không sửa baseline; migration giữ 0002_user_approval; không xóa/reset DB/volume. Các mục Phase 1 bên dưới giữ làm lịch sử, không dùng để suy ra phạm vi F2.

## Môi trường đã xác minh

| Công cụ | Phiên bản/kết quả |
| --- | --- |
| Windows/WSL | Windows 11 build 26300.9711; WSL 3.0.3.0; docker-desktop chạy WSL2 |
| Python/pip | Python 3.12.10 cài tại LocalAppData/Python/pythoncore-3.12-64; pip 25.0.1; venv tại workspace |
| Node/npm | Node 24.22.1 và npm 11.19.1 tại Program Files/nodejs |
| Git | 2.56.0.windows.3 tại Program Files/Git; repo main tại workspace |
| Docker | Desktop 4.96.3; Engine 29.9.2 Linux; Compose 5.6.1 |
| PostgreSQL | 17.11, kết nối TCP 127.0.0.1:5432 thành công |
| Role DB | API dùng doi_pin_runtime; migration dùng doi_pin_migrator; bootstrap dùng postgres |
| Migration | 0002_user_approval (head); empty DB và nâng cấp có dữ liệu đã kiểm tra |

Không cài lại công cụ hệ thống hoặc sửa PATH Windows. Docker CLI chưa trên PATH của phiên Codex: helper tìm đường dẫn cài thật và chỉ bổ sung PATH của tiến trình khi cần credential helper, sau đó khôi phục. Docker/localhost bị sandbox chặn được chạy bằng quyền đã cấp.

Người dùng đã đồng ý tạo container/volume và tải postgres:17 nếu thiếu. Trước đó Docker không có container/volume. Đã tạo doi-pin-dev-db-1, network doi-pin-dev_default, volume doi-pin-dev_postgres17_data; không xóa dữ liệu/volume nào. PostgreSQL bind loopback, không cài PostgreSQL native.

Git đã cấu hình **local repository** theo tên/email người dùng cung cấp. Commit nghiệm thu dùng thông điệp `feat: initialize project foundation and authentication`; lấy hash bằng `git log -1 --oneline`. Không thay cấu hình Git global hoặc push remote.

## P0-01/02/03

- **P0-01 Passed:** migration mới thêm APPROVED_FOR_SIMULATION_BY_USER và approval_evidence; seed giữ đúng thẩm quyền duyệt user và hash nguồn approved; không giả TEAM_CONFIRMED. Policy immutable, audit append-only.
- **P0-02 Passed:** OpenAPI validator, Draft 2020-12 approved config và pglast parse 278 SQL statements. Hash 5 file baseline và 74 file manifest vẫn khớp. Output ở docs, không ghi đè biên bản/tài liệu gốc.
- **P0-03 Passed:** 422/CONFIG_NOT_READY cho policy thiếu/không hợp lệ; 503 cho DB/service unavailable. Startup fail closed; health/login không tạo phiên nếu policy hết hợp lệ. Test trực tiếp case thiếu fee. Reserve/payment chưa triển khai.

QD01–QD09, FR01–FR19, UC01–UC17, BR01–BR12 giữ nguyên. Seed 3 tài khoản/3 vai trò, 2 trạm, 12 ngăn, 11 pin (gồm pin khách đang giữ), assignment Technician tại S01. Ngăn BLOCKED/cửa UNKNOWN, không giả telemetry hoặc bật khả dụng trước Phase 2/3.

## Sản phẩm Phase 1

- FastAPI factory, cấu hình approved fail closed, SQLAlchemy/PostgreSQL, structured errors đã loại thông tin nhạy cảm.
- Opaque bearer token chỉ hash trong DB, password Argon2id; 5 lần sai/15 phút bằng counters/locks trong PostgreSQL, username và IP kết nối; không tin X-Forwarded-For tùy ý.
- Login/logout/me; Admin list/create/update users và station assignments; kiểm role hiện hành mỗi request; thu hồi session khi khóa/đổi role; chặn thay role còn custody/assignment/active swap, chặn khóa quản trị viên cuối.
- Mutation idempotency với request hash, principal/route/key; 409 khi đổi body hoặc version cũ. State, response idempotency và audit commit trước khi gửi HTTP response.
- React/TypeScript/Vite có login, profile ba vai trò, admin account list/create/lock/unlock/change role; token chỉ trong bộ nhớ tab; Vite proxy API.
- Hai forward migrations, provisioning role/schema/grants và seed idempotent; không reset credential/custody hiện có. DDL đầy đủ là nền tảng schema, chưa có API nghiệp vụ Phase 2+.

## File tạo/chỉnh sửa

| Nhóm | File |
| --- | --- |
| Backend | services/backend/app/config.py, main.py, api/schemas.py, application/identity.py, domain/identity.py, infrastructure/db.py, seed.py và các __init__.py |
| Migration | services/backend/alembic.ini, alembic/env.py, versions/0001_baseline.py, 0002_user_approval.py |
| Frontend | apps/web/package.json, package-lock.json, index.html, tsconfig.json, vite.config.ts, src/main.tsx, src/styles.css |
| Config/dependency | .env.example, deploy/compose.yaml, requirements.in, requirements.lock.txt, pytest.ini; .gitignore hiện có được giữ và sử dụng |
| Tool | tools/provision_database.py, validate_contracts.py, dev.ps1; helper Phase 0 giữ nguyên |
| Test | tests/conftest.py, tests/test_phase1.py |
| Tài liệu | README.md, IMPLEMENTATION_DECISIONS.md, IMPLEMENTATION_PLAN.md cập nhật, IMPLEMENTATION_STATUS.md này |
| Bằng chứng | CONTRACT_VALIDATION.json, PHASE1_TEST_RESULTS.xml, TEST_ENVIRONMENT.json, HTTP_SMOKE_RESULTS.json, PHASE1_ENVIRONMENT.json |
| Local không commit | .env secret ngẫu nhiên, .venv, node_modules, dist, .cache, .pytest_cache, __pycache__ |

Tài liệu gốc doi-pin-giai-doan-2 và tài liệu riêng docs/CODEX_11_BUOC_MODEL_VA_PROMPT.md không bị chỉnh sửa hoặc đưa vào commit source của lượt này. Source hiện tham chiếu bộ hồ sơ gốc tại workspace; README ghi rõ phải giữ/khôi phục bundle khi lấy source từ Git. Không tạo bản sao DOCX/ảnh hoặc bản backup dự án.

## Kiểm thử và bằng chứng

| Kiểm tra | Kết quả | Phạm vi |
| --- | --- | --- |
| Pytest | **18 Passed, 0 Failed** | 8.70 giây lượt cuối; TC01/TC02 và foundation checks |
| TC01 | Passed | Ba role login/me; token hash; từ chối cross-role; giới hạn login kể cả 6 request đồng thời; spoof XFF không reset; expiry/logout/replay; validation không lộ password |
| TC02 | Passed | Create/retry/conflict; pagination; khóa thu hồi session và giữ lịch sử; đổi role/version; assignment atomic và scope; giữ active Admin; audit/runtime permissions |
| Migration | Passed | Từ schema sạch tới 0001, thêm marker dữ liệu, upgrade 0002, lặp upgrade head giữ marker |
| Seed | Passed | Chạy lại không đổi password/hash và bản ghi hiện có; đủ trạm/ngăn và trạng thái approved |
| OpenAPI/JSON Schema/SQL | Passed | Validator chuẩn + live OpenAPI 8 operations (gồm health) |
| Frontend build | Passed | tsc --noEmit và Vite production build; không có lỗi CSS còn lại |
| Dependency integrity | Passed | pip check: No broken requirements found |
| HTTP thật | **5 Passed** | HTML/proxy health; admin/customer/technician login → me → users 200/403 → logout/revoked; live OpenAPI |
| Browser | Passed giới hạn | Màn hình login được mở và kiểm tra bố cục qua in-app browser; không chạy toàn bộ form E2E trên browser |
| TC03–19, CT01–14 đầy đủ, NFR performance/restore | Not Run | Thuộc các phase chưa giao |

Pytest có 2 deprecation warnings: Starlette TestClient dùng httpx và openapi-spec-validator.validate_spec. Không làm test thất bại; nên chuyển API/dependency tương ứng khi cập nhật toolchain, không nâng cấp global trong lượt này.

Có một lượt test đầu bị dừng vì fixture lịch sử tạo FK qua kết nối thứ hai khi tài khoản đang bị test giữ khóa. Đã sửa thứ tự fixture và đặt statement_timeout 15s/lock_timeout 5s; các lượt đầy đủ sau Passed. Không có test ứng dụng quan trọng đang Failed.

Tests dùng schema phase1_test_* riêng, API bằng role runtime, per-test rollback. Bốn schema từ các lượt test được giữ trong volume, có tên trong PHASE1_ENVIRONMENT.json; không xóa dữ liệu để làm sạch kết quả. Bằng chứng JUnit chỉ giữ lượt nghiệm thu cuối, log chẩn đoán cục bộ trong .cache.

## Lệnh đã chạy

- Đọc AGENTS, status/plan, START_HERE, handoff, approved decisions/config, invariants, OpenAPI và DDL; kiểm PATH/đường dẫn cài thật.
- Python --version, pip --version, node --version, npm.cmd --version, git --version/config, wsl --version/list --verbose, Docker version/compose version/ps/volume ls.
- Python 3.12 `-m venv .venv`; ensurepip được hoàn tất trong venv sau lỗi quyền thư mục tạm sandbox. Không thay Python nền; dependency dùng cache/tmp trong workspace.
- `.venv/Scripts/python.exe -m pip install -r requirements.in` với cache local; `pip freeze --all` tạo lock; `pip check`.
- `npm.cmd --prefix apps/web install --ignore-scripts --no-audit --no-fund` với cache .cache/npm; `npm.cmd --prefix apps/web run build`.
- `docker compose --env-file .env -f deploy/compose.yaml config --quiet`, `up -d --wait db`; truy vấn SQL read-only xác nhận server/role/count/revision; Docker image inspect và du đo dung lượng.
- `python tools/provision_database.py roles`, `python -m alembic -c services/backend/alembic.ini upgrade head`, `python tools/provision_database.py grants`, `python -m app.seed` (PYTHONPATH=services/backend).
- `python tools/validate_contracts.py docs/CONTRACT_VALIDATION.json`.
- `python -m pytest -q --basetemp=.cache/pytest-tmp-commit --junitxml=docs/PHASE1_TEST_RESULTS.xml` (lượt cuối).
- `tools/dev.ps1 backend`, `tools/dev.ps1 frontend`; HTTP smoke bằng httpx, credential đọc từ env và không in ra log; mở browser login.
- `git init -b main`, cấu hình tên/email local, `git check-ignore`, stage chọn lọc, kiểm secret/artifacts trước commit. Không git add toàn workspace, không push.

## Khởi động và tài khoản

Xem [README.md](../README.md) để chuẩn bị lần đầu. Trong workspace hiện tại, DB và môi trường đã khởi tạo:

```powershell
.\tools\dev.ps1 database
.\tools\dev.ps1 backend
# Terminal khác:
.\tools\dev.ps1 frontend
```

Frontend http://127.0.0.1:5173; Backend http://127.0.0.1:8000; Swagger /docs; health /health. Hai server đang chạy ở cuối lượt; không khởi động thêm nếu port đang được dùng.

User admin/customer/technician; mật khẩu tương ứng trong biến DEMO_ADMIN_PASSWORD, DEMO_CUSTOMER_PASSWORD, DEMO_TECHNICIAN_PASSWORD của .env local. Không có mật khẩu mặc định trong source hoặc báo cáo. Reload tab yêu cầu login lại vì token không lưu persistent.

## Dung lượng và dọn an toàn

Số đo trong PHASE1_ENVIRONMENT.json; dung lượng thực trên đĩa có thể khác do filesystem/Docker VHDX.

| Thư mục/tài nguyên | Dung lượng gần đúng | Tác động nếu dọn |
| --- | --- | --- |
| .venv | 95,84 MiB | Cần cài lại từ requirements.lock.txt; không xóa khi server đang chạy |
| apps/web/node_modules | 56,39 MiB | Cần npm ci; không xóa khi Vite đang chạy |
| apps/web/dist | 0,22 MiB | Build lại bằng npm run build |
| .cache | 146,42 MiB | Có thể tái tạo; npm ~125,89 MiB, pip ~19,91 MiB; giữ log cần chẩn đoán trước khi dọn |
| PostgreSQL image | ~610,29 MiB | Docker quản lý; không tự xóa |
| PostgreSQL volume | ~69,85 MiB | Chứa DB demo và schemas test, cần bảo toàn |

Không dọn file hoặc volume trong lượt này. Chỉ cân nhắc cache/build rõ nguồn gốc trong workspace khi cần. Giữ source, migrations, lockfile, thiết kế gốc, docs bằng chứng, .env local và DB để khôi phục; không dùng docker down -v/prune volumes. Source/config/tài liệu mới nhỏ, không có bản sao dự án hoặc backup trùng lặp.
