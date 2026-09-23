# Template Administrator Guide

> **Cập nhật 06/09/2026:** pack đã phát hành có thể chọn trực tiếp trong Configure.
> Xem mục **Luồng tích hợp hiện tại** cuối tài liệu để dùng chuẩn hóa → mapping →
> validation → phát hành → Preview/Generate. Các mô tả “chưa nối Generate” bên dưới
> là ranh giới của bản trước khi người dùng duyệt tích hợp TS-15.

Tài liệu này dành cho người quản trị template trong môi trường cá nhân/team. Nó
mô tả đường thử nghiệm Template Studio; không thay đổi cách Reporter Pro tạo các
báo cáo `full`, `server_only`, `client_only` và những report type mặc định khác.

## Trạng thái và phạm vi

- Template Studio hiện diện sẵn trong sidebar và backend mặc định chạy với
  `AUTO_REPORT_TEMPLATE_PACKS=1`.
- Có thể đặt flag thành `0` rồi khởi động lại để cô lập khẩn cấp API quản trị;
  thao tác này không ảnh hưởng Legacy Renderer.
- Việc bật flag chỉ mở API quản trị. Template Pack **không xuất hiện trong
  Generate** và catalog trả `selectionIntegrated: false`.
- “Active” chỉ là phiên bản được chọn bên trong catalog thử nghiệm. Legacy
  Renderer và các template mặc định vẫn là đường tạo báo cáo duy nhất.
- Chưa dùng template khách hàng thật làm fixture công khai. Không đưa dữ liệu,
  template hoặc report của khách hàng vào Git.

## Vai trò tối thiểu

Trong bản local/team chưa có authentication hoặc RBAC. Team phải phân công bằng
quy trình:

| Vai trò | Trách nhiệm |
|---|---|
| Author | Phân tích template, tạo workspace và mapping semantic |
| Reviewer | Kiểm tra DOCX baseline, xác nhận đúng checksum và phê duyệt trực quan |
| Publisher | Chạy lượt xác minh thứ hai và publish với catalog revision hiện tại |

Reviewer không nên là người duy nhất tạo mapping cho template quan trọng. Trường
`actor`/`reviewer` là dấu vết vận hành, chưa phải danh tính được xác thực.

## Quy trình đưa một template mới vào catalog

```text
DOCX mới
  -> Analyze (0% approved coverage)
  -> Workspace + manual mapping
  -> 100% semantic coverage
  -> Baseline validation run
  -> Human review of exact artifact SHA-256
  -> Approve baseline
  -> Second validation run against approved baseline
  -> Publish exact verified artifact
  -> Catalog version available only inside Template Studio
```

1. Tạo Workspace Backup của Reporter Pro và lưu riêng DOCX nguồn.
2. Mở **Template Studio** trong mục **Tools** ở sidebar. Có thể mở trực tiếp
   `/?view=template-studio`; Swagger `/docs` vẫn dùng được cho kiểm tra API.
3. Gọi `POST /api/template-packs/analyze-template`. Xem anchor trùng, token,
   heading, bảng, section, header/footer và relationship; analyzer chỉ gợi ý.
4. Gọi `POST /api/template-packs/workspaces`, sau đó duyệt từng mapping bằng
   `PUT /api/template-packs/workspaces/{workspace_id}/mappings/{semantic}`.
   Luôn gửi `expectedRevision`; HTTP 409 nghĩa là phải tải revision mới rồi áp
   dụng lại thay đổi, không ghi đè mù.
5. Chỉ tiếp tục khi backend báo `mapping_complete` và coverage 100%. Không sửa
   file workspace hoặc phần trăm coverage bằng tay.
6. Tạo baseline bằng
   `POST /api/template-packs/workspaces/{workspace_id}/validation-runs`.
7. Tải artifact qua
   `GET /api/template-packs/workspaces/{workspace_id}/validation-runs/{run_id}/artifact`.
   Ghi SHA-256, mở DOCX và kiểm tra heading, bảng, numbering, section, hình ảnh,
   page break, dữ liệu và nội dung không mong muốn.
8. Phê duyệt đúng artifact checksum qua endpoint `approve-baseline`, sau đó tạo
   lượt validation thứ hai với baseline vừa duyệt.
9. Chỉ publish lượt thứ hai đã đạt fixture, integrity, structural và visual gate.
   Gửi đồng thời workspace revision và catalog revision hiện tại.
10. Xác minh catalog, export draft để lưu hồ sơ và chạy regression/golden test
    ngoài dữ liệu khách hàng trước khi đề xuất pilot.

## Quản lý version và thay đổi

- `packId + version` là bất biến. Nội dung khác phải dùng version mới.
- Clone workspace để bắt đầu thay đổi lớn; archive bản cũ thay vì xóa.
- Export `.rptdraft` để chuyển draft giữa máy. Import luôn tạo workspace identity
  mới và kiểm tra manifest/checksum.
- Catalog install/activate/rollback đều dùng `expectedRevision`. Khi revision cũ,
  tải snapshot mới và đánh giá lại lựa chọn.
- Retention luôn preview trước, chỉ chuyển draft đủ điều kiện vào quarantine và
  có thể restore; API không cung cấp permanent delete.

