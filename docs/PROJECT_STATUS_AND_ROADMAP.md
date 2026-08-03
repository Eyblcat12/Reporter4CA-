# Báo cáo hiện trạng và kế hoạch phát triển Reporter Pro

**Ngày cập nhật:** 21/07/2026
**Phạm vi:** mã nguồn, cấu trúc dữ liệu, giao diện, API, kiểm thử và quy trình chạy trong workspace hiện tại.

## 1. Tóm tắt điều hành

Reporter Pro là công cụ local-first tự động hóa việc tạo báo cáo DFIR/Compromise Assessment từ dữ liệu tài sản và bằng chứng kỹ thuật. Tool giải quyết chuỗi công việc từ nhập dữ liệu, chuẩn hóa và ánh xạ cột, hiệu chỉnh danh sách tài sản, chọn loại báo cáo và template, xem trước, đến xuất DOCX.

Sản phẩm hiện đã vượt qua giai đoạn proof-of-concept. Backend có 44 REST endpoint, sáu loại báo cáo, SQLite schema v7 để lưu template/version/preset/lịch sử/rule tùy chỉnh và lịch sử rule, rule engine cấu hình được, cơ chế plugin và report engine xử lý sâu cấu trúc Word. Frontend đã hình thành luồng ba bước hoàn chỉnh, hỗ trợ song ngữ, giao diện sáng/tối, dashboard hoạt động, command palette, phím tắt, quản lý template/version/rule, preview DOCX và tải workspace backup.

Chất lượng lõi đang ở mức tốt cho một ứng dụng desktop nội bộ: 83 kiểm thử backend, 30 kiểm thử frontend và E2E Chromium đều đạt; E2E bao phủ luồng import → tạo/dry-run rule → configure → preview → background job → download. Frontend production build thành công với Vite 8.1.5. GitHub Actions và quality gate local đã được thiết lập. Tuy nhiên, dự án chưa sẵn sàng để mở trực tiếp ra mạng hoặc vận hành nhiều người dùng. Các khoảng trống chính là restore an toàn, dependency lock đầy đủ và quy trình phát hành desktop tái lập hoàn chỉnh; kiểm soát plugin nâng cao được giữ cho giai đoạn server mode sau này.

Khuyến nghị chiến lược là tiếp tục theo hướng **local-first, enterprise-ready**: củng cố độ tin cậy và an toàn của bản desktop trước, sau đó mới mở rộng sang mô hình server nhiều người dùng.

## 2. Bài toán và giá trị của sản phẩm

### 2.1. Bài toán được giải quyết

Quy trình lập báo cáo đánh giá an ninh thường gặp các vấn đề:

- Dữ liệu đầu vào đến từ nhiều định dạng và đặt tên cột không thống nhất.
- Chuyên viên phải phân loại server/client và làm sạch dữ liệu thủ công.
- Nội dung Word dễ sai numbering, mục lục, định dạng bảng hoặc không đồng nhất giữa các dự án.
- Mỗi loại đối tượng đọc báo cáo cần mức chi tiết khác nhau.
- Việc tái sử dụng template, cấu hình và báo cáo cũ thiếu hệ thống quản lý.

Reporter Pro gom các thao tác trên vào một workflow thống nhất và có thể lặp lại. Giá trị lớn nhất hiện tại không chỉ là “xuất một file Word”, mà là chuẩn hóa quy trình tạo báo cáo và giảm phụ thuộc vào thao tác thủ công.

### 2.2. Nhóm người dùng mục tiêu

- Chuyên viên DFIR và Compromise Assessment.
- SOC/Blue Team cần tổng hợp kết quả rà soát tài sản.
- Đơn vị tư vấn an toàn thông tin cần chuẩn hóa đầu ra cho nhiều khách hàng.
- Quản lý kỹ thuật cần bản summary ngắn gọn bên cạnh báo cáo chi tiết.

## 3. Kiến trúc hiện tại

```text
Browser / Desktop shell
        │
        ▼
React + Vite frontend
        │ REST /api
        ▼
FastAPI backend
  ├── Input parser + column mapper
  ├── Validation + GUI state conversion
  ├── DOCX report generator
  ├── Template analyzer/manager
  ├── Plugin manager
  └── SQLite persistence
        │
        ├── templates/*.docx
        ├── data/reporter.db
        └── generated reports
```

Repository đã được tổ chức theo mô hình monorepo:

