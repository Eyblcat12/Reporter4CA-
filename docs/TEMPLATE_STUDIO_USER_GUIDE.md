# Template Studio — hướng dẫn sử dụng và tự kiểm tra

Ngày cập nhật: 10/09/2026. Phạm vi: tính năng Template Studio trong Reporter Pro local/team.

Template Studio dùng để chuẩn bị một cấu trúc Word mới thành bộ template tái sử dụng.
Tool phân tích cấu trúc; **bạn chọn và duyệt mapping**, xem báo cáo thử rồi mới phát hành.
Không tự hiểu 100% một template bất kỳ, không tự thay template mặc định đang dùng.

## Lưu và khôi phục bản nháp mapping

1. Mở workspace và chọn nội dung cần mapping. Khi sửa anchor/cột, tool tự lưu
   bản nháp sau khi ngừng gõ khoảng 600 ms. Chờ **Đã lưu nháp · chưa duyệt mapping**
   trước khi đóng trang; trạng thái này chỉ xuất hiện sau xác nhận từ backend.
2. Khi mở lại cùng workspace/nội dung, mở **Bản nháp đã lưu**, chọn checkpoint rồi
   **Khôi phục bản nháp**. Dùng phân trang/làm mới nếu chưa thấy bản cần tìm.
   Nếu editor đang có checkpoint, cần giải quyết bản đó trước khi khôi phục bản khác.
3. Kiểm tra lại và bấm **Duyệt ánh xạ** riêng. Tự lưu/khôi phục không tăng coverage,
   không tự sửa mapping đã duyệt hoặc template mặc định.
4. Nếu workspace đã đổi revision, draft cũ được giữ để xem nhưng không được duyệt
   trên revision mới. Bỏ bản nháp để dùng bản hiện hành rồi nhập lại sau khi đối chiếu;
   chưa có chức năng tự merge. Nguồn DOCX khác checksum không được khôi phục chéo.
5. Khi lỗi hoặc timeout, bấm thử lại; tool giữ cùng mã thao tác để tránh ghi trùng.
   Không coi draft đã lưu khi chưa có xác nhận. **Bỏ bản nháp** đóng checkpoint,
   không xóa vật lý nội dung lưu và không xóa mapping đã duyệt.

Giới hạn kiểm chứng: queue, UI component và API đã có test tự động; kiểm thử thực tế
restart/hai tab và giao diện đối chiếu conflict vẫn nằm trong checklist C02.

## 1. Hiểu nhanh các phần

| Thành phần | Lưu gì / dùng khi nào |
|---|---|
| Thư viện nguồn | DOCX đã phân tích, checksum, kết quả phân tích, liên kết workspace; chọn lại mà không cần upload từ máy |
| Workspace | Bản nháp mapping của một nguồn và một report type; mở lại để tiếp tục công việc |
| Chuẩn hóa cấu trúc | Tạo bản sao có các mốc chèn dữ liệu khi Word chưa có anchor |
| Validation | Tạo DOCX thử, duyệt bản chuẩn và chạy lại để phát hiện khác biệt |
| Catalog | Các Template Pack đã phát hành với phiên bản bất biến |

```text
Chọn DOCX / Thư viện nguồn
          ↓
Phân tích → Tạo workspace
          ↓
Chưa có anchor? → Chuẩn hóa trên bản sao
          ↓
Ánh xạ từng nội dung → Duyệt → Coverage 100%
          ↓
Rà soát → Tạo baseline → Tải DOCX và kiểm tra trong Word
          ↓
Duyệt baseline → Chạy lượt xác minh → Kiểm tra kết quả
          ↓
Phát hành vào Catalog
          ↓
Chủ động chọn pack trong Cấu hình khi muốn dùng
```

Luồng báo cáo mặc định vẫn độc lập. Không chọn pack Studio thì tiếp tục dùng template cũ.

## 2. Chuẩn bị lần đầu

1. Đóng và mở lại tool sau khi cập nhật để backend nạp mã mới.
2. Chọn **Template Studio** trong sidebar.
3. Chọn **Quản lý → Template mới**.
4. Dùng một bản sao template để thử. Không cần sửa template mặc định của khách hàng.

Nếu chưa có template mới, repository đã có ba template tổng hợp, không chứa dữ liệu khách hàng:

| Report type | Tệp trong `tests/fixtures/template_studio/synthetic_templates/` |
|---|---|
| Full | `cross_platform_assessment_full.docx` |
| Server | `infrastructure_review_server.docx` |
| Client | `endpoint_assurance_client.docx` |

Chọn Tracking CSV có cả máy bình thường và bất thường để kiểm thử. Có thể dùng
`samples/Tracking.csv` nếu có trong bản source của bạn. Không sửa nội dung CSV gốc.

## 3. Chọn và phân tích nguồn

### Nguồn mới

