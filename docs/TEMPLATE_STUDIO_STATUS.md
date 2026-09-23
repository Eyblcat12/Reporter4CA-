# Template Studio — trạng thái triển khai và hồ sơ bàn giao

> **Ngày cập nhật:** 23/09/2026
> **Nhánh tích hợp:** `codex/reporter-pro-github-release`
> **Baseline ổn định:** `github/main` tại commit `5ddfc44`
> **Trạng thái hiện tại:** ứng viên đã qua clean-clone gate, gồm pack selection,
> source library/normalization và editor checkpoints. Trạng thái push/clean-clone
> ghi tại GITHUB_SYNC_PLAN_2026-09-23.md; không xem checklist C01–C15 là đã đóng.
> **Feature flag:** `AUTO_REPORT_TEMPLATE_PACKS=1` theo mặc định; `0` là kill switch

Tài liệu này là nguồn trạng thái chính cho chương trình Template Studio. Mỗi lần
tiếp tục công việc phải đọc tài liệu này và `TEMPLATE_PACKS.md` trước khi sửa mã.
Khi trạng thái thay đổi, cập nhật tài liệu này trong cùng commit với thay đổi.

## Checkpoint TS-15 — tích hợp được người dùng yêu cầu ngày 06/09/2026

### 23/09/2026 — cổng đồng bộ source

Ứng viên `2144f1d` (trên `4653a83`): setup mới từ lockfile, launcher production,
402 backend / 134 frontend / 7 E2E đạt trong clone cách ly. Bản vá Vitest 4.1.11
được tách commit; npm audit 0 advisory tại thời điểm kiểm tra. Source runtime và
template mặc định được giữ nguyên so với baseline. Xem hồ sơ sync cho trạng thái
push/clone GitHub sau cùng; đây không phải phát hành prebuilt hoặc đóng C01–C15.

Readiness: 402 backend tests, 134 frontend tests, Ruff/ESLint/Prettier/build đạt.
3 E2E API thật (kho tạm) và 3 E2E report/theme đạt. E2E mock Studio từng lỗi do
thiếu editor-drafts; đã bổ sung save/retire và xác minh thứ tự, chạy lại 1/1 đạt.
Chưa thay Legacy Renderer/templates. Không công bố backup toàn Studio hoặc Word
visual approval đã hoàn tất. Kế hoạch và bằng chứng clean-clone được theo dõi tại
[GITHUB_SYNC_PLAN_2026-09-23.md](GITHUB_SYNC_PLAN_2026-09-23.md).

### 10/09/2026 — C02 lifecycle checkpoint

**Cập nhật UI cùng ngày:** đã nối autosave debounce 600 ms, hàng đợi save tuần tự,
chỉ báo đã lưu sau ACK, retry giữ nguyên operation ID khi kết quả chưa xác định.
API draft có timeout 15 giây. Có danh sách checkpoint phân trang, khôi phục theo
source/semantic, giữ base revision gốc; draft stale không được duyệt. Bỏ draft và
duyệt thành công đóng checkpoint qua retire, không xóa nội dung hay nâng coverage
bằng autosave. Hướng dẫn tại TEMPLATE_STUDIO_USER_GUIDE.md.

Kiểm chứng lượt UI: 134 frontend tests/27 files, ESLint và production build đạt;
42 backend tests (draft store/API integration) đạt. Vẫn có warning React act ở
suite lịch sử. Chưa test browser restart/hai tab với backend thật hoặc visual QA
lượt này. Chưa đóng C02: còn conflict comparison, điều hướng nội bộ và E2E recovery.
Không thay template mặc định/Legacy Renderer; chưa commit/push.

Thêm retire API/store: marker đóng thay vì xóa nội dung, revision/operation guard,
không hồi sinh từ save trễ; approved phải đối chiếu đúng source/anchor/fields của
mapping đã commit dưới workspace lock. 12 test draft store/API và bộ mở rộng
64 tests (draft/workspace/library/API integration) đạt; Ruff check/format đạt.
Không sửa report DB/template/Legacy Renderer. Mốc backend này được nối UI ở cập
nhật phía trên; chưa đóng C02. Chi tiết tại TEMPLATE_STUDIO_DRAFT_STORAGE_DESIGN.md.

### 08/09/2026 — kế hoạch hoàn thiện tổng thể

**Sửa lỗi người dùng kiểm thử (08/09, 13:52):** Studio fixture gọi column-preview
trước import-file và chuyển suggestedMapping/header/sheet, như importer hiện có;
parser bảng dùng định dạng thật thay vì đuôi file. API thật với samples đạt
Tracking.csv 20 server/10 client và Tracking_2.csv 22 server/28 client.
Ô cột nhận cả số 1/2/3 và column:N, gửi hợp đồng chuẩn lên backend; vẫn chặn
trùng/nhảy cóc. Tìm anchor chuẩn hóa cả query và tên; token Full
REMEDIATION_REGISTER được gợi ý chỉ khi có trong nguồn, không tự duyệt.
31 backend import/API tests và 126 frontend tests/26 files đạt; Ruff/ESLint/build
1.935 modules đạt. Suite frontend còn warning act lịch sử ở Dashboard/RuleManager.
Chưa chạy browser E2E/visual Word đợt này. Không sửa sample, template hoặc Legacy
Renderer; production frontend đã rebuild, cần khởi động lại tool để nạp backend.

**C02, backend checkpoint đã được duyệt:** thêm SQLite draft riêng và GET/PUT API
feature-gated, revision + idempotent operation journal, bounded editor payload,
list phân trang/stale, không tăng approval/coverage. 59 backend tests liên quan
đạt, Ruff check/format đạt; test mới vào CI. Chỉ dùng storage tạm khi test.
UI autosave/restore và retire/discard checkpoint còn lại, chưa đóng C02.

**C02, lượt tiếp theo:** thêm cảnh báo beforeunload cho RAM draft/mutation đang chạy,
không báo dirty khi đã sửa về baseline; theo dõi cả draft ở section khác.
20 Workbench tests, ESLint và production build 1.935 modules đạt. Chưa có checkpoint
qua restart. [Thiết kế lưu draft riêng](TEMPLATE_STUDIO_DRAFT_STORAGE_DESIGN.md)
đã viết để xin duyệt trước khi bổ sung storage/API. Chưa sửa database hay nguồn khách hàng.

**Checkpoint triển khai sau khi duyệt:** bắt đầu phần C06 về an toàn mapping cột.
Chặn target nhảy cóc ở approval/profile/pack gate và UI, giữ hỗ trợ đảo thứ tự đủ
cột 1..N. Thêm regression và sửa fixture đích cột bằng tên không khớp renderer.
86 backend tests liên quan + 18 frontend Workbench tests đạt; Ruff check/format
đạt; ESLint và production build 1.935 modules đạt. Runtime test có cảnh báo CScript access denied, chưa xác nhận Word field/TOC
hay visual QA. C06 chưa hoàn tất và chưa chạy full release gate.

Đã lập [kế hoạch C01–C15](TEMPLATE_STUDIO_COMPLETION_PLAN.md): 15 task, 5 đợt,
chi tiết đầu việc/phụ thuộc/ảnh hưởng/gate và điểm cần duyệt. Người dùng sau đó
đã duyệt thực hiện; checkpoint triển khai ghi riêng ở trên. Giữ UI cũ,
pack selection đã tích hợp và Legacy Renderer/template mặc định không đổi.
Lượt lập kế hoạch chỉ rà soát và viết tài liệu; không chạy lại test, migrate, xóa dữ liệu
hoặc commit/push. Kết quả frontend 119 tests bên dưới vẫn là lượt 07/09.

### 07/09/2026 — chốt UI cũ, triển khai đồng bộ backend

Quyết định mới nhất thay thế hướng phát triển Stitch: giữ UI Studio cũ và hoàn
thiện chức năng thật. Xem [kế hoạch và audit](TEMPLATE_STUDIO_BACKEND_ALIGNMENT.md).
Đợt đầu sửa request lỗi thời, phản hồi approval sau đổi workspace, summary bỏ
mapping, AbortError và thông báo 404. Bảy test mới tập trung đạt. Chưa hoàn tất
draft recovery, mutation timeout, chuẩn hóa/validation/publish audit hoặc E2E.

Đợt 2: giữ draft trong bộ nhớ theo workspace/nguồn Word/section, bảo toàn revision
gốc, chặn duyệt draft lỗi thời và cột trùng; ràng buộc phản hồi lưu với editor.
Frontend 119 tests/26 files, lint và production build đạt (07/09, 13:22).
Chưa có draft qua refresh, merge conflict hoặc đối chiếu mutation timeout;
chưa chạy lại backend/E2E/golden đợt này. Chi tiết và giới hạn trong kế hoạch trên.

### Nhánh công việc UI Stitch — 06/09/2026

#### 07/09/2026 — lối vào so sánh riêng theo mẫu người dùng

- `?view=template-studio-next`: UI mẫu Stitch được cách ly, chỉ dữ liệu tổng hợp;
  không nối các thao tác save/import/publish vào backend.
- `?view=template-studio`: Studio chức năng hiện có, thêm link so sánh UI. Chuyển
  cùng trang giữ draft của Studio/report và một RuntimeLifecycle duy nhất.
- Mẫu iframe sandbox không script/same-origin, CSP chặn mạng, CSS offline và
  SVG nội bộ. Không thay module legacy renderer, template hoặc database.
- Sáu test tập trung (navigation + isolation) đạt; toàn bộ frontend 120 test/25
  file, lint và format:check đạt. Production build đạt 1.935 modules. Không chạy
  lại backend/E2E trong đợt UI-only này. Visual QA và duyệt người dùng vẫn còn,
  không coi mockup là flow hoàn chỉnh.
- Thư mục mới: apps/frontend/src/features/template-studio-next/; xem README ở đó
  cho phạm vi, rebuild CSS và gate tiếp theo. Bản HTML mockup cũ không bị xóa.

Đã lưu [kế hoạch UI/UX Stitch](TEMPLATE_STUDIO_STITCH_PLAN.md). Người dùng đã chốt
phương án B / Mapping Workspace, yêu cầu UI/backend chất lượng enterprise;
còn gate duyệt prototype tương tác trước tích hợp UI. Đợt này chỉ thiết
kế/tài liệu, không thay UI thật, importer Tracking hoặc renderer mặc định. Mục
tiêu là thích nghi template khách hàng với Tracking hiện có, không đổi Tracking
để khớp template. Xem nhật ký trong kế hoạch trước khi tiếp tục hoặc tạo lại screen.

