# Soak test cho report jobs

Soak test chạy hoàn toàn cục bộ, không sử dụng database hoặc thư mục generated report của
workspace. DOCX được tạo trong RAM; chỉ file kết quả JSON được ghi vào `artifacts/soak/`.

## Chạy smoke trước khi commit

```powershell
apps/backend/.venv/Scripts/python.exe scripts/soak_report_jobs.py --profile smoke
```

## Chạy profile dài hai giờ

```powershell
apps/backend/.venv/Scripts/python.exe scripts/soak_report_jobs.py --profile long
```

Có thể điều chỉnh trên máy yếu hoặc mạnh hơn:

```powershell
apps/backend/.venv/Scripts/python.exe scripts/soak_report_jobs.py `
  --profile long --duration-minutes 180 --rows 2500 --job-timeout 1200 `
  --memory-growth-mb 512
```

## Điều kiện đạt

- Có ít nhất một job hoàn thành và DOCX trong RAM hợp lệ.
- Không có job treo quá `job-timeout`.
- Job giống nhau được deduplicate về cùng ID.
- Các ca hủy/lỗi có chủ đích kết thúc đúng trạng thái.
- Python heap cuối không tăng quá ngưỡng cấu hình.
- Job terminal cũ được giới hạn trong bộ nhớ bởi `max_retained`.

Kết quả gồm thời gian min/p50/p95/max, heap baseline/final/peak, trạng thái job và danh sách
điều kiện thất bại. Profile dài không chạy trong CI thông thường vì có chủ đích kéo dài nhiều giờ.
## Heartbeat và phục hồi trạng thái

Trong khi chạy, harness cập nhật file `*.checkpoint.json` sau mỗi job và heartbeat trong
`*.status.json`. Việc ghi sử dụng thay thế nguyên tử để tránh JSON bị cắt dở. Khi lần chạy tiếp theo
phát hiện status `running` nhưng PID không còn tồn tại, status cũ được chuyển thành `interrupted`
thay vì tiếp tục hiển thị trạng thái chạy giả.
