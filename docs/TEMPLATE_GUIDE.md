# Template DOCX

Reporter Pro quản lý template theo report type: `full`, `server_only`,
`client_only`, `summary`, `technical` và `incident_response`.

## Chọn và upload

Khi upload, engine phân tích token, section và table bắt buộc rồi phân loại:

- **Compatible:** đủ cấu trúc bắt buộc.
- **Compatible with warnings:** có thể tạo report nhưng thiếu phần tùy chọn.
- **Incompatible:** thiếu cấu trúc quan trọng và không thể đặt làm mặc định.

Thông báo compatibility chỉ rõ token hoặc section cần sửa. Luôn tạo một phiên bản
template mới thay vì ghi đè file đang dùng cho dự án quan trọng.

## Nguyên tắc chỉnh template

- Giữ nguyên token/marker do engine yêu cầu.
- Không tách một token qua nhiều Word run bằng cách định dạng một phần ký tự.
- Giữ heading, table header và page break của section động.
- Dùng style Word thay vì format thủ công từng paragraph.
- Kiểm tra header/footer, numbering và relationship của hình ảnh sau khi chỉnh.
- Chọn đúng report type; template Full không mặc nhiên là Server hoặc Client.

## Kiểm tra trước khi phát hành

1. Upload và xác nhận trạng thái compatibility.
2. Tạo report bằng sample chuẩn của loại tương ứng.
3. Mở DOCX trong Word/LibreOffice và kiểm tra mục lục, bảng, hình, page break.
4. Chạy golden DOCX tests để phát hiện thay đổi cấu trúc ngoài ý muốn.

```powershell
apps\backend\.venv\Scripts\python.exe -m unittest -v tests.test_template_schema tests.test_template_categories tests.test_docx_golden
```

Template tùy chỉnh có thể chứa thông tin tổ chức. Không commit logo hoặc nội dung
khách hàng khi chưa được phép.