### Chốt phiên thư viện nguồn và hướng dẫn tự kiểm tra

Phạm vi phiên này chỉ là Template Studio, theo xác nhận của người dùng; không
thay đổi luồng tạo report legacy hoặc template khách hàng.

- Gate đầy đủ `scripts/check.ps1`: **385 backend**, **116 frontend**, Ruff,
  ESLint, Prettier và build **1.931 modules** đạt. Test tài liệu hướng dẫn mới
  thêm sau lượt full gate cũng đạt **5/5** (thêm một test so với gate).
- E2E **8/8** trên Chromium; bốn kịch bản API thật dùng kho tạm riêng. Không dùng
  workspace/template khách hàng làm dữ liệu ghi thử. Các kịch bản mock còn lại
  bảo vệ luồng báo cáo và theme đã có.
- Đã build lại `apps/frontend/dist` để launcher dùng bản mới. Cần khởi động lại
  tool để backend nạp SQLite library/API mới. Chưa commit/push các thay đổi phiên này.
- Đã xem screenshot thư viện nguồn dark/light/760px, giữ bố cục Workbench hiện có.
- [Hướng dẫn tự kiểm tra](TEMPLATE_STUDIO_USER_GUIDE.md) có bài tập fixture Full,
  bảng anchor/cột, thư viện nguồn, chuẩn hóa và xử lý lỗi.
- Còn bước nghiệm thu của người dùng: chọn/duyệt mapping và xem DOCX với template
  thực tế của khách hàng. Giới hạn v1 (body paragraph/table, semantic catalog hiện có)
  vẫn áp dụng; không tuyên bố tương thích vô điều kiện với mọi cấu trúc Word.

Checkpoint này thay thế các giới hạn lịch sử “chưa nối Generate” ở bên dưới.
Người dùng yêu cầu hoàn thiện toàn luồng và đưa Template Studio vào tool chính.
Không thay các template khách hàng hoặc Legacy Renderer.

- Sửa stepper tĩnh và nút review bị disabled ở 100%; bước Rà soát có thao tác thật,
  hiển thị blocker, rồi chuyển vào validation/publish hiện có.
- Workspace thực tế được kiểm tra chỉ đọc: 54 heading, 37 bảng, không có anchor,
  coverage 0%. Không tự phê duyệt hoặc tự sửa workspace này.
- Thêm chuẩn hóa copy-only: đọc danh sách đoạn/bảng, người dùng chọn vị trí cho
  từng semantic và chọn chèn sau/thay nội dung. Tạo workspace và source mới; nguồn
  cũ không đổi. Revision, vị trí trùng, thiếu semantic, anchor lồng/trùng bị chặn.
- Validation nhận JSON hoặc Tracking CSV qua import API hiện có; rule evaluation
  và scope server/client được áp dụng cho cả fixture và production pack.
- `/api/templates` cung cấp các pack đã phát hành, kiểm checksum và report type.
  Chọn `rptpack:<id>:<version>` là quyết định rõ ràng của người dùng; không tự đổi
  template mặc định hoặc theo activeVersion của Catalog.
- Preview/Generate dùng job, cache, history, download và cancellation hiện có.
  Snapshot pin toàn bộ pack SHA-256 vào signature; pack sai loại, hỏng hoặc Studio
  bị tắt sẽ bị từ chối, không fallback sang Legacy Renderer.
- Plugin tùy chỉnh không chạy trong pack đã kiểm duyệt; UI tắt plugin khi chọn pack.
  Template Manager cũ chỉ quản lý DOCX legacy; version pack quản lý trong Catalog.
- Profile Renderer bảo tồn bảng prototype khi chuẩn hóa theo chế độ thay bảng
  (header, widths, borders, row/cell properties); số cột không khớp bị chặn.
- Kiểm thử mới: `tests.test_template_pack_runtime`, `NormalizeDialog.test.jsx`,
  regression bước 2→3→4, fixture CSV và `e2e/studio-publish-live.spec.js`.
- Backend E2E cô lập: `python scripts/serve_studio_test_backend.py` dùng thư mục
  tạm, port 8011, không ghi workspace/catalog/report thử vào dữ liệu người dùng.
  Chạy Playwright với `REPORTER_STUDIO_TEST_API=http://127.0.0.1:8011` và
  `REPORTER_LIVE_API=http://127.0.0.1:8011` để bật hai kịch bản API thật.

### Những điều không được suy diễn là đã tự động hoàn thành

**Kết quả chốt 06/09/2026:** `scripts/check.ps1` đạt **381 backend tests**, **112
frontend tests**, Ruff, ESLint, Prettier và production build **1.930 modules**.
Chromium E2E đạt **7/7**: 3 kịch bản dùng backend thật với storage tạm (giữ phiên,
map/review/validate/publish/production Preview→Generate, chuẩn hóa DOCX thô); 4
kịch bản còn lại dùng fixture/mock. Test full/server/client ngoài sandbox đạt,
không còn cảnh báo CScript access denied trong lượt đó. Mặc định/template legacy
không có diff. Build `apps/frontend/dist` đã cập nhật, cần khởi động lại tool để
backend nạp module mới. Chưa nghiệm thu DOCX khách hàng hiện tại vì người dùng
chưa chọn/duyệt các vùng mapping của template đó.

- Template tùy ý vẫn cần người dùng chọn vị trí/mapping và duyệt DOCX thực tế.
  Công cụ không thể biết các đoạn tĩnh nào là dữ liệu mẫu cần bỏ nếu chưa được chỉ ra.
- Chuẩn hóa v1 hỗ trợ đoạn/bảng cấp body; layout lồng phức tạp, text box hoặc anchor
  trong header/footer cần chuẩn hóa trong Word trước. Không nhận là hỗ trợ mọi DOCX.
- Kết quả test synthetic không thay cho nghiệm thu nội dung/định dạng của khách hàng.
- Những mục bên dưới là hồ sơ lịch sử; release gate hiện tại phải được chạy lại
  trên working tree này trước khi commit/build giao người dùng.

**Checkpoint khả dụng ngày 06/09/2026:** Template Studio đã có entry riêng trong
sidebar, authoring API mặc định bật và có nút quay lại Reporter Pro. Visual QA với
frontend/backend thật xác nhận mở Studio, trạng thái workspace rỗng và quay lại
dashboard đều đạt. Full gate đạt **378/378 backend tests**, **106/106 frontend
tests**, Ruff, ESLint, Prettier và production build **1.929 modules**. Catalog vẫn
trả `selectionIntegrated: false`; không tệp template mặc định hay module Legacy
Renderer nào bị sửa.

## 1. Mục tiêu đã thống nhất

### Hotfix điều hướng và phiên chạy — 06/09/2026

- Sửa chuyển Reporter Pro ↔ Template Studio: điều hướng trong ứng dụng thay vì
  tải lại trang; giữ provider, dữ liệu report và bản nháp Studio trong cùng tab.
  Back/Forward đồng bộ màn hình với URL. F5/đóng tab không thuộc cam kết giữ draft này.
- RuntimeLifecycle được giữ ở cấp ứng dụng, kể cả khi mở trực tiếp Studio;
  chuyển màn hình không đóng phiên khiến launcher tưởng người dùng đã thoát.
- Thêm `App.navigation.test.jsx` (giữ draft hai chiều và phiên mở trực tiếp).
- Thêm `e2e/studio-live.spec.js`: chuyển tiếp request tới backend thật qua
  `REPORTER_LIVE_API`, import CSV, phân tích DOCX synthetic, xác nhận heartbeat,
  giữ dữ liệu và Back/Forward. Đã chạy đạt trên Chromium với backend cục bộ.
  Test không tạo workspace lâu dài, không sửa template khách hàng; không phải
  kiểm thử đóng cửa sổ CMD thực tế hoặc nối pack vào production Generate.
- Chạy lại test này từ `apps/frontend` khi backend cục bộ đang chạy:

  ```powershell
  $env:REPORTER_LIVE_API='http://127.0.0.1:8000'
  npm run test:e2e -- studio-live.spec.js
  ```

- Giữ nguyên ranh giới: Template Studio phục vụ authoring/test/publish;
  chọn pack trong Generate vẫn là TS-15, chưa tích hợp.
- Xác minh sau sửa: **378 backend tests**, **108 frontend tests**, **5 Chromium
  E2E tests** đạt (1 E2E dùng backend thật, các E2E còn lại dùng fixture/mock).
  Ruff, ESLint, Prettier và production build 1.929 modules đạt. Bộ backend bao
  gồm roundtrip Tracking 30 máy/8 bất thường và Tracking đa dạng 50 máy.
  Không suy rộng kết quả này thành bảo đảm mọi template khách hàng đều tương thích.

Reporter Pro hiện tạo report tốt bằng các template mặc định đã chuẩn hóa. Hướng
phát triển mới không thay thế luồng đó. Mục tiêu là bổ sung một đường xử lý song
song để hỗ trợ template Word có cấu trúc hoàn toàn khác:

```text
DOCX mới
  → phân tích cấu trúc
  → người vận hành mapping và chuẩn hóa thủ công
  → bắt buộc đạt 100% semantic mapping
  → chạy fixture, integrity và visual validation
  → đóng gói thành Template Pack có version
  → Profile Renderer tạo report thử
  → chỉ tích hợp opt-in sau khi được duyệt
```

Tool không cần tự hiểu mọi template với độ chính xác 100%. Template mới luôn phải
được phân tích, mapping, kiểm thử và chuẩn hóa trước khi đưa vào kho tái sử dụng.

## 2. Các quyết định sản phẩm không được tự ý thay đổi

1. Luồng `full`, `server_only`, `client_only` và các template mặc định hiện tại là
   baseline theo yêu cầu khách hàng; không chỉnh format hoặc renderer nếu không có
   yêu cầu trực tiếp.
2. Legacy Renderer phải sử dụng được trong mọi thời điểm phát triển.
3. Template Studio là một phần của ứng dụng local/team và phải truy cập được từ
   sidebar; việc khả dụng không đồng nghĩa được phép thay luồng Generate.
