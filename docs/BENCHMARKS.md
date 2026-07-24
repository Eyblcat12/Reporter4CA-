# Benchmark Reporter Pro

Tài liệu này ghi lại các phép đo đã chạy thực tế để người dùng hiểu đúng khả
năng hiện tại của Reporter Pro. Đây là benchmark trên một workstation, không
phải cam kết hiệu năng cho mọi máy hoặc mọi template.

## Môi trường thử nghiệm

| Thành phần | Cấu hình |
|---|---|
| Thiết bị | Lenovo 82RD |
| CPU | AMD Ryzen 7 6800H, 8 nhân / 16 luồng |
| RAM | 16 GB cài đặt, khoảng 15,2 GiB khả dụng cho hệ điều hành |
| Hệ điều hành | Windows 64-bit |
| Runtime | Python 3.12, Node.js 20+ |
| Giới hạn giám sát | Peak RSS 3.072 MB, timeout 600 giây/job lớn |
| Đầu ra | Một file DOCX, giữ nguyên template được chọn |

Đợt đo được thực hiện trong tháng 07/2026. Số liệu được lấy từ JSON kết quả do
supervisor của benchmark ghi lại, không ước lượng từ cảm nhận giao diện.

## Bộ dữ liệu 50.000 máy

Fixture có 50.000 dòng, gồm 20.000 server và 30.000 client. Pipeline đã:

- đọc đủ 50.000 dòng;
- parse và phân loại đủ 20.000 server / 30.000 client;
- chạy data-quality trên toàn bộ dữ liệu;
- xác nhận không mất hostname đầu hoặc cuối;
- không phát hiện dòng lỗi, hostname trùng, IP sai, thiếu OS hoặc thiếu result
  trong fixture chuẩn.

Việc đọc và kiểm tra 50.000 dòng hoàn tất trong khoảng 20 giây. Con số này
không đồng nghĩa engine hiện có thể đưa chi tiết 50.000 máy vào một DOCX.
Phần tốn tài nguyên nhất là tạo hàng nghìn heading và table theo template Word.

## Kết quả tạo một DOCX chi tiết

Các mốc dưới đây dùng report `server_only` và cùng input 50.000 dòng; cột
“máy trong DOCX” là số asset được đưa vào phần chi tiết.

| Máy trong DOCX | Trạng thái | Tổng thời gian | Peak RSS | Kích thước | Kiểm tra cấu trúc |
|---:|---|---:|---:|---:|---|
| 1.000 | Hoàn tất | 93,8 giây | 848,1 MB | 1,17 MiB | ZIP/đầu-cuối hợp lệ |
| 2.000 | Hoàn tất | 188,2 giây | 1.575,6 MB | 2,31 MiB | ZIP/đầu-cuối hợp lệ |
| 3.000 | Hoàn tất | 375,2 giây | 2.433,3 MB | 3,45 MiB | ZIP/đầu-cuối hợp lệ |
| 3.500 | Hoàn tất | 419,4 giây | 2.661,1 MB | 4,01 MiB | ZIP/đầu-cuối hợp lệ |
| 3.750 | Hoàn tất | 414,1 giây | 2.927,8 MB | 4,30 MiB | ZIP/đầu-cuối hợp lệ |
| 4.000 | Dừng bảo vệ | 404,2 giây | 3.099,0 MB | — | Vượt giới hạn RAM |
| 5.000 | Dừng bảo vệ | 556,5 giây | 3.072,7 MB | — | Vượt giới hạn RAM |
| 20.000 | Dừng bảo vệ | 600,2 giây | 710,1 MB | — | Hết timeout khi đang generate |

Mốc Full 3.000 máy cũng hoàn tất: 376,6 giây, peak RSS 2.258,0 MB, file
3,48 MiB, 3.006 bảng và 3.016 heading.

### Kết luận hiện tại

- Pipeline import/quality tương thích với dự án 50.000 máy.
- Với template chi tiết hiện tại và watchdog 3 GB, mốc đã xác nhận ổn định
  trong một DOCX là 3.750 máy.
- 4.000 máy không được xem là “hỏng ngẫu nhiên”: supervisor chủ động hủy khi
  RAM vượt ngưỡng để bảo vệ workstation.
- Dự án lớn hơn nên tách volume/report hoặc chờ tối ưu engine theo hướng giảm
  số object Word giữ đồng thời trong RAM. Không nên tăng giới hạn một cách mù
  quáng vì có thể làm máy cá nhân mất phản hồi.

## Soak test job nền

Soak test dài 120 phút chạy workload 500 dòng/job:

| Chỉ số | Kết quả |
|---|---:|
| Job gửi vào | 83 |
| Hoàn tất | 66 |
| Failed theo kịch bản | 6 |
| Cancelled theo kịch bản | 11 |
| Timeout | 0 |
| Lỗi ngoài dự kiến | 0 |
| Dedup mismatch | 0 |
| P50 | 66,0 giây |
| P95 | 214,5 giây |
| Peak RSS | 524,6 MB |
| RSS tăng từ đầu đến cuối | 18,4 MB |
| Kết luận supervisor | Pass |

Các job `failed` và `cancelled` ở đây là nhánh được chủ động đưa vào kịch bản để
kiểm tra cleanup và phục hồi; `unexpectedFailures` bằng 0.

## Cách tái lập

Soak test:

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\soak_report_jobs.py `
  --profile long --duration-minutes 120 --rows 500
```

Hướng dẫn đầy đủ: [testing/soak-test.md](testing/soak-test.md).

Benchmark DOCX lớn hiện được giữ như một quality exercise có giám sát thay vì
chạy trong CI thông thường, vì mỗi mốc có thể cần nhiều phút và vài GB RAM.
Khi công bố số liệu mới, cần ghi cùng fixture, template, cấu hình máy, watchdog,
timeout và JSON kết quả để việc so sánh có ý nghĩa.
