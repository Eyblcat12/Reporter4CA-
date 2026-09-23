# Template Studio — kế hoạch UI/UX với Google Stitch

Ngày: 06/09/2026. Trạng thái: người dùng đã chốt hướng B; tiếp tục thiết kế
chi tiết và prototype tương tác trước khi tích hợp giao diện thật.

## Quyết định đã duyệt — B / Mapping Workspace

Người dùng chọn phương án B và yêu cầu UI/backend có chất lượng enterprise.
Giữ outline trái, ngữ cảnh Word giữa, inspector phải; thêm chế độ bảng mapping
để rà soát tổng thể. Đây là duyệt hướng thiết kế, chưa phải nghiệm thu tính năng
hay cho phép thay đổi luồng report mặc định.

Enterprise trong phạm vi này nghĩa là nhất quán, truy vết được, phục hồi được và
có kiểm thử. Không tự mở rộng sang multi-tenant, RBAC hay hạ tầng toàn server.

### Hợp đồng UI/backend cần kiểm chứng

| Tương tác UI B | Nền tảng đã thấy trong source | Điều kiện cần kiểm chứng khi triển khai |
|---|---|---|
| Chọn section và xem ngữ cảnh | GET workspace structure | Vị trí đúng version nguồn, payload giới hạn; không giả render Word chính xác |
| Duyệt & tiếp theo | PUT semantic mapping; expectedRevision | Chờ server xác nhận; không chuyển mục khi lỗi; ngăn double submit |
| Chỉnh mapping đã duyệt | Backend kiểm revision, anchor và required fields | Hiện draft chưa duyệt; không báo đã lưu trước acknowledgement |
| Xung đột | Client nhận HTTP 409; domain có revision guard | Giữ draft; đối chiếu với bản mới; không tự ghi đè hoặc tự replay mutation |
| Timeout khi lưu | Client phân biệt lỗi kết nối/5xx | Kết quả có thể chưa rõ; đọc lại workspace trước retry, tránh duyệt hai lần |
| Kiểm thử và phát hành | validation-runs, approve-baseline, publish | Evidence phải khớp nguồn/mapping; chặn stale result; kiểm tra DOCX thật |
| Thư viện nguồn | Library API phân trang 20 mục | Loading khác empty; tìm kiếm hủy request cũ; không hiển thị kết quả lỗi thời |

Đối chiếu này dựa trên templateStudioApi.js và template_mapping_workspace.py,
không thay thế test tích hợp. Các dòng trên là tiêu chí phải xác minh, không phải
tuyên bố mọi hành vi đã hoàn thiện.

### Trình tự công việc tiếp theo

1. Chốt state contract: loading, empty, selected, dirty, saving, approved,
   conflict, unknown-save-result, unsupported, stale-validation.
2. Prototype B tương tác, gồm outline/bảng đồng bộ cùng selection và draft;
   chỉ dùng dữ liệu giả, chưa nối API sản xuất.
3. Kiểm tra dark/light, keyboard, focus, zoom/reflow và lỗi/retry; xin người dùng
   duyệt prototype tương tác theo gate S5.
4. Tích hợp từng component Studio; chỉ thêm API ngữ cảnh đọc nếu API hiện có
   không đủ. Kiểm tra capability trước khi hiển thị control chỉnh sửa.
5. Test frontend/API/E2E và regression template mặc định, rồi mới nghiệm thu.

Không lưu nội dung khách hàng vào analytics/log theo mặc định. Lịch sử thao tác
chỉ chứa dữ liệu cần truy vết; actor local không được quảng bá là danh tính đã
xác thực enterprise. Không thêm dependency UI lớn chỉ để giống ảnh Stitch.

## 1. Mục tiêu và ranh giới

Khách hàng cung cấp template Word mới; dữ liệu đầu vào vẫn theo cấu trúc Tracking
hiện có. Studio phân tích cấu trúc, hỗ trợ người dùng chuẩn hóa và mapping, kiểm
thử rồi phát hành bộ template có thể tái sử dụng trong tool.

Không yêu cầu tự động hiểu mọi template. Người dùng xác nhận toàn bộ mapping sau
khi chuẩn bị template. Tuy nhiên, 100% mapping các mục engine biết chưa đồng nghĩa
100% nội dung khách hàng đã được hỗ trợ: phải kiểm kê cả nội dung tĩnh, động,
nội dung nhập thủ công và cấu trúc chưa hỗ trợ. Không âm thầm bỏ nội dung.

- Giữ nguyên importer Tracking và mô hình dữ liệu chuẩn hóa hiện có.
- Không thay đổi template mặc định Full/Server/Client hoặc Legacy Renderer.
- Không sửa report_generator.py, report_orchestrator.py, report_snapshot.py trong
  đợt UI này. Không migration database để phục vụ một thay đổi giao diện.
