# Kế hoạch tối ưu hiệu năng Preview và Generate DOCX

> **Trạng thái:** Đề xuất kiến trúc, chưa triển khai  
> **Phạm vi:** Reporter Pro dành cho cá nhân và team nội bộ  
> **Ưu tiên:** Tăng tốc nhưng không thay đổi template, nội dung, integrity hoặc giới hạn benchmark đã xác nhận  
> **Cập nhật:** 30/07/2026

## 1. Tóm tắt điều hành

Mục tiêu của kế hoạch không chỉ là giảm thời gian chờ. Mọi tối ưu phải đồng thời:

- Giữ nguyên template người dùng đã chọn.
- Đảm bảo Preview phản ánh đúng report cuối.
- Không thiếu hostname, finding, evidence hoặc bảng.
- Không tăng peak RAM vượt benchmark hiện tại.
- Không làm backend hoặc launcher ngắt nhầm khi CPU bận.
- Cho phép tắt từng tối ưu và quay lại engine cũ.
- Không tái sử dụng preview khi dữ liệu, rule, template hoặc metadata đã thay đổi.

Kết quả profile thực tế với `Tracking_2.csv` gồm 50 máy:

| Pha | Thời gian | Tỷ trọng gần đúng |
|---|---:|---:|
| Parse CSV | 19 ms | <1% |
| Rule engine | 3 ms | <1% |
| Dựng cấu trúc DOCX | 22.297 ms | ~98% |
| Lưu DOCX/ZIP | 152 ms | <1% |
| Cập nhật Word fields | 264 ms | ~1% |
| **Tổng** | **22.735 ms** | **100%** |

Điểm nghẽn chính:

1. Xóa nội dung mẫu khỏi template theo từng XML node.
2. Quét template nhiều lần để tìm prototype table.
3. Format lại hàng nghìn cell/run dù prototype đã có style.
4. Preview và Generate dựng lại hai DOCX gần như giống hệt nhau.

Chiến lược được đề xuất:

1. Đo timing chi tiết trong engine.
2. Tối ưu thao tác trim template.
3. Cache blueprint bất biến của template.
4. Tối ưu fast path cho cell đơn giản.
5. Tái sử dụng DOCX Preview khi Generate nếu signature vẫn khớp.
6. Chỉ nghiên cứu raw XML batch nếu benchmark lớn vẫn chưa đạt.

---

## 2. Baseline và giới hạn không được diễn giải sai

Các mốc đã xác nhận phải được giữ nguyên:

| Năng lực | Mốc đã xác nhận |
|---|---|
| Import, parse và data-quality | 50.000 máy |
| Một DOCX chi tiết dưới giới hạn RAM 3 GB | 3.750 máy |
| 4.000–5.000 máy | Chưa đạt; từng vượt watchdog RAM |
| 50.000 máy trong một DOCX | Chưa được hỗ trợ hoặc xác nhận |

Việc tối ưu tốc độ không tự động nâng mức hỗ trợ. Chỉ cập nhật benchmark sau khi có
kết quả đo thực tế về thời gian, peak RSS, output size và integrity.

---

## 3. Kiến trúc mục tiêu

```mermaid
flowchart LR
    UI["Frontend Workflow"] --> API["FastAPI"]
    API --> ORC["Report Orchestrator"]

    ORC --> VAL["Validation Service"]
    ORC --> SIG["Signature Service"]
    ORC --> JOB["Job Manager"]

    SIG --> PC["Preview Artifact Cache"]
    SIG --> TC["Template Blueprint Cache"]

    JOB --> TP["Template Preparation"]
    TP --> TB["Optimized DOCX Builder"]
    TB --> SAVE["Atomic DOCX Writer"]
    SAVE --> VERIFY["Integrity Verifier"]

    VERIFY --> PC
    VERIFY --> HISTORY["Report History"]
    VERIFY --> DOWNLOAD["Download Artifact"]

    PC --> PROMOTE["Preview Promotion"]
    PROMOTE --> VERIFY
```

### 3.1. Trách nhiệm

