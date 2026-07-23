# Hướng dẫn sử dụng

## 1. Bắt đầu một report

Từ màn hình đầu, chọn **File**, **Raw text** hoặc **Sample**. File tracking có thể
là Excel, CSV hoặc JSON. Reporter Pro hiển thị preview và đề xuất mapping cột; hãy
kiểm tra hostname, IP, OS, loại tài sản, result và note trước khi tiếp tục.

## 2. Kiểm tra chất lượng dữ liệu

Bảng quality summary cho biết số dòng hợp lệ, lỗi/cảnh báo, hostname trùng, IP
không hợp lệ và trường bắt buộc còn thiếu. Nhấn vào chỉ số để lọc các dòng liên
quan. Lỗi nghiêm trọng cần được sửa trước khi generate; cảnh báo không bắt buộc có
thể được chấp nhận sau khi xem xét.

## 3. Xác nhận finding

Rule engine đánh giá nội dung tracking và tạo finding có nguồn. Nếu note thực tế
chưa được nhận diện, thêm hoặc chỉnh rule trước khi xuất. Xem
[USER_RULE_GUIDE.md](USER_RULE_GUIDE.md) để hiểu điều kiện và kết quả đầu ra.

Không nên dùng một keyword quá chung làm bằng chứng bất thường. Rule cần đủ cụ thể
để tránh biến thông tin vận hành bình thường thành finding.

## 4. Cấu hình report

Chọn một trong sáu report type:

- **Full:** cả server và client.
- **Server:** chỉ tài sản server.
- **Client:** chỉ tài sản client/workstation.
- **Summary:** tổng quan ngắn cho quản lý.
- **Technical:** chi tiết kỹ thuật, finding và evidence.
- **Incident Response:** timeline, IoC và hoạt động xử lý sự cố.

Chọn template tương thích, preset, tiêu đề và metadata dự án. Template incompatible
không thể đặt làm mặc định.

## 5. Preview và generate

Preview giúp kiểm tra nội dung trước khi tạo file. Khi generate, ứng dụng tạo một
job có tiến độ; có thể đóng modal và quay lại sau. Job hoàn thành được ghi vào lịch
sử và dashboard. Nếu hủy hoặc lỗi, file tạm được dọn an toàn.

## 6. Lưu và bảo vệ dữ liệu

Report, database, log và `.env` chỉ nằm trên máy cục bộ và không được Git theo dõi.
Sử dụng Workspace Backup trước các thay đổi lớn về template hoặc rule. Không chia
sẻ backup nếu chưa loại bỏ dữ liệu nhạy cảm.