4. Không tự động đưa pack mới vào dropdown template hoặc Generate.
5. Mapping phải do người dùng duyệt; gợi ý từ analyzer không phải mapping đã duyệt.
6. Coverage 100% phải do validator tính, không cho nhập phần trăm thủ công.
7. Không fallback âm thầm sang template hoặc renderer khác khi Profile Renderer lỗi.
8. Bản hiện tại ưu tiên cá nhân/team. Server mode, authentication, multi-tenancy và
   plugin không tin cậy chưa nằm trong phạm vi triển khai.
9. PDF export đã được hoãn để giữ bản local/team gọn.
10. Chính sách tài nguyên phải tính tới dự án dưới 50.000 máy; không đặt giới hạn
    thấp tùy tiện chỉ để che vấn đề hiệu năng.
11. UI Template Studio phải ít chú thích, mật độ thông tin hợp lý và theo mô hình
    authoring workbench của công cụ enterprise, không phải dashboard nhiều card.

## 3. Ranh giới kiến trúc bắt buộc

### Luồng ổn định đang hoạt động

```text
Tracking/raw input
  → import + normalize + data quality + rule engine
  → Configure
  → Legacy Renderer
  → template mặc định hiện tại
  → Preview/Generate DOCX
```

### Luồng thử nghiệm

```text
DOCX mới
  → Template Profile Analyzer
  → Mapping Workspace
  → Pack Builder
  → Isolated Pack Catalog
  → Profile Renderer (domain-only, chưa nối Generate)
```

Ba module legacy sau bị kiểm thử kiến trúc cấm import runtime Template Pack:

- `apps/backend/core/report_generator.py`
- `apps/backend/core/report_orchestrator.py`
- `apps/backend/core/report_snapshot.py`

Catalog trả về `selectionIntegrated: false` và `legacyRendererUnchanged: true`.
“Active” trong catalog hiện chỉ là lựa chọn nội bộ của Template Studio, không có
quyền thay template tạo report.

## 4. Trạng thái Git và dữ liệu tại thời điểm bàn giao

| Nội dung | Trạng thái |
|---|---|
| `github/main` | Đã merge Template Studio tại `32e82e5`, hardening flag tại `5ddfc44` |
| Nhánh làm việc | `codex/reporter-pro-github-release`, theo dõi `github/main` |
| UI Workbench V2 | React route đã duyệt và đã merge; bổ sung entry sidebar mặc định |
| `apps/backend/data/` | Runtime/user data, untracked; tuyệt đối không stage hoặc commit |

Các thay đổi chưa commit hợp lệ hiện tại:

- React Template Studio feature-gated: workspace lifecycle, upload/analyze,
  mapping, retention, validation/publish và catalog activate/rollback.
- Experimental API bổ sung validation history cùng artifact DOCX deterministic;
  domain mapping chặn một anchor được dùng cho nhiều semantic.
- Component/API/E2E regression và tài liệu cho các phần trên.
- `docs/template-studio-workbench-v2.html` là prototype nguồn của React route.
- `docs/template-studio-workbench.html`, phần Workbench trong
  `tests/test_template_studio_prototype.py` và `docs/skill-drafts/` đã tồn tại từ
  trước checkpoint UI hiện tại; không tự ý xóa hoặc coi là runtime artifact.
- `apps/backend/data/` là runtime/user data; tuyệt đối không stage hoặc commit.
- Ba DOCX fixture tổng hợp `full`, `server_only`, `client_only` cùng generator và
  manifest checksum. Người dùng cho phép tự tạo các template này để hoàn tất
  kiểm thử khi chưa có template khách hàng; chúng không thay thế template mặc định.

Workspace Index và toàn bộ lifecycle/transfer/retention TS-10 đã được chốt tại
commit `7b81937`. Profile Renderer domain TS-11 đã được chốt tại commit `1ca3eea`;
Validation Runner domain TS-12 được chốt tại commit `8aef963`. Các phần này không
còn là thay đổi làm việc chưa commit. Preview/diff domain TS-13 được chốt tại
commit `619faaa`, với tài liệu checkpoint tại `576b4ac`.

Nếu trạng thái Git khác danh sách trên ở phiên sau, phải kiểm tra chủ sở hữu thay
đổi trước khi stage, sửa hoặc xóa.

## 5. Những phần đã hoàn thành

### TS-01 — Feature boundary và schema v1 — hoàn thành

- Feature flag `AUTO_REPORT_TEMPLATE_PACKS`, mặc định bật cho authoring; giá trị
  `0` chỉ dùng để cô lập khẩn cấp API Studio.
- Bốn JSON Schema Draft 2020-12 cho manifest, layout, mapping và validation.
- Semantic catalog riêng cho sáu report type.
- Validator kiểm tra profile ID, schema version, renderer, source, anchor, field,
  semantic coverage và validation evidence.
- Trạng thái profile: `draft`, `analyzed`, `mapping_incomplete`,
  `mapping_complete`, `test_failed`, `test_passed`, `published`.

Tệp chính:

- `apps/backend/core/template_profiles.py`
- `apps/backend/config/template_packs/*.schema.json`
- `apps/backend/core/config.py`

### TS-02 — DOCX analyzer chỉ đọc — hoàn thành

- Phân tích content control, bookmark và token kể cả token bị tách qua nhiều run.
- Thống kê heading, table, header/footer, section, page break, TOC, numbering và
  relationship.
- Phát hiện anchor trùng hoặc không ổn định.
- Tạo checklist gợi ý nhưng luôn bắt đầu ở 0% mapping.
- Chặn XML declaration nguy hiểm.

Tệp chính: `apps/backend/core/template_profile_analyzer.py`.

### TS-03 — Mapping Workspace — hoàn thành phần domain/backend

- Pin source DOCX bất biến theo SHA-256.
- Workspace JSON có checksum và ghi nguyên tử.
- Approve/remove từng semantic mapping.
- Anchor phải tồn tại đúng một lần trong kết quả analyzer.
- Một anchor chỉ được gán cho một semantic; backend từ chối ghi đè hoặc dùng lại
  anchor đã được block khác sở hữu.
- Field mapping bắt buộc đầy đủ và không trùng source/target.
- Optimistic concurrency qua `expectedRevision`; stale editor bị từ chối.
- Audit log theo revision và actor.
- Đạt 100% chỉ chuyển sang `mapping_complete`, chưa được tự publish.

Tệp chính: `apps/backend/core/template_mapping_workspace.py`.

### TS-04 — Safe Template Pack inspector — hoàn thành

- Pack chỉ được chứa đúng năm tệp dữ liệu.
- Kiểm tra checksum, DOCX package, file count, archive size, expanded size và
  compression ratio.
- Chặn path traversal, file thừa, symlink, encryption và trường JSON không hỗ trợ.
- Không extract hoặc thực thi nội dung pack.

Tệp chính: `apps/backend/core/template_pack.py`.

### TS-05 — Pack Builder — hoàn thành phần domain

- Chỉ build từ workspace `mapping_complete` có source checksum khớp.
- Yêu cầu fixture, integrity và visual evidence đều đạt.
- Tạo archive ổn định, sinh checksum và tự inspect đầu ra trước khi trả kết quả.
- Pack Builder không có endpoint nhận pack/evidence tùy ý. TS-14 chỉ gọi Builder
  sau workflow validation hai lượt do backend sở hữu; browser không thể tự chứng
  nhận fixture/integrity bằng các boolean do client gửi lên.

Tệp chính: `apps/backend/core/template_pack_catalog.py`.

### TS-06 — Version catalog và rollback — hoàn thành backend

- Version pack bất biến; cùng `packId + version` không thể bị thay bằng nội dung
  khác.
- Install, activate và rollback có revision guard và audit log.
- Kiểm tra checksum payload trước khi chọn version.
- Catalog nằm riêng trong `data/template_studio/catalog`, không dùng database
  template hiện tại.

### TS-07 — Experimental API — hoàn thành baseline

Tất cả endpoint trả `404` khi feature flag tắt:

| Method | Endpoint | Trạng thái |
|---|---|---|
| POST | `/api/template-packs/inspect` | Hoàn thành |
| POST | `/api/template-packs/analyze-template` | Hoàn thành |
| POST | `/api/template-packs/workspaces` | Hoàn thành |
| POST | `/api/template-packs/workspaces/import` | Hoàn thành TS-10B.2 |
| GET | `/api/template-packs/workspaces` | Hoàn thành TS-10A |
| GET | `/api/template-packs/workspaces/{id}` | Hoàn thành |
| GET | `/api/template-packs/workspaces/{id}/export` | Hoàn thành TS-10B.2 |
| PATCH | `/api/template-packs/workspaces/{id}/rename` | Hoàn thành TS-10B.1 |
| POST | `/api/template-packs/workspaces/{id}/clone` | Hoàn thành TS-10B.1 |
| POST | `/api/template-packs/workspaces/{id}/archive` | Hoàn thành TS-10B.1 |
| GET | `/api/template-packs/workspaces/retention/preview` | Hoàn thành TS-10B.3 |
| POST | `/api/template-packs/workspaces/retention/apply` | Hoàn thành TS-10B.3 |
| POST | `/api/template-packs/workspaces/retention/{id}/restore` | Hoàn thành TS-10B.3 |
| PUT | `/api/template-packs/workspaces/{id}/mappings/{semantic}` | Hoàn thành |
| POST | `/api/template-packs/workspaces/{id}/mappings/{semantic}/remove` | Hoàn thành |
| GET | `/api/template-packs/catalog` | Hoàn thành |
| POST | `/api/template-packs/catalog/install` | Hoàn thành |
| POST | `/api/template-packs/catalog/{packId}/activate` | Hoàn thành |
| POST | `/api/template-packs/catalog/{packId}/rollback` | Hoàn thành |
| GET | `/api/template-packs/catalog/recovery` | Hoàn thành TS-17A |
| POST | `/api/template-packs/catalog/recovery` | Hoàn thành TS-17A |
| POST | `/api/template-packs/workspaces/{id}/validation-runs` | Hoàn thành TS-14 |
| GET | `/api/template-packs/workspaces/{id}/validation-runs` | Hoàn thành TS-09C.2 |
| GET | `/api/template-packs/workspaces/{id}/validation-runs/{runId}/artifact` | Hoàn thành TS-14 |
| POST | `/api/template-packs/workspaces/{id}/validation-runs/{runId}/approve-baseline` | Hoàn thành TS-14 |
| POST | `/api/template-packs/workspaces/{id}/validation-runs/{runId}/publish` | Hoàn thành TS-14 |

