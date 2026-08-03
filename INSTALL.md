# Cài đặt Reporter Pro

## Yêu cầu hệ thống

- Windows 10/11 x64.
- Python 3.12 trở lên, có `python.exe` trong `PATH`.
- Node.js từ 20.19 đến 25.x và npm 10 trở lên.
- Khoảng 2 GB dung lượng trống cho môi trường phát triển, dependency và output.

Microsoft Word không bắt buộc để tạo DOCX, nhưng nên dùng Word hoặc LibreOffice để
kiểm tra kết quả trực quan.

## Cài đặt tự động

```powershell
git clone https://github.com/Eyblcat12/Reporter4CA-.git
cd Reporter4CA-
.\setup.bat
.\start.bat
```

Script setup thực hiện:

1. Kiểm tra phiên bản Python và Node.js.
2. Tạo `apps\backend\.venv`.
3. Cài backend dependency từ file phiên bản đã khóa.
4. Prewarm sáu template DOCX bundled vào cache content-addressed để lần Preview đầu
   không phải compile template đồng bộ; nếu warm-up lỗi, engine vẫn fallback an toàn.
5. Tạo `.env` từ `.env.example` nếu chưa có.
6. Chạy `npm ci` và build frontend production.

Script không ghi đè `.env` đã tồn tại.

## Dừng ứng dụng

Launcher và giao diện trình duyệt được đồng bộ theo một phiên chạy cục bộ:

- Đóng tab Reporter Pro cuối cùng sẽ dừng launcher và backend sau khoảng đệm 5 giây.
- Refresh trang không làm tool tắt; tab mới sẽ đăng ký lại trong khoảng đệm.
- Nếu mở nhiều tab Reporter Pro, backend chỉ dừng khi tab cuối cùng được đóng.
- Nhấn `Enter` hoặc đóng cửa sổ CMD sẽ dừng backend. Tab giao diện sẽ thử tự đóng;
  nếu trình duyệt chặn quyền này, tab sẽ hiện thông báo ứng dụng đã dừng.

Không dùng Task Manager để dừng riêng backend trong lúc đang tạo report; hãy hủy
job trước, sau đó đóng tab hoặc launcher để file tạm được xử lý đúng luồng.

## Cài đặt thủ công

```powershell
python -m venv apps\backend\.venv
apps\backend\.venv\Scripts\python.exe -m pip install -r apps\backend\requirements.txt
Copy-Item .env.example .env
cd apps\frontend
npm ci
npm run build
cd ..\..
.\start.bat
```

## Development mode

```powershell
.\setup.bat -Development
powershell -ExecutionPolicy Bypass -File .\scripts\start-reporter.ps1 -Development
```

Frontend chạy tại `http://127.0.0.1:5173`; backend và Swagger chạy tại
`http://127.0.0.1:8000` và `http://127.0.0.1:8000/docs`.

## Cấu hình

Backend tự động đọc `.env` ở thư mục gốc.

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `AUTO_REPORT_CORS_ORIGINS` | localhost:5173 | Origin được phép gọi API |
| `AUTO_REPORT_MAX_IMPORT_MB` | 50 | Giới hạn file import, 1–512 MB |
| `AUTO_REPORT_MAX_ROWS` | 50000 | Giới hạn dòng/report, 100–500000 |
| `AUTO_REPORT_ALLOW_CUSTOM_PATHS` | 0 | Cho phép đường dẫn runtime tùy chỉnh |
| `AUTO_REPORT_PREVIEW_JOBS` | 0 | Bật Preview Job API thử nghiệm |
| `AUTO_REPORT_PREVIEW_CACHE` | 0 | Cho phép Generate dùng lại Preview đã xác minh |
| `AUTO_REPORT_PREVIEW_TTL_SECONDS` | 900 | TTL artifact Preview cục bộ |
| `ELASTIC_HOST` | rỗng | Endpoint plugin Elasticsearch tùy chọn |
| `ELASTIC_INDEX` | rỗng | Index plugin Elasticsearch tùy chọn |

Elasticsearch không cần thiết cho chức năng cốt lõi. Nếu sử dụng plugin này, cài
thêm package `elasticsearch` vào venv và chỉ dùng tài khoản read-only.

Hai flag Preview vẫn mặc định tắt. Frontend tự fallback về endpoint Preview tương
thích cũ; chỉ bật hai flag khi muốn thử workflow artifact cache và đã đọc giới hạn
cold Preview trong [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Xử lý lỗi thường gặp

**Frontend production build is missing**

Chạy lại `setup.bat`, hoặc chạy `npm ci` và `npm run build` trong `apps\frontend`.

**Port 8000 hoặc 5173 đang được sử dụng**

Đóng ứng dụng đang chiếm cổng. Launcher chỉ tự tái sử dụng hoặc dọn tiến trình
Reporter Pro thuộc đúng workspace hiện tại.

**Python/Node không được tìm thấy**

Mở terminal mới sau khi cài, kiểm tra `python --version`, `node --version` và
`npm --version`, sau đó chạy lại setup.

**Cần xem lỗi backend/frontend**

Log launcher được lưu trong thư mục `logs\` và không được commit vào Git.

**Đã đóng CMD nhưng tab trình duyệt vẫn còn**

Đây là giới hạn bảo mật của trình duyệt đối với tab không được JavaScript tạo trực
tiếp. Backend vẫn đã dừng; đóng tab có thông báo “Reporter Pro đã dừng” bằng tay.
