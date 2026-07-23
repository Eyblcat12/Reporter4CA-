# Tác vụ tạo report có tiến độ và hủy

## Phạm vi

Thiết kế local-first này đã được nối vào runtime. Endpoint `/api/generate` cũ vẫn được
giữ để tương thích ngược và làm đường lui kỹ thuật; giao diện chính sử dụng job API.

## Luồng đề xuất

1. Người dùng nhấn **Tạo báo cáo**.
2. Backend trả `202 Accepted` cùng `jobId`, không giữ HTTP request lâu.
3. Frontend theo dõi `GET /api/report-jobs/{jobId}` mỗi 750 ms.
4. Job lần lượt qua `queued`, `running`, rồi `completed`, `failed` hoặc `cancelled`.
5. Người dùng có thể đóng panel; job tiếp tục cục bộ và xuất hiện lại khi mở panel.
6. Khi hoàn thành, frontend tải file từ `GET /api/report-jobs/{jobId}/download`.

## API đã triển khai

- `POST /api/report-jobs`: tạo job, trả `jobId` và phát hiện request trùng.
- `GET /api/report-jobs`: danh sách job gần đây trong phiên local.
- `GET /api/report-jobs/{jobId}`: trạng thái, phase, progress và thời gian.
- `DELETE /api/report-jobs/{jobId}`: yêu cầu hủy; không xóa lịch sử.
- `GET /api/report-jobs/{jobId}/download`: tải kết quả đã hoàn thành.

## Quy tắc an toàn

- Tối đa một job chạy và hai job chờ trên máy cá nhân theo mặc định.
- Fingerprint từ rows, settings và template ngăn tạo job trùng khi double-click.
- Cancel là cooperative: kiểm tra giữa các phase, không kết thúc process Word cưỡng bức.
- File DOCX được ghi vào tệp tạm, chỉ công bố đường dẫn tải sau khi finalize thành công.
- Mọi nhánh failed/cancelled đều dọn tệp tạm, kể cả lỗi xảy ra giữa bước lưu/finalize.
- Lịch sử chỉ ghi một record cuối cùng cho mỗi job.
- Job hiện lưu trong bộ nhớ của phiên backend. Nếu backend bị dừng cưỡng bức, job không
  được phục hồi; đây là giới hạn chủ động của phạm vi local/team hiện tại.

## Quyết định UX đã chốt

- Panel tiến độ dạng popover ở góc dưới, có thể thu gọn trong khi job tiếp tục.
- Giới hạn mặc định một job chạy và hai job chờ.
- Trình duyệt/desktop shell hiển thị xác nhận trước khi đóng cửa sổ nếu job đang chạy.