| Thành phần | Trách nhiệm |
|---|---|
| Report Orchestrator | Quyết định cache hit, cold generate, dedup hoặc fallback |
| Signature Service | Xác định preview có còn khớp request hiện tại |
| Template Blueprint Cache | Cache metadata và prototype XML bất biến |
| Optimized DOCX Builder | Dựng report nhanh nhưng giữ nguyên cấu trúc |
| Preview Artifact Cache | Lưu DOCX preview cục bộ trong thời gian ngắn |
| Integrity Verifier | Kiểm tra asset, finding, section, table và relationship |
| Atomic DOCX Writer | Chỉ publish file hoàn chỉnh |
| Job Manager | Progress, cancel, dedup và giới hạn concurrency |
| Report History | Chỉ ghi một terminal record cho report cuối |

---

## 4. Luồng Preview

```mermaid
flowchart TD
    A["Người dùng nhấn Preview"] --> B["Frontend chụp snapshot cấu hình"]
    B --> C["POST /api/preview-jobs"]
    C --> D["Validate rows và metadata"]

    D -->|"Có lỗi nghiêm trọng"| E["Trả lỗi Data Quality"]
    D -->|"Hợp lệ"| F["Snapshot rule và template"]

    F --> G["Tính canonical signature"]
    G --> H{"Đã có preview job cùng signature?"}

    H -->|"Đang chạy"| I["Trả lại cùng job ID"]
    H -->|"Đã hoàn tất"| J["Kiểm tra artifact cache"]
    H -->|"Không có"| K["Tạo preview job mới"]

    J --> L{"Artifact còn hợp lệ?"}
    L -->|"Có"| M["Trả preview từ cache"]
    L -->|"Không"| K

    K --> N["Load Template Blueprint"]
    N --> O{"Blueprint cache hit?"}

    O -->|"Có"| P["Dùng metadata và prototype đã cache"]
    O -->|"Không"| Q["Phân tích template một lần"]
    Q --> R["Lưu immutable blueprint"]
    R --> P

    P --> S["Fast template trim"]
    S --> T{"Invariant hợp lệ?"}

    T -->|"Không"| U["Fallback thuật toán trim cũ"]
    T -->|"Có"| V["Dựng inventory và summary"]
    U --> V

    V --> W["Dựng detail theo batch"]
    W --> X["Lưu DOCX tạm"]
    X --> Y["Integrity verification"]

    Y -->|"Không đạt"| Z["Không publish và báo lỗi"]
    Y -->|"Đạt"| AA["Atomic publish vào preview cache"]

    AA --> AB["Trả previewId và DOCX"]
    AB --> AC["Frontend hiển thị Preview Current"]
```

### 4.1. Nguyên tắc

- Preview chạy bằng job nền, không chặn event loop.
- Hai request cùng signature dùng chung một job.
- Artifact chỉ chuyển sang `ready` sau khi integrity đạt.
- Fast trim lỗi sẽ tự fallback về legacy trim.
- Backend, không phải frontend, quyết định cache còn hợp lệ.

---

## 5. Luồng Generate sau Preview

```mermaid
flowchart TD
    A["Người dùng nhấn Generate"] --> B["POST /api/report-jobs"]
    B --> C["Validate dữ liệu hiện tại"]
    C --> D["Tính signature mới"]

    D --> E{"Có previewId?"}

    E -->|"Không"| F["Cold Generate"]
    E -->|"Có"| G["Tải metadata preview"]

    G --> H{"Preview tồn tại?"}
    H -->|"Không"| F
    H -->|"Có"| I{"Chưa hết TTL?"}

    I -->|"Không"| J["Đánh dấu Expired"]
    J --> F

    I -->|"Có"| K{"Signature khớp?"}
    K -->|"Không"| L["Đánh dấu Stale"]
    L --> F

    K -->|"Có"| M{"Integrity trước đó hợp lệ?"}
    M -->|"Không"| F
    M -->|"Có"| N["Lock artifact"]

    N --> O["Copy hoặc hard-link sang output tạm"]
    O --> P["Verify DOCX lần cuối"]
    P -->|"Không đạt"| Q["Bỏ cache và Cold Generate"]
    P -->|"Đạt"| R["Atomic move sang output chính thức"]

    R --> S["Ghi History đúng một lần"]
    S --> T["Cập nhật Dashboard"]
    T --> U["Cho phép Download"]

    F --> V["Dựng DOCX từ đầu"]
    V --> W["Verify Integrity"]
    W --> R
```

