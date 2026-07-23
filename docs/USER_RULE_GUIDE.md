# Hướng dẫn thêm rule phát hiện từ cột Note

Reporter Pro chỉ kết luận một máy có dấu hiệu bất thường khi rule khớp với bằng chứng trong dữ liệu đầu vào. Nếu tên mã độc, công cụ tấn công hoặc hành vi mới chỉ xuất hiện trong cột `Note`, người dùng có thể bổ sung rule ngay trên giao diện mà không cần sửa mã nguồn.

## Cách nhanh: tạo rule cho từ khóa mới

1. Import file tracking và chuyển tới bước **Configure**.
2. Mở **Rule Manager**, chọn **Thêm rule**.
3. Đặt tên dễ truy vết, ví dụ `Malware tools from tracking note`.
4. Chọn **Phân loại: Bất thường**. Đây là lựa chọn làm đầu ra của máy khớp rule trở thành **Ghi nhận dấu hiệu bất thường**.
5. Trong **Tìm trong trường**, chọn **Ghi chú**. Chỉ chọn thêm **Kết quả** hoặc **Phần mềm** khi dữ liệu thực tế có bằng chứng ở các trường đó.
6. Nhập các tên mới vào **Từ khóa cần khớp**, ngăn cách bằng dấu phẩy hoặc xuống dòng. Ví dụ:

   ```text
   cobalt strike
   reverse shell
   emotet
   hawkeye
   ```

7. Nhập cụm từ phủ định hoặc trường hợp đã được phê duyệt vào **Loại trừ khi có**, ví dụ:

   ```text
   false positive
   đã xác minh an toàn
   được phê duyệt
   authorized
   ```

8. Chọn **Thử trên dữ liệu hiện tại**. Kiểm tra số dòng khớp, hostname, trường bằng chứng và từ khóa khớp.
9. Chỉ chọn **Lưu rule** khi danh sách máy khớp đúng với kết quả mong muốn; sau đó chạy Preview trước khi Generate.

Rule không phân biệt chữ hoa/chữ thường và chỉ cần khớp một từ khóa trong danh sách. `Note` gốc vẫn được giữ trong report làm bằng chứng; rule không tự suy diễn khi không có chuỗi khớp.

## Duy trì một rule malware chung cho team

Rule mặc định không sửa trực tiếp được. Khi team muốn quản lý toàn bộ từ khóa malware trong một rule duy nhất:

1. Chọn **Nhân bản** rule `Malware evidence detected`.
2. Sửa bản sao, bổ sung các từ khóa mới và chạy thử trên dữ liệu hiện tại.
3. Lưu bản sao với tên có phiên bản hoặc phạm vi rõ ràng, ví dụ `Team malware evidence v2`.
4. Tắt rule mặc định trong preset/report đang dùng để tránh hai rule cùng tạo finding cho một bằng chứng.
5. Export gói rule JSON để các thành viên khác import; dùng cảnh báo rule chồng lấn trước khi generate.

Nếu chỉ cần phát hiện vài từ khóa mới, tạo một rule nhỏ chỉ chứa các từ khóa chưa có sẽ dễ kiểm soát hơn. Không lặp lại các từ khóa đã được rule mặc định nhận diện.

## Kiểm tra trước khi xuất báo cáo

- Số máy **Ghi nhận dấu hiệu bất thường** phải bằng số máy có evidence khớp rule, không phải số lần từ khóa xuất hiện.
- Một máy có nhiều từ khóa vẫn chỉ được tính là một máy bất thường trong thống kê tài sản.
- Dùng **Cần xác minh** thay vì **Bất thường** nếu tên công cụ chưa đủ để kết luận.
- Luôn thêm cụm phủ định phù hợp để tránh các note như “không phát hiện”, “false positive” hoặc “được phê duyệt”.
- Preview và đối chiếu bảng tổng hợp với file tracking trước khi tạo bản chính thức.

## Ví dụ kết quả

| Dữ liệu đầu vào | Phân loại rule | Kết luận trong report |
|---|---|---|
| Note chứa `Cobalt Strike` | Bất thường | Ghi nhận dấu hiệu bất thường |
| Note chứa `Proxifier`, chưa xác minh mục đích | Cần xác minh | Ghi nhận dấu hiệu cần xác minh |
| Không có evidence khớp rule | — | Không phát hiện dấu hiệu bất thường |