- `apps/backend/`: FastAPI, report engine, plugin, template và runtime data.
- `apps/frontend/`: React/Vite UI.
- `artifacts/desktop/`: bản desktop build cục bộ, được tách khỏi source tree.
- `scripts/`: launcher và automation.
- `tests/`: kiểm thử backend và các script integration.
- `docs/`: tài liệu kỹ thuật và roadmap.

### 3.1. Backend

Backend sử dụng FastAPI, Pydantic, pandas/openpyxl và python-docx/docxtpl. Hệ thống hiện có 44 endpoint, chia thành các nhóm:

| Nhóm | Khả năng chính |
|---|---|
| Health và sample | Kiểm tra dịch vụ, tải dữ liệu mẫu |
| Import | Xem trước cột, chọn sheet, import file, chuẩn hóa raw text |
| Dữ liệu | Validate row, tạo preview dạng text |
| Báo cáo | Tạo DOCX đồng bộ tương thích ngược; tạo, theo dõi, hủy và tải background job; preview DOCX; lưu báo cáo thành template |
| Template | Liệt kê, upload, cập nhật, xóa, đọc nội dung, phân tích |
| Preset | Lưu, tải, liệt kê và xóa cấu hình |
| History và dashboard | Lưu trạng thái/thời gian tạo report, truy vấn lịch sử và tổng hợp KPI theo kỳ |
| System | Tạo và tải workspace backup nhất quán |

SQLite dùng WAL mode, foreign key và câu truy vấn có tham số. Ba nhóm dữ liệu chính là:

- `templates`: metadata, hash, loại báo cáo, template mặc định và kết quả phân tích.
- `presets`: cấu hình báo cáo, mapping cột và template được chọn.
- `report_history`: thông tin đầu ra, số lượng tài sản, trạng thái, thời gian xử lý, mã lỗi an toàn và đường dẫn file.

Workspace Backup cung cấp snapshot SQLite nhất quán qua `sqlite3.backup()`, đóng
gói cùng template DOCX và manifest có SHA-256. Generated report và file môi trường
được loại khỏi gói theo mặc định; ZIP có thể chứa cấu hình kết nối đã lưu nên phải
được quản lý như dữ liệu nhạy cảm.

### 3.2. Frontend

Frontend sử dụng React 18, Vite, Framer Motion, Lucide React và docx-preview. Luồng người dùng gồm ba bước:

1. **Import:** kéo thả file, nhập raw text, xem sheet/header, ánh xạ cột và chỉnh bảng tài sản.
2. **Configure:** cấu hình tiêu đề/đơn vị/ngày, nguồn dữ liệu, preset và template.
3. **Export:** chọn loại báo cáo, xem preview/log, tạo và tải DOCX.

Các tiện ích UX đã có gồm dark/light mode, VI/EN, sidebar responsive, command palette, keyboard shortcuts, toast, dashboard 30/90/180 ngày, thống kê server/client và preview DOCX trong modal.

### 3.3. Report engine

Report engine là phần có giá trị kỹ thuật cao nhất của dự án. Sáu loại báo cáo được hỗ trợ:

1. `full`
2. `server_only`
3. `client_only`
4. `summary`
5. `technical`
6. `incident_response`

Engine có khả năng:

- Dùng template có sẵn hoặc tạo cover fallback.
- Thay token tiêu đề, tổ chức và thời gian đánh giá.
- Giữ hoặc tái tạo style, bảng và numbering của Word.
- Loại bỏ cache TOC trước khi sinh báo cáo.
- Tạo inventory trên 1.000 dòng mà vẫn giữ sequence đúng.
- Phân tách nội dung server/client theo report type.
- Sinh summary ba phần, technical report theo bằng chứng và báo cáo IR có cấu trúc riêng.
- Đánh dấu bất thường dựa trên bằng chứng thay vì gán cảnh báo đại trà.
- Yêu cầu Word cập nhật field/TOC và thay file theo cơ chế an toàn trên Windows.

### 3.4. Plugin system

Plugin có hai hook chính:

- `process_input()`: biến đổi dữ liệu trước khi tạo báo cáo.
- `modify_document()`: thay đổi document trước khi xuất.

Hai plugin mẫu hiện có là OS Detector và Elasticsearch raw-log fetcher. Cơ chế này tạo nền tảng tốt để bổ sung nguồn dữ liệu mới mà không làm phình core engine.

## 4. Những gì đã hoàn thành đến hiện tại

### 4.1. Import và chuẩn hóa dữ liệu

