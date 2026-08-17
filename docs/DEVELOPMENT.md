# Phát triển và kiểm thử

## Chuẩn bị

```powershell
.\setup.bat -Development
powershell -ExecutionPolicy Bypass -File .\scripts\start-reporter.ps1 -Development
```

`requirements.txt` và `requirements-dev.txt` là đầu vào trực tiếp dễ review.
`requirements.lock.txt` và `requirements-dev.lock.txt` là môi trường cài đặt thực,
khóa toàn bộ dependency gián tiếp và SHA-256. Frontend dùng `package-lock.json`.
CI bắt buộc dùng `pip --require-hashes` và `npm ci`.

Khi chủ động nâng dependency Python, tạo lại lockfile bằng:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\lock-python-dependencies.ps1
```

Chỉ commit lockfile sau khi review diff và chạy quality gate trên virtualenv sạch.

## Quality gate

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

Lệnh này chạy Ruff check/format check, ESLint, Prettier check, backend regression/API
tests, Vitest/React Testing Library và build frontend vào thư mục kiểm tra tạm.

Chạy từng nhóm kiểm tra khi đang phát triển:

```powershell
# Python
apps\backend\.venv\Scripts\python.exe -m ruff check apps\backend scripts tests
apps\backend\.venv\Scripts\python.exe -m ruff format --check apps\backend scripts tests

# Frontend
cd apps\frontend
npm run lint
npm run format:check
```

Chỉ dùng `ruff format` hoặc `npm run format` cho source do dự án quản lý. DOCX, CSV
fixture, golden snapshot, lockfile và release artifact nằm ngoài phạm vi formatter.

E2E:

```powershell
cd apps\frontend
npx playwright install chromium
npm run test:e2e
```

Playwright khởi chạy test server riêng và kiểm tra workflow import → configure →
preview → generate. Test server có endpoint teardown chỉ tồn tại trong E2E runtime;
suite chủ động đóng server sau khi hoàn tất để không để lại process/cổng 4173 trên Windows.

## Nhóm kiểm thử backend

- API import/validate/generate/template/preset/history/backup.
- Database migration transaction, pre-migration checkpoint và rollback khi lỗi.
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
