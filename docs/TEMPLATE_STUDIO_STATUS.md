# Template Studio — trạng thái triển khai và hồ sơ bàn giao

> **Ngày chốt:** 31/08/2026
> **Nhánh phát triển:** `codex/template-studio`
> **Baseline ổn định:** `github/main` tại commit `ec5795d`
> **Checkpoint mã nguồn Template Studio:** commit `8aef963`
> **Trạng thái tích hợp:** chưa nối vào luồng tạo report mặc định
> **Feature flag:** `AUTO_REPORT_TEMPLATE_PACKS=0` theo mặc định

Tài liệu này là nguồn trạng thái chính cho chương trình Template Studio. Mỗi lần
tiếp tục công việc phải đọc tài liệu này và `TEMPLATE_PACKS.md` trước khi sửa mã.
Khi trạng thái thay đổi, cập nhật tài liệu này trong cùng commit với thay đổi.

## 1. Mục tiêu đã thống nhất

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
3. Template Studio nằm trên nhánh riêng cho đến khi đạt đủ quality gate và được
   người dùng đồng ý tích hợp.
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
| `github/main` | Không thay đổi, đang ở `ec5795d` |
| Nhánh làm việc | `codex/template-studio` |
| Checkpoint đã commit | `8aef963 feat(template-studio): add trusted pack validation runner` |
| Push nhánh lên remote | Đã push `github/codex/template-studio` |
| UI Workbench mới | Chưa commit, đang chờ người dùng review |
| `apps/backend/data/` | Runtime/user data, untracked; tuyệt đối không stage hoặc commit |

Các thay đổi chưa commit hợp lệ hiện tại:

- `docs/template-studio-workbench.html`
- phần kiểm thử Workbench trong `tests/test_template_studio_prototype.py`
- `docs/skill-drafts/` là tài liệu nháp ngoài checkpoint sản phẩm

Workspace Index và toàn bộ lifecycle/transfer/retention TS-10 đã được chốt tại
commit `7b81937`. Profile Renderer domain TS-11 đã được chốt tại commit `1ca3eea`;
Validation Runner domain TS-12 được chốt tại commit `8aef963`. Các phần này không
còn là thay đổi làm việc chưa commit.

Nếu trạng thái Git khác danh sách trên ở phiên sau, phải kiểm tra chủ sở hữu thay
đổi trước khi stage, sửa hoặc xóa.

## 5. Những phần đã hoàn thành

### TS-01 — Feature boundary và schema v1 — hoàn thành

- Feature flag `AUTO_REPORT_TEMPLATE_PACKS`, mặc định tắt.
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
- Pack Builder chưa mở trực tiếp qua HTTP vì browser không được phép tự chứng nhận
  fixture/integrity bằng các boolean do client gửi lên.

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

### TS-08 — UI exploration — đang chờ duyệt

Ba file HTML độc lập đã được tạo để nghiên cứu UI. Hai file đầu là lịch sử thử
nghiệm; không dùng làm thiết kế triển khai cuối:

- `docs/template-studio-prototype.html` — prototype ban đầu.
- `docs/template-studio-enterprise.html` — prototype enterprise đầu tiên, người
  dùng đánh giá vẫn chưa phù hợp.
- `docs/template-studio-workbench.html` — hướng mới đang chờ review.

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
thay đổi chỉ nằm trong prototype độc lập; cần người dùng duyệt hình ảnh trước TS-09.

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

### TS-10B.3 — Retention preview-first — hoàn thành backend

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

Lệnh gate chuẩn:

```powershell
.\scripts\check.ps1
```

Không dùng `tests/test_integration.py` làm unit quality gate; đây là smoke script
cần frontend đang chạy tại localhost.

## 7. Công việc đang thực hiện ngay lúc này

| ID | Công việc | Trạng thái | Blocker/điểm duyệt |
|---|---|---|---|
| TS-08.1 | Review bố cục Workbench mới | Chờ người dùng | Cần xác nhận hướng UI |
| TS-08.2 | Chỉnh màu, mật độ, thuật ngữ và drawer theo feedback | Hoàn thành phần prototype | Chờ người dùng duyệt hình ảnh |
| TS-08.3 | Commit UI prototype đã được duyệt | Chưa bắt đầu | Chỉ commit sau review |
| TS-10A | Workspace Index metadata-only, filter/search/cursor | Hoàn thành | Không nối Generate |
| TS-10B.1 | Rename/clone/archive draft | Hoàn thành backend | Chưa nối UI |
| TS-10B.2 | Export/import draft portable | Hoàn thành backend | Chưa nối UI |
| TS-10B.3 | Retention preview/quarantine/restore | Hoàn thành backend | Không xóa vĩnh viễn |
| TS-11 | Profile Renderer v1 chạy song song | Hoàn thành domain | Chưa nối API/job/UI/Generate |
| TS-12 | Fixture/integrity/structural validation runner | Hoàn thành domain | Chưa nối API/publish workflow |
| TS-09 | Chuyển UI được duyệt thành React route tách biệt | Chưa bắt đầu | Cần hai lần duyệt UI |