- Hỗ trợ Excel, CSV/TSV, JSON và raw text.
- Phát hiện định dạng thực dựa trên nội dung, không chỉ dựa vào phần mở rộng.
- Chọn sheet, nhận diện header row và xem trước cột.
- Tự động mapping các biến thể tên cột sang hostname, IP, OS, result và notes.
- Xử lý file tracking có cột server/client song song.
- Cho phép sửa, thêm, xóa và phân loại row trước khi xuất.
- Validate dữ liệu và trả lỗi theo row/field.

### 4.2. Quản lý template

- Upload và kiểm tra file DOCX.
- Giới hạn/kiểm tra cấu trúc file và làm sạch tên file.
- Phân tích token, heading, table và template mode.
- Tách thư mục template theo sáu loại báo cáo.
- Thiết lập template mặc định độc lập cho từng loại.
- Cập nhật metadata, đổi loại, xóa và xem thumbnail/preview.
- Lưu preview hoặc báo cáo đã tạo thành template mới.

### 4.3. Tạo và xem trước báo cáo

- Xuất DOCX trực tiếp từ giao diện.
- Preview dạng text và preview DOCX.
- Lưu lịch sử cả lần tạo thành công/thất bại và thời gian xử lý.
- Tổng hợp dashboard phía server: số report, số tài sản, tỷ lệ thành công, xu hướng và hoạt động gần đây.
- Giữ định dạng template và xử lý các lỗi numbering phức tạp.
- Hỗ trợ báo cáo quản trị, kỹ thuật và incident response thay vì chỉ một mẫu cố định.
- Báo cáo Incident Response có readiness gate đồng nhất ở frontend/backend: bắt buộc mã sự cố, thời điểm phát hiện, timeline hợp lệ và IoC/action đủ cấu trúc; owner, evidence và liên kết IoC còn thiếu được cảnh báo để tăng khả năng truy vết.

### 4.4. Trải nghiệm sử dụng

- Workflow ba bước dễ hiểu.
- Song ngữ Việt/Anh.
- Theme sáng/tối.
- Command palette và keyboard shortcuts.
- Hiển thị tiến độ job nền, cho phép thu gọn panel, hủy an toàn, tải lại kết quả, log thao tác, thống kê tài sản và thông báo lỗi.
- Launcher Windows hỗ trợ production/development, kiểm tra port và tái sử dụng instance hợp lệ.

### 4.5. Độ tin cậy đã được xác nhận

Tại thời điểm lập báo cáo:

- **83 kiểm thử backend trong quality gate**, gồm job queue, rule engine/versioning/import-export, IR validation/evidence, template versioning/schema v7, golden DOCX, soak harness, IoC/MITRE và các regression cũ.
- **30/30 kiểm thử frontend đạt** bằng Vitest và React Testing Library; các trường hợp phục hồi mới bao phủ import 422, preview 500, queue 429, polling gián đoạn tạm thời và retry sau khi job chuyển sang trạng thái unavailable mà không làm mất dữ liệu đang thao tác.
- Golden DOCX sinh báo cáo diff JSON và HTML theo report type/category khi có regression; CI lưu artifact lỗi để review trước khi cập nhật baseline.
- **E2E Chromium đạt** cho workflow Sample → Configure → tạo/dry-run rule → Preview DOCX → Background job → Download.
- **Frontend production build đạt**, 1.910 module được transform bằng Vite 8.1.5.
- `npm audit` đạt **0 vulnerability** sau khi nâng đồng bộ Vite/Vitest/plugin React.
- Launcher PowerShell được kiểm tra cú pháp thành công.
- Không còn tham chiếu đến đường dẫn repository cũ sau khi chuyển sang monorepo.
- Hash SHA-256 và tổng số byte của bản `Reporter.exe` được giữ nguyên sau khi sắp xếp.

Phạm vi test hiện đã bao phủ các regression có giá trị cao: import lần đầu, tracking mapping, template category/default, database migration v3, dashboard summary, workspace backup, DOCX field update, report type, TOC, numbering và inventory trên 1.000 dòng.

## 5. Đánh giá chất lượng hiện tại

### 5.1. Điểm mạnh

- Phân tách frontend/backend/core/plugin tương đối rõ.
- Report engine giải quyết được nhiều vấn đề Word khó và có test regression.
- Pydantic và parameterized SQL tạo nền tảng dữ liệu an toàn hơn.
- Template/preset/history biến tool từ script đơn lẻ thành ứng dụng có trạng thái.
- UI đã đủ hoàn chỉnh để người dùng không cần thao tác CLI.
- Cấu trúc monorepo mới dễ hiểu và thuận lợi cho CI/CD.

