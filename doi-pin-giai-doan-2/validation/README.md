# Biên bản kiểm tra thiết kế

Ngày 23/10/2026. Bộ hồ sơ đề xuất 0.2.

## Đã kiểm chứng
- Hash của 5 file baseline Giai đoạn 1 khớp bản sao lưu SHA256.json; không chỉnh nội dung baseline.
- 16 nguồn PlantUML đã render ra PNG và SVG bằng PlantUML 1.2025.2, layout Smetana. SVG parse XML thành công; PNG mở đầy đủ. Sơ đồ ngăn/cửa dùng hai state machine độc lập để tránh lỗi renderer bỏ vùng trực giao. Nguồn và hình cuối đã được đối chiếu.
- OpenAPI 3.1: 50 operations, validator chấp nhận; operation ID duy nhất; các x-fr và x-uc thuộc baseline; bao phủ 19 FR và 17 UC.
- PostgreSQL DDL: pglast parse 278 câu lệnh thành công. Có 24 bảng; ràng buộc liên bảng/transaction còn yêu cầu service thực hiện theo INVARIANTS.md.
- File cấu hình đề xuất hợp lệ với JSON Schema; null chưa chốt được cho phép trong tài liệu đề xuất, không được hiểu là cấu hình sẵn sàng chạy.
- DOCX render thành 37 trang, có trang bản vẽ A3; đã kiểm tra hình và bố cục. Văn bản/bảng chỉnh sửa trong Word; sơ đồ sửa bằng nguồn .puml.

## Chưa kiểm chứng bằng chạy hệ thống
Chưa chạy migration PostgreSQL; chưa chạy API server, simulator hoặc UI; chưa kiểm thử đồng thời, timeout thực, hiệu năng, backup restore hay an toàn phần cứng. TC01–TC19 và CT01–CT14 chưa có kết quả thực nghiệm. Không được suy ra “hệ thống đạt nghiệm thu” từ kiểm tra tĩnh này.

## Chạy lại kiểm tra tĩnh
Cài Python cùng pyyaml, openapi-spec-validator, pglast, jsonschema, pillow, rồi chạy `python validation/validate_design.py` từ bộ hồ sơ. Kết quả JSON ở structural-checks.json. Cần Java và PlantUML để render nguồn; jar không được đóng gói trong bộ thiết kế.

Để nghiệm thu khi triển khai: chuyển DDL thành migration; chạy trên PostgreSQL 17 sạch và nâng cấp; kiểm tra concurrency/restart/idempotency; xác nhận contract thực tế; thực hiện TC GĐ1 và CT bổ sung. Ghi chính xác môi trường, log và kết quả.
