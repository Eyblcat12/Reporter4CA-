# Template Studio Migration and Rollback Runbook

Runbook này áp dụng cho subsystem Template Studio đang thử nghiệm. Hiện không có
database migration và không thay đổi Legacy Renderer. Mục tiêu là nâng cấp hoặc
khôi phục catalog/workspace mà luồng report mặc định luôn sẵn sàng.

## Nguyên tắc

1. Feature flag mặc định phải là `AUTO_REPORT_TEMPLATE_PACKS=0`.
2. Backup trước, preview trước, kiểm tra checksum trước khi ghi.
3. Không copy riêng `index.json`; catalog metadata và mọi `.rptpack` được tham
   chiếu là một đơn vị nhất quán.
4. Không migration tại chỗ khi Reporter Pro khác đang ghi catalog.
5. Rollback code và rollback dữ liệu là hai quyết định riêng.
6. Không nối pack vào Generate như một bước migration ngầm.

## Preflight

- Ghi lại version, Git commit, `.env` (không commit secret) và trạng thái flag.
- Dừng các job Template Studio; Legacy report job đang chạy nên hoàn tất hoặc hủy
  an toàn trước khi dừng launcher.
- Chạy `scripts/check.ps1` trên source đích.
- Tạo Workspace Backup và thử dry-run restore backup đó.
- Export các workspace quan trọng thành `.rptdraft`; ghi SHA-256 cho backup,
  draft và pack cần giữ.
- Gọi `GET /api/template-packs/catalog` và lưu revision/audit snapshot.
- Gọi `GET /api/template-packs/catalog/recovery`. Nếu checkpoint không an toàn,
  xử lý pack thiếu/sai checksum trước khi nâng cấp.

## Migration thử nghiệm

1. Giữ flag `0`, nâng cấp source/dependency và khởi động Reporter Pro.
2. Chạy smoke test Legacy Renderer với sample: import, preview, generate và mở
   DOCX. Nếu bước này lỗi, rollback source ngay; không bật Template Studio.
3. Đặt flag `1` và khởi động lại backend trong cửa sổ bảo trì.
4. Đọc catalog/workspace; không tự ghi nếu schema không được hỗ trợ.
5. Inspect các pack quan trọng, kiểm tra manifest, template checksum và validation
   evidence. Chạy fixture/golden/visual gate trên bản sao.
6. Nếu cần publish version mới, dùng workflow hai lượt và optimistic revision;
   không sửa version đã cài.
7. Xác minh `selectionIntegrated: false` và tạo lại một report mặc định.
8. Kết thúc cửa sổ bảo trì với flag `0` trừ khi pilot opt-in đã được người dùng
   phê duyệt riêng.

## Rollback code

1. Đặt `AUTO_REPORT_TEMPLATE_PACKS=0` và khởi động lại. Đây là cách cô lập nhanh
   subsystem; report mặc định vẫn dùng Legacy Renderer.
2. Checkout release/tag Reporter Pro đã xác minh và cài dependency đúng lockfile.
3. Không đưa catalog mới vào code cũ nếu schema chưa được xác nhận tương thích.
4. Chạy sample import -> preview -> generate và `scripts/check.ps1` trước khi mở
   lại cho team.

## Rollback catalog version

Khi primary catalog còn hợp lệ nhưng cần trở về pack version trước:

1. Lấy snapshot catalog và revision hiện tại.
2. Xác minh pack đích tồn tại, checksum đúng và đã publish.
3. Gọi `POST /api/template-packs/catalog/{pack_id}/rollback` với version đích,
   actor và `expectedRevision`.
4. Nếu HTTP 409, tải lại catalog và đánh giá thay đổi; không tự tăng revision.
5. Xác minh audit event và chạy lại fixture/visual check.

Lưu ý: thao tác này chỉ đổi lựa chọn nội bộ Template Studio, không đổi template
của Generate hiện tại.

## Recovery catalog bị hỏng

1. Không sửa hoặc xóa primary/checkpoint bằng tay.
2. Gọi `GET /api/template-packs/catalog/recovery`.
3. Chỉ tiếp tục khi response xác nhận checkpoint seal hợp lệ và **mọi** payload
   được tham chiếu tồn tại, đúng SHA-256.
4. Ghi lại confirmation token và trạng thái nguồn được bind vào token.
5. Gọi `POST /api/template-packs/catalog/recovery` bằng token đó ngay trong cửa
   sổ bảo trì. Token stale hoặc đã dùng phải bị từ chối.
6. Đọc lại catalog, kiểm tra revision/audit, inspect pack và chạy fixture.

Nếu recovery preview không cấp token, restore toàn bộ workspace backup đã dry-run
thành công; không ghép catalog từ các backup khác thời điểm.

## Rollback workspace/draft

- Sai mapping chưa publish: clone/export bản cần giữ, archive draft lỗi.
- Draft bị retention chuyển đi: dùng endpoint restore theo `quarantine_id`.
- Workspace corrupt/mất source: import `.rptdraft` đã kiểm checksum; identity mới
  là hành vi mong đợi.
- Restore toàn workspace: chạy dry-run, kiểm manifest/checksum và preview nội
  dung; chỉ apply khi database/template/preset/history tương thích. Nếu apply lỗi,
  cơ chế restore phải hoàn nguyên trạng thái trước đó.

## Tiêu chí hoàn tất và bằng chứng

- Default full/server/client sample tạo DOCX đạt trước và sau thao tác.
- Feature flag trở về trạng thái đã phê duyệt; mặc định repository vẫn là `0`.
- Catalog seal, checkpoint và referenced pack checksums hợp lệ.
- Không có file runtime/customer trong Git.
- Có version/commit, thời gian, actor/reviewer, revision trước/sau, checksum backup
  và kết quả test trong biên bản.
- Không có thay đổi ở template mặc định hoặc ba module Legacy Renderer do quy
  trình migration gây ra.

Nếu bất kỳ tiêu chí nào không đạt, giữ flag `0`, dùng default flow và mở incident
thay vì cố fallback hoặc tiếp tục publish.
