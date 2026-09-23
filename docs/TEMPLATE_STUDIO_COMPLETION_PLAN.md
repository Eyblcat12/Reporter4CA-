# Template Studio — kế hoạch hoàn thiện tổng thể

Ngày: **08/09/2026**. Phiên bản kế hoạch: **1.0 — người dùng đã duyệt triển khai**.
Phạm vi: hoàn thiện tính năng Template Studio trên **UI cũ đã chốt**, cho bản local/team.
Đây là kế hoạch công việc, không phải tuyên bố các hạng mục bên dưới đã hoàn thành.

## 1. Đích đến và ranh giới

Người dùng nhận DOCX của khách hàng, phân tích cấu trúc, chủ động chuẩn hóa và
mapping một lần, kiểm thử rồi phát hành một Template Pack dùng lại được.
Đầu vào báo cáo vẫn là Tracking theo hợp đồng hiện tại. Không yêu cầu tự động
hiểu/mapping toàn bộ template và không đổi Tracking để chiều theo bố cục Word.

### Điều phải giữ nguyên

- Tool chính vẫn sử dụng được trong quá trình phát triển; không chạy kiểm thử ghi
  vào database, workspace hoặc template thật của người dùng.
- Không sửa template Full/Server/Client đã được khách hàng duyệt hoặc Legacy Renderer.
- Studio là một phần của tool. Theo quyết định tích hợp đã có, flag mặc định `1`;
  `0` là kill switch. Không quay lại yêu cầu mặc định tắt của checkpoint lịch sử.
- Pack chỉ được dùng khi người dùng chọn rõ phiên bản đã phát hành. Active version
  trong Catalog không tự thay template mặc định hoặc report đang cấu hình.
- Pack lỗi phải báo lỗi đúng nguồn, không âm thầm chuyển renderer/template.
- Không xây lại UI bằng Stitch, thêm thư viện UI lớn, PDF, plugin thực thi,
  RBAC/multi-tenant hay hệ thống toàn server trong kế hoạch này.
- Dọn thư mục là công việc riêng theo `PROJECT_CLEANUP_CHECKLIST.md`, chưa được duyệt xóa.

### Bốn lớp nghiệm thu độc lập

| Lớp | Ý nghĩa | Không được suy diễn |
|---|---|---|
| Tương thích cấu trúc | Biết vùng nào đọc được, giữ nguyên được, sinh động được | Analyzer thấy một bảng không có nghĩa renderer xử lý mọi kiểu merge/lồng |
| Mapping dữ liệu | Mọi semantic bắt buộc đúng nguồn, anchor, renderer, cột | Coverage 100% không chứng minh đã loại hết nội dung mẫu cũ |
| Chất lượng DOCX | Đúng tài sản/phát hiện, không mất bố cục/nội dung đã duyệt | Structural test đạt không thay thế xem Word thực tế |
| Vận hành | Lưu, retry, version, restart, rollback có kết quả xác định | Nút báo thành công không thay thế evidence từ backend |

“Bất kỳ template mới” là khả năng **tiếp nhận và đánh giá**. Nếu cấu trúc nằm ngoài
khả năng hiện tại, phải chuẩn hóa có duyệt hoặc bổ sung adapter/semantic có test;
không hứa mọi file Word đều sinh chính xác ngay lần import đầu tiên.

## 2. Baseline được biết ở thời điểm lập kế hoạch

- Nhánh kiểm tra: `codex/reporter-pro-github-release`; HEAD đọc được `41fc19a`.
  Working tree có nhiều thay đổi chưa commit: HEAD không đại diện toàn bộ mã đang chạy.
- Có analyzer, workspace revision, thư viện nguồn SQLite riêng, copy-only normalization,
  mapping, validation hai lượt, catalog/version/recovery và tích hợp pack Preview/Generate.
- Ngày 07/09: đã bổ sung chống phản hồi cũ, giữ draft theo workspace/SHA/section,
  expectedRevision gốc, chặn draft stale và cột trùng.
- Gate gần nhất được ghi nhận: **119 frontend tests/26 files, lint và build đạt**
  ngày 07/09. Không chạy lại gate đó trong lượt lập kế hoạch 08/09.
- Backend/E2E/golden có kết quả lịch sử nhưng **phải chạy lại trên bản cuối cùng**.
- Draft hiện chỉ trong bộ nhớ. Mutation timeout chưa có đối chiếu kết quả đầy đủ.
- Kho nguồn riêng đã có; backup report hiện tại không được coi là backup toàn Studio.
- Nhiều tài liệu còn đoạn “domain-only/chưa nối Generate” của checkpoint cũ:
  cần đồng bộ tài liệu, không lấy chúng làm yêu cầu mới.

Nguồn đối chiếu: `TEMPLATE_STUDIO_STATUS.md`, `TEMPLATE_PACKS.md`,
`TEMPLATE_STUDIO_BACKEND_ALIGNMENT.md`, `TemplateStudioRoute.jsx`,
`templateStudioApi.js`, các route `/api/template-packs/*` và module library/normalization/runtime.
Đây chưa phải kiểm toán từng dòng toàn bộ backend.

