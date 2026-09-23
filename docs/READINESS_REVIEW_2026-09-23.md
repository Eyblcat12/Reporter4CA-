# Rà soát sẵn sàng sử dụng — 23/09/2026

> Bổ sung sau rà soát: source đã được commit/push, sửa E2E mock và kiểm chứng clone
> GitHub trong [hồ sơ đồng bộ](GITHUB_SYNC_PLAN_2026-09-23.md). Các mục “chưa commit”
> và “mock E2E lỗi” bên dưới là kết quả trước đợt khắc phục; các giới hạn backup
> Studio, recovery và duyệt Word vẫn còn hiệu lực.

Phạm vi: working tree hiện tại trên nhánh `codex/reporter-pro-github-release`,
HEAD `41fc19a`. Đây không phải chứng nhận bản đã push hoặc clean-clone.
Không sửa mã nghiệp vụ, template khách hàng hoặc kho dữ liệu thật trong lượt rà soát.

## Kết luận

Luồng báo cáo mặc định có thể cân nhắc dùng trong pilot có người kiểm tra DOCX.
Chưa coi toàn bộ tool, đặc biệt Template Studio, là bản phát hành đã nghiệm thu.
Kết quả test tự động không thay thế duyệt Word thực tế của khách hàng.

## Bằng chứng lượt này

- Ruff check/format: đạt, 130 files; merge-boundary check đạt.
- Python `pip check`: không phát hiện dependency bị thiếu/xung đột.
- ESLint/Prettier: đạt.
- Frontend: 134 tests / 27 files đạt; còn warning React act trong suite.
- Production build cách ly: đạt, 1.937 modules; không ghi đè dist đang dùng.
  Mọi file trong bản build kiểm chứng khớp hash với file tương ứng của dist hiện tại.
- E2E với API giả lập: 3 đạt (tiến độ import, workflow report, sáng/tối),
  1 lỗi (Studio approve). Mock chưa xử lý editor-drafts mới, trả 404 trước
  approve nên coverage vẫn 0. Cần cập nhật test, không bỏ assertion để làm xanh.
- E2E backend thật với dữ liệu tạm: 3/3 đạt, gồm thư viện nguồn/reload;
  mapping → baseline → xác minh → publish → chọn pack → preview → generate/download;
  và chuẩn hóa tài liệu nguồn không có anchor. Dùng template/dữ liệu tổng hợp.
- Bộ hồi quy backend trong scripts/check.ps1: **402 tests đạt**, 464,383 giây.
  Bao gồm golden sáu report type, API/jobs, runtime lifecycle, Tracking, backup/
  restore và rollback. Không đồng nghĩa mọi kịch bản production đều đã bao phủ.
- Tracking.csv: sinh/lưu/mở lại DOCX xác nhận đủ 30 máy (20 server/10 client),
  8 bất thường, 8 mục điều tra và 8 máy trong phần gỡ bỏ mã độc.
- Tracking_2.csv: đủ 50 máy (22 server/28 client), 20 bất thường, 11 cần rà soát,
  17 sạch và 2 thiếu dữ liệu; 20 mục điều tra, 10 máy cần phần gỡ bỏ mã độc.
- Log launcher mới nhất trên máy (15/09) không có ERROR/Traceback qua tìm kiếm;
  có shutdown do launcher heartbeat hết hạn. Không dùng log này để khẳng định
  đã kiểm tra lại launcher hôm nay.

## Các vấn đề cần xử lý trước khi bàn giao rộng

### 1. P1 — Chưa nghiệm thu recovery/xung đột bản nháp đầu cuối

App giữ Studio mounted khi quay lại Reporter Pro; không kết luận liên kết đó
làm mất draft. beforeunload có cảnh báo khi còn thay đổi. Tuy nhiên chưa có
nghiệm thu browser reload/restart/hai tab, mất kết nối sau commit và conflict
comparison hoàn chỉnh. Test thư viện nguồn reload không chứng minh recovery draft.
Đây là khoảng trống kiểm chứng, không phải lỗi mất dữ liệu đã tái hiện.
Luôn chờ “Đã lưu nháp” trước khi đóng/reload, không bỏ qua cảnh báo còn thay đổi.

### 2. P1 — Backup hiện tại không phải backup toàn bộ Template Studio

`core/workspace_backup.py` đóng gói reporter.db và templates/*.docx, không
đóng gói data/template_studio (nguồn, workspace, catalog, validation, editor DB).
Không coi ZIP backup hiện có là phương án phục hồi toàn bộ Studio. Cần snapshot
nhất quán kho Studio và kiểm thử restore. Trước đó, chỉ sao lưu toàn kho khi tool
đã dừng sạch; bảo vệ dữ liệu nhạy cảm trong bản sao.

### 3. P1 — Release chưa có baseline chứa đầy đủ thay đổi

Working tree có nhiều file modified/untracked, gồm runtime data. Không dùng
`git add .` rồi push. Cần phân loại source/data, commit có phạm vi, tag baseline,
và kiểm tra cài/chạy từ clean clone trước khi phân phối cho thành viên khác.

### 4. P1 — Gate E2E Studio chưa xanh

Test mock lỗi như trên dù luồng backend thật đạt. Phải sửa hợp đồng mock và
kiểm thử cả autosave lỗi/retry trước khi gọi đây là release pass.

## Chưa được chứng minh trong lượt này

- Hình thức DOCX trong Microsoft Word: mục lục/số trang, header/footer,
  ngắt trang, bảng và heading với dữ liệu thực của dự án.
- Tải hàng chục nghìn máy/soak nhiều giờ: không chạy lại benchmark.
- Clean-clone/install, kiểm toán CVE/dependency trực tuyến và launcher khởi động/
  đóng thực tế hôm nay. pip check chỉ kiểm tra tương thích, không kiểm tra CVE.
- Studio draft khôi phục sau restart/hai tab, xung đột, lỗi đĩa và phục hồi toàn kho.
- Template bất kỳ không có nghĩa tự mapping đúng 100%; pack mới vẫn cần người duyệt.

## Checklist dùng dự án thực tế

1. Chốt bản source và lưu backup trước khi nhập dữ liệu khách hàng.
2. Dùng template Full/Server/Client đã được khách hàng duyệt; không chỉnh template
   trong quá trình làm dự án nếu chưa có nghiệm thu riêng.
3. Chạy bộ dữ liệu đại diện; đối chiếu tổng máy, server/client, máy bất thường,
   điều tra và gỡ bỏ mã độc với input, không chỉ xem job báo thành công.
4. Mở DOCX trong Word và kiểm tra định dạng/mục lục trước khi gửi khách hàng.
5. Với Studio, nghiệm thu pack riêng bằng dữ liệu đại diện trước khi dùng thật;
   chưa dùng bản nháp mapping làm nguồn duy nhất của dự án.
6. Giữ phạm vi local/team, không mở API ra Internet hoặc dùng như server đa người dùng.

## Dấu vết kiểm chứng

- Build riêng: `.verification-readiness-20260923/` (artifact kiểm tra, không phải source
  để commit). Không xóa thư mục dự án nào trong lượt này.
- Backend test server dùng kho tạm và đã dừng sau E2E; không gọi vào kho khách hàng.
- Chỉ thêm tài liệu rà soát này; không sửa lỗi, commit hay push thay người dùng.