### TS-08 — UI exploration — đã chốt hướng để tiếp tục

Ba file HTML độc lập đã được tạo để nghiên cứu UI. Hai file đầu là lịch sử thử
nghiệm; không dùng làm thiết kế triển khai cuối:

- `docs/template-studio-prototype.html` — prototype ban đầu.
- `docs/template-studio-enterprise.html` — prototype enterprise đầu tiên, người
  dùng đánh giá vẫn chưa phù hợp.
- `docs/template-studio-workbench.html` — hướng mới đang chờ review.
- `docs/template-studio-workbench-v2.html` — hướng enterprise đã tinh gọn và được
  dùng làm baseline triển khai React.

Workbench mới có workflow `Analyze → Map → Review → Test → Publish`, bảng mapping
làm nội dung chính, search/filter, contextual drawer và dark/light mode. File
không có external asset, form, API call hoặc liên kết tới tool thật.

Ngày 27/08/2026, prototype được audit bằng skill cá nhân
`reporter-enterprise-ui-ux`. Pass đầu tiên chỉ sửa usability/accessibility, không
đổi visual direction: bổ sung keyboard-accessible mapping rows, search label,
table/progress semantics, trạng thái filter/theme, focus-visible, focus return
khi đóng drawer và reduced-motion support. Bố cục Workbench và ranh giới Legacy
Renderer được giữ nguyên; visual direction vẫn cần người dùng duyệt.

Ngày 28/08/2026, pass enterprise thứ hai hoàn thiện hành vi của prototype mà vẫn
không nối API: drawer phản ánh đúng `mapped/unmapped` và renderer, dùng Word anchor
control thật, cho phép approve/unmap cục bộ, cập nhật coverage/blocker/revision,
giữ selection đồng bộ với search/filter và hỗ trợ Escape/focus return. CTA dẫn
thẳng tới blocker thay vì cho Review khi coverage chưa đủ 100%.

Workbench cũng đã chuyển sang một ngôn ngữ nhất quán, bỏ annotation lặp, rút gọn
summary, bổ sung overlay drawer/reflow ở viewport hẹp, local table scrolling,
loading-recovery variants qua `?state=conflict|load-error|save-timeout`, và token
contrast tối thiểu 4.5:1 cho text/filled action, 3:1 cho control boundary. Các
thay đổi chỉ nằm trong prototype độc lập.

Ngày 01/09/2026, Workbench V2 bổ sung inline primary-detail trên desktop, drawer
có focus trap ở viewport hẹp, một primary action theo ngữ cảnh, phân biệt loading/
empty/filter-empty, giữ draft khi lưu lỗi và trạng thái revision conflict. Sau khi
review file độc lập, người dùng yêu cầu tiếp tục; đây là quyền triển khai route
React feature-gated, chưa phải quyền nối Template Pack vào Generate hoặc thay đổi
template mặc định.

### TS-09A — React Mapping Workbench — hoàn thành working tree

- Route mở khi URL có `?view=template-studio`; AppShell baseline vẫn là route mặc định.
- Sidebar có mục **Template Studio** riêng trong **Tools**. Không thêm pack vào
  Configure, template selector hoặc Generate.
- API client chỉ gọi workspace list/get/approve/remove feature-gated hiện có; xử
  lý network error, backend disabled và revision conflict `409` bằng error envelope.
- Mapping table có search/filter, coverage, blocker navigation và contextual
  inspector; field mapping gửi đúng `column:<n>` contract của backend.
- Inspector liệt kê toàn bộ content control, bookmark và token xuất hiện đúng một
  lần trong template, không chỉ các anchor được analyzer gợi ý. Gợi ý được ưu tiên,
  anchor mơ hồ bị loại và anchor đã dùng được khóa kèm semantic đang sở hữu.
- Mapping vẫn cần thao tác `Duyệt ánh xạ` rõ ràng; không auto-save quyết định duyệt
  để giữ audit/revision minh bạch và tránh ghi nhầm khi người dùng đang thử anchor.
- Draft cục bộ không mất khi save lỗi; remove cần xác nhận; light/dark, keyboard,
  focus return, overlay focus trap, loading/empty/error và reduced motion đã có.
- Gate đầy đủ sau nâng cấp anchor picker: **376/376 backend tests**, **105/105
  frontend tests**, ESLint, Prettier và production build **1.929 modules** đều đạt.
  Đây là checkpoint lịch sử trước khi authoring API được bật mặc định.

### TS-09B.1 — React Workspace lifecycle — hoàn thành working tree

- Workspace manager tách khỏi mapping screen, có active/archived tab, tìm kiếm,
  chọn nhanh và contextual action panel; không thêm vào Sidebar mặc định.
- List tự theo toàn bộ cursor ổn định thay vì âm thầm cắt ở 100 workspace; cursor
  lặp bị coi là lỗi retryable và workspace corrupt được báo là đã cô lập.
- Rename, clone, archive và restore gửi `expectedRevision`; archive có xác nhận và
  chỉ chuyển draft sang read-only, không xóa dữ liệu.
- Import chỉ nhận `.rptdraft` tối đa 30 MiB ở client rồi backend tiếp tục kiểm
  checksum/archive; export tải đúng payload data-only do backend cấp.
- Dialog có focus trap, Escape, focus return, loading/error/conflict và reflow
  cho viewport hẹp. Thay đổi không gọi Profile Renderer hoặc Generate.

### TS-09B.2a — React retention quarantine — hoàn thành working tree

- Nút `Dọn an toàn` nằm trong Workspace Manager, không xuất hiện ở flow Import,
  Configure, template selector hoặc Generate mặc định.
- Người dùng phải chạy dry-run trước; UI chỉ hiển thị số workspace, source và dung
  lượng dự kiến, không gửi lệnh apply ngay khi mở màn hình.
- Apply chỉ khả dụng khi backend trả confirmation token và không có blocker. Token
  không được hiển thị; conflict do plan thay đổi buộc người dùng preview lại.
- Kết quả được chuyển vào quarantine có mã batch và nút khôi phục ngay. UI không có
  thao tác xóa vĩnh viễn và vẫn hoạt động khi danh sách workspace đang trống.
- Regression bao phủ preview-before-apply, blocker, apply/restore và API contract.

### TS-09B.2b — Upload/analyze và tạo workspace — hoàn thành working tree

- `Template mới` mở workflow riêng trong Workspace Manager, kể cả khi danh sách
  workspace trống; không đi qua Import mặc định và không xuất hiện trong Sidebar,
  Configure, template selector hoặc Generate.
- Client chỉ đọc `.docx` không rỗng, tối đa 20 MiB, có trạng thái đọc file; backend
  tiếp tục xác minh package OOXML và giới hạn giải nén trước khi phân tích.
- Workflow bắt buộc hai lệnh tách biệt: phân tích chỉ đọc trước, sau đó mới cho tạo
  workspace. Đổi source hoặc report type làm mất hiệu lực kết quả phân tích cũ.
- Kết quả hiển thị anchor, heading, table, conflict, semantic có gợi ý và checksum;
  coverage luôn bắt đầu `0%`, không có anchor nào được tự phê duyệt.
- Tạo workspace giữ nguyên source/report type đã phân tích, yêu cầu profile ID, tên
  và version hợp lệ; lỗi backend giữ nguyên form và kết quả để người dùng sửa rồi
  thử lại.
- Đã kiểm tra trực quan route thật ở desktop, responsive 760 px, light/dark và
  console; không ghi nhận lỗi giao diện. Chưa chạy end-to-end với template khách
  hàng vì chưa có nguồn đầu vào được duyệt.
- Playwright E2E dùng DOCX synthetic và API cô lập xác minh đúng thứ tự
  analyze-before-create, mở workspace mới vào mapping và không gọi Generate.

Phần còn lại của TS-09 trước khi xin duyệt tích hợp: visual/e2e với template thực
tế đại diện và quyết định cuối cùng của người dùng về workflow.

### TS-09C.1 — Catalog inventory và recovery — hoàn thành working tree

- Catalog mở thành dialog riêng từ route thử nghiệm; hiển thị revision, pack,
  version, report type và version đang được chọn trong Template Studio.
- Mở catalog chỉ đọc inventory và không tự activate/rollback; mọi selection của
  TS-09C.3 vẫn không nối vào Generate. Trạng thái `Legacy Renderer không thay đổi`
  luôn được hiển thị.
- Catalog chính và checkpoint được kiểm tra song song. Recovery chỉ xuất hiện khi
  backend trả `canRecover`; người dùng phải xác nhận token từ preview vừa chạy.
- Conflict hoặc checkpoint thay đổi không được retry mù; UI yêu cầu tải/preview
  lại. Focus trap, Escape, focus return, loading/empty/error và mobile reflow đã có.

### TS-09C.2 — Validation hai lượt và publish — hoàn thành working tree

- Backend bổ sung API liệt kê validation record đã seal để UI có thể khôi phục
  workflow sau khi đóng/reload, đánh dấu run stale khi workspace revision/hash đổi
  và cô lập record hỏng thay vì làm mất toàn bộ lịch sử.
- UI nhận fixture JSON tối đa 30 MiB, yêu cầu workspace `mapping_complete`, tạo
  baseline, tải artifact DOCX và đối chiếu checksum header với validation record.
- Baseline chỉ được duyệt sau khi artifact đã tải trong phiên và có reviewer. Lượt
  hai luôn pin `baselineRunId` cùng fixture ID đã duyệt.
- Publish chỉ dùng exact checksum của second-pass run đạt, workspace revision và
  catalog revision hiện hành. Conflict buộc reload trạng thái; input reviewer và
  artifact gate không bị bỏ qua.
- DOCX validation được repack với ZIP metadata cố định; cùng workspace/fixture tạo
  byte và run identity ổn định, không còn flake qua ranh giới timestamp ZIP.
- Pack sau publish chỉ nằm trong isolated catalog; UI hiển thị rõ chưa kết nối
  Generate mặc định.

### TS-09C.3 — Activate/rollback cô lập — hoàn thành working tree

- Catalog cho chọn version bằng `expectedRevision`, phân biệt activate version mới
  và rollback version cũ, luôn cần xác nhận tác động.