1. Nhấn **Chọn template .docx**. Chấp nhận DOCX không rỗng, tối đa 20 MiB.
2. Chọn **Report type** đúng: Full, Server hoặc Client cho lần thử đầu.
3. Nhấn **Phân tích**.
4. Xem số Anchor, Heading, Table, Conflict. Phân tích thành công sẽ tự lưu nguồn vào thư viện.
5. Điền tên hiển thị, Profile ID và Version, rồi nhấn **Tạo workspace**.

Ví dụ: tên `Khách hàng A — Full`; ID `customer-a-full-test`; version `0.1.0`.
Profile ID dùng chữ thường không dấu, số, dấu `.`, `_` hoặc `-`, tối thiểu hai ký tự.

**Kết quả mong đợi:** workspace mở ở màn hình ánh xạ, coverage ban đầu 0%.
Đây không phải lỗi: phân tích cấu trúc khác với phê duyệt mapping.

### Dùng lại nguồn đã lưu

1. Tại màn hình **Template mới**, nhấn **Thư viện nguồn**.
2. Tìm tên, nhấn **Tìm** hoặc Enter; dùng **Trang trước/Trang sau** nếu cần.
3. Chọn đúng template, đối chiếu tên, loại report từng phân tích và phần checksum hiển thị.
4. Chọn report type cần dùng, **Phân tích** lại, điền thông tin và tạo workspace mới.

Chọn nguồn không tái sử dụng quyết định duyệt của workspace cũ. Muốn giữ mapping đã làm,
mở workspace cũ trong **Quản lý**, hoặc **Clone** workspace sang version mới.
Cùng nội dung DOCX chỉ lưu một nguồn theo SHA-256; file thay đổi nội dung sẽ là nguồn khác.

## 4. Khi Word chưa có anchor

Anchor là mốc xác định chính xác chỗ đưa dữ liệu vào Word: content control có tag,
bookmark hoặc token dạng `{{TEN_VUNG}}`. Tên heading đơn thuần không phải anchor.

1. Mở workspace, chọn **Chuẩn hóa cấu trúc**.
2. Với từng nội dung bắt buộc, chọn đoạn hoặc bảng tương ứng trong Word.
3. Chọn cách đặt:

| Chế độ | Tác động |
|---|---|
| Chèn phía sau | Giữ đoạn/bảng đã chọn; thêm vùng dữ liệu phía sau. Phù hợp chọn heading để giữ heading |
| Thay nội dung | Đánh dấu đúng đoạn/bảng mẫu sẽ được thay bằng dữ liệu khi render |

4. Nhấn **Tạo bản chuẩn hóa**. Tool tạo nguồn và workspace mới, không ghi đè file cũ.
5. Duyệt mapping trong workspace mới; chuẩn hóa không tự tăng coverage lên 100%.

Lưu ý quan trọng:

- Không chọn cùng một vị trí cho nhiều nội dung. Không thay một đoạn đang chứa section break.
- “Chèn phía sau” không tự xóa các bảng dữ liệu mẫu còn nằm ở nơi khác.
- Bảng prototype dùng chế độ thay phải có cấu trúc cột phù hợp, không dùng ô gộp cho phần động.
- Bản v1 hỗ trợ đoạn/bảng cấp thân tài liệu. Text box, bảng lồng, vùng động trong header/footer
  hoặc cấu trúc đặc biệt cần chuẩn hóa trước trong Word; không cố chọn nhầm một vùng khác để vượt gate.
- Giữ nguyên các đoạn tĩnh khách hàng yêu cầu. Chỉ đánh dấu nội dung thực sự cần thay.

## 5. Mapping và chuyển bước 2 → 3

1. Chọn một dòng nội dung ở bảng **Ánh xạ template**.
2. Chọn **Word anchor** đúng. Gợi ý chỉ hỗ trợ tìm; vẫn cần bạn xác nhận.
3. Với bảng, nhập số cột `1`, `2`, … từ trái sang phải. Cú pháp cũ `column:1`,
   `column:2` vẫn được hỗ trợ; UI chuyển sang hợp đồng backend khi duyệt.
   Phải dùng đủ cột 1..N, không trùng/nhảy cóc.
4. Nhấn **Duyệt ánh xạ** và chờ lưu thành công.
5. Lặp lại cho mọi dòng bắt buộc. Khi coverage 100% và không còn blocker,
   chọn **Rà soát template → Tạo báo cáo thử**.

Nếu kẹt bước 2: kiểm tra dòng chưa duyệt, anchor bị trùng/đã dùng, thiếu field mapping
hoặc yêu cầu chưa lưu thành công. Không cần sửa mã nguồn để tiếp tục.

### Bảng mapping để thử nhanh với template Full tổng hợp

Chỉ áp dụng cho `cross_platform_assessment_full.docx` đi kèm, không áp đặt cho template khách hàng.