## 3. Luồng đích

```text
DOCX mới / nguồn trong thư viện
    │
    ▼
Kiểm tra file an toàn → Phân tích cấu trúc + báo vùng chưa hỗ trợ
    │                                     │
    │ thiếu anchor/không phù hợp           └→ Hướng dẫn sửa Word hoặc đề xuất adapter
    ▼
Chọn vùng tĩnh/vùng sinh động → Preview chuẩn hóa → Tạo BẢN SAO
    │                                                │
    └──────────────── Phân tích lại nguồn mới ◄──────┘
    ▼
Mapping nguồn Tracking → semantic → anchor/cột → người dùng duyệt
    │
    ├→ thiếu/sai/stale: giữ draft, chỉ rõ mục cần sửa
    ▼
Rà soát coverage + nội dung tĩnh + cấu trúc hỗ trợ
    ▼
Tracking fixture → validation lượt 1 → tải DOCX → người dùng duyệt SHA chính xác
    ▼
Validation lượt 2 → so baseline + kiểm integrity → đủ evidence
    ▼
Publish pack ID/version bất biến → Catalog
    ▼
Configure chọn pack rõ ràng → Preview job → Generate → Download + History

Song song, luồng mặc định:
Tracking → Configure template mặc định → Legacy Renderer → DOCX (giữ nguyên)
```

## 4. Danh mục task và thứ tự

Ký hiệu: **Có nền** = đã có implementation, phải audit/test bổ sung;
**Còn thiếu** = chưa hoàn tất theo checkpoint; **Đề xuất mới** = cần thiết kế trước khi code.
P0 = chặn tin cậy/phát hành; P1 = cần hoàn thiện để bàn giao local/team.

| ID | Task | Ưu tiên | Tình trạng | Phụ thuộc |
|---|---|---|---|---|
| C01 | Baseline, phạm vi, bảng hợp đồng UI/API | P0 | Có nền | — |
| C02 | Draft, session, conflict | P0 | Còn thiếu | C01 |
| C03 | Mutation timeout, retry, phản hồi trễ | P0 | Còn thiếu | C01, phối hợp C02 |
| C04 | Upload, thư viện nguồn, phân tích cấu trúc | P0 | Có nền | C01, C03 |
| C05 | Chuẩn hóa DOCX không phá nguồn | P0 | Có nền | C04 |
| C06 | Mapping chính xác và rà soát 100% | P0 | Có nền | C02, C04, C05 |
| C07 | Tracking adapter và nội dung report | P0 | Có nền | C06 |
| C08 | Validation, baseline, diff và duyệt Word | P0 | Có nền | C03, C07 |
| C09 | Publish, version và catalog recovery | P0 | Có nền | C08 |
| C10 | Tích hợp report thật, bảo vệ luồng mặc định | P0 | Có nền | C09 |
| C11 | Kho Studio, backup/restore và retention | P1 | Có nền; backup tổng thể là đề xuất mới | C01, C09 |
| C12 | UX hoàn thiện trên UI cũ | P1 | Cần audit | Xuyên suốt C02–C11 |
| C13 | Hardening và tác vụ dài | P1; lỗi mất dữ liệu là P0 | Có nền | C03–C11 |
| C14 | Ma trận test và nghiệm thu thực tế | P0 | Có nền, chưa gate bản cuối | Xuyên suốt; chốt sau C10–C13 |
| C15 | Tài liệu, release, clean-clone và bàn giao | P0 | Cần đồng bộ | C14 |

## 5. Đầu việc chi tiết

### Nhật ký triển khai 08/09 — C06, bảo vệ vị trí cột (một phần)

Người dùng xác nhận giữ định dạng template là đầu ra bắt buộc. Audit phát hiện
renderer sắp field theo target nhưng tạo bảng theo số field: target nhảy cóc có
thể bị dồn vị trí. Đã chặn target không liên tục ở mapping approval, profile/pack
validation và UI. Cột đảo thứ tự vẫn hợp lệ khi phủ đúng 1..N; không tự sửa pack cũ.
Fixture pack trước đây dùng `column:hostname` được sửa về đích số như renderer yêu cầu.

Kiểm thử: 86 backend tests thuộc mapping/profile/pack/validation/runtime/publish/
catalog/preview đạt; 18 Workbench frontend tests đạt; Ruff check/format, ESLint và
production build 1.935 modules đạt. Đây là gate tập trung, chưa phải full release.
Backend runtime test có cảnh báo CScript access denied khi update Word fields:
kết quả này **không xác nhận TOC/field đã update hoặc visual Word đạt**.
Không sửa Legacy Renderer/template mặc định, database hoặc pack của người dùng.

Chưa đóng C06: còn kiểm cột thực tế của prototype, layout merged/nested, vùng tĩnh,
mapping inspector context và full gate. Không thay thế các task C01–C03 còn thiếu.