### 5.2. Hạn chế và nợ kỹ thuật

| Mức | Hạn chế | Tác động |
|---|---|---|
| Cao | Không có xác thực/phân quyền | Không phù hợp mở API ra mạng hoặc dùng chung nhiều người |
| Cao | Restore backup đã có dry-run/checksum/rollback | Đã xử lý; tiếp tục kiểm tra định kỳ trên backup release thật |
| Cao | Plugin được nạp như Python code trực tiếp | Plugin không tin cậy có toàn quyền trong process backend |
| Cao | Custom template/plugin path vẫn dành cho local mode | Đường dẫn template do database quản lý đã được chặn khỏi thao tác ngoài thư mục; cần policy riêng trước server mode |
| Trung bình | Coverage frontend mới tập trung workflow lõi | Cần mở rộng dần khi thêm component và trạng thái UI mới |
| Trung bình | Dependency Python đã lock toàn bộ cây và hash | Đã xử lý; mọi cập nhật phải regenerate và review lockfile |
| Trung bình | Migration schema v3 chưa có downgrade/restore workflow | Cần quy trình rollback trước các migration lớn hơn |
| Thấp | Job report chỉ tồn tại trong phiên backend | Khi ứng dụng bị dừng cưỡng bức, job đang chạy không thể tiếp tục sau lần khởi động kế tiếp |
| Thấp | Bản desktop artifact chưa được build lại theo baseline 2.0.0 | Source và binary bàn giao có thể chưa cùng revision |
| Thấp | Release automation chưa tạo changelog/checksum tự động | Release hiện vẫn cần bước rà soát thủ công |

Ngoài ra, Elasticsearch là tích hợp tùy chọn nhưng dependency và quy trình cấu hình/chẩn đoán kết nối chưa được đóng gói đầy đủ. Các script `test_integration.py` và `test_excel.py` hiện thiên về kiểm tra thủ công hơn là test suite có assertion và fixture chuẩn.

## 6. Rủi ro cần quản lý

### 6.1. Rủi ro dữ liệu

- SQLite WAL cần backup/restore đúng cách, không chỉ sao chép riêng file `.db` khi ứng dụng đang chạy.
- Lịch sử đang lưu đường dẫn file cục bộ; file có thể bị di chuyển hoặc mất ngoài database.
- Template upload cần quota, versioning và cơ chế phục hồi sau xóa.

### 6.2. Rủi ro bảo mật

- API hiện nên tiếp tục bind vào `127.0.0.1`.
- Không nên cho phép người dùng từ xa chỉ định thư mục plugin hoặc đường dẫn file tùy ý.
- Plugin chỉ nên chạy khi được cài từ nguồn tin cậy; về lâu dài cần manifest, chữ ký/hash allowlist hoặc process isolation.
- Nội dung lỗi không nên trả stack trace hoặc thông tin hệ thống nhạy cảm.

### 6.3. Rủi ro vận hành

- Word field update phụ thuộc nền tảng Windows và Microsoft Word.
- Chưa có pipeline đóng gói desktop từ source với checksum và provenance.
- Bản desktop hiện là artifact được bảo toàn, nhưng repository chưa có pipeline tạo installer mới từ đầu.

## 7. Kế hoạch phát triển đề xuất

### Giai đoạn 0 — Ổn định baseline (1–2 tuần)

**Mục tiêu:** tạo một phiên bản có thể tái lập, kiểm tra và phát hành nhất quán.

- Hoàn tất review và commit cấu trúc monorepo.
- Semantic version, changelog, release note, checksum workflow và baseline v2.1.0
  đã hoàn thành; desktop installer vẫn là bước đóng gói riêng tiếp theo.
- GitHub Actions và quality gate local cho backend/frontend đã hoàn thành.
- Chuẩn hóa formatter/linter: Ruff cho Python, ESLint/Prettier cho frontend.
- Dependency Python trực tiếp/gián tiếp và SHA-256 đã khóa trong hai lockfile;
  setup cùng CI bắt buộc `--require-hashes`.
- `npm ci` và package lock đã được đưa vào CI.
- Tách unit test khỏi script integration thủ công.
- Restore có kiểm tra manifest/checksum, dry-run preview và rollback database /
  template đã hoàn thành, cùng API/UI và regression test lỗi giữa chừng.
