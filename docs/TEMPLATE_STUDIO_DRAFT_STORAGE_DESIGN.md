# C02 — thiết kế checkpoint bản nháp cần duyệt

Ngày: 08/09/2026. Trạng thái: người dùng đã duyệt; backend checkpoint bước đầu đã triển khai.

## Checkpoint backend — 08/09

### Bổ sung 10/09 — đóng checkpoint an toàn

- POST `/api/template-packs/workspaces/{workspaceId}/editor-drafts/{draftId}/retire`:
  payload đóng gồm operationId, expectedDraftRevision, reason (`discarded`/`approved`).
- Retire lưu marker riêng, không xóa nội dung draft; list mặc định không trả checkpoint
  đã đóng. Không có permanent-delete trong đợt này.
- Lưu/retry đến muộn không thể hồi sinh ID đã đóng; retry retire cùng operation trả
  cùng kết quả; revision cũ không được bỏ bản mới hơn.
- Reason approved yêu cầu workspace hiện có cùng source và mapping thực sự khớp
  anchor/field của checkpoint (hỗ trợ đối chiếu số cột và column:N).
- API đối chiếu approval dưới workspace lock; không mutate mapping, source hay report DB.
- 12 test draft store/API và bộ mở rộng 64 backend tests đạt; Ruff check/format đạt.
  UI đã được nối trong cập nhật tiếp theo cùng ngày bên dưới.

- `EditorDraftStore`: SQLite riêng, chỉ tạo file khi thực sự gọi đọc/ghi; constructor
  không tạo hoặc migrate database báo cáo/thư viện nguồn.
- GET `/api/template-packs/workspaces/{workspaceId}/editor-drafts`: phân trang,
  cờ stale/sourceChanged, không tự khôi phục hoặc phê duyệt.
- PUT `/api/template-packs/workspaces/{workspaceId}/editor-drafts/{draftId}`:
  expectedDraftRevision, operationId idempotent, identity/baseline bất biến;
  workspace archived/tested/published bị chặn ghi mới.
- Body đóng và bounded field/anchor; không chấp nhận field ngoài semantic catalog.
- Transaction SQLite bao gồm checkpoint và operation journal. Hai writer cùng
  revision chỉ một bên commit; retry cùng operation/payload trả cùng result.
- Storage lỗi trả 503 không lộ path/SQL; client phải đối chiếu trước retry.
- Chín test mới (8 store + 1 API), bộ liên quan **59 tests đạt**, Ruff check/format đạt.
  Test đã thêm vào check.ps1/GitLab CI; GitHub CI sử dụng check.ps1.
- Chỉ test trên kho tạm; chưa tạo editor DB trong data người dùng.

### Cập nhật UI — 10/09

Đã nối GET/PUT/retire qua client timeout 15 giây. Autosave debounce 600 ms, tuần tự
theo draft; ACK mới chuyển trạng thái saved. Retry save/retire giữ operation ID và
payload cũ trước khi lưu thay đổi mới. Duyệt chờ flush, sau đó retire approved;
discard retire trước khi bỏ draft khỏi editor. Retire thất bại vẫn cho retry.

UI có danh sách checkpoint phân trang và khôi phục có chủ ý; giữ nguyên session,
source hash/base revision. Source khác bị chặn restore, revision cũ bị chặn approve.
134 frontend tests/27 files, ESLint/build và 42 backend tests liên quan đạt.

**Chưa hoàn tất:** retention operation journal, so sánh conflict hai phía, cảnh báo
điều hướng nội bộ và E2E reload/restart/hai tab với backend thật. Các test hiện tại
chứng minh queue/component/API riêng; chưa phải chứng nhận recovery đầu cuối.

## Quyết định đề xuất

Lưu draft chưa duyệt vào SQLite riêng `data/template_studio/editor_drafts.sqlite3`,
cùng kho Studio nhưng không dùng `reporter.db` hay đổi schema thư viện nguồn.
Tự lưu có debounce; trạng thái UI phân biệt “Đang lưu nháp”, “Đã lưu nháp” và
“Chưa lưu được”. Nút “Duyệt ánh xạ” vẫn là thao tác riêng của người dùng.