### C01 — Khóa baseline và đối chiếu UI/backend

1. [ ] Ghi branch/HEAD, manifest file thay đổi, trạng thái test và cấu hình runtime;
   không tự stage tất cả hoặc lấy code chưa commit làm baseline đã phát hành.
2. [ ] Lập bảng mỗi nút UI → API → request → response → error → thay đổi storage → test.
3. [ ] Phân biệt trạng thái UI với trạng thái domain; backend quyết định coverage,
   revision, validation và quyền publish, không dựa vào bước stepper.
4. [ ] Đánh dấu file bảo vệ, kiểm checksum template mặc định và merge-boundary hiện có.
5. [ ] Kiểm tra harness API thật dùng storage tạm, port riêng; không đụng process/tool đang chạy.
6. [ ] Chạy gate nền có log lưu để biết lỗi sẵn có, gồm warning React act trong suite.

**Đầu ra:** bảng API/state và baseline test có commit/working-tree identity.
**Đạt khi:** mọi thao tác hiện hữu có đầu mối API/test; ranh giới default/pack rõ ràng.

### C02 — Không mất draft và giải quyết revision conflict

Checkpoint 10/09: backend checkpoint/retire và UI autosave/restore đã nối; retry
idempotent, ACK, stale revision guard có regression. 134 frontend tests/27 files,
42 backend draft/API tests, lint/build đạt. Chưa đóng C02: audit điều hướng nội bộ,
conflict comparison và E2E recovery/restart/hai tab còn lại.
[Thiết kế checkpoint đã duyệt](TEMPLATE_STUDIO_DRAFT_STORAGE_DESIGN.md).

1. [ ] Audit cache draft hiện có: đổi section/workspace/SHA, archive, rename, clone,
   normalize, đóng Studio rồi quay lại; không nhầm draft giữa các nguồn.
2. [ ] Phân biệt dirty/saving/saved/conflict; trở về giá trị ban đầu thì hết dirty.
3. [ ] Chặn điều hướng nội bộ khi còn draft bằng lựa chọn ở lại/bỏ thay đổi;
   trước refresh/đóng trang dùng cảnh báo browser phù hợp, không hứa chặn được mọi cách tắt máy.
4. [x] Thiết kế khôi phục phiên: ưu tiên checkpoint draft riêng trong kho Studio,
   có schema version, revision/SHA gốc; không ghi note Tracking vào localStorage.
5. [x] Tách “Lưu bản nháp” khỏi “Duyệt ánh xạ”: checkpoint không nâng coverage,
   không tạo approval hoặc thay version đã publish. Thiết kế storage cần duyệt trước migration.
6. [ ] Khi conflict, hiển thị giá trị draft và giá trị mới của backend; cho tải lại
   hoặc bỏ draft có chủ ý. Chỉ cho áp lại lên revision mới sau khi người dùng xem và duyệt lại.
7. [ ] Test reload, restart, hai tab, draft hỏng/khác schema, nguồn đã đổi và quota/ghi đĩa lỗi.

**Đạt khi:** không mất thay đổi âm thầm; draft khôi phục không trở thành approval giả.
**Ảnh hưởng:** thêm trạng thái/checkpoint riêng, có thể phát sinh storage migration;
không thay format workspace đã được duyệt nếu chưa có migration tương thích.

### C03 — Retry an toàn và xử lý kết quả chưa xác định

1. [ ] Rà soát mọi mutation, không chỉ approve/remove: create, clone, import,
   normalize, archive, baseline approval, publish, activate, rollback, retention, recovery.
2. [ ] Tách lỗi chưa gửi, backend từ chối, response mất sau commit và request bị hủy.
3. [ ] Với timeout sau gửi: UI báo “Chưa xác định kết quả”, giữ draft và đọc lại trạng thái.
4. [ ] Thiết kế operation ID/idempotency cho thao tác tạo đối tượng/phát hành; cùng ID
   cùng payload trả cùng kết quả, payload khác bị từ chối; journal không lộ dữ liệu nhạy cảm.
5. [ ] Mapping dùng revision + đối chiếu giá trị đã lưu; không coi revision tăng đơn thuần là
   chính request của mình đã thành công. Unknown chưa đối chiếu xong thì không blind retry.
6. [ ] Guard phản hồi theo workspace/source/editor/operation; chống bấm kép trước render,
   chuyển tab trong lúc lưu và kết quả cũ về sau request mới.
7. [ ] Retry có giới hạn; backend lỗi validation/conflict không tự lặp mutation.
8. [ ] Test server commit rồi mất response, response đảo thứ tự, restart giữa write/reply,
   cùng ID khác payload và operation journal hết hạn.

**Đạt khi:** không tạo workspace/version trùng, không báo “thất bại” chắc chắn khi chưa biết kết quả.
**Ảnh hưởng:** có thể thêm trường API/journal; giữ tương thích client hiện có và test hợp đồng.

### C04 — Upload, thư viện nguồn và capability report

