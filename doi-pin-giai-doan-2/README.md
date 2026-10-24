# Bộ thiết kế Giai đoạn 2

Đọc tài liệu DOCX và handoff/CODEX_HANDOFF.md trước triển khai. baseline giữ bản GĐ1 cùng SHA256. Mọi QD01–QD09 chưa có xác nhận nhóm trong hội thoại; cấu hình đề xuất giữ phần chưa chốt. Chưa có ứng dụng hoàn chỉnh.

- diagrams: 16 nguồn PlantUML cùng PNG và SVG đã render; ERD dùng ký pháp crow foot, không gọi là UML. Activity, State Machine và component deployment dùng PlantUML. GĐ1 Use Case được giữ trong baseline.
- database: PostgreSQL DDL, từ điển dữ liệu và bất biến/service guard.
- contracts: OpenAPI 3.1, enum, cấu hình và truy vết FR/UC.
- handoff: thứ tự module, tiêu chí test và quyết định cần nhóm xác nhận.
- validation: kết quả kiểm tra tĩnh; không phải kết quả vận hành hệ thống.

Render lại: `java -jar plantuml.jar -charset UTF-8 -tpng diagrams/*.puml` hoặc `-tsvg`. Đã kiểm tra bằng PlantUML 1.2025.2 và layout Smetana; không cần Graphviz trong cấu hình này. Bản PNG nằm trong DOCX; sửa sơ đồ ở .puml rồi render lại. Nội dung văn bản và bảng trong DOCX chỉnh sửa được.