- Conflict tự tải lại catalog trước khi cho thao tác tiếp; thành công hiển thị rõ
  lựa chọn chỉ áp dụng trong Template Studio.
- Không có code nào đưa active pack vào template selector, Preview hoặc Generate.

### TS-10A — Workspace Index chỉ đọc — hoàn thành

- API metadata-only liệt kê workspace theo `updatedAt DESC`, có tie-break ổn định
  bằng `workspaceId`.
- Lọc theo trạng thái/report type, tìm theo display name/profile ID và phân trang
  cursor với giới hạn 1–100 bản ghi.
- Cursor gắn với filter và fingerprint của collection. Nếu workspace thay đổi giữa
  hai trang, API trả `409` và yêu cầu tải lại từ trang đầu thay vì âm thầm bỏ sót
  hoặc lặp bản ghi.
- Summary tự tính lại coverage từ semantic slot thực, không tin các trường tổng hợp
  lưu sẵn và không trả source DOCX, checksum template, analysis, mapping, audit hay
  đường dẫn local.
- Workspace JSON hỏng/không hợp lệ được cô lập khỏi danh sách và báo bằng
  `skippedCorrupt`; feature flag tắt vẫn trả `404` như baseline.
- Mutation mapping đồng thời cùng revision có đúng một lệnh thắng; lệnh còn lại
  nhận revision conflict, không ghi đè im lặng.

Phần rename/clone/archive/export/import và retention an toàn được tách thành TS-10B;
chưa có mutation lifecycle mới trong TS-10A.

### TS-10B.1 — Lifecycle draft không phá hủy — hoàn thành phần backend

- Rename chỉ đổi display name, giữ profile identity, source và toàn bộ mappings.
- Clone tạo workspace ID/revision/audit mới, giữ snapshot mapping và tham chiếu tới
  source DOCX content-addressed đã được xác minh checksum.
- Archive/restore không xóa dữ liệu. Workspace đã archive là read-only cho mapping
  và rename đến khi được restore.
- Mọi mutation yêu cầu `expectedRevision`; stale request trả `409` và không ghi đè.
- Workspace Index có filter `archived=true|false`; cursor cũng gắn với filter này.
- Feature flag tắt vẫn ẩn toàn bộ endpoint lifecycle bằng `404`.

### TS-10B.2 — Portable draft transfer — hoàn thành backend

- Export tạo archive `.rptdraft` deterministic gồm đúng `manifest.json`,
  `workspace.json` và `template.docx`; không chứa path local hoặc code thực thi.
- Manifest khóa checksum workspace/DOCX và source workspace ID/revision.
- Inspector chặn path traversal, member thừa/trùng, symlink, encryption, archive
  vượt giới hạn và compression ratio đáng ngờ; không extract archive.
- Import luôn cấp workspace ID/revision/audit mới, xác minh lại workspace checksum,
  mapping contract, DOCX và source hash trước khi ghi nguyên tử.
- Source DOCX content-addressed được tái sử dụng khi checksum giống nhau; không ghi
  đè template nguồn bằng bytes khác.

### TS-10B.3 — Retention preview-first — hoàn thành backend + React UI

- Preview trả danh sách workspace/source ứng viên, cutoff, dung lượng có thể thu hồi,
  blockers, fingerprint và confirmation token có HMAC/hạn 15 phút.
- Chỉ archived draft `analyzed`/`mapping_incomplete` đủ tuổi mới là ứng viên;
  workspace active/mapping complete/tested/published không bị chọn.
- Workspace corrupt/unsupported chặn toàn bộ cleanup. Source đang được workspace
  còn lại hoặc Template Pack catalog tham chiếu được bảo vệ.
- Apply chỉ chạy khi token và fingerprint còn khớp; thay đổi giữa preview/apply trả
  conflict và yêu cầu preview lại.
- Không có permanent-delete endpoint. Apply chuyển file vào quarantine theo batch;
  lỗi giữa chừng rollback, và endpoint restore đưa toàn bộ batch về vị trí cũ.

## 6. Bằng chứng kiểm thử gần nhất

### Quality gate đầy đủ gần nhất ngày 28/08/2026

- Ruff check và Ruff format: đạt.
- Backend regression: **291 tests đạt**.
- Frontend Vitest: **51 tests đạt**.
- ESLint và Prettier: đạt.
- Frontend production build: đạt, 1.916 module được transform.
- Golden DOCX của sáu report type: đạt, không thay đổi baseline.

### Sau khi hoàn thiện Workbench ngày 28/08/2026

- `tests.test_template_studio_prototype`: **6/6 đạt**.
- Embedded JavaScript syntax: đạt.
- Isolation test chặn external asset/navigation/embed/network primitive: đạt.
- Contrast contract cho dark/light và control boundary: đạt.
- Ruff cho test Workbench: đạt.
- `git diff --check`: đạt.
- Workbench vẫn là HTML độc lập chưa nối ứng dụng. Full quality gate sau đó đã
  được chạy cùng TS-10A và đạt toàn bộ.

### Sau khi hoàn thiện Workspace Index TS-10A ngày 28/08/2026

- Targeted domain/API/architecture/Workbench: **23/23 đạt**.
- Toàn bộ `tests.test_api_integration`: **24/24 đạt**.
- Toàn bộ `tests.test_template_packs` + `tests.test_template_mapping_workspace`:
  **32/32 đạt**.
- Ruff check và Ruff format cho sáu tệp Python thay đổi: đạt.
- Embedded JavaScript syntax và `git diff --check`: đạt.
- Full quality gate `scripts/check.ps1`: **đạt** — Ruff, **291 backend tests**,
  ESLint, Prettier, **51 frontend tests** và production build 1.916 modules.

### Sau lát cắt lifecycle TS-10B.1 ngày 28/08/2026

- Toàn bộ `tests.test_api_integration`: **25/25 đạt**.
- Toàn bộ `tests.test_template_mapping_workspace` + `tests.test_template_packs`:
  **33/33 đạt**.
- Ruff check/format cho domain, API model/route và test thay đổi: đạt.
- Full gate 291/51 ở trên chạy trước TS-10B.1; phải chạy lại sau khi hoàn tất toàn
  bộ TS-10B hoặc trước commit/push, tùy mốc nào đến trước.

### Sau khi hoàn thành backend TS-10B ngày 28/08/2026

- Workspace lifecycle/transfer/retention + toàn bộ API integration + Template Pack:
  **66/66 đạt**.
- Ruff check và format cho chín tệp Python liên quan: đạt.
- Kiến trúc cấm ba module Legacy Renderer import Mapping Workspace, transfer,
  retention và các runtime Template Pack khác: đạt.
- Quality gate phát hành đã được cập nhật để luôn chạy hai module transfer và
  retention mới.
- Full backend gate sau cập nhật: **301/301 đạt**; Ruff check/format đạt.
- Frontend gate trong cùng checkpoint: ESLint, Prettier, **51/51 Vitest** và
  production build 1.916 modules đều đạt.

### Sau khi hoàn thành domain Profile Renderer TS-11 ngày 30/08/2026

- Profile Renderer xử lý đủ semantic catalog của sáu report type từ Template
  Pack publication-ready và accepted normalized snapshot.
- Targeted renderer/pack/catalog: **32/32 đạt**; riêng Profile Renderer:
  **8/8 đạt**.
- Ruff check cho renderer, pack inspector và regression tests: đạt.
- Regression architecture tiếp tục cấm ba module Legacy Renderer import Profile
  Renderer hoặc các runtime Template Pack.
- Hủy hợp tác được kiểm tra cả trong render và sau bước lưu; file tạm thuộc
  renderer được dọn khi lỗi/hủy.
- Full release gate: Ruff check/format, **309/309 backend tests**, ESLint,
  Prettier, **51/51 frontend tests**, production build 1.916 modules và golden
  DOCX đều đạt.
- Chưa có API, job, UI hoặc catalog selection gọi Profile Renderer.

### Sau khi hoàn thành domain Validation Runner TS-12 ngày 31/08/2026

- Targeted validation/renderer/pack/catalog/API: **65/65 đạt**.
- Ma trận runner hai lượt của sáu report type: đạt; candidate vẫn không
  publishable và normal renderer từ chối candidate.
- Kiểm thử baseline thiếu/sai, unresolved token, artifact checksum sai,
  cancellation và evidence provenance: đạt.
- Ruff check/format cho domain và regression tests: đạt.
- Full release gate: **315/315 backend tests**, **51/51 frontend tests**, Ruff,
  ESLint, Prettier, production build 1.916 modules và golden DOCX đều đạt.

### Sau khi hoàn thành domain Preview/diff TS-13 ngày 31/08/2026

- Targeted preview/validation/renderer/pack/API: **71/71 đạt**.
- Sáu report type preview thành công; cache identity, same-version changed bytes,
  stale prepared snapshot, corrupt artifact, bounded eviction và cancellation:
  đạt.
- Preview promotion giữ byte-for-byte artifact và content signature: đạt.
- Ruff check/format cho preview domain và regression tests: đạt.
- Full release gate: **321/321 backend tests**, **51/51 frontend tests**, Ruff,
  ESLint, Prettier, production build 1.916 modules và golden DOCX đều đạt.

### Sau khi hoàn thành trusted Publish API TS-14 ngày 31/08/2026

- Validation run và artifact DOCX được lưu bởi backend với record checksum; client
  không thể gửi cờ `passed=true` để tự chứng nhận.
- Workflow bắt buộc hai lượt: tạo baseline → duyệt đúng artifact checksum → chạy
  lại với baseline đã duyệt → publish đúng artifact checksum của lượt hai.
- Publish kiểm tra lại workspace revision, toàn bộ workspace hash, template hash,
  baseline approval và catalog revision ngay tại commit point.
- Catalog rollback payload mới nếu ghi index thất bại; không để version nửa vời.
- Targeted publish/API regression: **33/33 đạt**; tamper, stale workspace/catalog,
  baseline chưa duyệt, checksum sai và lỗi ghi index đều bị chặn.
- Full backend gate gần nhất: **375/375 backend tests** và merge boundary đạt.
  Sau validation/catalog UI: **95/95 frontend tests** đạt; targeted backend
  validation/publish/catalog/API/documentation/merge boundary **38/38 đạt**.
  ESLint, Prettier, production build **1.926 modules** và merge boundary đều đạt.
