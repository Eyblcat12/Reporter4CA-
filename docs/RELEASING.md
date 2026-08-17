# Quy trình phát hành

Reporter Pro dùng Semantic Versioning `MAJOR.MINOR.PATCH`. File `VERSION` là mốc
review chính; backend, backup manifest và frontend package phải đồng bộ với file
này trước khi tạo tag.

## Chọn version

- `PATCH`: sửa lỗi tương thích ngược, không thêm workflow đáng kể.
- `MINOR`: thêm tính năng tương thích ngược, report type hoặc workflow mới.
- `MAJOR`: thay đổi API/template/schema không tương thích và cần migration rõ ràng.

## Chuẩn bị release

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set-version.ps1 -Version 2.2.0
```

Sau đó cập nhật `CHANGELOG.md`, tạo `docs/releases/v2.2.0.md`, kiểm tra diff và chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-release.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

Commit version/release metadata trước khi tag. Không di chuyển hoặc ghi đè tag đã
phát hành; nếu release sai, sửa bằng version mới.

## Tạo và đẩy tag

```powershell
git tag -a v2.2.0 -m "Reporter Pro v2.2.0"
powershell -ExecutionPolicy Bypass -File .\scripts\verify-release.ps1 -RequireTag
git push github main
git push github v2.2.0
```

Tag `vMAJOR.MINOR.PATCH` kích hoạt `.github/workflows/release.yml`. Workflow cài
dependency từ lockfile có hash, chạy toàn bộ quality gate, tạo source ZIP/TAR.GZ,
tạo Windows prebuilt ZIP, tạo `SHA256SUMS.txt` rồi publish GitHub Release bằng
release note đã commit. Gói `windows-prebuilt.zip` chứa production frontend đã build
từ cùng commit; chạy `setup-prebuilt.bat` để chỉ cài Python dependency có hash mà
không cần Node/npm. Đây là portable bundle, không phải offline installer.

## Xác minh và rollback

- So sánh SHA-256 file tải về với `SHA256SUMS.txt`.
- Mở `BUNDLE-MANIFEST.json` trong Windows bundle và kiểm tra version/git commit.
- Clone sạch tag và chạy `setup.bat` trước khi thông báo release ổn định.
- Tạo Workspace Backup trước khi nâng cấp.
- Rollback source bằng tag cũ; restore dữ liệu chỉ sau khi dry-run xác nhận schema
  tương thích.
