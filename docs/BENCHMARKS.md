# Benchmark Reporter Pro

Tài liệu này ghi lại các phép đo đã chạy thực tế để người dùng hiểu đúng khả
năng hiện tại của Reporter Pro. Đây là benchmark trên một workstation, không
phải cam kết hiệu năng cho mọi máy hoặc mọi template.

## Môi trường thử nghiệm

| Thành phần | Cấu hình |
|---|---|
| Thiết bị | Lenovo 82RD |
| CPU | AMD Ryzen 7 6800H, 8 nhân / 16 luồng |
| RAM | 16 GB cài đặt, khoảng 15,2 GiB khả dụng cho hệ điều hành |
| Hệ điều hành | Windows 64-bit |
| Runtime | Python 3.12, Node.js 20+ |
| Giới hạn giám sát | Peak RSS 3.072 MiB (3 GiB), timeout 600 giây/job lớn |
| Đầu ra | Một file DOCX, giữ nguyên template được chọn |

Đợt đo được thực hiện trong tháng 07/2026. Số liệu được lấy từ JSON kết quả do
supervisor của benchmark ghi lại, không ước lượng từ cảm nhận giao diện.

## Baseline Phase 0 — `mixed/full`, 50 máy, 5 trial

Baseline ngày 30/07/2026 dùng fixture `mixed-50`, template `full` mặc định và
engine chưa bật bất kỳ feature flag tối ưu nào. Mỗi trial chạy trong một Python
process mới (`process-cold/cache-miss`); cache filesystem của Windows không được
chủ động xóa và Microsoft Word field updater bị tắt. Vì vậy, số liệu này là mốc
so sánh cho các phase tối ưu tiếp theo, không phải phép đo “cold disk” tuyệt đối.

| Chỉ số | Kết quả |
|---|---:|
| Trial thành công | 5/5 |
| Product latency P50 | 16.220,5 ms |
| Product latency min–max | 16.163,3–16.687,7 ms |
| Peak RSS P50 / max | 720,8 / 721,5 MiB |
| Kích thước DOCX | 91.594 byte |
| Asset / finding / evidence | 50 / 42 / 67 |
| Kiểm tra save → reopen → semantic integrity | 5/5 đạt |

P95 chưa được công bố vì mới có 5 mẫu; benchmark runner chỉ xuất P95 khi có ít
nhất 10 trial.

## Preview Job release gate — `Tracking_2.csv`, 50 máy, 10 trial

Ngày 03/08/2026, Preview Job API được đo đủ 10 process độc lập với prepared
template đã prewarm, report `full`, plugin tắt và Word field update được kiểm soát.
Mỗi trial import lại `Tracking_2.csv`, poll job thật, tải DOCX, mở lại ZIP và xác
nhận semantic integrity. Ngưỡng release cho workstation tham chiếu là 10 giây.

| Chỉ số | Kết quả |
|---|---:|
| Trial đạt integrity | 10/10 |
| Trial dưới 10 giây | 10/10 |
| Preview P50 / P95 | 6.300,499 / 7.882,863 ms |
| Preview min / max | 4.831,658 / 7.926,317 ms |
| Product latency P50 / P95 | 6.212,551 / 7.791,045 ms |
| Peak RSS P50 / P95 | 734,832 / 735,186 MiB |

Release gate đạt. `AUTO_REPORT_PREVIEW_JOBS` và `AUTO_REPORT_PREVIEW_CACHE` được
bật mặc định cho local/team; đặt một trong hai về `0` sẽ rollback ngay về API
Preview tương thích hoặc cold Generate mà không cần migrate database. Có thể tái
lập phép tổng hợp bằng `scripts/summarize_preview_benchmarks.py`.

### Phân rã thời gian P50