Cache miss hoặc mismatch không phải lỗi. Backend sẽ tự động chuyển sang cold
generate và giữ nguyên workflow hiện tại.

---

## 6. Luồng Cold Generate

```mermaid
flowchart TD
    A["Report Request"] --> B["Validate Data"]
    B --> C["Snapshot Rules"]
    C --> D["Resolve Template"]
    D --> E["Load Blueprint"]

    E --> F["Open fresh Document"]
    F --> G["Replace cover tokens"]
    G --> H["Remove cached TOC result"]
    H --> I["Fast trim template body"]

    I --> J["Build report sections"]
    J --> K["Build inventory tables"]
    K --> L["Build summary tables"]

    L --> M["Split assets into batches"]
    M --> N["Build batch"]
    N --> O["Cancellation checkpoint"]

    O -->|"Còn batch"| N
    O -->|"Hoàn tất"| P["Finalize headings và numbering"]

    P --> Q["Save temporary DOCX"]
    Q --> R["Optional Word field update"]
    R --> S["Integrity verification"]

    S -->|"Fail"| T["Không publish"]
    S -->|"Pass"| U["Atomic publish"]
    U --> V["Record history"]
    V --> W["Download ready"]
```

---

## 7. Tối ưu Template Body

### 7.1. Luồng hiện tại

```mermaid
flowchart TD
    A["Mở template"] --> B["Dò Heading 1"]
    B --> C["Xóa XML node đầu tiên"]
    C --> D["XML tree re-index"]
    D --> E{"Còn node?"}
    E -->|"Có"| C
    E -->|"Không"| F["Tiếp tục build"]
```

Thao tác xóa từng node có thể làm XML tree phải cập nhật chỉ mục lặp lại và dẫn đến
độ phức tạp gần O(n²).

### 7.2. Luồng tối ưu

```mermaid
flowchart TD
    A["Mở template"] --> B["Đọc danh sách body node một lần"]
    B --> C["Xác định cover boundary"]
    C --> D["Xác định content boundary"]
    D --> E["Xác định sectPr"]
    E --> F["Chụp invariant trước khi trim"]

    F --> G["Xóa toàn bộ content range theo block"]
    G --> H["Kiểm tra invariant sau trim"]

    H -->|"Đạt"| I["Tiếp tục builder"]
    H -->|"Không đạt"| J["Discard document"]
    J --> K["Mở lại template"]
    K --> L["Chạy legacy trim"]
    L --> I
```

### 7.3. Invariant bắt buộc

```text
section_count_after >= 1
sectPr_after tồn tại
cover_hash_before == cover_hash_after
header_relationships_before == header_relationships_after
footer_relationships_before == footer_relationships_after
template_file_hash không thay đổi
TOC field còn tồn tại nếu template có TOC
```

### 7.4. Ảnh hưởng

| Mặt | Ảnh hưởng |
|---|---|
| Tốc độ | Dự kiến cải thiện lớn nhất |
| RAM | Có thể giảm nhẹ |
| Template gốc | Không bị sửa |
| Format | Có rủi ro nếu boundary sai |
| Rollback | Feature flag và legacy fallback |

---

## 8. Template Blueprint Cache

```mermaid
flowchart TD
    A["Template Path"] --> B["Đọc SHA-256"]
    B --> C["Kết hợp report type và engine version"]
    C --> D["Blueprint Cache Key"]

    D --> E{"Cache hit?"}

    E -->|"Có"| F["Clone immutable prototype XML"]
    E -->|"Không"| G["Analyze template"]

    G --> H["Detect mode"]
    H --> I["Detect boundaries"]
    I --> J["Index prototype tables"]
    J --> K["Collect styles và relationships"]
    K --> L["Create immutable blueprint"]
    L --> M["Store LRU cache"]
    M --> F
```

### 8.1. Blueprint model

```text
TemplateBlueprint
├── cache_key
├── template_hash
├── template_path
├── report_type
├── compatibility_version
├── template_mode
├── cover_boundary
├── content_boundary
├── section_fingerprint
├── relationship_fingerprint
├── toc_metadata
├── style_map
├── prototype_map
└── created_at
```

### 8.2. Không cache

