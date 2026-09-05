# Synthetic Profile Renderer benchmark

Harness này đo riêng Profile Renderer bằng Template Pack và payload tổng hợp. Nó
không dùng Legacy Renderer, không chỉnh template mặc định và không phải benchmark
template khách hàng.

Mỗi mốc chạy trong tiến trình mới. Parent theo dõi RSS và dừng worker khi vượt
`--memory-limit-mib` hoặc `--timeout-seconds`, do đó mốc lớn không được phép làm
treo toàn bộ Reporter Pro.

```powershell
apps\backend\.venv\Scripts\python.exe scripts\benchmark_profile_renderer.py `
  --asset-counts 50 1000 10000 50000 `
  --report-type full `
  --allow-large `
  --memory-limit-mib 3072 `
  --timeout-seconds 900
```

Kết quả nằm dưới `artifacts/benchmarks/profile-renderer/` và ghi rõ
`engineering-only-not-customer-benchmark`. `resource_limited` là kết quả an toàn,
không phải pass. Chỉ công bố benchmark chính thức sau khi chạy cùng pack/template
được duyệt, fixture thực tế và tối thiểu 10 trial tương thích.
