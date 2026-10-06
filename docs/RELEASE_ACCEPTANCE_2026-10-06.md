# Nghiệm thu Reporter Pro v2.3.0

Phạm vi: Windows local, một tiến trình backend cho mỗi workspace, các mẫu đi kèm
và fixture tổng hợp. Báo cáo này tiếp nối
[audit ban đầu](READINESS_AUDIT_2026-10-06.md); không thay đổi kết luận lịch sử của
baseline v2.2.1/main trước sửa lỗi.

## Các lỗi đã xử lý

| Audit | Kết quả |
|---|---|
| R01 — mất IoC có cấu trúc | Giữ list/dict trong normalization; test từ web rows đến DOCX Full/Technical |
| R02 — thiếu Studio trong backup | Archive v2, SQLite backup API, lock phối hợp Studio, dry-run/rollback, đọc v1 |
| R03 — gộp URL sai/crash port | Canonical hóa theo loại; giữ URL path/query case; invalid URL trả lỗi kiểm tra |
| R04 — Full bỏ qua IoC | Full/Server/Client xuất evidence đã cung cấp; nội dung điều tra chưa có dữ liệu vẫn cần analyst |
| R05 — dependency dev | brace-expansion 5.0.12, source-map-js 1.2.2; npm audit: 0 advisory tại lần kiểm tra |
| R06 — gate thiếu coverage | Gate gồm publish/workbench; CI/release chạy API thật; browser recovery thêm reload/hai tab |
| R07/R08 — source/release lệch | Version mới 2.3.0; source/prebuilt cùng commit; prebuilt dùng sửa cache path đã có trên main |

## Kiểm chứng tại máy phát triển

- Backend gate: 423/423 test qua, gồm golden DOCX, API, migration, job, Studio,
  snapshot và rollback. Hai test bổ sung sau đó kiểm tra Studio rỗng và khôi phục
  thư viện/workspace/editor sang thư mục mới; suite backup/scheduled chạy lại 13/13.
  Gate đầy đủ tại CI/release sẽ bao gồm tổng cộng 425 test.
- Frontend: lint/format, 135 test và production build.
- Playwright: 9/9, retries=0; 5 test dùng backend thật. Kiểm tra import/navigation,
  thư viện reload, mapping→publish→preview/generate, normalization giữ nguồn,
  bản nháp chưa duyệt khôi phục sau reload và ở tab thứ hai.
- Microsoft Word: cả 6 loại báo cáo cập nhật field thành công; Full và Technical
  giữ IoC sau khi Word lưu lại. Đây là kiểm chứng engine/field và nội dung, chưa
  phải duyệt hình thức của mọi template khách hàng.
- Soak tổng hợp: 12 job × 100 dòng, 12 lượt dedup đúng, không timeout, không lỗi
  ngoài dự kiến; có một failure và một cancellation được cố tình đưa vào test.
  RSS cuối tăng khoảng 10,5 MiB; kết quả harness `passed=true`.
- Dependency: npm audit không có advisory tại thời điểm kiểm tra; runtime Python
  vẫn dùng lockfile có hash đã kiểm tra ở audit ban đầu.

Log tái lập lưu cục bộ dưới `artifacts/verification/readiness-20261006/` (không
đưa vào Git). Các kết quả CI và Release trên GitHub gắn với commit/tag là bằng
chứng công khai của bản đã xuất bản. Workflow release còn kiểm tra source sạch,
metadata/tag, build archive và checksum trước khi tạo GitHub Release.

## Phạm vi cam kết

Không tuyên bố phần mềm không thể có lỗi trên mọi máy. Baseline phát hành được
nghiệm thu theo các kiểm tra trên; template khách hàng, tải lớn kéo dài, nhiều
backend cùng ghi và triển khai Internet/multi-tenant nằm ngoài phạm vi này.
Phân tích mã độc bằng MCP/API là nhánh phát triển tiếp theo, chưa có trong v2.3.0.

Nguồn và gói cài chỉ được coi là đã đồng bộ khi tag `v2.3.0` trỏ đúng commit trên
main và GitHub Release hoàn tất với source ZIP/TAR.GZ, Windows prebuilt và
`SHA256SUMS.txt`. Hướng dẫn cài/nâng cấp nằm trong [release notes](releases/v2.3.0.md).
