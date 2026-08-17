# Changelog

Mọi thay đổi đáng chú ý của Reporter Pro được ghi tại đây. Dự án tuân theo
[Semantic Versioning](https://semver.org/); ngày phát hành dùng định dạng ISO.

## [Unreleased]

## [2.2.0] - 2026-08-17

### Fixed

- Setup phát hiện sớm Python MSYS2/Cygwin có layout venv không tương thích và hỗ
  trợ chọn rõ interpreter Windows bằng `-PythonExecutable`.
- Đồng bộ E2E rule-builder với response contract và nhãn UI hiện tại; kiểm tra
  download qua HTTP response ổn định thay vì phụ thuộc sự kiện blob của trình duyệt.
- Sửa script tạo Python lockfile truyền sai đường dẫn output cho `pip-compile`.
- Preview polling và tải artifact tự phục hồi sau lỗi mạng/408/429/5xx tạm thời,
  giữ nguyên dữ liệu import và trả lỗi rõ ràng sau ba lần thử lại.
- E2E server trên Windows tự shutdown sau suite thay vì để lại Node/Vite process;
  workflow chính cũng đợi download hoàn tất trước khi kết thúc test.
- Benchmark tách product peak RSS khỏi peak audit mở lại DOCX, tránh đánh giá sai
  lượng RAM mà workflow Generate thực sự sử dụng.

### Added

- Ruff 0.16.2 cho Python và ESLint 10/Prettier 3 cho frontend, được pin trong
  dependency lock và bắt buộc trong local check, GitHub Actions và GitLab CI.
- `.editorconfig`, cấu hình lint/format thống nhất và các lệnh `lint`, `format`,
  `format:check` dành cho contributor.
- Thanh tiến độ import file xác định từ 0–100% trên dashboard và màn Import, kèm
  giai đoạn đọc/phân tích/nhập dữ liệu, số dòng hoàn tất, trạng thái lỗi và hủy an toàn.
- Resource monitor cho Preview/Generate: đo elapsed time và backend RSS ngay trong
  panel tiến độ; hỗ trợ ngưỡng RAM/timeout opt-in, hủy hợp tác, cleanup và termination
  reason rõ ràng mà không áp giới hạn cứng lên template khách hàng theo mặc định.
- Windows prebuilt release bundle chứa production frontend và manifest gắn version
  với Git commit; hỗ trợ setup production không cần Node/npm và được đưa vào checksum.
- Automatic workspace backup theo chu kỳ, retention giới hạn và namespace an toàn;
  archive vẫn dùng manifest/checksum và restore dry-run/rollback hiện có.
- Pre-migration SQLite checkpoint có SHA-256 và retention ba phiên bản; toàn bộ
  pending migration chạy trong một transaction và tự phục hồi checkpoint nếu lỗi.
- Compact table prototype được bật mặc định sau gate Full 3.000 asset giữ nguyên
  integrity/output và giảm product peak RSS; flag `0` vẫn rollback về legacy path.
- Stability gate Full 3.000 asset đạt 10/10 fresh process: không thiếu asset/finding,
  product latency P50/P95 229,6/236,9 giây và product peak RSS P95 2.457,5 MiB.

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
[2.2.0]: https://github.com/Eyblcat12/Reporter4CA-/releases/tag/v2.2.0
[Unreleased]: https://github.com/Eyblcat12/Reporter4CA-/compare/v2.2.0...HEAD