| Nội dung | Loại anchor | Giá trị anchor | Cột cần ánh xạ |
|---|---|---|---|
| Tiêu đề báo cáo | bookmark | `report_title` | — |
| Tổng quan | content_control | `overview` | — |
| Danh sách máy chủ | token | `{{SERVER_INVENTORY}}` | hostname → column:1; ip → column:2; os → column:3 |
| Danh sách máy trạm | token | `{{CLIENT_INVENTORY}}` | hostname → column:1; ip → column:2; os → column:3 |
| Kết quả máy chủ | content_control | `server_results` | hostname → column:1; result → column:2 |
| Kết quả máy trạm | content_control | `client_results` | hostname → column:1; result → column:2 |
| Phân tích và điều tra | bookmark | `investigation` | — |
| Gỡ bỏ mã độc | token | `{{REMEDIATION_REGISTER}}` | hostname → column:1; ip → column:2; status → column:3 |
| Chỉ dấu xâm nhập | content_control | `ioc_register` | type → column:1; value → column:2 |
| Khuyến nghị | bookmark | `recommendations` | — |

Mapping anchor của Server/Client được liệt kê trong `manifest.json` cùng thư mục fixture.
Token gỡ bỏ mã độc của Full là `{{REMEDIATION_REGISTER}}`, được xếp vào gợi ý khi
thực sự có trong nguồn. Có thể tìm nguyên tên token có dấu gạch dưới; anchor đã
gán cho mục khác vẫn nằm trong nhóm đã dùng, không tự gỡ mapping của mục đó.
Các field bắt buộc hiện trực tiếp trong inspector; không cần thêm field không có trong UI.

## 6. Kiểm thử hai lượt và phát hành

### Lượt 1 — bản chuẩn để duyệt

1. Trong **Kiểm thử Template Pack**, chọn Tracking CSV hoặc fixture JSON hợp lệ.
   Studio nhận diện định dạng/cột qua import API trước khi đọc dữ liệu; file mẫu
   `apps/backend/samples/Tracking.csv` có nội dung XLSX vẫn được đọc đúng, không
   cần đổi đuôi hoặc sửa file. Fixture nhiều sheet chưa có UI chọn sheet: dùng bản
   test một sheet, không tự lấy dữ liệu từ sheet bất kỳ.
2. Nhấn **Tạo baseline**, chờ backend hoàn tất.
3. Nhấn **Tải DOCX để duyệt**, mở đúng file vừa tải bằng Word.
4. Kiểm tra theo checklist dưới đây. Chỉ khi đạt, điền **Người duyệt** và nhấn **Duyệt baseline**.

### Lượt 2 — xác minh không thay đổi ngoài ý muốn

1. Giữ nguyên fixture và workspace; nhấn **Chạy lượt xác minh**.
2. Kiểm tra kết quả integrity/diff. Tải DOCX lượt 2 và xem lại.
3. Nhấn **Phát hành vào Catalog** khi gate cho phép.

Không nhấn duyệt chỉ vì nút đã bật. Test cấu trúc không thể thay thế đánh giá bố cục và
nội dung của bạn. Nếu sửa mapping/template/fixture, phải kiểm thử lại; không bỏ qua khác biệt.

### Checklist DOCX trước khi duyệt

- [ ] Đúng tiêu đề, tên dự án, loại report và các phần tĩnh cần giữ.
- [ ] Full có cả server/client; Server không lẫn client; Client không lẫn server.
- [ ] Số tài sản và danh sách hostname khớp dữ liệu thuộc phạm vi report.
- [ ] Máy có dấu hiệu bất thường không bị mất; không tự kết luận mã độc khi chỉ có dấu hiệu cần điều tra.
- [ ] Bảng không còn dòng dữ liệu mẫu của template bị để lại ngoài vùng mapping.
- [ ] Không còn token chưa thay như `{{...}}` trong phần cần sinh dữ liệu.
- [ ] Heading, số trang, bảng, ngắt trang, header/footer và hình ảnh không hỏng.
- [ ] Nội dung phân tích và khuyến nghị phù hợp bằng chứng, không được xem là kết luận tự động đã kiểm chứng.

## 7. Dùng pack mà không ảnh hưởng báo cáo mặc định

Sau khi phát hành, quay lại Reporter Pro. Nếu muốn thử pack mới:

1. Import Tracking như bình thường.
2. Ở **Cấu hình**, chọn report type tương ứng rồi chọn template có hậu tố **(Studio)**.
3. Preview, kiểm tra và Generate như thường lệ.

Pack không tự trở thành mặc định. “Active”/rollback trong Catalog không tự đổi template của
report đang làm. Chọn lại **Template mặc định** để dùng luồng cũ.
Plugin tùy chỉnh không chạy với pack; pack lỗi bị báo lỗi, không âm thầm đổi sang layout khác.

