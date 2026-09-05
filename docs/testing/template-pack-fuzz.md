# Template Pack fuzz/soak testing

`scripts/fuzz_template_packs.py` chạy mutation có seed trên một `.rptpack` đã
publish để tìm exception parser thoát khỏi `TemplatePackError`. Harness không cài
pack, không extract và không nối vào Generate.

## Chạy nhanh

```powershell
apps\backend\.venv\Scripts\python.exe scripts\fuzz_template_packs.py `
  --pack C:\path\approved-pack.rptpack `
  --iterations 10000 `
  --seed 3235823838
```

## Soak theo thời gian

`--duration-minutes` là giới hạn bổ sung; runner dừng khi đạt thời gian hoặc số
iteration trước:

```powershell
apps\backend\.venv\Scripts\python.exe scripts\fuzz_template_packs.py `
  --pack C:\path\approved-pack.rptpack `
  --iterations 1000000 `
  --duration-minutes 120 `
  --checkpoint-every 250 `
  --output artifacts\template-pack-fuzz\customer-a.json
```

Runner dùng bảy mutation: truncate, bit flip, append, zero/delete/duplicate range
và overwrite range. Mỗi case được sinh từ `seed + case`, vì vậy có thể replay mà
không lưu byte nguồn trong JSON.

## Fuzz sâu DOCX, workspace và catalog

Byte mutation mặc định chủ yếu kiểm tra lớp ZIP ngoài. TS-17F bổ sung ba target
giữ outer ZIP và checksum nhất quán để mutation thực sự đi tới `template.docx`:

```powershell
# Nested DOCX trong pack
apps\backend\.venv\Scripts\python.exe scripts\fuzz_template_packs.py `
  --pack C:\path\approved-pack.rptpack --target nested-pack --iterations 10000

# Nested DOCX trong workspace draft export
apps\backend\.venv\Scripts\python.exe scripts\fuzz_template_packs.py `
  --pack C:\path\workspace-draft.zip --target nested-workspace --iterations 10000

# Cài mutation vào catalog tạm; mọi rejection phải giữ snapshot nguyên vẹn
apps\backend\.venv\Scripts\python.exe scripts\fuzz_template_packs.py `
  --pack C:\path\approved-pack.rptpack --target catalog --iterations 10000
```

Target `catalog` chỉ dùng catalog trong thư mục tạm, không chạm catalog đang dùng
của ứng dụng. Nếu một pack bị từ chối nhưng revision/metadata thay đổi, harness
coi đó là unexpected error và dừng với recipe có thể replay.

## Đọc kết quả

- `passed`: mọi input được accept hoặc bị từ chối bằng `TemplatePackError` có
  kiểm soát.
- `failed`: có exception khác thoát ra; runner dừng ở case đầu tiên.
- `acceptedMutations + controlledRejections` phải bằng `completedIterations` khi
  pass.
- `failure.recipe` cùng `seed`, `case` và pack có đúng `sourceSha256` dùng để tái
  hiện lỗi.
- P50/P95/max là latency inspector trên tập mẫu bounded; `peakRssMiB` là RSS nếu
  `psutil` có sẵn.

Checkpoint được ghi nguyên tử, không chứa nội dung template, JSON mapping hoặc
tracking data. Dù vậy, tên output không nên chứa tên khách hàng. Không commit
pack thật hoặc kết quả có metadata nhạy cảm.

## Release gate

Unit test chạy corpus nhỏ để giữ tính deterministic và contract không rò dữ liệu.
Soak nhiều giờ không chạy trong CI thông thường; thực hiện trước pilot/release,
lưu kết quả ở artifact nội bộ và ghi seed, pack SHA-256, số iteration, thời gian,
P95, peak RSS và outcome vào biên bản review.
