# Kiến trúc Reporter Pro

Reporter Pro là ứng dụng web local-first chạy trên một workstation.

## Thành phần

- **Frontend:** React/Vite, quản lý launcher, import editor, quality summary,
  configure, preview, dashboard và history.
- **Backend:** FastAPI cung cấp REST API, validation và điều phối workflow.
- **Core:** import/mapping, quality checks, rule engine, report jobs, template
  compatibility, DOCX generation, backup và history.
- **Storage:** SQLite và file runtime trong `apps/backend/data`; không commit Git.
- **Plugins:** hook tùy chọn quanh dữ liệu/report. Workflow cốt lõi không phụ thuộc
  vào kết nối ngoài.

## Luồng dữ liệu

```text
Input file/raw text
  → parser & column mapping
  → normalized assets
  → quality validation
  → rules & findings
  → report configuration
  → background preview/generate job
  → DOCX + history/dashboard metadata
```

Finding phải truy vết được về input, rule và evidence. Template được kiểm tra trước
khi generate để tránh âm thầm xuất tài liệu thiếu section.

## Ranh giới an toàn

- API bind vào `127.0.0.1` theo launcher mặc định.
- CORS dùng allow-list, không bật wildcard mặc định.
- File import và số dòng có giới hạn cấu hình.
- Preview/Generate luôn đo elapsed time và backend RSS. Trần RAM/timeout là opt-in;
  khi bật, job hủy hợp tác tại checkpoint, dọn tệp tạm và ghi termination reason.
- Scheduler local tạo workspace backup nguyên tử theo chu kỳ, giữ số phiên bản hữu
  hạn và không xóa archive thủ công hoặc generated report.
- Custom runtime path bị tắt mặc định.
- `.env`, database, log, build và output nằm ngoài source control.
- Plugin kết nối ngoài là opt-in và dependency được cài riêng.

Ứng dụng hiện không cung cấp authentication/multi-tenancy để triển khai như dịch
vụ dùng chung trên server công cộng.