1. [ ] Kiểm DOCX rỗng/sai đuôi/ZIP hỏng, file vượt giới hạn, phần tử archive nguy hiểm,
   mã hóa, external relationship và XML bất thường bằng chính policy backend.
2. [ ] UI hiển thị đúng giai đoạn đọc file/gửi/phân tích; chỉ hiện % khi có số đo thật,
   không chạy thanh % giả cho analyzer chưa có progress.
3. [ ] Đổi file/report type phải hủy hiệu lực kết quả cũ; response phân tích trễ không được
   tạo workspace từ file trước. Người dùng vẫn chủ động chọn tạo workspace.
4. [ ] Phân loại từng cấu trúc: đọc được, giữ tĩnh được, sinh động được, cần sửa Word,
   chưa hỗ trợ; kèm vị trí và lý do, không chỉ đếm heading/table.
5. [ ] Cho xem ngữ cảnh đoạn/bảng/anchor và phát hiện anchor lặp/lồng/split-run;
   không dùng tên heading hoặc số thứ tự bảng làm khóa lâu dài.
6. [ ] Thư viện: tìm kiếm/phân trang, checksum trước tải, dedup nội dung, liên kết workspace,
   ngày nguồn/phân tích; nguồn cũ luôn phải được đánh giá cho report type mới.
7. [ ] Test list/detail race, nguồn hỏng/thiếu, backfill partial, DB khóa và cùng file khác tên.

**Đạt khi:** người dùng biết chính xác vì sao một template dùng được hay phải chuẩn hóa.
**Giới hạn v1 cần công khai:** dynamic ở body paragraph/table; phát hiện header/footer,
text box hay bảng lồng không tự chứng minh renderer hỗ trợ chúng.

### C05 — Chuẩn hóa copy-only có preview và khả năng truy vết

1. [ ] Xác minh normalize luôn tạo source/workspace mới; hash/bytes nguồn gốc không đổi.
2. [ ] Hiển thị cấu trúc trước/sau: chèn ở đâu, thay đoạn/bảng nào, vùng tĩnh nào giữ lại.
3. [ ] Các lựa chọn thay nội dung phải nêu phạm vi bị thay; không tự xóa mẫu khách hàng.
4. [ ] Khóa target bằng source hash/revision; chặn chọn cùng vùng, anchor lồng/trùng,
   index stale, số cột không khớp và layout chưa hỗ trợ.
5. [ ] Bảo toàn style, header bảng, width, border, paragraph/row/cell properties, section,
   media và relationships trong phạm vi cam kết; trường hợp chưa bảo toàn phải chặn/cảnh báo cụ thể.
6. [ ] Phân tích lại output và mở đúng workspace mới; không tự chuyển approval từ nguồn cũ.
7. [ ] Ghi normalization manifest (nguồn, output hash, thao tác, phiên bản normalizer).
8. [ ] Fault injection lỗi tạo source/workspace/library: không để workspace trỏ nguồn thiếu;
   orphan được phát hiện/thu hồi theo cơ chế an toàn, không dọn artifact của job khác.

**Đạt khi:** source cũ byte-identical; mọi thay đổi nằm trong preview được duyệt và truy vết được.
**Điểm hỏi:** khi cần thay bố cục khách hàng thay vì chỉ gắn anchor.

### C06 — Mapping đầy đủ và đúng vị trí thật

1. [ ] Kiểm mỗi semantic theo report type: renderer, data source, bắt buộc/tùy chọn,
   anchor sở hữu duy nhất và đủ field mapping.
2. [ ] Không dừng ở regex `column:1..999`: kiểm cột thật của bảng đích, header/body,
   bảng merge, số ô và khả năng renderer; backend là nơi quyết định hợp lệ.
3. [ ] Inspector hiển thị nguồn Tracking/canonical, field, cột Word và ví dụ đã ẩn dữ liệu nhạy cảm;
   chọn cột qua header khi đọc được, vẫn cho cách nhập nâng cao có validation.
4. [ ] Bảng mapping hỗ trợ tìm/lọc chưa duyệt/lỗi; click blocker mở đúng semantic.
5. [ ] Phân biệt nội dung tĩnh, placeholder và vùng lặp; rà soát dữ liệu mẫu chưa thay,
   nhất là tên khách hàng/tài sản/ngày trong template.
6. [ ] Coverage lấy từ backend và hiển thị số semantic đã duyệt/tổng bắt buộc;
   review không mở tiếp nếu còn blocker dù UI đang ở bước cao hơn.
7. [ ] Đổi nguồn, catalog/renderer compatibility hoặc report type phải đánh giá lại mapping;
   không kế thừa “100%” từ dữ liệu cũ.
8. [ ] Test thiếu field, cột vượt bảng, anchor bị chiếm, semantic không hỗ trợ,
   field mapping đảo thứ tự, bảng rỗng và cùng tên heading ở nhiều vị trí.

**Đạt khi:** coverage 100% có kiểm chứng cấu trúc/nguồn, không chỉ đủ số dòng UI.