- Đối tượng `python-docx.Document` đang chỉnh sửa.
- Dữ liệu tracking.
- Finding hoặc evidence.
- Rule output.
- Metadata khách hàng.

### 8.3. Giới hạn

- Tối đa 8 blueprint.
- LRU eviction.
- Cache chỉ nằm trong RAM.
- Xóa toàn bộ khi backend restart.
- Invalidate khi hash template hoặc engine compatibility version thay đổi.

---

## 9. Tối ưu Table Builder

```mermaid
flowchart TD
    A["Cell cần ghi dữ liệu"] --> B{"Cell structure?"}

    B -->|"Một run đơn giản"| C["Fast text replacement"]
    B -->|"Nhiều run"| D["Safe python-docx path"]
    B -->|"Có hyperlink"| D
    B -->|"Có Word field"| D
    B -->|"Merged cell"| D
    B -->|"Không xác định"| D

    C --> E{"Cần conditional style?"}
    E -->|"Không"| F["Giữ style prototype"]
    E -->|"Có"| G["Chỉ cập nhật property thay đổi"]

    D --> H["Format đầy đủ như engine hiện tại"]

    F --> I["Append row"]
    G --> I
    H --> I
```

### 9.1. Fast path

- STT.
- Hostname.
- IP.
- OS.
- Asset type.
- Result thông thường.
- Note plain text.

### 9.2. Safe path

- Finding nhiều đoạn.
- Evidence.
- IoC.
- MITRE ATT&CK.
- Remediation.
- Timeline.
- Severity styling.
- Hyperlink, field hoặc merged cell.

### 9.3. Batch

Batch mặc định đề xuất: 25–50 asset.

Sau mỗi batch:

- Cập nhật progress.
- Kiểm tra cancel.
- Đo RSS.
- Ghi timing.
- Cho heartbeat và request khác cơ hội xử lý.

Không cho nhiều thread cùng chỉnh một `Document`.

---

## 10. Canonical Signature

```mermaid
flowchart TD
    A["Normalized Rows"] --> H["Canonical Serializer"]
    B["Report Metadata"] --> H
    C["Template Hash"] --> H
    D["Rule Snapshot"] --> H
    E["Report Type"] --> H
    F["Plugin Fingerprint"] --> H
    G["Engine Version"] --> H

    H --> I["Stable JSON Stream"]
    I --> J["SHA-256"]
    J --> K["Report Signature"]
```

### 10.1. Thành phần

```text
signature = SHA256(
    engine_version
    + compatibility_version
    + report_type
    + template_hash
    + normalized_rows
    + row_order
    + title
    + organization
    + assessment_date
    + metadata
    + rule_snapshot_hash
    + disabled_rule_ids
    + plugin_fingerprint
)
```

### 10.2. Quy tắc canonical hóa

| Loại | Quy tắc |
|---|---|
| Dictionary | Sort theo key |
| List asset | Giữ nguyên thứ tự |
| Unicode | Chuẩn hóa NFC |
| Ngày | ISO-8601 |
| Boolean | `true/false` |
| Missing field | Chuẩn hóa về giá trị xác định |
| Rule | Hash definition đã snapshot |

Không cần đưa output filename vào signature vì đổi tên file không làm thay đổi nội
dung report.

---

## 11. State machine của Preview Artifact

```mermaid
stateDiagram-v2
    [*] --> Generating

    Generating --> Ready: "Generate và verify thành công"
    Generating --> Failed: "Builder hoặc integrity lỗi"
    Generating --> Cancelled: "Người dùng hủy"

    Ready --> Promoting: "Generate cache hit"
    Ready --> Stale: "Signature không còn khớp"
    Ready --> Expired: "Quá TTL"

    Promoting --> Ready: "Giữ preview đến hết TTL"
    Promoting --> Failed: "Promote hoặc verify lỗi"

    Stale --> Expired: "Cleanup"
    Failed --> Expired: "Cleanup"
    Cancelled --> Expired: "Cleanup"
    Expired --> [*]
```

### 11.1. Quy tắc

- `Generating → Ready` chỉ khi file tồn tại và integrity đạt.
- `Ready → Promoting` phải lấy lock.
- Artifact `Promoting` không được cleanup.
- Artifact `Stale` không được dùng để Generate.
- Artifact `Failed` không được trả về frontend như preview hợp lệ.