- Không suy diễn nội dung điều tra khi Tracking không cung cấp bằng chứng.
- Cấu trúc Word phức tạp chưa được renderer hỗ trợ phải được chỉ rõ; cần chuẩn
  hóa bản sao hoặc đề xuất adapter riêng, không giả vờ hỗ trợ bằng giao diện.
- Giữ tích hợp pack đã được người dùng duyệt ở TS-15; đợt này không tự thay đổi
  feature flag hoặc lựa chọn template trong luồng Generate.

## 2. Luồng mục tiêu

```text
Word khách hàng → Thư viện nguồn → Phân tích → Chuẩn hóa bản sao
                                               ↓
Tracking → Importer hiện có → Dữ liệu chuẩn → Mapping từng vùng Word
                                               ↓
                         Rà soát nội dung và các phần chưa hỗ trợ
                                               ↓
                         Tạo DOCX thử → người dùng kiểm tra
                                               ↓
                         Xác minh → Phát hành pack có version
                                               ↓
                         Chọn pack rõ ràng trong tool → Report
```

Word nguồn giữ checksum và không bị ghi đè. Mapping gắn với version template.
Thay nguồn hoặc mapping phải làm mất hiệu lực bằng chứng kiểm thử cũ tương ứng.

## 3. Các giai đoạn thực hiện

| Bước | Công việc | Sản phẩm và điều kiện qua bước |
|---|---|---|
| S0 | Kiểm kê UI, API, state, thay đổi đang có và baseline | Xác định ranh giới Studio; không ghi đè working tree |
| S1 | Project Stitch private, brief dùng dữ liệu tổng hợp | Không đưa CSV/DOCX khách hàng, khóa API hoặc dữ liệu thật lên Stitch |
| S2 | Hai phương án Mapping cùng tình huống và design system | Người dùng duyệt hướng A/B trước khi thay UI thật |
| S3 | Chốt token, typography, bảng, form, focus và theme | Ít chú thích; semantic color; dark/light rõ ràng |
| S4 | Thiết kế thư viện, nguồn, chuẩn hóa, mapping, rà soát, test, phát hành | Mỗi bước có loading/empty/error/retry/stale và cách phục hồi |
| S5 | Prototype tương tác độc lập dùng dữ liệu giả | Người dùng duyệt luồng hoàn chỉnh; không kết nối dữ liệu sản xuất |
| S6 | Tích hợp React từng phần trong Studio | Tái sử dụng API/component; không CSS toàn cục; test theo từng thay đổi |
| S7 | Regression, QA và bàn giao | Full gate, E2E, DOCX review, tài liệu và người dùng nghiệm thu |

Ba điểm duyệt: hướng Mapping; prototype tương tác; bản tích hợp trước phát hành.
Không coi ảnh Stitch là chức năng đã được triển khai hoặc đã kiểm thử.

## 4. Hai phương án Mapping

**A — Bảng mapping tập trung:** bảng chiếm phần lớn chiều rộng, inspector bên
phải có ngữ cảnh Word và cặp trường dữ liệu. Ưu tiên quét nhiều mục và sửa nhanh.

**B — Ngữ cảnh Word:** outline hẹp bên trái, vùng cấu trúc tài liệu ở giữa,
inspector bên phải. Ưu tiên hiểu dữ liệu sẽ xuất hiện ở vị trí nào trong template.
Ngữ cảnh cấu trúc không được quảng bá là bản render Word chính xác từng pixel.

Cùng tình huống tổng hợp: Mẫu khách hàng A.docx, Full, v0.1.0; 7/10 mục đã duyệt.
Mục máy chủ đang chờ duyệt; IoC thiếu anchor; khuyến nghị chưa mapping.
hostname → Tên máy, ip → Địa chỉ IP, os → Hệ điều hành.
Ví dụ SRV-DEMO-01, 192.0.2.10, Linux. Một CTA chính: Duyệt & tiếp theo.

## 5. Yêu cầu theo màn hình

- Thư viện: tìm kiếm/phân trang nguồn, workspace và version; phân biệt tạo mới,
  tiếp tục và xem phiên bản. Không biến thành dashboard trang trí.
- Nguồn: chọn file hoặc nguồn đã lưu; phân tích thành công không có nghĩa đã duyệt.
- Chuẩn hóa: preview thay đổi, tạo bản sao; không tự xóa nội dung mẫu của khách.
- Mapping: trạng thái đã lưu/đã duyệt riêng biệt; chỉ chuyển sau server xác nhận;
  chỉ rõ anchor trùng, thiếu, không sở hữu và cột không hợp lệ.