- Authoring API hiện bật mặc định; vẫn không tự activate pack, không thêm dropdown
  và không nối Profile Renderer vào Preview/Generate mặc định.

### Sau khi hoàn thành React upload/analyze TS-09B.2b ngày 02/09/2026

- Frontend Vitest: **102/102 đạt**, gồm giới hạn `.docx`, analyze-before-create,
  invalidation khi đổi report type, giữ form khi backend lỗi và API payload tách
  biệt giữa analyze/create.
- ESLint, Prettier và production build **1.928 modules**: đạt.
- Hai API integration test cho analyzer `0%` và workspace revision contract: đạt.
- Visual QA route thật: desktop, responsive 760 px, light/dark và console không
  lỗi. Backend không được bật trong phiên visual nên không truyền template thật.
- Playwright: **4/4 E2E đạt**, gồm workflow report mặc định, theme/data quality và
  workflow Template Studio synthetic analyze → create → mapping.
- Luồng mặc định và ba template full/server/client không thay đổi. Kết quả này là
  checkpoint trước quyết định bật sẵn authoring API ngày 06/09/2026.

### Sau khi hoàn thành anchor picker tổng quát ngày 03/09/2026

- Mapping UI có thể chọn mọi anchor duy nhất mà analyzer đã phát hiện, kể cả tên
  tùy biến hoàn toàn khác semantic catalog; recommendation chỉ thay đổi thứ tự,
  không còn giới hạn danh sách lựa chọn.
- Anchor trùng occurrence bị loại khỏi danh sách. Anchor đã gán cho semantic khác
  bị vô hiệu hóa ở frontend và tiếp tục bị backend từ chối để chống request thủ
  công hoặc hai editor sử dụng trùng.
- Component/API contract test kiểm tra chọn anchor tùy biến, trạng thái anchor đã
  dùng và revision không đổi sau rejection. Playwright synthetic kiểm tra chuỗi
  analyze → create → tìm anchor → duyệt mapping đạt 100% mà không gọi Generate.
- Full release gate: Ruff check/format, merge boundary, **376/376 backend tests**,
  ESLint, Prettier, **105/105 frontend tests** và production build **1.929 modules**
  đều đạt. Playwright đầy đủ: **4/4 E2E đạt**.
- Người dùng đã review route React với workspace synthetic ngày 03/09/2026 và
  chấp thuận hướng UI hiện tại. Đây là duyệt giao diện authoring, không phải duyệt
  template khách hàng hoặc quyền nối Template Pack vào Preview/Generate mặc định.

Lệnh gate chuẩn:

```powershell
.\scripts\check.ps1
```

Không dùng `tests/test_integration.py` làm unit quality gate; đây là smoke script
cần frontend đang chạy tại localhost.

## 7. Công việc đang thực hiện ngay lúc này

| ID | Công việc | Trạng thái | Blocker/điểm duyệt |
|---|---|---|---|
| TS-08.1 | Review bố cục Workbench mới | Hoàn thành hướng V2 | Được phép tiếp tục sang React |
| TS-08.2 | Chỉnh màu, mật độ, thuật ngữ và drawer theo feedback | Hoàn thành, UI synthetic đã duyệt | Còn visual pilot bằng template thực |
| TS-08.3 | Commit UI prototype đã được duyệt | Hoàn thành và đã merge | Route thật đã được người dùng duyệt |
| TS-10A | Workspace Index metadata-only, filter/search/cursor | Hoàn thành | Không nối Generate |
| TS-10B.1 | Rename/clone/archive draft | Hoàn thành backend + React UI | Không xóa dữ liệu |
| TS-10B.2 | Export/import draft portable | Hoàn thành backend + React UI | `.rptdraft` data-only |
| TS-10B.3 | Retention preview/quarantine/restore | Hoàn thành backend + React UI | Không xóa vĩnh viễn |
| TS-11 | Profile Renderer v1 chạy song song | Hoàn thành domain | Chỉ TS-14 gọi để validate; chưa nối Preview/Generate |
| TS-12 | Fixture/integrity/structural validation runner | Hoàn thành + nối TS-14 | Chưa nối UI/job/Generate |
| TS-13 | Preview/diff và byte-for-byte promotion | Hoàn thành domain | Chưa nối API/job/UI/Generate |
| TS-14 | Publish API với trusted two-pass evidence | Hoàn thành backend | Không activate hoặc nối Generate |
| TS-16A | Pilot manifest và evidence contract | Hoàn thành | Ba fixture tổng hợp đã chạy pipeline thật |
| TS-17A | Catalog checksum, recovery và concurrent install | Hoàn thành backend | Đã có cross-process regression |
| TS-17B | Pack/OOXML corpus và concurrent publish/select | Hoàn thành backend | Đã có concurrent regression |
| TS-17C | Cross-process catalog lock và seeded fuzz | Hoàn thành backend | Capacity 50k đã có trên pack synthetic tối giản |
| TS-17D | Reproducible fuzz/soak harness | Hoàn thành | Corpus synthetic đã đạt; khách hàng chạy lại khi có template thật |
| TS-17E | Synthetic Profile Renderer capacity harness | Hoàn thành | Engineering-only, chưa thay benchmark khách hàng |
| TS-17F | Nested DOCX/workspace/catalog fuzz | Hoàn thành synthetic | Khách hàng chạy lại khi có template thật |
| TS-18A | Administrator guide và migration/rollback contract | Hoàn thành | Đã cập nhật cho Studio mặc định khả dụng |
| TS-18B | Automated merge-safety boundary | Hoàn thành | PR gate bảo vệ default flow |
| TS-09A | React mapping route + API client tách biệt | Hoàn thành, UI đã duyệt | Có entry sidebar; không nối Generate |
| TS-09B.1 | Workspace lifecycle React UI | Hoàn thành, UI đã duyệt | Không xóa dữ liệu |
| TS-09B.2 | Upload/analyze + retention quarantine UI | Hoàn thành | Không chạm Import mặc định |
| TS-09C | Validation/publish/catalog UI | Hoàn thành | Không nối Generate |
| TS-16C | Ba fixture Word khác cấu trúc | Hoàn thành synthetic | Analyzer, mapping, validation, pack, preview/promotion đều đạt |

TS-09 được truy cập trực tiếp từ sidebar và gọi authoring API mặc định khả dụng.
Không thêm pack vào menu Generate hoặc template selector trước cổng TS-15.

## 8. Backlog còn lại của Template Studio

### P0 — Hoàn thiện authoring workflow

#### TS-09 — React Template Studio tách biệt — hoàn thành

- Route riêng và entry **Template Studio** trong sidebar đã được tích hợp sau khi
  người dùng duyệt. AppShell và workflow ba bước vẫn giữ nguyên.
- Các màn: upload/analyze, mapping table, review blockers, test, publish/catalog.
- API client có error envelope, loading, retry và revision conflict 409.
- Việc chỉnh draft diễn ra cục bộ; quyết định mapping chỉ được lưu khi người dùng
  bấm `Duyệt ánh xạ`, với revision guard để không ghi đè editor mới hơn.
- Light/dark, keyboard navigation, focus state và WCAG AA.

**Definition of Done:** UI component/API tests đạt; build mặc định hiển thị entry
Studio; đặt backend flag `0` cô lập API mà Legacy Renderer vẫn hoạt động.

#### TS-10 — Workspace index và lifecycle

- **TS-10A hoàn thành:** API liệt kê metadata workspace, lọc/tìm kiếm, cursor ổn
  định, đếm corrupt và phát hiện collection thay đổi giữa hai trang.
- **TS-10B.1 hoàn thành backend:** đổi tên/clone/archive/restore draft theo cơ chế
  không phá hủy, có revision và audit.
- **TS-10B.2 hoàn thành backend:** export/import draft portable để chuyển giữa
  thành viên team bằng archive data-only có checksum.
- **TS-10B.3 hoàn thành backend:** preview retention, confirmation token,
  quarantine có rollback và restore; không cung cấp permanent delete.

**Definition of Done:** không phải biết workspace ID thủ công; mọi mutation có
revision/audit và không xóa source đang được pack sử dụng.

### P1 — Renderer và validation thực

#### TS-11 — Profile Renderer v1 chạy song song

- **Hoàn thành domain renderer:** đọc profile declarative, không chạy Python từ
  pack và không import Legacy Renderer.
- Đã implement text, rich text, asset/result/summary/finding/remediation/IoC,
  field-group, timeline, MITRE và incident response blocks.
- Chỉ đọc accepted normalized snapshot; kiểm tra report type và template hash,
  không thay parser/rule engine.
- Không fallback sang Legacy Renderer; lỗi trả semantic và anchor gây lỗi.
- Có cooperative cancellation, progress, row counts, manifest truy vết và atomic
  save có temp cleanup.
- Chưa nối API/job/UI/Generate. Việc chọn pack vẫn bị cô lập trong catalog.

**Definition of Done domain: đạt.** Một pack test có thể tạo DOCX mà không import
từ hoặc sửa Legacy Renderer; lỗi trả rõ semantic/anchor gây lỗi. Tích hợp chỉ được
xem xét sau TS-12/TS-13 và cổng duyệt TS-15.

#### TS-12 — Fixture, integrity và visual validation runner

- **Hoàn thành domain runner:** candidate pack ở trạng thái `mapping_complete`,
  deterministic nhưng không publishable/cài được.
- Fixture runner kiểm tra đủ semantic, row count và giá trị asset/finding/evidence
  trên accepted normalized snapshot cho sáu report type.
- Structural snapshot/diff bao phủ paragraph, heading style, table/content/format,
  numbering, relationship, media, section và token còn sót.
- Table do Profile Renderer tạo có semantic caption ẩn để diff truy về block.
- Hai lượt bắt buộc: tạo baseline để review, sau đó render lại và so khớp baseline.
- Visual approval bị khóa vào checksum DOCX, structural hash, validation run ID,
  reviewer và thời gian review.
- Pack Builder từ chối evidence đạt nhưng thiếu provenance của runner.
- Đã nối vào Publish API TS-14 theo workflow checksum hai lượt; browser vẫn không
  có đường gửi ba cờ `passed=true`.

**Definition of Done domain: đạt.** Runner tạo evidence có provenance cho Pack
Builder; diff lỗi đọc được và table diff truy về semantic block. API/publish
orchestration thuộc TS-14, sau TS-13 preview/diff.