| Phase | P50 |
|---|---:|
| Document build | 15.354,4 ms |
| Template trim | 10.354,4 ms |
| Report body build | 2.776,9 ms |
| Template load | 1.070,7 ms |
| Input parse | 802,5 ms |
| Prototype capture | 743,3 ms |
| Semantic integrity sau reopen | 714,7 ms |
| Integrity verify trong engine | 286,7 ms |
| Template detect | 142,6 ms |
| Save ZIP/DOCX | 78,2 ms |
| Reopen DOCX | 66,0 ms |
| TOC cleanup | 58,8 ms |

`templateTrim` chiếm khoảng 67% thời gian dựng document trong baseline này. Đây
là bằng chứng ưu tiên cho prepared-template cache ở phase tiếp theo; chưa có thay
đổi định dạng hoặc bỏ bước kiểm tra nào để đạt số liệu trên.

Baseline 5 trial này vẫn là mốc so sánh hiệu năng chính của Phase 0. Kết quả smoke
cuối phase ở phần tiếp theo dùng để xác nhận coverage của instrumentation, không
thay thế baseline và không được dùng để suy ra regression/cải thiện hiệu năng.

## Smoke xác nhận instrumentation cuối Phase 0 — 1 trial

Ngày 31/07/2026, runner được chạy thêm đúng một trial sau khi hoàn thiện timing cho
route, job, plugin và aggregate table. Cấu hình vẫn là `mixed-50`, report `full`,
`process-cold/cache-miss`, các feature flag tối ưu đều tắt và Word field updater
bị tắt. Artifact gốc nằm tại
`artifacts/benchmarks/phase0-final-smoke.json`.

| Chỉ số | Giá trị quan sát |
|---|---:|
| Trial thành công | 1/1 |
| Product latency | 30.706,1 ms |
| Peak RSS | 705,0 MiB |
| Kích thước DOCX | 91.594 byte |
| Asset / finding / evidence | 50 / 42 / 67 |
| Asset được xác nhận sau reopen | 50/50 |
| P95 | Không công bố — chỉ có 1 mẫu |

Giá trị 30,71 giây chỉ là số đo của một smoke run, không phải P50 có ý nghĩa thống
kê. Runner có thể lưu trường P50 cho tập một mẫu, nhưng tài liệu không dùng trường
đó như một median đã được xác lập. P95 chỉ được công bố khi có ít nhất 10 trial.

### Aggregate tạo và định dạng bảng trong smoke run

Các phép đo dưới đây cộng dồn theo loại bảng, không phát sinh event cho từng cell
hoặc ghi nội dung cell vào artifact:

| Loại bảng | Số bảng | Tạo bảng tổng / lớn nhất | Style tổng / lớn nhất |
|---|---:|---:|---:|
| Asset detail | 50 | 2.902,349 / 79,812 ms | 892,747 / 29,306 ms |
| Asset inventory | 2 | 506,644 / 307,710 ms | 81,134 / 47,872 ms |
| Asset summary | 2 | 338,264 / 209,051 ms | 60,056 / 33,774 ms |
| Remediation | 1 | 146,380 / 146,380 ms | 35,649 / 35,649 ms |
| IoC | 1 | 5,935 / 5,935 ms | 2,000 / 2,000 ms |
| **Tổng quan sát** | **56** | **3.899,572 ms** | **1.071,586 ms** |

`tableCreate` và `tableStyle` là metric lồng bên trong `reportBodyBuild`; không được
cộng thêm lần nữa vào product latency. Cùng smoke run ghi nhận `templateTrim`
20.736,5 ms và `reportBodyBuild` 5.185,0 ms. Kết quả tiếp tục chỉ ra template trim
là mục tiêu tối ưu đầu tiên, còn aggregate table cung cấp baseline chi tiết cho
Phase 1.

### Coverage của runtime metrics

`AUTO_REPORT_PERF_METRICS` mặc định bằng `0`. Khi chủ động bật bằng `1`, runtime
ghi metric đã lọc cho:

