# Chất lượng và tính toàn vẹn báo cáo

Reporter Pro sử dụng một pipeline đánh giá thống nhất từ dữ liệu nhập đến DOCX.
Mục tiêu của pipeline là không âm thầm bỏ sót tài sản, finding hoặc kết luận.

## Trạng thái kết luận

Mỗi tài sản có đúng một kết luận chuẩn:

| Mã | Nội dung trong báo cáo | Ý nghĩa |
|---|---|---|
| `clean` | Không phát hiện dấu hiệu bất thường | Không có finding đủ evidence |
| `insufficient_data` | Không đủ dữ liệu để kết luận | Thiếu kết quả hoặc nguồn dữ liệu chưa đủ |
| `needs_review` | Ghi nhận dấu hiệu cần xác minh | Có dấu hiệu cần chuyên viên xác nhận |
| `anomaly` | Ghi nhận dấu hiệu bất thường | Có finding bất thường kèm evidence |

Thứ tự ưu tiên là `anomaly` → `needs_review` → `insufficient_data` → `clean`.
Vì vậy một finding nghiêm trọng không bị che khuất bởi cảnh báo mức thấp hơn.

## Finding và evidence

Finding do rule tạo ra chứa tối thiểu:

- ID và phiên bản rule;
- nguồn rule (`builtin`, `custom` hoặc `data_quality`);
- classification và severity;
- trường dữ liệu, giá trị gốc và nội dung đã khớp;
- remediation và MITRE mapping nếu có.

Kết quả trống không được tự động xem là sạch. Engine tạo finding
`SOURCE_RESULT_MISSING` và phân loại tài sản là `insufficient_data`.

## Integrity manifest

Trước khi render, engine tạo manifest gồm:

- report type và phạm vi server/client;
- tổng số tài sản, finding và evidence;
- số tài sản theo từng trạng thái;
- hostname, kết luận và rule tương ứng của từng tài sản.

Sau khi dựng DOCX, engine đọc cấu trúc bảng trong tài liệu và đối chiếu lại manifest.
Với báo cáo thông thường, mỗi tài sản phải có một dòng chứa đồng thời hostname và
kết luận chuẩn. Với báo cáo Technical/Incident Response, các finding còn được đối
chiếu theo hostname và rule ID.

Nếu đối chiếu không đạt, tác vụ thất bại với `ReportIntegrityError`; file không được
ghi nhận là report thành công. API download/preview trả header
`X-Report-Integrity: verified`, còn job nền trả summary trong trường `integrity`.

## Regression bắt buộc

Fixture `Tracking.csv` có 30 tài sản, trong đó 8 tài sản khai báo phát hiện mã độc.
Regression test tạo DOCX full thực tế và yêu cầu:

- 30/30 tài sản xuất hiện với kết luận tương ứng;
- đúng 8 tài sản được phân loại `anomaly`;
- integrity verification phải đạt trước khi test hoàn thành.

Ngoài regression này, sáu report type tiếp tục được kiểm tra bằng golden DOCX theo
cấu trúc heading, paragraph, table, numbering, token, section và relationship.
