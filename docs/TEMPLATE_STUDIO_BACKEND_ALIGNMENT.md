# Template Studio — hoàn thiện UI cũ và hợp đồng backend

Ngày bắt đầu: 07/09/2026. Người dùng chốt UI cũ; dừng phát triển thiết kế Stitch.
Không thay template Full/Server/Client, Legacy Renderer hoặc hợp đồng Tracking.

Kế hoạch tổng thể cập nhật 08/09: [15 task hoàn thiện Template Studio](TEMPLATE_STUDIO_COMPLETION_PLAN.md).
Tài liệu này tiếp tục ghi bằng chứng các đợt sửa UI/API, không thay thế backlog tổng thể.

## Thứ tự triển khai đã duyệt

1. Rà soát từng thao tác UI/API, dữ liệu gửi/nhận và test.
2. Trạng thái lưu/duyệt, revision, draft, lỗi mạng và phản hồi lỗi thời.
3. Anchor duy nhất, mapping nguồn–đích, ngữ cảnh và phần chưa hỗ trợ.
4. Chuẩn hóa copy-only, preview thay đổi, phân tích lại nguồn mới.
5. Rà soát, validation evidence, stale checks và publish version.
6. E2E với Tracking 30/50 máy và template tổng hợp; regression luồng cũ.
7. Hướng dẫn tự kiểm tra và nghiệm thu DOCX thực tế.

## Đối chiếu ban đầu (không phải kiểm toán hoàn tất)

| Thao tác | API / trạng thái quan sát | Kết quả đợt đầu |
|---|---|---|
| Tải danh sách/chọn workspace | GET workspaces + GET workspace | Thêm generation guard: phản hồi đọc cũ không ghi đè lựa chọn mới |
| Duyệt mapping | PUT mappings, expectedRevision | Không đưa phản hồi workspace A vào workspace B vừa chọn; không hạ revision đã hiển thị |
| Bỏ mapping | POST mapping/remove | Đồng bộ revision/coverage/status vào cả workspace và summary thư viện |
| Hủy request đọc | fetch AbortError | Giữ nguyên AbortError thay vì biến thành mất kết nối |
| Không tìm thấy nguồn/workspace | HTTP 404 | Không kết luận mặc định subsystem bị tắt; giữ detail của backend nếu có |
| Revision conflict | HTTP 409 | Giữ cờ conflict và thông báo backend; chưa hoàn tất đối chiếu draft |

## Bằng chứng kiểm thử đợt đầu

Lượt chạy 07/09/2026 12:14: lint đạt; Vitest phát hiện và chạy 114 tests/26 files,
tất cả đạt; production build 1.935 modules đạt. Đây là số thực tế của working
tree ở lượt này, không tái sử dụng số 120 của checkpoint UI so sánh trước đó.
Chưa chạy backend/E2E/golden trong đợt sửa request này.

Bảy test mới trong templateStudioApi.test.js và TemplateStudioRoute.requests.test.jsx:
hủy request; 404; 409; hai lựa chọn trả về ngược thứ tự; lỗi đọc đến muộn;
approval đến muộn sau đổi workspace; summary sau bỏ mapping. Test dùng mock API,
chưa phải E2E backend thật.

## Vấn đề tiếp theo cần giải quyết

- Draft hiện giữ trong bộ nhớ theo workspace + SHA nguồn Word + semantic; chưa
  tồn tại qua refresh/đóng trang. Cần thêm cảnh báo rời trang khi chưa lưu.
- Timeout mutation chưa có quy trình đọc lại để xác định kết quả trước retry.
- Kiểm tra khả năng thao tác hai lần trước React render; không chỉ dựa disabled UI.
- Rà soát retry/reload khi conflict để không bỏ draft hoặc gán revision mới mà
  chưa có quyết định rõ ràng của người dùng.
- Rà soát toàn bộ analysis/normalization/validation/publish chưa hoàn tất.

## Đợt 2 — draft và revision (07/09/2026)

- Đóng/mở inspector hoặc đổi section không xóa draft đang chỉnh; nguồn Word mới
  dùng khóa riêng, không tái sử dụng mapping nháp của nguồn cũ.
- Draft giữ revision gốc. Khi workspace có revision mới, UI chặn duyệt và cho
  người dùng chủ động bỏ draft để dùng dữ liệu mới; chưa hỗ trợ merge draft.
- API nhận expectedRevision của draft, không tự gán revision workspace mới.
- Trạng thái lưu/lỗi chỉ cập nhật editor tương ứng; sửa trường xóa trạng thái
  “Đã lưu”. Khóa đồng bộ ngăn gọi mutation lặp trong khi request còn chạy.
- Chặn ánh xạ trùng cột và đồng bộ định dạng column:1 đến column:999 với backend.

Kiểm thử 13:22 ngày 07/09/2026: **119 tests/26 files đạt**, ESLint đạt,
production build 1.935 modules đạt; diff-check các file đã sửa đạt.
Năm test bổ sung kiểm tra mở lại draft/đổi section, stale revision, nguồn Word
mới, cột trùng và truyền revision gốc. Đây là component/API-mock tests,
chưa phải E2E backend thật. Suite còn warning React act ở RuleManager và
DashboardHome; không coi log đã hoàn toàn sạch.

Đợt này không sửa backend hoặc template khách hàng; ba module report_generator,
report_orchestrator và report_snapshot không có diff. Chưa commit/push.

## Ranh giới bàn giao

Đợt đầu chỉ sửa frontend điều phối request và lỗi API của UI cũ, chưa sửa backend,
không migrate database, không ghi thử nguồn khách hàng. UI Next cũ chưa xóa,
không coi nó là hướng thiết kế tiếp tục. Các số test lịch sử không thay thế
backend/E2E/golden gate cho toàn bộ kế hoạch.