- Rà soát: kiểm kê phần tĩnh/động/thủ công/chưa hỗ trợ và nguồn dữ liệu từng phần.
- Kiểm thử: dùng Tracking qua importer cũ, tải DOCX đọc thật, xác minh bằng chứng
  lượt hai; không hiển thị phần trăm hay nút hủy giả khi backend chưa hỗ trợ.
- Phát hành: version bất biến, checksum, lịch sử và khôi phục; kỹ thuật nâng cao
  thu gọn, không phủ kín màn hình bằng cảnh báo và hướng dẫn dài.

## 6. Backend tương ứng

Trước tiên dùng API hiện có. Nếu inspector cần ngữ cảnh chưa có, chỉ bổ sung API
đọc có giới hạn: đoạn lân cận, cột bảng, vị trí và trạng thái anchor. Không trả
toàn bộ hàng chục nghìn dòng vào DOM. Revision conflict phải giữ draft và cho
người dùng tải lại/đối chiếu. Mapping không được làm biến đổi hợp đồng Tracking.

Nếu template cần dữ liệu ngoài Tracking, khai báo trường nhập bổ sung có nguồn
rõ ràng hoặc báo chưa hỗ trợ; không tự tạo thông tin chuyên môn. Mở rộng renderer
hay semantics là công việc riêng cần đánh giá tác động trước khi triển khai.

## 7. Kiểm thử và tiêu chí nghiệm thu

- Ba template tổng hợp khác cấu trúc dùng cùng Tracking; kiểm tra Full/Server/Client,
  bộ 30/50 máy, tổng số và máy bất thường không mất; nội dung tĩnh giữ nguyên.
- Đối chiếu từng mục khách hàng với vùng Word và nguồn dữ liệu; không chỉ đếm anchor.
- Source checksum không đổi; mở lại workspace còn mapping; thay template/version
  không tái sử dụng nhầm kết quả test hoặc report cache cũ.
- Lỗi mạng, timeout, conflict, thiếu anchor, schema không hỗ trợ đều phục hồi được.
- Keyboard, focus, screen-reader status, 200% zoom, viewport 760px, light/dark.
- Backend/frontend tests, production build, E2E kho tạm, golden DOCX legacy đạt.
- Người dùng đọc DOCX thực tế để duyệt định dạng, không thay bằng kiểm thử byte.
- Không công bố benchmark mới nếu chưa đo. Stitch không là dependency runtime.

## 8. Rủi ro và cách kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| UI đẹp nhưng API không hỗ trợ | Đối chiếu từng control với capability thật trước S6 |
| Hiểu nhầm template nào cũng chạy ngay | Inventory chưa hỗ trợ và gate kiểm thử bắt buộc |
| Mất draft hoặc duyệt nhầm revision | Server acknowledgement, conflict recovery, evidence binding |
| Rò dữ liệu qua dịch vụ thiết kế | Chỉ prompt và dữ liệu tổng hợp; không upload nguồn khách hàng |
| HTML sinh ra có script/dependency ngoài | Rà soát rồi viết lại trong component hiện có; không chép thẳng |
| Ảnh hưởng luồng cũ | Diff riêng Studio, regression legacy, rollback UI riêng |

## 9. Nhật ký và điểm tiếp tục

### 07/09/2026 — UI mới có lối vào riêng

Theo yêu cầu người dùng, mẫu HTML mới họ cung cấp được đưa vào lối so sánh
`?view=template-studio-next` của ứng dụng, không thay Studio cũ. Thêm link chuyển
qua lại, giữ mounted state của report/Studio. Mẫu là synthetic read-only trong
iframe sandbox, dùng CSS đã biên dịch và SVG nội bộ, không mạng/script/API.
Chưa triển khai flow phân tích/mapping/publish thật cho UI này. 120 frontend tests,
lint, format:check và production build đạt; chưa visual QA/E2E đợt này. Xem README
trong apps/frontend/src/features/template-studio-next/ để tiếp tục, không quay lại
các mockup B cũ đã bị người dùng từ chối làm chuẩn thiết kế.

### Prototype B tương tác — 06/09/2026

**Bản tương tác bên dưới bị người dùng đánh giá chưa đạt thẩm mỹ. Không dùng nó
làm chuẩn thị giác để tích hợp.**

### Dựng lại theo source B của Stitch

- Đã lấy HTML của screen `a70a20885eff4b89aaebbadd0962e494` qua get_screen,
  đọc source thay vì tiếp tục suy đoán bố cục từ mô tả.
- File duyệt mới: [template-studio-b-design-review.html](template-studio-b-design-review.html).
- Bám cấu trúc source: top navigation, outline 256px, context canvas giữa,
  inspector 320px, mapping cards và CTA chân inspector. Không còn hero workspace,
  trang giấy Word giả hay thanh mô phỏng lỗi trên màn hình duyệt.