- `queueWait`;
- snapshot/validation hoặc snapshot build;
- plugin load, input plugin và document plugin;
- template preparation/hash;
- template resolve/load/detect, prototype capture, TOC cleanup và template trim;
- rule evaluation, report body, manifest và integrity trong engine;
- aggregate `tableCreate`/`tableStyle` theo loại bảng;
- save/ZIP, Word field update và post-plugin integrity;
- tổng thời gian dựng artifact và trạng thái kết thúc.

Log không chứa rows, hostname, note, payload plugin hoặc nội dung report. Lỗi ghi
metrics không được phép làm thay đổi kết quả generate. Runner benchmark gọi trực
tiếp parser/generator nên artifact smoke không có `queueWait`, phase HTTP/plugin
runtime hoặc Word field update đã tắt; các phase này được đo khi chạy qua route/job
thực với flag metrics bật.

## Bộ dữ liệu 50.000 máy

Fixture có 50.000 dòng, gồm 20.000 server và 30.000 client. Pipeline đã:

- đọc đủ 50.000 dòng;
- parse và phân loại đủ 20.000 server / 30.000 client;
- chạy data-quality trên toàn bộ dữ liệu;
- xác nhận không mất hostname đầu hoặc cuối;
- không phát hiện dòng lỗi, hostname trùng, IP sai, thiếu OS hoặc thiếu result
  trong fixture chuẩn.

Việc đọc và kiểm tra 50.000 dòng hoàn tất trong khoảng 20 giây. Con số này
không đồng nghĩa engine hiện có thể đưa chi tiết 50.000 máy vào một DOCX.
Phần tốn tài nguyên nhất là tạo hàng nghìn heading và table theo template Word.

## Kết quả tạo một DOCX chi tiết

Các mốc dưới đây dùng report `server_only` và cùng input 50.000 dòng; cột
“máy trong DOCX” là số asset được đưa vào phần chi tiết.

| Máy trong DOCX | Trạng thái | Tổng thời gian | Peak RSS | Kích thước | Kiểm tra cấu trúc |
|---:|---|---:|---:|---:|---|
| 1.000 | Hoàn tất | 93,8 giây | 848,1 MB | 1,17 MiB | ZIP/đầu-cuối hợp lệ |
| 2.000 | Hoàn tất | 188,2 giây | 1.575,6 MB | 2,31 MiB | ZIP/đầu-cuối hợp lệ |
| 3.000 | Hoàn tất | 375,2 giây | 2.433,3 MB | 3,45 MiB | ZIP/đầu-cuối hợp lệ |
| 3.500 | Hoàn tất | 419,4 giây | 2.661,1 MB | 4,01 MiB | ZIP/đầu-cuối hợp lệ |
| 3.750 | Hoàn tất 1 lần | 414,1 giây | 2.927,8 MB | 4,30 MiB | ZIP/đầu-cuối hợp lệ |
| 4.000 | Dừng bảo vệ | 404,2 giây | 3.099,0 MB | — | Vượt giới hạn RAM |
| 5.000 | Dừng bảo vệ | 556,5 giây | 3.072,7 MB | — | Vượt giới hạn RAM |
| 20.000 | Dừng bảo vệ | 600,2 giây | 710,1 MB | — | Hết timeout khi đang generate |

Mốc Full 3.000 máy cũng hoàn tất: 376,6 giây, peak RSS 2.258,0 MB, file
3,48 MiB, 3.006 bảng và 3.016 heading.

### Kết luận hiện tại

- Pipeline import/quality tương thích với dự án 50.000 máy.
- Với template chi tiết hiện tại và watchdog 3 GiB, 3.750 máy là mốc cao nhất đã
  hoàn tất trong **một lần chạy có giám sát**, chưa đủ số lần lặp để gọi là giới
  hạn ổn định.
- Mốc 3.000 máy sẽ được dùng làm release gate ban đầu; chỉ công bố là “ổn định”
  sau khi benchmark mới chạy lặp lại đủ số mẫu và kiểm tra semantic integrity.
- 4.000 máy không được xem là “hỏng ngẫu nhiên”: supervisor chủ động hủy khi
  RAM vượt ngưỡng để bảo vệ workstation.