---

## 12. Concurrency và deduplication

### 12.1. Hai Preview giống nhau

```mermaid
sequenceDiagram
    participant U1 as "Preview Request 1"
    participant U2 as "Preview Request 2"
    participant O as "Orchestrator"
    participant J as "Job Manager"
    participant B as "DOCX Builder"

    U1->>O: "Signature ABC"
    O->>J: "Create job ABC"
    J->>B: "Start build"

    U2->>O: "Signature ABC"
    O->>J: "Find active job ABC"
    J-->>U2: "Return same job ID"

    B-->>J: "Artifact ready"
    J-->>U1: "Preview ready"
    J-->>U2: "Preview ready"
```

### 12.2. Preview và Generate cùng lúc

```mermaid
sequenceDiagram
    participant P as "Preview"
    participant G as "Generate"
    participant J as "Job Manager"
    participant B as "Builder"
    participant A as "Artifact Cache"

    P->>J: "Start preview signature ABC"
    J->>B: "Build ABC"

    G->>J: "Generate signature ABC"
    J-->>G: "Wait for existing build"

    B->>A: "Publish verified artifact"
    A-->>J: "Artifact ready"

    J->>A: "Promote artifact"
    J-->>P: "Preview ready"
    J-->>G: "Report ready"
```

### 12.3. Quy tắc

- Hai request cùng signature không dựng hai DOCX.
- Generate có thể chờ Preview đang chạy.
- Hai lần nhấn Generate vẫn chỉ ghi một history record.
- Chỉnh dữ liệu trong lúc Preview chạy tạo signature mới, không hủy artifact cũ
  nhưng artifact cũ sẽ bị đánh dấu stale đối với workflow hiện tại.

---

## 13. Luồng lỗi và fallback

```mermaid
flowchart TD
    A["Fast optimization path"] --> B{"Có lỗi?"}

    B -->|"Không"| C["Tiếp tục"]
    B -->|"Có"| D["Phân loại lỗi"]

    D --> E{"Lỗi optimization?"}
    E -->|"Có"| F["Disable optimization cho request"]
    F --> G["Retry bằng legacy path"]

    E -->|"Không"| H{"Lỗi dữ liệu hoặc template?"}
    H -->|"Dữ liệu"| I["Trả validation error"]
    H -->|"Template"| J["Trả compatibility error"]
    H -->|"Không xác định"| K["Fail job an toàn"]

    G --> L{"Legacy path thành công?"}
    L -->|"Có"| M["Report thành công và ghi fallback log"]
    L -->|"Không"| K

    K --> N["Cleanup temporary files"]
    N --> O["History failed hoặc cancelled"]
```

Không fallback đối với:

- Template incompatible.
- Data-quality blocking.
- Integrity fail do thiếu asset.
- Signature mismatch.
- Plugin output không xác định.

---

## 14. Cleanup cache

```mermaid
flowchart TD
    A["Cleanup Scheduler"] --> B["Đọc artifact registry"]
    B --> C{"Artifact state?"}

    C -->|"Promoting"| D["Bỏ qua"]
    C -->|"Generating"| D
    C -->|"Ready"| E{"Hết TTL hoặc vượt giới hạn?"}
    C -->|"Stale"| F["Đưa vào cleanup"]
    C -->|"Failed"| F
    C -->|"Cancelled"| F
    C -->|"Expired"| F

    E -->|"Không"| D
    E -->|"Có"| F

    F --> G["Xác minh path nằm trong cache root"]
    G -->|"Không an toàn"| H["Không xóa và ghi security log"]
    G -->|"An toàn"| I["Đánh dấu Expired"]
    I --> J["Xóa artifact"]
    J --> K["Xóa registry entry"]
```

### 14.1. Giới hạn đề xuất

| Thiết lập | Giá trị |
|---|---:|
| TTL | 15 phút |
| Artifact tối đa | 2 |
| Tổng dung lượng | 1 GB |
| Cache qua restart | Không |
| Cleanup khi lỗi | Ngay lập tức |
| Cleanup khi shutdown | Có |

Cleanup chỉ được phép thao tác trong cache root đã xác minh. Template và report đã
tải không thuộc phạm vi cleanup.