#### TS-13 — Preview/diff cho pack

- **Hoàn thành domain:** preview pin pack ID/version/full checksum, template hash,
  request signature, content signature và renderer version.
- Cache bounded theo entry/bytes; pack hoặc normalized data đổi thì key đổi và
  không thể reuse, kể cả khi version string giữ nguyên.
- Artifact chứa original-template structure, rendered structure và readable diff.
- Promotion chỉ trả đúng preview bytes khi toàn bộ identity, content signature và
  artifact checksum còn khớp; không render lần hai.
- Có progress/cancellation; chưa nối API/job/UI/Generate mặc định.

**Definition of Done domain: đạt.** Pack đổi version, bytes hoặc prepared content
không thể tái sử dụng nhầm preview cũ; Preview/Generate promotion byte-for-byte.

### P1–P2 — Publish và opt-in integration

#### TS-14 — Publish API có trusted evidence

- **Hoàn thành backend:** nối Mapping Workspace → validation runner → Pack Builder
  → isolated catalog bằng endpoint feature-gated.
- Baseline chỉ hợp lệ sau khi reviewer duyệt checksum đúng của artifact lượt đầu;
  publish chỉ nhận lượt hai đã so khớp baseline này.
- Validation record, structural snapshot và DOCX artifact được lưu trong staging
  directory rồi rename nguyên tử; khi đọc luôn xác minh checksum.
- Workspace revision/hash/template và catalog revision được kiểm tra lại trước
  publish; stale/tampered input bị từ chối.
- Catalog install rollback payload vừa tạo nếu index write lỗi; cùng version khác
  bytes tiếp tục bị từ chối và rollback version không xóa archive nào.

**Definition of Done backend: đạt.** Chưa có UI, background job, activate tự động
hoặc kết nối với Generate mặc định.

#### TS-15 — Chọn pack theo cơ chế opt-in

- Chỉ pack `published`, checksum hợp lệ và validation đạt mới có thể được chọn.
- UI phân biệt rõ “Default templates” và “Template Packs”.
- Không đổi template mặc định trong database hiện tại.
- Request snapshot pin pack ID, version, pack hash và template hash.
- Tắt flag phải ẩn toàn bộ pack và quay lại hành vi baseline.

**Điểm dừng bắt buộc:** cần người dùng duyệt prototype Preview/Generate với pack
trước khi TS-15 được bật trong workflow chính.

### P2 — Pilot và ổn định

#### TS-16 — Ma trận template thực tế

- **TS-16A hoàn thành:** schema manifest đóng, validator offline, draft example và
  checklist evidence cho từng template. `ready` chỉ có nghĩa đủ bằng chứng để
  review; `approved` mới yêu cầu phê duyệt opt-in và vẫn không tự nối Generate.
- Validator pin pack/template/workspace/fixture bằng SHA-256, kiểm hai lượt
  validation, golden/integrity/visual, 12 capability Word, benchmark tối thiểu 10
  trial, recovery, quality gate và chín evidence file trong root an toàn.
- Full release gate TS-16A: **364/364 backend tests**, **51/51 frontend tests**,
  merge boundary, Ruff check/format, ESLint, Prettier và production build 1.916
  modules đều đạt trên implementation commit `be67f74`.
- **TS-16B hoàn thành phần offline:** preflight đọc chín record evidence đã xác
  minh checksum và tự đối chiếu mapping, hai lượt validation, baseline binding,
  golden, feature, visual, benchmark trial thô, recovery và quality gate thay vì
  chỉ tin cờ `passed` trong manifest.
- Matrix gate yêu cầu tối thiểu ba template/template structure khác nhau, phủ
  `full`, `server_only`, `client_only`, cùng quality-gated commit và hợp lại chứng
  minh đủ 12 capability Word. Kết quả chỉ là readiness, không publish/activate hay
  nối vào Generate.
- Full release gate TS-16B: **374/374 backend tests**, **51/51 frontend tests**,
  merge boundary, Ruff check/format, ESLint, Prettier và production build 1.916
  modules đều đạt trên implementation commit `c6a2c73`.
- Ít nhất ba template khác cấu trúc do người dùng cung cấp.
- Full/server/client trước; summary/technical/IR sau.
- Mỗi template có fixture, golden, benchmark và hướng dẫn mapping.
- Kiểm thử token split-run, bookmark/content control, bảng merge, header/footer,
  TOC, numbering, image và section break.

**Checkpoint synthetic ngày 05/09/2026:** khi chưa có template khách hàng, người
dùng cho phép tạo ba fixture độc lập cho `full`, `server_only`, `client_only`.
Mỗi fixture dùng phối hợp token, bookmark và content control khác nhau; template
client có section portrait/landscape. Cả ba đã đạt analyzer → mapping 100% →
validation hai lượt → publishable pack → Preview → byte-for-byte promotion.
Toàn bộ năm trang fixture đã được render bằng Microsoft Word cài sẵn và kiểm tra
trực quan sau khi sửa khoảng cách header/page break. Đây là bằng chứng tích hợp
synthetic đủ để đưa authoring subsystem vào tool; nó không thay thế visual/
benchmark lại bằng template khách hàng trước khi bật Generate thật.

#### TS-17 — Security/performance hardening

- **TS-17B hoàn thành backend:** corpus chặn duplicate archive member, symlink,
  path traversal, compression bomb, JSON quá sâu/phức tạp và ZIP codec lỗi bằng
  error có kiểm soát thay vì exception thoát ra ngoài.
- `template.docx` lồng bên trong pack có safety pass riêng cho số part, expanded
  size, compression ratio, duplicate/unsafe path, encryption, symlink và khai báo
  XML `DOCTYPE`/`ENTITY` nguy hiểm.
- **TS-17A hoàn thành backend:** catalog index được seal bằng SHA-256 canonical;
  sửa metadata nhưng không cập nhật seal sẽ bị phát hiện trước mọi mutation.
- **TS-17A hoàn thành backend:** giữ một checkpoint revision hợp lệ; recovery bắt
  buộc preview/token và xác minh checksum của mọi pack payload trước khi cho khôi
  phục. Checkpoint thiếu/hỏng payload không được xem là recoverable.
- Concurrent catalog install cùng revision đã được kiểm thử: đúng một lệnh thắng,
  lệnh còn lại nhận conflict và không tạo lost update/version thừa.
- Concurrent publish cùng validation run và activate/rollback cùng revision đã
  được kiểm thử: đúng một lệnh commit, lệnh còn lại nhận revision conflict, audit
  không lặp và catalog không có version thừa.
- Full release gate TS-17B: **331/331 backend tests**, **51/51 frontend tests**,
  Ruff check/format, ESLint, Prettier và production build 1.916 modules đều đạt.
- **TS-17C hoàn thành backend:** catalog dùng OS byte-range lock có timeout cho cả
  Windows/POSIX; bốn backend process cùng install revision `0` có đúng một lệnh
  thắng, ba lệnh conflict, một audit event và không có lost update/version thừa.
- Seeded mutation corpus chạy 128 biến thể truncate/bit-flip/append/zero-range.
  Fuzz phát hiện và đã đóng đường `zlib.error` thoát khỏi inspector; mọi biến thể
  giờ chỉ thành pack hợp lệ hoặc `TemplatePackError` có kiểm soát.
- **TS-17D hoàn thành:** thêm fuzz/soak runner có seed, bảy mutation, giới hạn
  iteration/thời gian, checkpoint nguyên tử, recipe replay, latency/RSS aggregate
  và không lưu source bytes. Corpus tổng hợp 10.000 case đạt trong 23,49 giây:
  1.434 mutation vẫn hợp lệ, 8.566 controlled rejection, 0 exception thoát;
  inspector P50 0,503 ms, P95 7,036 ms, max 11,347 ms.
- TS-17D phát hiện thêm `ValueError: negative seek value` từ ZIP bị xóa range;
  pack/DOCX inspector đã chuẩn hóa lỗi thư viện này thành `TemplatePackError` và
  recipe được giữ thành regression test cố định.
- Full release gate TS-17D: **347/347 backend tests**, **51/51 frontend tests**,
  merge boundary, Ruff check/format, ESLint, Prettier và production build 1.916
  modules đều đạt.
- Còn lại của security hardening: chạy soak nhiều giờ với pack được duyệt và
  benchmark Template Pack thực tế ở 50/1.000/10.000/50.000 tài sản.
- Full release gate TS-17C: **333/333 backend tests**, **51/51 frontend tests**,
  Ruff check/format, ESLint, Prettier và production build 1.916 modules đều đạt.
- Full release gate TS-17A: **326/326 backend tests**, **51/51 frontend tests**,
  Ruff check/format, ESLint, Prettier và production build 1.916 modules đều đạt.
- Benchmark analyzer, renderer, preview và generate với 50/1.000/10.000/50.000
  tài sản theo loại template.
- Xác định giới hạn từ dữ liệu đo; không suy đoán.

**TS-17E hoàn thành phần synthetic capacity:** mỗi mốc chạy trong worker riêng có
watchdog RAM/timeout cả trong worker và parent; workload lớn cần `--allow-large`.
Full synthetic pack đạt 50, 1.000, 10.000 và 50.000 tài sản, không dùng Legacy
Renderer. Kết quả một trial/mốc trên máy phát triển: 50 = 1,05 giây/43,2 MiB;
1.000 = 2,24 giây/49,4 MiB; 10.000 = 23,34 giây/144,4 MiB; 50.000 = 164,70
giây/549,0 MiB. Đây là engineering capacity smoke với template tối giản, không
phải SLA hoặc benchmark template khách hàng; TS-16 vẫn phải chạy lại matrix với
pack thực tế và tối thiểu 10 trial tương thích trước khi công bố P50/P95.
- Full release gate TS-17E: **351/351 backend tests**, **51/51 frontend tests**,
  merge boundary, Ruff check/format, ESLint, Prettier và production build 1.916
  modules đều đạt.
- **TS-17F hoàn thành phần synthetic:** harness có thể giữ ZIP/checksum ngoài hợp
  lệ rồi mutate trực tiếp `template.docx` trong Template Pack hoặc workspace
  draft. Target catalog cài vào catalog tạm và so snapshot trước/sau mỗi rejection;
  bất kỳ thay đổi state ngoài ý muốn đều là lỗi dừng có recipe replay.