## Xử lý sự cố

| Hiện tượng | Xử lý an toàn |
|---|---|
| API trả 404 | Kiểm tra `AUTO_REPORT_TEMPLATE_PACKS`; đặt `1` và khởi động lại |
| HTTP 409 | Tải workspace/catalog mới, so sánh thay đổi rồi thử lại |
| Workspace/checksum lỗi | Dừng publish; dùng bản export/backup đã xác minh |
| Baseline khác DOCX đã xem | Không approve; tải lại artifact và đối chiếu SHA-256 |
| Catalog primary hỏng | Gọi recovery preview, kiểm tra toàn bộ pack payload rồi dùng token một lần |
| Profile Renderer lỗi | Giữ lỗi hiển thị rõ; không fallback sang layout khác |
| Cần report gấp | Đặt flag về `0`, khởi động lại và dùng luồng Legacy Renderer mặc định |

Không chỉnh trực tiếp `apps/backend/data/template_studio/catalog/index.json`,
checkpoint hoặc `.rptpack`. Catalog có seal, kiểm tra payload và khóa liên tiến
trình; sửa tay làm mất chuỗi kiểm chứng.

## Gate trước pilot

Tạo một manifest theo [Template Studio pilot evidence contract](TEMPLATE_PILOT.md)
cho từng template, chạy validator với `--evidence-root`, sau đó chạy
`preflight_template_pilot.py` để đối chiếu record evidence thật. Khi có đủ ba
template, chạy `preflight_template_pilot_matrix.py` cho full/server/client. Trạng
thái `ready` hoặc `matrixReady` chỉ xác nhận hồ sơ đủ bằng chứng để review; chúng
không bật tích hợp hoặc Generate.

- Template và dữ liệu được phép sử dụng, đã loại thông tin nhạy cảm khỏi fixture.
- Mapping 100%; hai lượt validation cùng workspace/template checksum.
- Reviewer đã xem đúng artifact checksum và lưu biên bản.
- Golden/structural diff, integrity và visual review đạt.
- Benchmark đúng report type và quy mô dự kiến đạt.
- Recovery/rollback đã thử trên bản sao workspace.
- Full quality gate `scripts/check.ps1` đạt.
- Người dùng đã duyệt việc tích hợp opt-in. Cho tới lúc đó không nối pack vào
  dropdown hoặc Generate.

Xem thêm [kiến trúc Template Pack](TEMPLATE_PACKS.md),
[migration/rollback runbook](TEMPLATE_STUDIO_MIGRATION_ROLLBACK.md) và
[trạng thái triển khai](TEMPLATE_STUDIO_STATUS.md).
# Luồng tích hợp hiện tại — cập nhật 06/09/2026

Hướng dẫn thao tác và bài tự kiểm tra có bảng mapping mẫu:
[Template Studio User Guide](TEMPLATE_STUDIO_USER_GUIDE.md).

1. Mở **Template Studio → Quản lý → Template mới**, chọn DOCX và report type,
   phân tích rồi tạo workspace.
2. Nếu Word chưa có anchor, chọn **Chuẩn hóa cấu trúc**. Với mỗi nội dung bắt buộc,
   chọn đúng đoạn/bảng: **Chèn phía sau** giữ nguyên đoạn đã chọn; **Thay nội dung**
   đánh dấu đoạn/bảng đó để thay bằng dữ liệu khi xuất. Bản chuẩn hóa là bản sao,
   không ghi đè nguồn. Phải rà soát dữ liệu mẫu cũ ở ngoài các vùng đã chọn.
3. Trong **Ánh xạ**, chọn từng block, anchor và cột (`column:1`, `column:2`, …),
   rồi **Duyệt ánh xạ**. Mọi block bắt buộc phải đạt 100%; không có nút bỏ qua lỗi.
4. **Rà soát template → Tạo báo cáo thử**. Chọn Tracking CSV hoặc fixture JSON.
   Tạo baseline, tải DOCX, mở Word kiểm tra bố cục/nội dung và nhập người duyệt.
   Chỉ duyệt khi chính bạn đã xem đúng tài liệu được tải.
5. Chạy lượt xác minh trên cùng fixture, tải/duyệt kết quả, **Phát hành vào Catalog**.
6. Quay lại Reporter Pro, import dữ liệu → **Cấu hình → Template báo cáo**.
   Chọn phiên bản có hậu tố **(Studio)** đúng report type; Preview rồi Generate
   như bình thường. Chọn lại “Template mặc định” để quay về luồng khách hàng cũ.

Các pack không tự trở thành mặc định. Thay lựa chọn “active” trong Catalog không
đổi report đang làm. Plugin tùy chỉnh tắt khi chọn pack; template lỗi hoặc checksum
không khớp bị chặn thay vì xuất âm thầm bằng template khác.

**Giới hạn chuẩn hóa:** v1 chọn đoạn/bảng cấp body. Text box, layout lồng, header/
footer động cần chuẩn hóa trước trong Word. Bảng thay thế cần số cột khớp mapping;
định dạng và nội dung đặc thù khách hàng luôn phải được duyệt bằng DOCX thực tế.

---