---

## 15. API contract đề xuất

### 15.1. Tạo Preview Job

```http
POST /api/preview-jobs
```

```json
{
  "rows": [],
  "title": "",
  "organization": "",
  "assessmentDate": "",
  "reportType": "full",
  "templatePath": "",
  "metadata": {}
}
```

```json
{
  "job": {
    "id": "preview-job-id",
    "status": "queued",
    "signature": "sha256"
  },
  "deduplicated": false
}
```

### 15.2. Trạng thái

```http
GET /api/preview-jobs/{jobId}
```

```json
{
  "job": {
    "status": "running",
    "phase": "asset_details",
    "progress": 62
  }
}
```

### 15.3. Nội dung Preview

```http
GET /api/preview-jobs/{jobId}/content
```

Headers:

```text
X-Preview-ID
X-Preview-Signature
X-Report-Integrity
X-Template-Hash
```

### 15.4. Generate

```http
POST /api/report-jobs
```

```json
{
  "rows": [],
  "previewId": "optional-preview-id",
  "title": "",
  "organization": "",
  "reportType": "full"
}
```

Response bổ sung:

```json
{
  "job": {
    "mode": "preview_cache_hit",
    "status": "queued"
  }
}
```

---

## 16. Thay đổi frontend

### 16.1. State

```text
previewState
├── status: none | generating | current | stale | failed
├── previewId
├── signature
├── generatedAt
├── templateHash
└── integrity
```

### 16.2. Invalidation

```mermaid
flowchart TD
    A["Preview Current"] --> B{"Người dùng thay đổi gì?"}

    B -->|"Theme hoặc modal"| C["Giữ Current"]
    B -->|"Output filename"| C
    B -->|"Rows"| D["Đánh dấu Stale"]
    B -->|"Template"| D
    B -->|"Report type"| D
    B -->|"Rule"| D
    B -->|"Metadata"| D

    D --> E["Generate không gửi previewId cũ"]
    E --> F["Backend cold generate"]
```

### 16.3. UX

- Badge `Preview hiện tại`.
- Badge `Dữ liệu đã thay đổi`.
- Cache hit hiển thị `Đang sử dụng bản preview đã xác nhận`.
- Cache miss dùng progress generate hiện tại.
- Không hiển thị hash hoặc đường dẫn cache.

---

## 17. Progress

### 17.1. Cold generate

```text
10%  Validate
20%  Prepare template
35%  Inventory
40–80% Asset detail batches
88%  Save DOCX
94%  Verify integrity
100% Complete
```

### 17.2. Cache hit

```text
10%  Validate preview
45%  Verify cached artifact
75%  Prepare download
95%  Record history
100% Complete
```

---

## 18. Metrics

Mỗi Preview/Generate cần ghi:

```json
{
  "mode": "cold_generate | preview_cache_hit",
  "rows": 50,
  "templatePrepareMs": 0,
  "templateTrimMs": 0,
  "prototypeIndexMs": 0,
  "tableBuildMs": 0,
  "saveMs": 0,
  "fieldUpdateMs": 0,
  "integrityMs": 0,
  "totalMs": 0,
  "peakRssMb": 0,
  "outputBytes": 0,
  "cacheHit": false,
  "fallbackUsed": false
}
```

Giai đoạn đầu chỉ log JSON. Chưa thay database schema cho đến khi format metrics ổn
định.

---

## 19. Feature flags và rollback

```text
AUTO_REPORT_FAST_TEMPLATE_TRIM=1
AUTO_REPORT_TEMPLATE_BLUEPRINT_CACHE=1
AUTO_REPORT_FAST_TABLES=1
AUTO_REPORT_PREVIEW_CACHE=0
```

Quy tắc rollback:

1. Tắt riêng feature gây lỗi.
2. Restart backend.
3. Không cần rollback database.
4. Không sửa template.
5. Report đã tạo không bị ảnh hưởng.
6. Cache cũ bị bỏ qua và hết hạn.

Preview cache để tắt mặc định trong giai đoạn prototype.

---

## 20. Work Breakdown Structure

### WP-A — Instrumentation

Backend:

- Tạo `GenerationMetrics`.
- Thêm timer context manager.
- Đo từng phase.
- Log JSON một dòng/job.
- Không ghi raw tracking vào log.