## 8. Lưu, phiên bản và sao lưu

- **Quản lý:** mở workspace để tiếp tục; đổi tên, clone, archive/restore, export/import `.rptdraft`.
- **Version:** muốn sửa pack đã phát hành thì clone workspace, tăng version (ví dụ `0.1.1`),
  chạy lại validation. Không ghi đè nội dung khác lên cùng ID + version.
- **Archive:** không xóa workspace. Dọn an toàn phải preview và chuyển vào quarantine có thể khôi phục.
- **Thư viện nguồn:** lưu trong SQLite riêng `apps/backend/data/template_studio/template_library.sqlite3`
  dưới thư mục dự án. Không dùng chung database report. DOCX gốc được lưu trong DB,
  kết quả phân tích mới nhất được lưu theo từng report type; lịch sử mapping vẫn nằm ở workspace.
- **Sao lưu toàn Studio:** dừng tool, sao chép toàn bộ `apps/backend/data/template_studio` sang nơi an toàn.
  Không chỉ copy SQLite vì mapping, catalog và validation artifact còn ở các thư mục cùng cấp.
  Không mặc định rằng backup database báo cáo đã bao gồm kho Studio.
- Không sửa SQLite/JSON/checksum bằng tay. Không đưa DOCX khách hàng hay thư viện runtime lên Git.

## 9. Bài tự kiểm tra gợi ý

| Test | Cách làm | Kết quả mong đợi |
|---|---|---|
| Nguồn mới | Phân tích template Full tổng hợp | Có số liệu cấu trúc; coverage 0% |
| Lưu bền | Đóng/mở lại tool, mở Thư viện nguồn | Tìm được DOCX đã phân tích |
| Không lưu trùng | Phân tích lại cùng file | Một nguồn theo checksum, không thêm bản sao DOCX |
| Mapping chưa đủ | Chưa duyệt hết các dòng | Không phát hành được |
| Đủ mapping | Duyệt đúng bảng mục 5 | Coverage 100%; mở bước rà soát/kiểm thử được |
| Hai lượt | Tạo baseline → xem Word → duyệt → xác minh | Hai lượt đạt trước khi publish |
| Tái dùng | Mở lại workspace | Mapping đã lưu còn nguyên |
| Chuẩn hóa | Dùng DOCX chưa có anchor, tạo bản chuẩn hóa | Workspace mới; nguồn cũ không đổi; mapping chưa tự duyệt |
| Scope | Lặp lại với fixture Server/Client | Không lẫn máy ngoài phạm vi |
| Luồng cũ | Không chọn pack Studio, tạo report như trước | Dùng đúng template mặc định, không bị thay thế |

Các test thật sẽ tạo workspace/pack mang ID bạn đặt. Nên thêm hậu tố `-test` để phân biệt.
Không dùng dữ liệu khách hàng nhạy cảm nếu chỉ cần kiểm tra khả năng của tính năng.

## 10. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Không có anchor | Dùng Chuẩn hóa cấu trúc trên bản sao; 0% sau phân tích là bình thường |
| Nút Tạo workspace chưa bật | Phân tích lại đúng report type, điền tên/ID/version; đóng thư viện trước |
| Anchor đã được dùng | Chọn anchor khác hoặc gỡ mapping cũ sau khi kiểm tra; không dùng chung một anchor |
| Mapping 100% nhưng chưa publish được | Còn gate baseline/duyệt/xác minh; thực hiện mục 6 |
| HTTP 409 | Workspace/catalog đã thay đổi; tải lại trạng thái trước khi thao tác tiếp |
| Checksum lỗi | Dừng dùng nguồn/pack này, phục hồi bản backup tin cậy; không sửa checksum để vượt lỗi |
| Thư viện không kết nối được | Kiểm tra backend đang chạy, nhấn Thử lại; không mất nguồn đã lưu |
| Workspace cũ chưa được bổ sung vào kho | Nguồn DOCX hoặc workspace cũ thiếu/hỏng; phục hồi backup hoặc import lại bản hợp lệ |
| Bảng prototype không phù hợp | Sửa bản sao Word cho đúng số cột, bỏ merge ở vùng động rồi phân tích lại |
| Pack không hiện trong Cấu hình | Kiểm tra đã publish, đúng report type; mở lại ứng dụng nếu danh sách đang cũ |

Nếu cần hỗ trợ, ghi lại: bước gặp lỗi, Profile ID/version, report type, thông báo đầy đủ,
số hàng input và ảnh màn hình. Không gửi dữ liệu nhạy cảm nếu chưa được phép.

Tài liệu chuyên sâu: [Template Administrator](TEMPLATE_ADMIN_GUIDE.md),
[trạng thái và bằng chứng test](TEMPLATE_STUDIO_STATUS.md).