- Dự án lớn hơn nên tách volume/report hoặc chờ tối ưu engine theo hướng giảm
  số object Word giữ đồng thời trong RAM. Không nên tăng giới hạn một cách mù
  quáng vì có thể làm máy cá nhân mất phản hồi.

## Full 3.000 máy — phân tách product/audit RSS

Ngày 17/08/2026, fixture tổng hợp `mixed-3000` gồm 1.200 server, 1.800 client
và 2.500 finding dự kiến được chạy trong fresh process với template Full mặc định.
Kết quả một lượt A/B có integrity đầy đủ:

| Cấu hình | Product latency | Product peak RSS | Peak gồm reopen audit | Output | Asset |
|---|---:|---:|---:|---:|---:|
| Legacy prototype | 221,7 giây | Chưa tách ở artifact cũ | 3.891,6 MiB | 3.679.182 byte | 3.000/3.000 |
| Compact prototype | 243,9 giây | **2.318,8 MiB** | 3.302,8 MiB | 3.679.182 byte | 3.000/3.000 |

Hai peak không được diễn giải như nhau. `productPeakRssMiB` được chụp ngay sau khi
DOCX đã save và trước audit; đây là peak gần với workflow Generate của người dùng.
`peakRssMiB` còn gồm benchmark mở lại DOCX trong khi object document gốc vẫn tồn tại
để kiểm tra semantic integrity, nên cao hơn nhưng không phải RAM của Generate.

Compact prototype giữ nguyên số byte output ở A/B này, vượt structural golden cho
sáu report type và đưa product peak dưới gate 2.765 MiB. Flag được bật mặc định cho
local/team với rollback `AUTO_REPORT_COMPACT_PROTOTYPE=0`. Kết quả trên mới là một
trial xác nhận instrumentation; bảng stability P50/P95 chỉ công bố sau 10 fresh run.

## Soak test job nền

Soak test dài 120 phút chạy workload 500 dòng/job:

| Chỉ số | Kết quả |
|---|---:|
| Job gửi vào | 83 |
| Hoàn tất | 66 |
| Failed theo kịch bản | 6 |
| Cancelled theo kịch bản | 11 |
| Timeout | 0 |
| Lỗi ngoài dự kiến | 0 |
| Dedup mismatch | 0 |
| P50 | 66,0 giây |
| P95 | 214,5 giây |
| Peak RSS | 524,6 MB |
| RSS tăng từ đầu đến cuối | 18,4 MB |
| Kết luận supervisor | Pass |

Các job `failed` và `cancelled` ở đây là nhánh được chủ động đưa vào kịch bản để
kiểm tra cleanup và phục hồi; `unexpectedFailures` bằng 0.

## Cách tái lập

Fixture và baseline Phase 0:

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\generate_tracking_fixture.py --verify
.\apps\backend\.venv\Scripts\python.exe .\scripts\benchmark_report_generation.py `
  --profile mixed --report-type full --trials 5 `
  --output artifacts\benchmarks\phase0-baseline-mixed-full.json
```

Smoke xác nhận instrumentation cuối Phase 0:

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\benchmark_report_generation.py `
  --profile mixed --report-type full --trials 1 `
  --output artifacts\benchmarks\phase0-final-smoke.json
```

Để ghi metrics ở luồng runtime thực, đặt `AUTO_REPORT_PERF_METRICS=1` trước khi
khởi động backend. Giữ flag ở `0` cho hoạt động thông thường nếu không cần chẩn
đoán hiệu năng chi tiết.

Soak test:

```powershell
.\apps\backend\.venv\Scripts\python.exe .\scripts\soak_report_jobs.py `
  --profile long --duration-minutes 120 --rows 500
