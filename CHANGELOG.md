# Changelog

Mọi thay đổi đáng chú ý của Reporter Pro được ghi tại đây. Dự án tuân theo
[Semantic Versioning](https://semver.org/); ngày phát hành dùng định dạng ISO.

## [Unreleased]

### Fixed

- Đồng bộ E2E rule-builder với response contract và nhãn UI hiện tại; kiểm tra
  download qua HTTP response ổn định thay vì phụ thuộc sự kiện blob của trình duyệt.
- Sửa script tạo Python lockfile truyền sai đường dẫn output cho `pip-compile`.

### Added

- Ruff 0.16.2 cho Python và ESLint 10/Prettier 3 cho frontend, được pin trong
  dependency lock và bắt buộc trong local check, GitHub Actions và GitLab CI.
- `.editorconfig`, cấu hình lint/format thống nhất và các lệnh `lint`, `format`,
  `format:check` dành cho contributor.
- Thanh tiến độ import file xác định từ 0–100% trên dashboard và màn Import, kèm
  giai đoạn đọc/phân tích/nhập dữ liệu, số dòng hoàn tất, trạng thái lỗi và hủy an toàn.

## [2.1.2] - 2026-08-03

### Fixed

- Khóa line ending của CSV ở LF trên mọi hệ điều hành để fixture benchmark giữ
  nguyên byte và SHA-256 sau khi checkout trên Windows runner.
- Khôi phục release gate tái lập cho bộ fixture hiệu năng mà không thay đổi dữ liệu,
  manifest hay kết quả benchmark đã công bố.

## [2.1.1] - 2026-08-03

### Fixed

- Tách quality gate của release thành backend test, frontend test và production build
  để lỗi trên runner được định vị chính xác và không bị che trong một bước tổng hợp.
- Giữ nguyên tag baseline `v2.1.0`; bản vá phát hành được tạo bằng tag bất biến mới
  thay vì di chuyển tag đã công bố.

## [2.1.0] - 2026-08-03

### Added

- Workspace restore có dry-run, preview nội dung, manifest/checksum validation,
  migration schema và automatic rollback database/template.
- Preview Job API, managed Preview artifact cache và byte-for-byte promotion từ
  Preview sang Generate.
- Rule builder/version history, template compatibility/versioning và data-quality
  workflow cho dữ liệu tracking thực tế.
- Bộ dependency lock Python đầy đủ với SHA-256 và script tái tạo lockfile.
- Preview benchmark gate 10 trial cùng công cụ tổng hợp P50/P95 có kiểm thử.

### Changed

- Bật Preview Job và Preview Cache mặc định cho local/team sau khi đạt gate 10/10;
  vẫn hỗ trợ rollback tức thời bằng environment flags.
- Dashboard, report jobs, heading mặc định, golden DOCX và launcher lifecycle được
  củng cố cho workflow desktop.
- Setup và CI cài Python dependency bằng `--require-hashes`.

### Fixed

- Không bỏ sót asset có dấu hiệu bất thường trong báo cáo tracking.
- Dashboard đồng bộ lịch sử/biểu đồ và hiển thị trục thời gian, ngày giờ đầy đủ.
- Light mode data-quality, DOCX field update và xung đột port launcher.

[2.1.0]: https://github.com/Eyblcat12/Reporter4CA-/releases/tag/v2.1.0
[2.1.1]: https://github.com/Eyblcat12/Reporter4CA-/releases/tag/v2.1.1
[2.1.2]: https://github.com/Eyblcat12/Reporter4CA-/releases/tag/v2.1.2
[Unreleased]: https://github.com/Eyblcat12/Reporter4CA-/compare/v2.1.2...HEAD