### C07 — Chất lượng nội dung từ Tracking đến DOCX

1. [ ] Đối chiếu canonical snapshot giữa importer/rule evaluation/quality và pack runtime;
   không tạo một cách hiểu Tracking thứ hai riêng cho Studio.
2. [ ] Test scope Full/Server/Client: tổng tài sản, danh sách host/IP, số bất thường,
   note/evidence, không thiếu máy hoặc lẫn scope.
3. [ ] Tái hiện ca 30 máy/8 bất thường nếu fixture hiện hữu xác nhận đúng dữ liệu đó;
   tạo expected manifest độc lập từ fixture, không lấy output engine làm expected.
4. [ ] Test Tracking 50 máy đa kết quả, thiếu trường tùy chọn, ký tự tiếng Việt,
   note dài, nhiều IP, hostname trùng theo chính sách importer hiện tại.
5. [ ] Với semantic điều tra/remediation: sinh heading/vùng người dùng tự viết và bảng
   đúng mapping; không bịa phân tích hoặc kết luận đã gỡ mã độc khi chưa có bằng chứng.
6. [ ] Empty-state trong DOCX có quy tắc rõ: không có bất thường, không có server/client;
   không để nguyên hàng mẫu như dữ liệu thật.
7. [ ] Ghi traceability tới source row/asset/rule/semantic theo khả năng hiện có,
   phát hiện unresolved token và giá trị bị mất sau render.
8. [ ] Full/Server/Client là acceptance chính. Ba loại còn lại kiểm regression semantic
   đang hỗ trợ; không công bố tương thích template mới cho chúng nếu chưa có fixture/visual gate.

**Đạt khi:** danh sách và số liệu output khớp expected độc lập, finding có nguồn,
không thay rule nghiệp vụ hoặc template mặc định để làm test đạt.

### C08 — Validation hai lượt, diff và duyệt artifact

1. [ ] Audit fixture CSV/JSON → snapshot → renderer dùng cùng logic production pack.
2. [ ] Lượt 1 tạo DOCX và kiểm row/semantic/value/integrity; UI hiển thị tiến trình và
   kết quả có thể tải lại sau đóng modal/restart nếu backend hỗ trợ, không giả lập job.
3. [ ] UI phân biệt “Sinh được file”, “Integrity đạt”, “Chờ duyệt Word”, “Baseline đã duyệt”.
4. [ ] Download kiểm checksum; approval gắn đúng run/artifact SHA và người/thời điểm duyệt.
   Reviewer ở local/team là thông tin audit, không tuyên bố xác thực enterprise.
5. [ ] Lượt 2 so baseline: heading, paragraph, table, numbering, section, media,
   relationship; diff dễ đọc có semantic/vị trí và expected/actual.
6. [ ] Thay workspace/source/fixture/rule hoặc phiên bản engine có ảnh hưởng nội dung
   phải làm evidence stale theo signature hợp đồng; không dùng lại approval không khớp.
7. [ ] Test baseline thiếu/hỏng, artifact sửa ngoài, validation failed/unknown,
   restart giữa hai lượt, duyệt run cũ và duplicate approval.
8. [ ] Xem bằng Word thực tế: TOC/field, heading ngang hàng theo template được duyệt,
   bảng qua trang, footer/header, ảnh, trang ngang; không tự update lại baseline để che lỗi.

**Đạt khi:** publish chỉ dùng evidence backend hợp lệ của đúng revision/artifact;
người dùng hiểu còn gì cần duyệt bằng Word.

### C09 — Publish, version, catalog và recovery

1. [ ] Validate pack ID/version, report type, compatibility version và evidence trước publish.
2. [ ] Recheck workspace/catalog revision tại commit; cùng version khác bytes bị từ chối.
3. [ ] Kết hợp C03 để publish thành công nhưng mất response không tạo version thứ hai.
4. [ ] Catalog hiển thị published/active/selected rõ nghĩa; xem version, checksum,
   evidence và lịch sử; không gọi active là đã đổi template report hiện tại.
5. [ ] Test install/publish write lỗi, hai process cùng revision, payload hỏng,
   index hỏng, checkpoint thiếu pack và recovery token stale.
6. [ ] Rollback chọn version hợp lệ, không xóa version mới và không đổi job đã pin snapshot.
7. [ ] Retention không bỏ nguồn/evidence đang được pack tham chiếu; hành động có preview.

**Đạt khi:** version bất biến, chọn/rollback truy vết được, không tồn tại catalog trỏ pack thiếu.

### C10 — Dùng pack trong tool chính và bảo vệ default flow

1. [ ] Configure chỉ liệt kê pack published/hợp loại/checksum; legacy template vẫn như cũ.
2. [ ] Snapshot pin pack ID/version/hash, template hash, input và engine identity;
   đổi bất kỳ đầu vào liên quan phải invalid preview đúng cách.
3. [ ] Preview → Generate tái dùng chính artifact hợp lệ; test output byte-identical
   khi hợp đồng promotion cho phép, không render lại hoặc dùng cache khác pack.
