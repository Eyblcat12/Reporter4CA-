# Đóng góp cho Reporter Pro

Cảm ơn bạn đã giúp Reporter Pro tốt hơn. Dự án ưu tiên thay đổi có phạm vi rõ,
kiểm thử được và không làm mất tính tương thích của template/report hiện có.

## Quy trình

1. Fork repository và tạo branch từ `main`.
2. Cài môi trường bằng `setup.bat -Development`.
3. Thực hiện một thay đổi tập trung; bổ sung test cho hành vi mới hoặc lỗi đã sửa.
4. Chạy quality gate trước khi mở pull request.
5. Mô tả dữ liệu kiểm thử, ảnh hưởng template và cách khôi phục nếu có migration.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
cd apps\frontend
npm run test:e2e
```

## Nguyên tắc thay đổi

- Không commit dữ liệu khách hàng, report thật, `.env`, database, log hoặc API key.
- Không thay template mặc định mà thiếu golden DOCX regression test.
- Thay đổi rule phải nêu rõ điều kiện, severity, remediation và bằng chứng.
- API mới cần validation, thông báo lỗi có thể hành động và integration test.
- UI mới cần kiểm thử trạng thái thành công, lỗi và phục hồi tương ứng.
- Plugin ngoài phải là tùy chọn; lỗi plugin không được làm hỏng workflow cốt lõi.

## Pull request

Pull request nên nhỏ, có tiêu đề mô tả kết quả và liên kết issue nếu có. Nếu thay
đổi giao diện, đính kèm ảnh trước/sau. Nếu ảnh hưởng hiệu năng, ghi lại dataset và
cấu hình máy để kết quả có thể lặp lại.