Không được bắt đầu nối UI vào API hoặc menu Generate trước khi TS-08 được duyệt.

## 8. Backlog còn lại của Template Studio

### P0 — Hoàn thiện authoring workflow

#### TS-09 — React Template Studio tách biệt

- Route hoặc entry riêng, chỉ tồn tại khi frontend feature flag được bật.
- Không sửa `AppShell`, Sidebar hoặc Configure mặc định trước khi có duyệt tích hợp.
- Các màn: upload/analyze, mapping table, review blockers, test, publish/catalog.
- API client có error envelope, loading, retry và revision conflict 409.
- Auto-save có debounce nhưng không được ghi đè revision mới hơn.
- Light/dark, keyboard navigation, focus state và WCAG AA.

**Definition of Done:** UI component/API tests đạt; build mặc định không hiển thị
Template Studio; tắt flag cho kết quả giống baseline hiện tại.

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
- Chưa nối API/UI/Publish; browser không có đường gửi ba cờ `passed=true`.

**Definition of Done domain: đạt.** Runner tạo evidence có provenance cho Pack
Builder; diff lỗi đọc được và table diff truy về semantic block. API/publish
orchestration thuộc TS-14, sau TS-13 preview/diff.

#### TS-13 — Preview/diff cho pack

- Preview từ cùng accepted snapshot với Generate.
- So sánh preview/generate bằng content signature.
- Hiển thị template structure và rendered structure cạnh nhau khi test.
- Cache phải có pack checksum và version trong key.

**Definition of Done:** pack đổi version hoặc bytes không thể tái sử dụng nhầm
preview cũ.

### P1–P2 — Publish và opt-in integration

#### TS-14 — Publish API có trusted evidence

- Nối Mapping Workspace → validation runner → Pack Builder → catalog.
- Atomic staging/install; lỗi giữa chừng không tạo version nửa vời.
- Publish cùng version khác bytes bị từ chối.
- Rollback catalog không xóa version mới.

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

- Ít nhất ba template khác cấu trúc do người dùng cung cấp.
- Full/server/client trước; summary/technical/IR sau.
- Mỗi template có fixture, golden, benchmark và hướng dẫn mapping.
- Kiểm thử token split-run, bookmark/content control, bảng merge, header/footer,
  TOC, numbering, image và section break.

#### TS-17 — Security/performance hardening

- Fuzz/zip-bomb/path traversal/malformed OOXML.
- Catalog recovery và checksum cho index metadata.
- Concurrent mapping/publish/rollback tests.
- Benchmark analyzer, renderer, preview và generate với 50/1.000/10.000/50.000
  tài sản theo loại template.
- Xác định giới hạn từ dữ liệu đo; không suy đoán.

#### TS-18 — Release và merge gate

- Tài liệu người dùng và template administrator.
- Migration/rollback instructions.
- Full backend/frontend/E2E/golden/security/performance gate.
- Branch review và merge có kiểm soát vào main.
- Feature flag vẫn mặc định tắt trong lần merge đầu.

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
1. Người dùng review Workbench
2. Chỉnh và duyệt UI lần cuối
3. Commit UI prototype checkpoint
4. React authoring UI riêng + workspace lifecycle
5. Profile Renderer tối thiểu
6. Validation runner + golden/diff
7. Publish API có trusted evidence
8. Preview/Generate thử nghiệm với pack
9. Pilot template thực tế
10. Opt-in integration, full gate, merge review
```

Không đảo TS-15 lên trước TS-11/TS-12. Catalog có version/rollback không đồng nghĩa
renderer đã đủ an toàn để sử dụng trong report thật.

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
[ ] Xác nhận AUTO_REPORT_TEMPLATE_PACKS vẫn mặc định 0
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
- Feature flag mặc định tắt.
- Sáu golden DOCX baseline đạt.
- Backend, frontend, production build và E2E đạt.
- Template Pack security tests đạt.
- Pilot template thực tế đạt fixture/integrity/visual gate.
- Rollback từ pack về default flow đã được test.
- Release note liệt kê rõ tính năng experimental và cách tắt.
- `apps/backend/data/`, log, cache, report sinh ra và template khách hàng không có
  trong commit.

## 14. Tài liệu liên quan

- [Kiến trúc và schema Template Pack](TEMPLATE_PACKS.md)
- [Kiến trúc Reporter Pro](ARCHITECTURE.md)
- [Quality và traceability của report](REPORT_QUALITY.md)
- [Kế hoạch/tiến độ tối ưu Preview và Generate](PERFORMANCE_IMPLEMENTATION_PLAN.md)
- [Benchmark đã công bố](BENCHMARKS.md)
- [Golden DOCX testing](testing/golden-docx.md)
- [Quy trình phát triển](DEVELOPMENT.md)