- Corpus TS-17F đạt **3.000/3.000 mutation** (1.000 nested pack, 1.000 nested
  workspace, 1.000 catalog), không có unexpected exception hoặc catalog state
  corruption. Kết quả chỉ là engineering synthetic; vẫn phải chạy lại bằng pack
  thực tế đã được duyệt trước pilot.

#### TS-18 — Release và merge gate

- **TS-18A hoàn thành:** hướng dẫn Template Administrator mô tả vai trò, workflow
  mapping/validation hai lượt, version, retention, recovery và pilot gate.
- **TS-18A hoàn thành:** migration/rollback runbook bắt buộc preflight, backup +
  dry-run, checksum, optimistic revision, checkpoint recovery và Legacy smoke test.
- Release documentation contract được chạy trong `scripts/check.ps1`: kiểm tra
  tài liệu/index, endpoint được mô tả có route thật, feature flag mặc định `0`,
  Legacy Renderer và `selectionIntegrated: false` không bị mô tả sai.
- Full release gate TS-18A: **337/337 backend tests**, **51/51 frontend tests**,
  Ruff check/format, ESLint, Prettier và production build 1.916 modules đều đạt.
- **TS-18B hoàn thành:** `scripts/check_template_studio_merge.py` kiểm tra flag
  mặc định tắt, Legacy Renderer không import Template Pack runtime và Git không
  track runtime/customer artifact. Trên pull request, checker so diff với base SHA
  và chặn mọi sửa/rename/copy ở ba module Legacy Renderer hoặc template mặc định.
- GitHub CI fetch đầy đủ history cho backend job và chạy merge checker trước full
  regression. Checker tĩnh cũng chạy trong `scripts/check.ps1` trên mọi môi trường.
- Full release gate TS-18B: **342/342 backend tests**, **51/51 frontend tests**,
  Ruff check/format, ESLint, Prettier và production build 1.916 modules đều đạt;
  diff gate với `github/main` xác nhận protected baseline không thay đổi.
- **TS-18C hoàn thành:** release workflow tạo archive từ exact Git ref, kiểm tra
  source contract, cài dependency khóa, build frontend, yêu cầu prewarm đủ sáu
  template và gọi backend health bằng chính clean environment vừa tạo. Workspace
  tạm chỉ được xóa khi gate đạt; bản lỗi được giữ để điều tra.
- Clean-source smoke trên commit `14e7c5b` đạt với Python 3.13: **6/6** bundled
  template prepared ở lượt đầu, **6/6** cache-hit verification, `npm ci` 270
  package/0 vulnerability, production build 1.916 modules và `/api/health` đạt.
  Gate đã phát hiện và sửa staging path vượt giới hạn Windows trong deep clone;
  regression test riêng bảo vệ trường hợp này.
- Full release gate TS-18C: **354/354 backend tests**, **51/51 frontend tests**,
  merge boundary, Ruff check/format, ESLint, Prettier và production build 1.916
  modules đều đạt sau bản sửa Windows path.
- Full backend/frontend/E2E/golden/security/performance gate.
- Branch review và merge có kiểm soát vào main.
- Lần merge đầu giữ mặc định tắt; quyết định ngày 06/09/2026 đưa authoring Studio
  thành phần sẵn có của tool nhưng vẫn không nối Generate.

**Checkpoint merge ngày 05/09/2026:** người dùng đã duyệt UI React và cho phép bắt
đầu merge subsystem vào `main`, với yêu cầu không ảnh hưởng luồng hiện tại. Gate
trước merge đạt **378/378 backend tests**, **105/105 frontend tests**, Template
Studio E2E **1/1**, Ruff, merge boundary, ESLint, Prettier và production build
**1.929 modules**. TS-15 Generate integration vẫn là công việc độc lập.

Clean-source smoke trên exact commit `d06d9da` cũng đạt: archive chỉ chứa source
được phép, dependency Python cài từ lockfile có hash, `npm ci` cài 270 package với
0 vulnerability, production build 1.929 modules, 6/6 template mặc định prewarm và
cache-hit, backend health trả `status=ok`. Lần chạy sandbox đầu bị chặn mạng; lần
chạy lại có quyền tải dependency đã đạt và là kết quả phát hành có hiệu lực.

## 9. Những việc không làm trong chương trình hiện tại

- Không chỉnh lại nội dung/heading/table của template mặc định đã được duyệt.
- Không viết lại Legacy Renderer.
- Không mở API ra toàn mạng.
- Không xây RBAC, multi-tenant hoặc PostgreSQL trong nhánh này.
- Không phát triển PDF export.
- Không cho pack chứa plugin, executable hoặc Python code.
- Không tự động publish template chỉ vì analyzer tìm thấy tên giống semantic.

## 10. Thứ tự triển khai bắt buộc từ thời điểm này

```text
1. Hiển thị Template Studio trong sidebar và bật authoring API theo mặc định
2. Chạy merge boundary, full gate và clean-source smoke
3. Giữ TS-15 Preview/Generate ngoài production flow
4. Khi có template khách hàng: chạy lại pilot/benchmark và xin duyệt TS-15
```

TS-11–TS-14 đã hoàn thành backend tách biệt. Việc merge authoring subsystem không
đồng nghĩa bật TS-15: catalog có version/rollback vẫn không có quyền thay template
hoặc renderer trong report thật.

## 11. Điểm cần hỏi người dùng

Phải dừng và xin ý kiến khi xảy ra một trong các trường hợp:

1. Chọn thiết kế UI cuối cùng.
2. Thay đổi workflow Preview/Generate hiện tại.
3. Cần chỉnh template full/server/client hoặc format report đã duyệt.
4. Bật pack trong dropdown thật.
5. Một template mới không thể đạt 100% với semantic catalog v1 và cần mở rộng
   semantic/renderer.
6. Benchmark cho thấy cần đổi cấu trúc DOCX hoặc giới hạn workload.
7. Cần migration database hiện tại.
8. Chuẩn bị merge vào main hoặc push release.

## 12. Checklist bắt đầu một phiên làm việc mới

```text
[ ] Đọc docs/TEMPLATE_STUDIO_STATUS.md và docs/TEMPLATE_PACKS.md
[ ] Kiểm tra git branch, HEAD và git status
[ ] Không stage apps/backend/data/
[ ] Xác nhận AUTO_REPORT_TEMPLATE_PACKS mặc định 1 và giá trị 0 vẫn cô lập API
[ ] Xác nhận task hiện tại theo ID TS-xx
[ ] Kiểm tra task có chạm Legacy Renderer/template mặc định không
[ ] Chạy test nhỏ trước khi sửa
[ ] Sửa theo module tách biệt và feature flag
[ ] Chạy test liên quan + Ruff/ESLint/Prettier
[ ] Chạy scripts/check.ps1 trước commit/push
[ ] Cập nhật tài liệu này trong cùng commit
```

## 13. Checklist trước merge vào main

- Người dùng đã duyệt UI và workflow.
- Không có diff ngoài phạm vi trong template mặc định và Legacy Renderer.
- Authoring Studio mặc định khả dụng; kill switch và Legacy Renderer vẫn hoạt động.
- Sáu golden DOCX baseline đạt.
- Backend, frontend, production build và E2E đạt.
- Template Pack security tests đạt.
- Pilot template thực tế đạt fixture/integrity/visual gate.
- Rollback từ pack về default flow đã được test.
- Release note liệt kê rõ tính năng experimental và cách tắt.
- `apps/backend/data/`, log, cache, report sinh ra và template khách hàng không có
  trong commit.

## 15. Kho template nguồn riêng — 2026-09-06

- Đã thêm SQLite `apps/backend/data/template_studio/template_library.sqlite3`, tách khỏi DB báo cáo.
- Khi phân tích thành công, lưu DOCX gốc (BLOB), SHA-256, tên file, thời gian,
  kết quả phân tích theo report type và liên kết workspace. File trùng nội dung
  chỉ lưu một bản; mapping workspace và catalog vẫn giữ cơ chế hiện tại.
- API `GET /api/template-packs/library` hỗ trợ tìm tên/phân trang và bổ sung
  workspace cũ còn đủ nguồn. `backfillSkipped` công khai số bản chưa bổ sung được.
- API `GET /api/template-packs/library/{sha256}` trả nguồn base64 và các phân tích;
  nguồn được kiểm tra checksum trước khi trả. Có thể dùng nguồn này tạo workspace
  qua API hiện hữu, không tự động phê duyệt mapping hay publish.
- Đã nối **Template mới → Thư viện nguồn**: tìm tên, phân trang, tải lại DOCX,
  loading/empty/error/retry và cảnh báo backfill thiếu nguồn. Chọn nguồn yêu cầu
  phân tích và duyệt mapping mới; không lấy approval cũ làm approval mới.
- Backup báo cáo hiện tại không được coi là backup kho này. Khi sao lưu thủ công,
  dừng tool và sao lưu toàn bộ `apps/backend/data/template_studio` (DB + nguồn + workspace + catalog).
- Không sửa template khách hàng, Legacy Renderer hay database báo cáo.
- Xác minh: `unittest tests.test_template_library tests.test_api_integration -q`
  đạt 31 test tại checkpoint backend. E2E bổ sung đã đạt toàn bộ 8 kịch bản,
  gồm 4 dùng backend thật với storage tạm; screenshot thư viện dark/light/760px đã xem.
- Hướng dẫn mới: [TEMPLATE_STUDIO_USER_GUIDE.md](TEMPLATE_STUDIO_USER_GUIDE.md).

## 14. Tài liệu liên quan

- [Kiến trúc và schema Template Pack](TEMPLATE_PACKS.md)
- [Kiến trúc Reporter Pro](ARCHITECTURE.md)
- [Quality và traceability của report](REPORT_QUALITY.md)
- [Kế hoạch/tiến độ tối ưu Preview và Generate](PERFORMANCE_IMPLEMENTATION_PLAN.md)
- [Benchmark đã công bố](BENCHMARKS.md)
- [Golden DOCX testing](testing/golden-docx.md)
- [Quy trình phát triển](DEVELOPMENT.md)
- [Hướng dẫn Template Administrator](TEMPLATE_ADMIN_GUIDE.md)
- [Migration và rollback runbook](TEMPLATE_STUDIO_MIGRATION_ROLLBACK.md)
