# Template Studio — trạng thái triển khai và hồ sơ bàn giao

> **Ngày chốt:** 27/08/2026
> **Nhánh phát triển:** `codex/template-studio`
> **Baseline ổn định:** `github/main` tại commit `ec5795d`
> **Checkpoint Template Studio:** commit `adc0995`
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
  → Profile Renderer (chưa triển khai)
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
| Checkpoint đã commit | `adc0995 feat(template-studio): add isolated template pack lifecycle` |
| Push nhánh lên remote | Chưa thực hiện |
| UI Workbench mới | Chưa commit, đang chờ người dùng review |
| `apps/backend/data/` | Runtime/user data, untracked; tuyệt đối không stage hoặc commit |

Các thay đổi chưa commit hợp lệ hiện tại:

- `docs/template-studio-workbench.html`
- phần kiểm thử Workbench trong `tests/test_template_studio_prototype.py`

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
| GET | `/api/template-packs/workspaces/{id}` | Hoàn thành |
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

## 6. Bằng chứng kiểm thử gần nhất

### Quality gate đầy đủ ngày 26/08/2026

- Ruff check và Ruff format: đạt.
- Backend regression: **281 tests đạt**.
- Frontend Vitest: **51 tests đạt**.
- ESLint và Prettier: đạt.
- Frontend production build: đạt, 1.916 module được transform.
- Golden DOCX của sáu report type: đạt, không thay đổi baseline.

### Sau khi tạo Workbench ngày 27/08/2026

- `tests.test_template_studio_prototype`: **4/4 đạt**.
- Ruff cho test Workbench: đạt.
- `git diff --check`: đạt.
- Chưa chạy lại toàn bộ quality gate vì Workbench chỉ là HTML độc lập chưa nối
  ứng dụng. Phải chạy lại toàn bộ gate trước commit hoặc push tiếp theo.

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
| TS-08.2 | Chỉnh màu, mật độ, thuật ngữ và drawer theo feedback | Chưa bắt đầu | Phụ thuộc TS-08.1 |
| TS-08.3 | Commit UI prototype đã được duyệt | Chưa bắt đầu | Chỉ commit sau review |
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

- API liệt kê workspace, lọc theo trạng thái và mở bản gần nhất.
- Đổi tên/clone/archive draft theo cơ chế không phá hủy.
- Dọn source/workspace orphan theo retention an toàn.
- Export/import draft để chuyển giữa thành viên team.

**Definition of Done:** không phải biết workspace ID thủ công; mọi mutation có
revision/audit và không xóa source đang được pack sử dụng.

### P1 — Renderer và validation thực

#### TS-11 — Profile Renderer v1 chạy song song

- Renderer đọc profile declarative, không chạy Python từ pack.
- Implement renderer theo semantic block: text, rich text, asset/result table,
  finding sections, remediation table và IoC table.
- Chỉ đọc normalized snapshot hiện tại; không thay parser/rule engine.
- Không fallback sang Legacy Renderer khi lỗi.
- Cancellation, progress, temp cleanup và metrics tương đương report job hiện tại.

**Definition of Done:** một pack test có thể tạo DOCX mà không import từ hoặc sửa
Legacy Renderer; lỗi trả rõ semantic/anchor gây lỗi.

#### TS-12 — Fixture, integrity và visual validation runner

- Fixture chuẩn cho report type/profile.
- Verify asset/finding/evidence coverage và section bắt buộc.
- Structural golden diff cho heading, paragraph, table, numbering, relationship,
  image/chart và anchor còn sót.
- Visual review tạo artifact có checksum và người duyệt.
- Evidence được backend tạo; browser không tự gửi ba cờ `passed=true`.

**Definition of Done:** chỉ validation runner mới có thể cấp evidence cho Pack
Builder; diff lỗi đọc được và truy về semantic block.

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