Điều kiện hoàn thành:

- Có baseline ổn định cho 50 máy.
- Timing phase cộng lại hợp lý với total.
- Lỗi/cancel vẫn ghi được phase đã chạy.

### WP-B — Fast Template Trim

Backend:

- Boundary detector.
- Block trim.
- Invariant verifier.
- Legacy fallback.
- Feature flag.

Kiểm thử:

- Cover hash.
- Section count.
- Header/footer relationship.
- TOC field.
- Sáu report type.
- Template tùy chỉnh.

Điều kiện hoàn thành:

- Golden test đạt.
- Không visual regression.
- Template preparation giảm rõ rệt.

### WP-C — Blueprint Cache

Backend:

- Template hash service.
- Blueprint extractor.
- LRU cache.
- Invalidation.
- Thread-safe read.

Kiểm thử:

- Cache hit/miss.
- Upload invalidation.
- Rollback invalidation.
- Không chia sẻ mutable state.

Điều kiện hoàn thành:

- Cold và warm output giống nhau.
- Cache không chứa dữ liệu tracking.

### WP-D — Fast Table Builder

Backend:

- Cell classifier.
- Fast text path.
- Safe path.
- Conditional style updater.
- Batch checkpoint.

Kiểm thử:

- Simple/rich cell.
- Hyperlink.
- Merged cell.
- Finding/evidence.
- Integrity 50 và 1.000 asset.

Điều kiện hoàn thành:

- Không visual diff ngoài ý muốn.
- Cancel hoạt động giữa batch.
- Tốc độ cải thiện theo số asset.

### WP-E — Preview Artifact Cache

Backend:

- Canonical signature.
- Artifact registry.
- Preview job API.
- Promote logic.
- TTL, size limit và locking.

Frontend:

- Lưu preview ID.
- Current/stale state.
- Gửi preview ID khi Generate.
- Cache-hit progress.

Điều kiện hoàn thành:

- Generate từ preview đạt mục tiêu.
- Cache invalidation đầy đủ.
- Cache mismatch fallback an toàn.
- Không ghi history hai lần.

---

## 21. Ma trận ảnh hưởng

| Thay đổi | Tốc độ | RAM | Rủi ro format | UX |
|---|---:|---:|---:|---:|
| Bulk trim XML | Rất lớn | Giảm nhẹ | Trung bình | Không |
| Blueprint cache | Trung bình | Tăng rất ít | Thấp | Không |
| Fast table formatting | Lớn với report dài | Giảm | Trung bình–cao | Không |
| Preview artifact cache | Generate rất lớn | Ít | Thấp nếu hash đúng | Có |
| Batch raw XML | Rất lớn ở hàng nghìn máy | Có thể giảm mạnh | Cao | Không |
| Bỏ Word fields | Rất nhỏ | Không đáng kể | Có thể sai TOC | Không làm |
| Bỏ rule/validate | Gần như không cải thiện | Không đáng kể | Giảm chất lượng | Không làm |

---

## 22. Benchmark plan

Mỗi mốc chạy tối thiểu ba chế độ:

1. Cold run.
2. Warm template cache.
3. Preview cache hit Generate.

Thu thập:

```text
wall time
CPU time
peak RSS
output size
template prepare time
table build time
integrity time
cache hit/miss
fallback count
asset count
finding count
```

| Assets | Preview cold | Generate cold | Generate cache hit | Peak RAM | Integrity |
|---:|---:|---:|---:|---:|---|
| 50 | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc |
| 1.000 | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc |
| 3.000 | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc | Bắt buộc |
| 3.750 | Bắt buộc | Bắt buộc | Bắt buộc | ≤3 GB | Bắt buộc |
| 4.000+ | Thử nghiệm | Thử nghiệm | Không công bố | Watchdog | Bắt buộc |

Mục tiêu ban đầu:

- Cold generate 50 máy giảm ít nhất 40%.
- Preview 50 máy mục tiêu dưới 8–10 giây.
- Generate cache hit mục tiêu dưới 2 giây.
- Không tăng peak RAM tại mốc 3.750 máy.
- Integrity luôn `True`.