4. [ ] Test tải report, tên file, history/dashboard metadata, cancel, đóng modal và retry.
5. [ ] Đổi pack sang default hoặc đổi ngược lại không làm mất Tracking/config phù hợp;
   cảnh báo nếu cấu hình/plugin không áp dụng, không âm thầm chuyển trạng thái khó thấy.
6. [ ] Flag `0`, pack thiếu/hỏng/sai loại phải lỗi rõ; không fallback sang legacy.
7. [ ] Regression sáu report type mặc định; Full/Server/Client phải kiểm DOCX và checksum
   nguồn template, không chỉ status HTTP 200.

**Đạt khi:** người khác chọn pack được và tạo report thật đúng Tracking; default flow không đổi.

### C11 — Lưu trữ Studio, backup/restore và vòng đời dữ liệu

1. [ ] Lập sơ đồ sở hữu: SQLite library → source hash → workspace → run/evidence → pack/catalog;
   xác định file nào immutable, mutable, rebuildable và bản duy nhất không thể tái tạo.
2. [ ] Audit giao dịch source/library/workspace: rollback hoặc repair index có kiểm chứng,
   không coi backfill đọc thư viện là luôn thành công toàn bộ.
3. [ ] Thiết kế **backup Studio riêng** bao gồm DB, source, workspace, validation/evidence,
   catalog/payload; không thay backup báo cáo hiện tại một cách âm thầm.
4. [ ] SQLite snapshot nhất quán (backup API hoặc quiesce có kiểm soát), không copy DB đang
   ghi và bỏ WAL. Manifest chứa schema/version/checksum và dependency graph.
5. [ ] Restore dry-run: kiểm archive/paths/hash/version/dung lượng, preview đối tượng tác động;
   chọn kho tạm để verify trước khi thay kho Studio.
6. [ ] Xác định điểm commit/rollback và khóa mutation trong thời gian restore; report default
   tiếp tục được bảo vệ. Không hứa restore online nếu chưa chứng minh consistency.
7. [ ] Retention preview → quarantine → restore; không permanent-delete tự động,
   không xóa nguồn được published pack/baseline/draft tham chiếu.
8. [ ] Test disk full, DB locked/corrupt, interrupted restore, schema mới hơn,
   mất blob/evidence và rollback giữa nhiều storage component.

**Đạt khi:** khôi phục vào môi trường sạch rồi map/validate/generate được cùng pack;
report DB không bị thay đổi. **Cần duyệt thiết kế storage/migration trước triển khai.**

### C12 — UX hoàn thiện, không thiết kế lại

1. [ ] Giữ workbench, outline/table và inspector hiện tại; một hành động chính rõ ở mỗi bước.
2. [ ] Tiêu đề ngắn, chú thích theo ngữ cảnh; lỗi gắn đúng field/section, có cách sửa.
3. [ ] Loading/empty/filter-empty/partial/stale/unknown/offline khác nhau; không dùng
   skeleton hoặc spinner che phần draft còn có thể đọc.
4. [ ] Hiển thị tên nguồn, report type, revision và trạng thái lưu vừa đủ;
   kỹ thuật nâng cao/hash/audit đặt trong chi tiết.
5. [ ] Keyboard/focus/Escape/return focus, status announcement, reduced motion,
   dark/light, 200% zoom, màn hình hẹp và chuỗi tiếng Việt dài.
6. [ ] Với danh sách lớn: kiểm phân trang/search có giới hạn; tránh luôn tải mọi workspace
   như cơ chế list-all hiện tại nếu đo cho thấy quá tải.
7. [ ] Visual QA screenshot các bước và trạng thái lỗi; xin duyệt nếu thay luồng điều hướng,
   checkpoint draft hoặc workflow background job đáng kể.

**Đạt khi:** hoàn thành bài test không cần chỉ dẫn ngoài UI ở các bước thông thường;
không có nút giả, bước kẹt, text khó đọc hoặc input mất khi đổi theme.

### C13 — Hardening và xử lý tác vụ dài

1. [ ] Đo riêng upload/analyze/normalize/validation/publish/render; không dùng số benchmark
   legacy hoặc synthetic tối giản để cam kết tốc độ template khách hàng.
2. [ ] Audit thao tác CPU/I/O dài đang chạy đồng bộ. Nếu chặn backend hoặc vượt timeout,
   thiết kế job Studio riêng/tái dùng hạ tầng an toàn, không đổi job report đang ổn tùy tiện.
3. [ ] Job nếu bổ sung phải có ID/trạng thái thật, giới hạn chạy/chờ, cancel, reconnect,
   restart outcome và cleanup theo ownership; đóng modal không đồng nghĩa hủy.
4. [ ] Giới hạn theo loại tài nguyên đo được: upload/ZIP expanded, JSON, RAM, timeout,
   artifact/cache; không áp trần số máy tùy tiện làm mất khả năng workload đã test.
