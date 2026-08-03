# Kế hoạch nâng cấp dashboard Reporter Pro

## Trạng thái triển khai

Dashboard V4 đã được triển khai và trở thành màn hình chính thức của frontend.
Nhánh giao diện legacy cùng feature flag rollback đã được loại bỏ sau khi người
dùng duyệt giao diện thực tế.

Dashboard hiện dùng API tổng hợp phía server trên toàn bộ dữ liệu của khoảng thời
gian được chọn. Schema v3 lưu trạng thái thành công/thất bại, thời gian xử lý và
mã lỗi an toàn. KPI gồm Reports, Assets và Success; biểu đồ hỗ trợ 30/90/180 ngày.
Lịch sử client cũ vẫn là fallback an toàn nếu API tổng hợp tạm thời không phản hồi.

## Mục tiêu

Biến màn hình chào hiện tại thành dashboard local-first hữu ích cho cá nhân/team,
nhưng vẫn giữ ba thao tác chính: import file, nhập text và dùng dữ liệu mẫu.

## Bố cục đề xuất

1. Header gọn với lời chào, phạm vi thống kê và các thao tác nhanh.
2. Ba KPI có ý nghĩa: báo cáo đã tạo, tài sản đã đánh giá và tỷ lệ thành công.
3. Biểu đồ hoạt động theo thời gian, hỗ trợ 30 ngày, 90 ngày và 6 tháng.
4. Danh sách báo cáo gần đây, hiển thị loại, số tài sản và thời điểm tạo.
5. Empty state cho người dùng mới, không hiển thị biểu đồ giả khi chưa có lịch sử.

## Dữ liệu backend đã hoàn thành

- Đã thêm trạng thái thành công/thất bại, thời gian xử lý và mã lỗi vào `report_history`.
- Endpoint `GET /api/dashboard/summary?days=30|90|180` trả KPI, chuỗi thời gian
  và danh sách hoạt động gần đây.
- Aggregate trực tiếp trong SQLite; không thêm PostgreSQL, cache server hoặc job
  nền ở giai đoạn này.
- Các metric chỉ lấy từ dữ liệu thật, không tạo "điểm sức khỏe" chủ quan.

## Thay đổi frontend đã hoàn thành

- Dùng `DashboardHome.jsx` và CSS riêng khi chưa import dữ liệu.
- Quick actions nối trực tiếp vào logic import hiện có.
- Thêm chọn khoảng thời gian 30 ngày, 90 ngày và 6 tháng.
- Hỗ trợ dark/light theme, VI/EN, responsive 320 px và reduced motion.
- Khi API lỗi, dashboard vẫn hiển thị quick actions và empty state an toàn.

## Trình tự triển khai

1. [x] Chốt bố cục demo và metric với người dùng.
2. [x] Migration schema v3 cho trạng thái/thời gian xử lý report.
3. [x] Viết aggregate và test endpoint dashboard.
4. [x] Xây component React từ demo đã duyệt.
5. [x] Giữ fallback an toàn cho empty/error state.
6. [x] Chạy backend regression và frontend production build.

E2E tự động cho workflow lõi đã được đưa vào GitHub Actions. Kiểm tra trực quan có hệ
thống ở 320 px và dark/light tiếp tục được mở rộng theo từng thay đổi giao diện.

## Tiêu chí hoàn thành

- Dashboard tải dưới 300 ms với 10.000 bản ghi lịch sử trên máy local.
- Không ảnh hưởng luồng import/configure/export hiện tại.
- Metric khớp trực tiếp với `report_history` và có test regression.
- Không có horizontal overflow ở 320 px.
- Frontend production build và toàn bộ backend test đạt.