- Loại avatar từ xa, CDN Tailwind, Google Fonts, nút Publish và các link giả.
  Dùng CSS/SVG nội bộ; font fallback Segoe UI khi máy không có Be Vietnam Pro.
  Đây là khác biệt typography đã biết, không tuyên bố pixel-perfect.
- Giữ cảnh báo IoC ở footer tổng thể, không đặt lỗi section khác vào inspector
  đang chọn máy chủ. Nút duyệt chỉ giải thích phạm vi mockup, không giả lưu thành công.
- Chỉ light mode ở đợt duyệt thị giác này; dark mode và interaction integration
  sẽ làm sau khi bản nhìn được chấp nhận. Không xóa prototype/state tests cũ.
- Test cấu trúc: `node --test docs/design/workspace-b-design-review.test.cjs`.
  Chưa có browser visual QA do hạn chế file URL đã ghi nhận; cần người dùng mở
  file đánh giá. Không gọi DOM tests là visual approval.

Đợt tinh chỉnh thị giác tiếp theo:

- Giữ bố cục B; bổ sung typography compact, toolbar dạng segmented control,
  icon SVG nội bộ, document canvas sáng tách biệt workspace dark/light, inspector
  theo nguồn–đích và row selection đồng bộ bảng/outline.
- Hover/focus và chuyển vùng 160ms, spinner chỉ khi saving; tôn trọng
  prefers-reduced-motion. Không CDN, font tải ngoài hoặc thư viện UI mới.
- Sửa prototype giữ recovery theo section; khóa chỉnh mapping khi kết quả lưu
  chưa rõ hoặc đang conflict; giữ focus bàn phím sau khi render lại field.
- Test DOM: `node --test docs/design/workspace-b-prototype.test.cjs`.
  Bộ test chỉ kiểm chứng demo, không phải backend/renderer thực tế.
- Chưa có visual QA browser do file URL bị policy chặn ở phiên trước. Cần người
  dùng mở lại file để đánh giá; không coi bước này là đã nghiệm thu UI enterprise.

- File độc lập: [template-studio-workspace-b.html](template-studio-workspace-b.html).
- Có outline, ngữ cảnh, bảng mapping, bộ lọc section, chỉnh cột/anchor, tiến độ
  duyệt, light/dark và mô phỏng save/error/conflict/unknown-result.
- Không dùng backend, CDN hoặc dữ liệu khách hàng. Refresh đặt lại demo; có cảnh
  báo rời trang khi còn draft. Không coi đây là chức năng persistence thật.
- Node kiểm tra cú pháp script đạt; git diff --check không báo lỗi whitespace.
- Browser policy chặn file URL: chưa chạy QA trực quan, keyboard hoặc interaction
  tự động. Không dùng đường vòng để mở file bị chặn. Cần người dùng mở file trực
  tiếp để duyệt; không tuyên bố prototype hay UI sản xuất đã đạt gate.
- Còn làm: kiểm chứng tương tác (đặc biệt đổi selection khi đang recovery), QA
  theme/reflow, state tests và các bước review/test/publish. Chưa tích hợp UI thật.

- Project private: `2380858661542370462` — Reporter Pro — Template Studio UI Lab.
- Design system: `assets/17266719944938089322` — Reporter Studio — Calm Violet.
- Kiểm tra kết nối 06/09/2026: get_project và list_design_systems thành công;
  list_screens chưa có màn hình. Không coi lần tạo A trước đó là hoàn thành.
- B đã được Stitch tạo: screen `a70a20885eff4b89aaebbadd0962e494`, session
  `7846803563055227621`, tên Ngữ cảnh cấu trúc — Mapping Workspace.
- A đã tạo từ B (chỉ thay layout): screen `b2fd51196bf044ed9b90547f6357333c`,
  session `10354827786534007320`, tên A · Mapping tập trung.
- Cả hai là mockup Stitch, chưa được kiểm chứng tương tác/accessibility hay kết
  nối backend. Người dùng đã chọn B; còn gate duyệt prototype tương tác.
- Stitch đề xuất tiếp tục màn Rà soát, lỗi IoC và dark mode; chưa chấp nhận các
  đề xuất này vì cần người dùng duyệt bố cục Mapping trước.
- Chưa tích hợp UI, chưa chạy lại gate ứng dụng trong đợt tài liệu/thiết kế này.
- Tiếp theo: state contract và prototype B tương tác theo quyết định đã duyệt.
- Gợi ý thêm từ Stitch cho A: thu gọn bảng, tăng ngữ cảnh Word, dark mode.
  Chỉ là lựa chọn để người dùng cân nhắc, chưa tự triển khai.