- Baseline tag v2.1.0 được tạo sau khi toàn bộ quality gate đạt.

**Điều kiện hoàn thành:** clone sạch có thể cài, test và build bằng tài liệu; không cần thao tác ngầm ngoài hướng dẫn.

### Giai đoạn 1 — Production hardening cho local/desktop (2–4 tuần)

**Mục tiêu:** bản desktop ổn định và an toàn khi dùng trong môi trường doanh nghiệp.

- CORS mặc định chỉ cho localhost và hỗ trợ danh sách origin qua environment (đã hoàn thành).
- Chuẩn hóa error envelope và logging có request ID.
- Đã khóa thao tác đọc/xóa template do database quản lý trong template root; custom template/plugin path cần policy theo local/server mode.
- Thêm giới hạn kích thước file, số row và thời gian xử lý.
- Thêm backup theo lịch, database migration framework và integrity check.
- Tác vụ tạo DOCX nền đã hoàn thành: 1 job chạy + 2 job chờ, chống request trùng, progress/cancel, panel thu gọn và dọn file tạm khi lỗi/hủy. Endpoint đồng bộ cũ được giữ để tương thích ngược.
- Thêm test API integration bằng FastAPI TestClient.
- Component test, API integration và E2E workflow import → configure → preview → export đã hoàn thành và chạy trong CI.
- Tạo installer, checksum và quy trình nâng cấp/rollback.

**Điều kiện hoàn thành:** không mất dữ liệu khi nâng cấp, có thể chẩn đoán lỗi từ log, và mọi đường dẫn/tệp người dùng đều được kiểm soát.

### Giai đoạn 2 — Nâng cao chất lượng báo cáo (4–8 tuần)

**Mục tiêu:** tăng giá trị nghiệp vụ của đầu ra thay vì chỉ tăng số màn hình.

- Versioning template, compare và rollback.
- Template compatibility schema v1.0 cho token/table/section của sáu report type đã hoàn thành; upload được phân loại compatible/warnings/incompatible và template không tương thích không thể làm mặc định hoặc generate.
- Dashboard hoạt động workspace và bảng chất lượng dữ liệu trước khi tạo báo cáo đã hoàn thành.
- Biểu đồ thống kê, severity, coverage và xu hướng phát hiện.
- Chuẩn hóa/validate/loại trùng IoC và kiểm tra MITRE ATT&CK theo evidence đã được nối vào Technical/IR; phần giao diện chỉnh mapping vẫn đang phát triển.
- Cho phép cấu hình rule phân loại bất thường thay vì hard-code.
- PDF export được hoãn theo quyết định sản phẩm để giữ bản local/team gọn nhẹ; không thuộc phạm vi phát triển hiện tại.
- Cải thiện IR timeline, evidence reference và remediation tracking.
- Bộ golden-file structural v1 cho cả sáu report type đã hoàn thành, so sánh heading, paragraph digest, table, numbering, token, section và relationship; cập nhật bằng cờ `UPDATE_GOLDEN_DOCX=1`.

**Điều kiện hoàn thành:** báo cáo có thể kiểm chứng, tái tạo và so sánh giữa các lần chạy.

### Giai đoạn 3 — Tích hợp và cộng tác (8–12 tuần)

**Mục tiêu:** hỗ trợ team và nhiều nguồn dữ liệu mà không làm mất tính đơn giản của bản desktop.

- Hoàn thiện Elasticsearch connector với retry, pagination và health diagnostics.
- Xây connector framework cho nguồn dữ liệu khác.
- Workspace/project để tách dữ liệu theo khách hàng hoặc vụ việc.
- Role-based access control nếu bật server mode.
- PostgreSQL và object storage cho triển khai nhiều người dùng.
- Audit log cho thay đổi template, preset và báo cáo.
- Chia sẻ preset/template qua export package có manifest và checksum.

**Điều kiện hoàn thành:** nhiều người có thể cộng tác mà vẫn đảm bảo phân quyền, truy vết và tách biệt dữ liệu.

### Giai đoạn 4 — Hệ sinh thái và open-source readiness

**Mục tiêu:** nếu quyết định công khai dự án, biến repository thành sản phẩm cộng đồng có thể đóng góp.

- MIT License, tài liệu cộng đồng và issue template đã được công bố.
- Thêm `CONTRIBUTING.md`, `SECURITY.md`, code of conduct và issue templates.
- Công bố plugin SDK, manifest và compatibility matrix.
- Tạo tài liệu kiến trúc, API examples và hướng dẫn viết template.
- Semantic versioning, changelog và release notes tự động.
- Dependency/security scanning và quy trình tiếp nhận vulnerability.

