# Bằng chứng được chọn cho commit sửa Phase 6

Người dùng đã chấp thuận nghiệm thu trong phạm vi kỹ thuật đã kiểm chứng và yêu cầu tạo commit. Không bao gồm Browser E2E (Not Run), tải dài hạn hoặc supervisor production.

## Probe P6-A02 và phạm vi test

Bản gốc nguyên byte: `HISTORICAL_P6_A02/test_phase6_acceptance.py.txt`; SHA256 trong manifest khớp bằng chứng ban đầu. Bản này là archive, không bị xóa. Ca test hiện hành cùng tên vẫn chạy, không skip/xfail; theo phê duyệt, kiểm riêng UNKNOWN sau receipt xung đột và SUCCEEDED đúng một audit sau callback hợp lệ. Test độc lập cũng kiểm replay/receipt của khoản thu cũ không đổi.

375 = 332 regression Phase1–6 đã có + 13 acceptance hiện hành + 25 blocker-fix + 5 worker-recovery. Không cộng các lượt targeted/E2E vào pytest; archive không được tính như một bản test trùng lặp. Kết quả lịch sử367/1 và370/0 giữ nguyên trong các artifact local.

## Kết quả sau sửa

| Nhóm | Kết quả | SHA256 artifact gốc (giữ local) |
| --- | --- | --- |
| A03_TARGETED | 12 Passed, 0 Failed, 0 Errors, 0 Skipped | `f9c6f122430e27fcf738fc094e3be5a08bed396c1f1df15ec837a6b7bec13166` |
| A03_FULL_REGRESSION | 375 Passed, 0 Failed, 0 Errors, 0 Skipped | `29ae98d83e71334d1e6f80f86ce8e398dc5c26660b6f57b17c0fd631e04dc3a4` |
| Payment E2E/smoke | 12 Passed | `f79360739a62fd2b54c890628535fb5df86fc06aed299c979ffef5acd7b5b5c3` |
| Receipt conflict E2E/smoke | 5 Passed | `67f27d6cff20f36cf4c7c014f92f944ab7057f713815f16546471cdc6f9870d9` |
| IoT E2E/smoke | 8 Passed | `deb192b70e87c8f3e9a98c221f92477ae24908a8945bcda97cdd5ec6cd0a83cf` |
| Phase5 E2E/smoke | 8 Passed | `f393565b6e01cadeb450b553641393f259a0aec0a34f3591f7aa2bfc3b2ed188` |
| HTTP E2E/smoke | 28 Passed | `fb4933b5e3481dc7c28e7e298533e5da510b1c80c937b5238e449fe80224da4b` |

OpenAPI/JSON Schema/278 SQL/baseline hashes Passed; pip check, npm dependency check và TypeScript/Vite Passed. Không chạy lại tests khi chuẩn bị commit vì chỉ cập nhật tài liệu và chọn file, source/test không thay đổi từ lượt375Passed.

## Bằng chứng lỗi gốc giữ trong Git

- `docs/PHASE6_ACCEPTANCE.md`: review và điều kiện tái hiện trước sửa.
- `docs/PHASE6_ACCEPTANCE/SLOW_READ_CONSENT.json`, `SLOW_READ_SETTLEMENT.json`: P6-A01 trước sửa.
- `docs/PHASE6_ACCEPTANCE/REFERENCE_COLLISION.json`: P6-A02, IntegrityError và worker exit1.
- `LOCK_TIMEOUT_CHARACTERIZATION/reports/PHASE6_FIX/LOCK_TIMEOUT_payment.json`, `LOCK_TIMEOUT_device.json`: P6-A03 trước sửa.
- `HISTORICAL_P6_A02/` và `HISTORICAL_P6_A03/`: hai archive test với manifest SHA256.

Không stage screenshot, log/XML/JSON trung gian, report lặp, .env, .venv, node_modules, dist, DB hoặc ledger. Các artifact không chọn vẫn giữ trên đĩa; không xóa. Runner tái hiện chuẩn là tools/run_phase6_fix.py; wrapper tools/phase6_acceptance_e2e.py trùng chức năng được giữ local.

## An toàn dữ liệu và giới hạn

Các E2E dùng schema riêng và xác nhận fingerprint demo không đổi; chuẩn bị commit chỉ đọc source/artifact, không truy vấn ghi DB hoặc thay volume. .local được bảo toàn, kiểm hash ledger trước/sau commit. Hết3 lần retry hoặc lỗi DB ngoài55P03 vẫn dừng có log; operator cần xử lý contention kéo dài. Không tự chuyển Phase7 hoặc push.

`.gitattributes` giữ hai archive test ở chế độ `-text -diff` (giữ byte gốc và xem CRLF lịch sử là archive) để hash trong Git cũng khớp nguyên byte, không bị chuẩn hóa CRLF/LF. Không thay quy tắc cho source hoặc baseline.
