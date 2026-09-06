# Clean-source release smoke

## Mục tiêu

Gate này xác nhận source được phát hành có thể tự đứng độc lập trên một máy Windows
sạch. Kiểm thử không dùng `.venv`, `node_modules`, frontend build, database, cache,
log hoặc file cấu hình cục bộ của workspace phát triển hiện tại.

## Phạm vi xác minh

`scripts/smoke-clean-source.ps1` tạo một ZIP bằng `git archive` từ đúng Git ref,
giải nén vào workspace tạm được quản lý chặt, sau đó:

1. kiểm tra source contract và loại runtime artifact khỏi archive;
2. cài toàn bộ dependency Python từ lockfile có hash;
3. cài frontend bằng `npm ci` và tạo production build;
4. yêu cầu cả sáu bundled template prewarm thành công;
5. khởi tạo ứng dụng bằng environment vừa cài và gọi `/api/health`;
6. xác nhận `apps/frontend/dist/index.html` tồn tại.

Script ghi kết quả máy đọc được tại
`artifacts/verification/clean-source-latest.json`. Workspace tạm chỉ bị xóa khi
toàn bộ gate đạt; nếu lỗi, nó được giữ lại để điều tra. Script chỉ được phép dọn
thư mục con do chính nó tạo bên dưới `artifacts/verification`.

## Cách chạy

Chạy đầy đủ trước khi tạo release:

```powershell
./scripts/smoke-clean-source.ps1 -Ref HEAD -PythonExecutable python.exe
```

Chỉ kiểm tra ranh giới source, không cài dependency:

```powershell
./scripts/smoke-clean-source.ps1 -Ref HEAD -PythonExecutable python.exe -SkipInstall
```

Giữ workspace sau khi đạt để kiểm tra thủ công:

```powershell
./scripts/smoke-clean-source.ps1 -Ref HEAD -PythonExecutable python.exe -KeepWorkspace
```

## Điều kiện đạt

- Source archive không chứa secret hoặc runtime/customer data.
- Dependency được cài đúng từ lockfile và frontend production build thành công.
- Sáu template mặc định đều được chuẩn bị; cold fallback không được tính là đạt
  cho release gate.
- Backend health trả HTTP 200 với `status=ok`.
- Gate chạy trên exact tag trong workflow release, trước khi tạo artifact/checksum.

Gate này không chỉnh template, không gọi Template Pack Generate và không thay đổi
Legacy Renderer. `AUTO_REPORT_TEMPLATE_PACKS=1` chỉ mở authoring Studio; catalog
vẫn không được nối vào Preview/Generate.