Lợi ích: khôi phục sau refresh/restart, không nhầm draft với mapping đã duyệt,
không cần migration hai database hiện tại. Chi phí: thêm một DB cần backup,
API và optimistic concurrency; không được coi đã bền vững trước ACK backend.

## Dữ liệu và khóa

- Draft ID ngẫu nhiên, schema version, workspace ID, template SHA, semantic.
- Editor/session ID cho phép hai tab giữ draft riêng, không last-write-wins âm thầm.
- Base workspace revision và bản mapping gốc để đối chiếu conflict.
- Giá trị anchor/cột đang sửa; draft revision riêng và updatedAt.
- Không lưu DOCX, Tracking, note, IoC, mật khẩu hoặc kết quả báo cáo trong DB này.
- Chỉ nhận field/semantic thuộc catalog, kích thước JSON có giới hạn; draft có thể
  chưa đủ cột để duyệt nhưng không chấp nhận cấu trúc/payload tùy ý.

## Hợp đồng đích (GET/PUT đã có; lifecycle còn lại chưa hoàn tất)

- Tạo/ghi checkpoint có expectedDraftRevision; cùng tab gửi tuần tự.
- List/read checkpoint của workspace/source; không tự approve hoặc rebase.
- Xóa checkpoint có xác nhận/revision guard; không xóa workspace hoặc source.
- API nằm trong feature boundary Studio; flag 0 vẫn cô lập, không đổi report API.
- Request cũ/timeout dùng operation ID và đối chiếu kết quả theo task C03;
  response đến trễ không được đánh dấu phiên bản editor mới hơn là đã lưu.

## Luồng khôi phục và duyệt

1. Mở workspace: chỉ hỏi khôi phục khi có draft tồn tại; cho xem thời gian/section.
2. Cùng source/revision: khôi phục dữ liệu editor, vẫn chưa duyệt.
3. Revision khác: giữ draft, so giá trị cũ/mới, yêu cầu chọn và duyệt lại.
4. Source hash khác: không áp draft lên nguồn mới; có thể xem draft cũ để tham khảo.
5. Approval thành công: đối chiếu mapping đã commit trước khi retire checkpoint.
   Hai DB không có transaction chung nên lỗi cleanup không được làm mất approval;
   checkpoint còn sót phải được nhận diện khi mở lại, không yêu cầu duyệt trùng.
6. Backend offline: giữ trong RAM + cảnh báo rời trang; không ghi localStorage để
   giả vờ đã lưu. Khôi phục chưa ACK không được bảo đảm sau crash.

## Safety và test trước khi bật

- Khóa draft/revision hai tab, concurrent save, payload trễ, mất response sau commit.
- Restart/DB locked/disk full/schema mới hơn; lỗi có kiểm soát và không hỏng nguồn.
- Test không tăng workspace coverage/revision chỉ vì autosave.
- Backup C11 bao gồm DB này bằng SQLite snapshot nhất quán; chưa tự thêm vào backup report.
- Không tự retention/permanent-delete; thiết kế retention cùng C11 có preview.
- Test bằng kho tạm, không migrate hoặc ghi thử DB người dùng.
- UI giữ bố cục hiện tại; thêm trạng thái ngắn cạnh vùng lưu, không thêm wizard mới.

## Phần đã thực hiện trước thiết kế này

Đã có RAM draft theo workspace/SHA/section, giữ revision gốc, chặn stale approval.
Ngày 08/09 bổ sung beforeunload guard khi còn draft hoặc mutation đang chạy;
sửa về baseline xóa dirty; draft ở section khác vẫn được cảnh báo.
20 Workbench tests, ESLint và production build đạt. Đây chỉ là cảnh báo browser,
không bảo đảm chống mất dữ liệu khi crash/tắt cưỡng bức hoặc browser bỏ qua prompt.

**Đã được người dùng duyệt:** kho draft riêng và autosave chưa duyệt theo thiết kế này.