Các con số mục tiêu không được công bố thành benchmark mới trước khi đo thực tế.

---

## 23. Quality Gates

```mermaid
flowchart LR
    A["Code Complete"] --> B["Unit Tests"]
    B -->|"Pass"| C["API Integration"]
    C -->|"Pass"| D["Golden DOCX"]
    D -->|"Pass"| E["Visual Render"]
    E -->|"Pass"| F["Tracking.csv"]
    F -->|"Pass"| G["Tracking_2.csv"]
    G -->|"Pass"| H["Large Benchmark"]
    H -->|"Pass"| I["Enable Feature Flag"]
    I --> J["Release Candidate"]
```

Bắt buộc:

- Backend tests đạt.
- Frontend tests đạt.
- Production build đạt.
- Sáu golden report type đạt.
- `Tracking.csv` đủ 30 máy và 8 bất thường.
- `Tracking_2.csv` đủ 50 máy.
- Không mất relationship, header hoặc footer.
- Integrity `True`.
- Lifecycle không ngắt khi CPU bận.
- Peak RAM không vượt mức cho phép.

---

## 24. Rollout

### Stage 1 — Internal Off

Code tồn tại nhưng feature flag tắt.

### Stage 2 — Benchmark Only

Chỉ bật trong script benchmark.

### Stage 3 — Builder Optimization On

Bật:

```text
FAST_TEMPLATE_TRIM
TEMPLATE_BLUEPRINT_CACHE
FAST_SIMPLE_CELLS
```

Preview cache vẫn tắt.

### Stage 4 — Preview Cache Prototype

Chỉ bật local development để kiểm tra workflow và UX.

### Stage 5 — Local/Team Default

Chỉ bật mặc định sau khi đạt toàn bộ quality gate.

---

## 25. Thứ tự triển khai và điểm dừng

### Sprint A — Builder Foundation

1. Instrumentation.
2. Fast trim.
3. Invariant validation.
4. Legacy fallback.
5. Benchmark 50 máy.

**Điểm dừng:** Báo cáo kết quả trước/sau.

### Sprint B — Template và Table

1. Blueprint cache.
2. Prototype index.
3. Fast path cho simple cell.
4. Safe path cho rich cell.
5. Benchmark 50 và 1.000 máy.

**Điểm dừng:** Chỉ tiếp tục nếu format hoàn toàn ổn.

### Sprint C — Preview Reuse Prototype

1. Artifact cache.
2. Canonical signature.
3. Cache hit/miss API.
4. Generate promotion.
5. TTL và cleanup.
6. Frontend current/stale.

**Điểm dừng:** Duyệt workflow và UX trước khi bật mặc định.

### Sprint D — Benchmark lớn

1. 1.000 máy.
2. 3.000 máy.
3. 3.750 máy.
4. So sánh thời gian, RAM và integrity.

### Sprint E — Raw XML Batch

Chỉ nghiên cứu nếu Sprint A–D chưa đạt hiệu năng mong muốn.

---

## 26. Quyết định kiến trúc đề xuất

| Vấn đề | Quyết định |
|---|---|
| Preview đầy đủ hay rút gọn | Preview đầy đủ |
| Số preview cache | Tối đa 2 |
| TTL | 15 phút |
| Dung lượng cache | Tối đa 1 GB |
| Cache qua restart | Không |
| Cache mutable Document | Không |
| Cache immutable blueprint | Có |
| Generate cache hit vẫn dùng job | Có |
| Cache mismatch | Cold generate |
| Fast trim lỗi | Legacy fallback |
| Parallel chỉnh cùng Document | Không |
| Batch asset | 25–50 asset |
| Raw XML trực tiếp | Chỉ sau benchmark |

---

## 27. Kết luận

Phương án cân bằng nhất:

1. Tối ưu bulk trim.
2. Cache blueprint template.
3. Tối ưu simple cell formatting.
4. Giữ Preview đầy đủ và chính xác.
5. Dùng preview artifact cho Generate khi signature khớp.
6. Giữ legacy fallback và feature flag.
7. Chỉ nâng benchmark sau khi kiểm thử thực tế.

Thiết kế này ưu tiên chất lượng report, khả năng truy vết và rollback trước khi
chuyển sang các tối ưu raw XML có rủi ro cao hơn.