## 8. Thứ tự ưu tiên sản phẩm

| Ưu tiên | Hạng mục | Lý do |
|---|---|---|
| P0 | CI, dependency lock, version và release baseline | Bảo vệ toàn bộ thành quả đã có |
| P0 | Database backup/migration | Tránh mất preset, template metadata và history |
| P0 | Path/CORS/plugin hardening | Điều kiện bắt buộc trước khi mở rộng phạm vi sử dụng |
| P1 | API/frontend/E2E tests | Baseline workflow lõi đã hoàn thành; tiếp tục tăng coverage theo tính năng mới |
| P1 | Background report jobs | Đã hoàn thành cho local/team; tiếp tục theo dõi hiệu năng với fixture lớn |
| P1 | Template versioning/golden tests | Bảo vệ chất lượng đầu ra Word |
| P2 | Dashboard, MITRE và IoC | Tăng giá trị chuyên môn của báo cáo; PDF đã hoãn |
| P2 | Multi-user/server mode | Chỉ làm sau khi local-first đã ổn định |
| P3 | Public plugin ecosystem | Phụ thuộc quyết định license và mô hình phân phối |

## 9. Chỉ số thành công đề xuất

- 100% pull request phải qua backend test và frontend build.
- Tỷ lệ tạo báo cáo thành công ≥ 99% với bộ dữ liệu hợp lệ.
- Không có regression trong bộ golden DOCX cho các template mặc định.
- Import 10.000 row và preview/tạo báo cáo nằm trong SLA được công bố.
- Backup có thể restore thành công trong bài test định kỳ.
- 0 đường dẫn tùy ý ra ngoài workspace trong server mode.
- Thời gian từ clone sạch đến chạy ứng dụng dưới 15 phút theo tài liệu.
- Mọi release có version, checksum, changelog và rollback instructions.

## 10. Kết luận

Reporter Pro đã có nền tảng sản phẩm rõ ràng, report engine đáng kể và trải nghiệm người dùng đủ hoàn chỉnh cho sử dụng nội bộ. Thành quả nổi bật nhất là khả năng biến dữ liệu không đồng nhất thành nhiều loại báo cáo Word có cấu trúc, đồng thời quản lý template, preset và lịch sử trong một workflow duy nhất.

Bước phát triển đúng tiếp theo là **củng cố**, không phải viết lại: đóng gói baseline, tự động hóa quality gate, bảo vệ dữ liệu, siết quyền truy cập tệp/plugin và xây test ở cấp API/UI. Sau khi các nền tảng đó ổn định, dự án có thể mở rộng hợp lý sang phân tích chuyên sâu, connector, cộng tác nhiều người và—nếu có quyết định về license—một hệ sinh thái open source thực sự.
## Cập nhật: rule builder theo dữ liệu thực tế

- Người dùng có thể tạo và chỉnh sửa rule tùy chỉnh ngay trong bước Configure.
- Nút **Thử trên dữ liệu hiện tại** chạy rule trên các dòng vừa import nhưng chưa lưu, đồng thời hiển thị hostname, trường và từ khóa đã khớp.
- Rule là cấu hình khai báo giới hạn theo trường/từ khóa/loại trừ; không thực thi mã tùy ý. Rule mặc định không thể bị sửa.
- Khi lưu, rule tùy chỉnh được lưu trong SQLite schema v6 và được snapshot vào preview/job để kết quả không thay đổi giữa lúc job đang chạy.
- Kết luận trong bảng tổng hợp được chuẩn hóa thành: **Không phát hiện dấu hiệu bất thường**, **Ghi nhận dấu hiệu cần xác minh**, hoặc **Ghi nhận dấu hiệu bất thường**. Note và result gốc vẫn được giữ làm evidence và nội dung chi tiết.
- SQLite schema v7 lưu lịch sử mỗi lần cập nhật rule. Người dùng có thể xem và khôi phục phiên bản cũ; thao tác khôi phục tạo một phiên bản mới để không làm mất dấu vết thay đổi.
- Rule Manager hỗ trợ nhân bản, export/import gói JSON cho team và cảnh báo các rule chồng lấn theo trường/từ khóa. Import không ghi đè rule hiện có; chế độ rename tạo tên an toàn khi trùng.