5. [ ] Log operation/run/workspace/revision/error code/elapsed, không dump DOCX, note,
   IoC hay đường dẫn người dùng vào log không cần thiết; rotation có retention rõ.
6. [ ] Chạy lại archive/path/XML/fuzz/concurrency security regression hiện có.
7. [ ] Workload 30/50 dùng thường xuyên; 1.000/10.000/50.000 là gate bổ sung có chủ đích
   trong worker cô lập và watchdog. Chỉ công bố P50/P95 khi đủ mẫu tương đồng.
8. [ ] Soak có giới hạn thời gian/disk, checkpoint và dừng an toàn; không tự chạy nhiều giờ
   trên máy người dùng đang làm việc nếu chưa thống nhất lịch/tải.

**Đạt khi:** không exception thoát ngoài kiểm soát, không hỏng kho, không job mồ côi;
giới hạn/support envelope được ghi bằng số đo thay vì suy đoán.

### C14 — Kiểm thử tổng thể và nghiệm thu

1. [ ] Thêm regression tại mỗi task, không đợi cuối dự án mới viết test.
2. [ ] Fixture độc lập, không dùng template khách hàng thật để test ghi; manifest/hash tái tạo được.
3. [ ] Chạy ma trận ở mục 6 bằng backend thật, default storage cô lập.
4. [ ] Full gate Ruff/format, ESLint/Prettier, backend/frontend, production build,
   API integration, E2E, golden, security và boundary trên cùng candidate.
5. [ ] Loại warning test thiếu act bằng sửa test phù hợp, không tắt log để coi như sạch.
6. [ ] Xem DOCX trực quan; lưu evidence theo candidate identity, fixture/source/pack hash,
   command/runtime và kết quả; phân biệt skipped/blocked/failed/passed.
7. [ ] Test với production build qua launcher, không chỉ Vite dev server.
8. [ ] Người dùng làm bài nghiệm thu độc lập; lỗi dữ liệu/bố cục/mất draft là blocker.

**Đạt khi:** mọi gate bắt buộc đạt trên đúng candidate, không lấy tổng số test lịch sử thay chứng cứ.

### C15 — Tài liệu, release và bàn giao

1. [ ] Đồng bộ STATUS/PACKS/USER_GUIDE/ADMIN_GUIDE/rollback: loại mâu thuẫn lịch sử
   “chưa tích hợp” khỏi mô tả hiện hành, giữ phần lịch sử có nhãn rõ.
2. [ ] Hướng dẫn Quick Start một template từ thư viện và một DOCX thô;
   từng bước có kết quả mong đợi, lỗi thường gặp và giới hạn v1.
3. [ ] Tài liệu phát triển adapter mới: semantic contract, fixture, normalization,
   validator/renderer và compatibility version; không import mã thực thi tùy ý trong pack.
4. [ ] Release note ghi tính năng, hạn chế, cách backup/rollback, cách chọn pack/default.
5. [ ] Chia commit theo task; review diff riêng, không stage data/log/report/clone artifacts.
6. [ ] Chỉ commit/push/merge sau khi được yêu cầu ở bước phát hành; clean-source smoke
   trên exact commit, khóa dependency, build và health + Studio scenario cơ bản.
7. [ ] Khi push được duyệt: xác minh remote commit đúng bản đã test, clone sạch và làm theo
   INSTALL; không dùng dependency/database có sẵn để che thiếu file trong repo.
8. [ ] Cập nhật bảng hoàn tất/còn chặn và đính kèm bằng chứng; dọn artifacts theo checklist riêng.

**Đạt khi:** người khác clone/cài/chạy/tự thử được; có mốc quay lại rõ ràng và không lộ dữ liệu khách hàng.

## 6. Ma trận nghiệm thu tối thiểu

| Kịch bản | Dữ liệu/template | Kết quả phải chứng minh |
|---|---|---|
| Default regression | Sáu loại report mặc định | Golden/integrity đạt; Full/Server/Client không bị đổi template |
| Pack thông thường | Ba synthetic cấu trúc khác nhau; Tracking 30/50 | Mapping → hai lượt validation → publish → production Preview/Generate |
| DOCX chưa có anchor | Đoạn/bảng body được hỗ trợ | Normalize copy-only → reanalyze → mapping; nguồn gốc giữ nguyên |
| Mapping khó | Anchor trùng, cột vượt bảng, merged/nested table | Chặn/hướng dẫn đúng; không báo coverage 100% giả |
| Dữ liệu đa kết quả | Notes bất thường/không bất thường và dữ liệu tùy chọn thiếu | Đủ host/phát hiện, đúng scope, không bịa kết luận |
| Session | Đổi section/workspace, refresh, restart, hai tab | Draft không lẫn nguồn; conflict rõ, approval không tự chuyển |
| Response mất | Commit thành công nhưng network timeout | Đối chiếu được, không duplicate workspace/version |
| Publish stale | Đổi source/mapping/fixture sau baseline | Approval/evidence không hợp lệ bị chặn |
| Catalog hỏng | Index/checkpoint/payload thiếu hoặc khác hash | Recovery preview chính xác, không ghi sai thêm |
| Studio restore | Backup toàn kho vào môi trường tạm | Nguồn/workspace/pack/evidence nhất quán, report DB nguyên vẹn |
| Production integration | Đổi default↔pack, hủy job, tải lại | Đúng snapshot, cache, history; không silent fallback |
| UX | Dark/light, keyboard, 200% zoom, màn hình hẹp | Không mất input, không kẹt focus, nội dung đọc được |
| Unsupported Word | Textbox/header-footer động/layout ngoài v1 | Báo giới hạn rõ, không hứa đã xử lý vì analyzer đọc được |

