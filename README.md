# Reporter Pro

[![CI](https://github.com/Eyblcat12/Reporter4CA-/actions/workflows/ci.yml/badge.svg)](https://github.com/Eyblcat12/Reporter4CA-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-6f42c1.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](.python-version)
[![Node 20](https://img.shields.io/badge/Node.js-20-339933.svg?logo=node.js&logoColor=white)](.nvmrc)

Reporter Pro là công cụ local-first giúp tự động hóa báo cáo DFIR và Compromise
Assessment từ dữ liệu tracking. Ứng dụng kết hợp giao diện React, API FastAPI và
template Word để chuẩn hóa quá trình import, kiểm tra dữ liệu, phân tích finding,
xem trước và xuất báo cáo DOCX.

> **Phạm vi hiện tại:** tối ưu cho cá nhân và nhóm nội bộ trên Windows. Reporter Pro
> chưa được thiết kế như một dịch vụ multi-tenant chạy trên toàn server.

## Điểm nổi bật

- Import Excel, CSV, JSON hoặc raw text; tự nhận diện và cho phép chỉnh mapping cột.
- Kiểm tra chất lượng dữ liệu trước khi tạo báo cáo, chỉ rõ dòng lỗi và cảnh báo.
- Rule engine có thể cấu hình để chuyển nội dung `Note` thành finding có truy vết.
- Sáu loại báo cáo: Full, Server, Client, Summary, Technical và Incident Response.
- Template DOCX theo từng loại báo cáo, kiểm tra tương thích trước khi sử dụng.
- Job tạo report có trạng thái, tiến độ, hủy an toàn và ghi lịch sử.
- Dashboard thống kê report, tài sản, tỷ lệ thành công và hoạt động theo thời gian.
- Workspace backup, template versioning và golden DOCX regression test.
- Giao diện Việt/Anh, dark/light mode và luồng thao tác tối ưu cho desktop.
- Plugin API mở rộng; tích hợp bên ngoài là tùy chọn và không bắt buộc để chạy.

## Bắt đầu nhanh trên Windows

Yêu cầu: **Python 3.12+**, **Node.js 20–25** và **npm 10+**.

```powershell
git clone https://github.com/Eyblcat12/Reporter4CA-.git
cd Reporter4CA-
.\setup.bat
.\start.bat
```

`setup.bat` tạo môi trường Python riêng, cài dependency đã khóa, tạo `.env` cục bộ,
cài frontend bằng `npm ci` và build production UI. `start.bat` sau đó mở ứng dụng
tại [http://127.0.0.1:8000](http://127.0.0.1:8000).

Xem [hướng dẫn cài đặt đầy đủ](INSTALL.md) nếu cần cài thủ công, chạy development
mode hoặc xử lý lỗi môi trường.

## Quy trình sử dụng

1. Chọn file tracking, raw text hoặc dữ liệu mẫu.
2. Kiểm tra mapping cột và bảng chất lượng dữ liệu.
3. Chỉnh tài sản, rule phát hiện và metadata nếu cần.
4. Chọn report type, template và preset.
5. Preview, theo dõi job và tải DOCX khi hoàn tất.

API tương tác có sẵn tại [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
khi ứng dụng đang chạy.

## Kiến trúc

```text
Browser / React + Vite
          │ REST API
          ▼
FastAPI ──┬── Import & data-quality pipeline
          ├── Rule / finding engine
          ├── Background report jobs
          ├── DOCX template & generation engine
          ├── SQLite history / workspace backup
          └── Optional plugins
```

```text
Reporter4CA-/
├── .github/            GitHub Actions và community templates
├── apps/
│   ├── backend/        FastAPI, engine, templates, samples
│   └── frontend/       React, Vitest và Playwright
├── docs/               Hướng dẫn người dùng và tài liệu kỹ thuật
├── scripts/            Setup, launcher và quality gate
├── tests/              Backend/API/DOCX regression tests
├── setup.bat           Cài đặt một lần trên Windows
└── start.bat           Khởi chạy production local
```

## Tài liệu

| Chủ đề | Tài liệu |
|---|---|
| Cài đặt và xử lý lỗi | [INSTALL.md](INSTALL.md) |
| Hướng dẫn sử dụng | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| Template và report type | [docs/TEMPLATE_GUIDE.md](docs/TEMPLATE_GUIDE.md) |
| Thêm rule từ cột Note | [docs/USER_RULE_GUIDE.md](docs/USER_RULE_GUIDE.md) |
| Kiến trúc và luồng dữ liệu | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Phát triển và kiểm thử | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Trạng thái và roadmap | [docs/PROJECT_STATUS_AND_ROADMAP.md](docs/PROJECT_STATUS_AND_ROADMAP.md) |

## Phát triển

```powershell
.\setup.bat -Development
powershell -ExecutionPolicy Bypass -File .\scripts\start-reporter.ps1 -Development
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

Quality gate gồm backend regression/API tests, frontend component tests và
production build. E2E chính:

```powershell
cd apps\frontend
npx playwright install chromium
npm run test:e2e
```

Chi tiết quy trình đóng góp nằm trong [CONTRIBUTING.md](CONTRIBUTING.md).

## Bảo mật và dữ liệu

Reporter Pro xử lý dữ liệu tại máy cục bộ. File `.env`, database, log, report sinh
ra, dependency và build artifact đều bị loại khỏi Git. Không commit dữ liệu khách
hàng, API key, token hoặc report thật. Xem [SECURITY.md](SECURITY.md) để báo cáo
lỗ hổng.

## Trạng thái hiệu năng

Các giới hạn mặc định hiện mang tính bảo vệ workstation, không phải cam kết năng
lực tối đa. Bảng benchmark chuẩn hóa cho report lớn sẽ được công bố sau khi hoàn
thành bộ test có thể tái lập trên cấu hình máy được ghi rõ.

## Giấy phép

Phát hành theo [MIT License](LICENSE).
