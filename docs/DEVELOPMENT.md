# Phát triển và kiểm thử

## Chuẩn bị

```powershell
.\setup.bat -Development
powershell -ExecutionPolicy Bypass -File .\scripts\start-reporter.ps1 -Development
```

Python dependency được khóa trong `apps/backend/requirements*.txt`; frontend dùng
`package-lock.json` và bắt buộc cài bằng `npm ci` trong CI.

## Quality gate

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

Lệnh này chạy backend regression/API tests, Vitest/React Testing Library và build
frontend vào thư mục kiểm tra tạm.

E2E:

```powershell
cd apps\frontend
npx playwright install chromium
npm run test:e2e
```

Playwright khởi chạy test server riêng và kiểm tra workflow import → configure →
preview → generate.

## Nhóm kiểm thử backend

- API import/validate/generate/template/preset/history/backup.
- Data quality, rule engine, incident validation và threat intelligence.
- Report job progress/cancel/cleanup.
- Template category/schema và golden DOCX structure.
- Upload/resource limits, system health và soak harness.

## GitHub Actions

Workflow `.github/workflows/ci.yml` tách backend, frontend và E2E thành các job độc
lập. Pull request chỉ nên merge khi tất cả job thành công.

## Dữ liệu kiểm thử

Chỉ dùng fixture tổng hợp trong `apps/backend/samples` và `tests`. Không dùng
tracking/report thật của khách hàng. Benchmark chính thức cần ghi rõ commit,
dataset, CPU, RAM, phiên bản Python/Node và tiêu chí pass/fail; bảng này chưa được
công bố cho đến khi quy trình đo có thể tái lập.