Chưa có template khách hàng: dùng synthetic để đóng engineering gate, ghi rõ
**“customer pilot pending”**, không tuyên bố đã tương thích mọi mẫu thực tế.
Template mới sau này phải có acceptance riêng, không cần mở lại toàn bộ phát triển sản phẩm.

## 7. Cách chia đợt thực hiện và bàn giao

```text
Đợt A: C01 → C02 + C03             Mốc: lưu/khôi phục/retry tin cậy
Đợt B: C04 → C05 → C06 → C07       Mốc: Tracking map đúng, DOCX có nội dung đầy đủ
Đợt C: C08 → C09 → C10             Mốc: publish và dùng pack thật, default không đổi
Đợt D: C11 + C12 + C13             Mốc: vận hành local/team và UX hoàn thiện
Đợt E: C14 chốt → C15              Mốc: candidate đã kiểm thử, tài liệu và release

C12/C13/C14 được làm từng phần trong mọi đợt, không dồn toàn bộ về cuối.
```

Không cam kết số ngày trước C01 vì phần lớn hạng mục đã có nền nhưng cần xác định
gap thực tế. Mỗi đợt chia PR/commit nhỏ theo ranh giới backend/frontend/test/docs;
không viết lại subsystem nếu audit chứng minh phần hiện có đã đúng.

Mỗi lần kết thúc phiên phải cập nhật task ID, checklist hoàn thành, file thay đổi,
test đã chạy/thời điểm, vấn đề phát hiện, quyết định cần hỏi và bước tiếp theo.
Một task chỉ đóng khi đủ implementation + regression + evidence + docs, không đóng
chỉ vì endpoint hoặc nút đã tồn tại.

## 8. Điểm cần người dùng duyệt

1. C02: cách lưu draft bền vững và migration dữ liệu Studio nếu cần.
2. C05/C07: bất kỳ thay đổi bố cục/nội dung template khách hàng hoặc semantic ngoài v1.
3. C11: thiết kế backup/restore, phạm vi thay kho và thời gian tạm khóa thao tác Studio.
4. C12/C13: thay workflow đáng kể, job nền mới hoặc lịch chạy workload lớn/soak.
5. C08/C14: duyệt DOCX baseline nhìn thực tế, nhất là template khách hàng.
6. C15: candidate release, push/merge, và việc xóa artifacts là yêu cầu riêng.

Các sửa lỗi khôi phục hành vi đã chốt có thể triển khai sau khi plan được duyệt,
nhưng không tự suy rộng sang đổi template mặc định, mở mạng toàn server hoặc xóa dữ liệu.

## 9. Định nghĩa “hoàn thiện Template Studio”

- [ ] DOCX mới được đánh giá, giới hạn hỗ trợ minh bạch, nguồn gốc không bị sửa.
- [ ] Mapping được duyệt đủ và đúng; Tracking không đổi hợp đồng.
- [ ] Draft/retry/restart/conflict không mất việc hoặc tạo approval/version giả.
- [ ] DOCX đúng dữ liệu, đúng bố cục trong phạm vi đã duyệt, có traceability.
- [ ] Validation/evidence/publish/version/recovery có backend enforcement.
- [ ] Pack được dùng thực tế trong Configure → Preview → Generate, default vẫn ổn.
- [ ] Kho Studio có quy trình backup/restore đã thử được, retention không mất nguồn quan trọng.
- [ ] UI cũ được hoàn thiện cả light/dark/keyboard/lỗi và tiến trình thật.
- [ ] Gate bản cuối và clean-clone đạt, hướng dẫn tự kiểm tra đầy đủ.
- [ ] Hạn chế/pilot chưa có được ghi công khai; không tuyên bố “100% mọi template”.

## Tài liệu liên quan

- [Trạng thái và lịch sử](TEMPLATE_STUDIO_STATUS.md)
- [Đợt đồng bộ UI/API đang làm](TEMPLATE_STUDIO_BACKEND_ALIGNMENT.md)
- [Kiến trúc pack](TEMPLATE_PACKS.md)
- [Hướng dẫn người dùng](TEMPLATE_STUDIO_USER_GUIDE.md)
- [Checklist dọn thư mục — chưa duyệt xóa](PROJECT_CLEANUP_CHECKLIST.md)