```

Hướng dẫn đầy đủ: [testing/soak-test.md](testing/soak-test.md).

Benchmark DOCX lớn hiện được giữ như một quality exercise có giám sát thay vì
chạy trong CI thông thường, vì mỗi mốc có thể cần nhiều phút và vài GB RAM.
Khi công bố số liệu mới, cần ghi cùng fixture, template, cấu hình máy, watchdog,
timeout và JSON kết quả để việc so sánh có ý nghĩa.

## A/B Phase 1–2 — `mixed/full`, 50 máy, 10 trial

Đợt đo ngày 03/08/2026 dùng cùng fixture, template hash, report type và kiểm tra
semantic integrity sau khi reopen. Mỗi cấu hình có 10/10 trial thành công nên P95
được công bố. Control là legacy prototype và không dùng prepared-template cache.

| Cấu hình | P50 | P95 | Peak RSS P50 | So với control | Quyết định |
|---|---:|---:|---:|---:|---|
| Control/legacy | 25.761,779 ms | 26.908,560 ms | 705,090 MiB | — | Mốc A/B |
| Compact prototype | 26.912,647 ms | 28.296,083 ms | 704,967 MiB | P50 +4,47%; P95 +5,16% | Không rollout |
| Prepared template + legacy prototype | 6.959,978 ms | 7.774,972 ms | 706,670 MiB | P50 −73,0%; P95 −71,1% | Bật mặc định |

Prepared-template cache loại bỏ lượt trim template lặp lại trên cache hit. Ở cấu
hình cuối, `documentBuild` P50 là 6.105,935 ms, `reportBodyBuild` là 3.305,135 ms,
`prototypeCapture` là 2.275,477 ms, lookup prepared artifact là 28,782 ms và load
artifact là 9,716 ms. File đầu ra vẫn 91.594 byte và giữ nguyên asset, finding,
evidence cũng như cấu trúc golden của sáu report type.

Peak RSS P50 tăng khoảng 1,58 MiB (0,22%), thấp hơn ngưỡng regression 5%. Compact
prototype đã hoàn thiện về correctness nhưng chưa có lợi về tốc độ trên workload
này nên `AUTO_REPORT_COMPACT_PROTOTYPE=0`. Prepared cache dùng
`AUTO_REPORT_PREPARED_TEMPLATE=1`; đặt thành `0` để quay lại đường trim legacy.

JSON gốc được lưu cục bộ tại:

- `artifacts/benchmarks/phase1-phase2/measured-legacy/benchmark.json`;
- `artifacts/benchmarks/phase1-phase2/measured-compact/benchmark.json`;
- `artifacts/benchmarks/phase1-phase2/measured-prepared-memory-optimized/benchmark.json`.

Các artifact benchmark bị loại khỏi Git theo mặc định; bảng trên là kết quả đã
được duyệt để công bố trong repository.

## A/B Phase 3 — Fast cell trên báo cáo 1.000 máy

Đợt đo ngày 03/08/2026 dùng fixture xác định `mixed-1000`, report `full`, prepared
template bật, compact prototype tắt và chỉ thay đổi `AUTO_REPORT_FAST_CELL`.
Mỗi nhánh chạy 10 process cô lập; toàn bộ 20/20 trial đạt save, reopen và semantic
integrity. Hai nhánh tạo cùng DOCX 1.249.300 byte.

| Chỉ số | Safe cell | Fast cell | Thay đổi |
|---|---:|---:|---:|
| Product latency P50 | 72.641,318 ms | 59.007,216 ms | −18,8% |
| Product latency P95 | 73.371,854 ms | 62.954,135 ms | −14,2% |
| Report body P50 | 58.627,393 ms | 45.217,167 ms | −22,9% |
| Report body P95 | 59.647,107 ms | 48.069,939 ms | −19,4% |
| Asset-detail style P50 | 29.487,836 ms | 14.820,990 ms | −49,7% |
| Peak RSS P50 | 1.488,660 MiB | 1.464,010 MiB | −1,7% |
| Peak RSS max | 1.489,195 MiB | 1.464,406 MiB | −1,7% |

Table-create P50 tăng từ 17.127,236 lên 21.001,413 ms do prototype row được
chuẩn hóa trước khi clone, nhưng lượt style giảm gần một nửa nên tổng report body
vẫn giảm rõ rệt. Integrity P50 dao động từ 8.707,947 lên 8.833,085 ms; đây không
phải thay đổi thuật toán và nằm ngoài phần cell writer.

Fast path chỉ nhận cell có đúng một paragraph/run đơn giản và canonical rPr.
Cell merge, field, hyperlink, content control, nhiều run hoặc newline tự fallback.
`AUTO_REPORT_FAST_CELL=1` là mặc định sau Phase 3; đặt `0` để quay lại safe writer.

## Phase 5 — Preview artifact promotion, 50 máy

Ngày đo: 03/08/2026. Fixture đầu vào: `Tracking_2.csv`, 50 asset. Benchmark chạy
trong workspace tạm, database/cache/generated output biệt lập và dùng một DOCX hợp lệ
có bảng chứa đủ 50 asset làm artifact đã Preview. Artifact được pin bằng đúng request
signature và template hash trước khi gọi `POST /api/report-jobs` với `previewId`.

| Chỉ số | Kết quả | Ngưỡng |
|---|---:|---:|
| Accepted → report job completed | **73,092 ms** | < 2.000 ms |
| Kích thước Preview/report | 37.704 bytes | Phải bằng nhau |
| Byte-for-byte | **Đạt** | Bắt buộc |
| SHA-256 | `ffa97650ab26b1be09fc6ede3da18edf1a8046b627f2ce7cae921c747f0194da` | Phải bằng nhau |

Word field update được đặt `deferred-controlled` vì promotion không chạy lại Word hoặc
report engine. Script tái lập: `scripts/benchmark_preview_promotion.py`.

### Profile Preview Job thật và prewarm setup

Profile tái lập ngày 03/08/2026 chạy `POST /api/preview-jobs` với đúng luồng import
`Tracking_2.csv`, workspace/database/cache biệt lập, Word field update được kiểm soát
ở trạng thái deferred và kiểm tra lại DOCX ZIP cùng report integrity.

| Chỉ số | Cache-miss | Setup prewarm + Preview | Ngưỡng Preview |
|---|---:|---:|---:|
| Prepared-template compile | 19.871,725 ms | 17.705,480 ms chạy trước Preview | Tách khỏi tương tác |
| Preview API hoàn tất | 28.130,778 ms | **7.164,178 ms** | < 10.000 ms |
| Product latency | 28.035,822 ms | **7.056,364 ms** | < 10.000 ms |
| Peak RSS quan sát | — | 734,961 MiB | Theo dõi regression |
| Integrity/DOCX ZIP | Đạt | Đạt | Bắt buộc |

Nút thắt cache-miss là compile template, không phải dựng 50 asset: `reportBodyBuild`
chỉ khoảng 2,5–3,0 giây. `setup.ps1` vì vậy prewarm sáu template bundled vào cache
content-addressed. Lỗi prewarm không chặn cài đặt; engine vẫn có legacy fallback.

Số liệu cũ vượt 360 giây không tái hiện bằng harness đã sửa contract `jobId` và không
còn được dùng làm baseline.

Development gate cuối chạy **10/10 trial prewarmed đạt**: P50 6.300,499 ms,
P95 7.882,863 ms và max 7.926,317 ms. Ma trận đủ điều kiện công bố P95 và rollout
mặc định cho local/team. Compatibility flags vẫn được giữ để rollback tức thời.

Tái lập:

```powershell
apps\backend\.venv\Scripts\python.exe scripts\benchmark_preview_job.py `
  --cache-state prewarmed --enforce-target `
  --output artifacts\benchmarks\preview-job-prewarmed-50.json
```

Artifact gốc:

- `artifacts/benchmarks/phase3/1000-fast-cell-off/benchmark.json`;
- `artifacts/benchmarks/phase3/1000-fast-cell-on/benchmark.json`.
