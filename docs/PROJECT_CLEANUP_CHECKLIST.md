# Checklist rà soát dung lượng và tệp có thể ngừng sử dụng

Ngày khảo sát: 07/09/2026. Trạng thái: **chỉ khảo sát, chờ người dùng duyệt; chưa xóa/di chuyển**.

Phạm vi: `C:\Users\Legion 5\Downloads\AUTO_REPORT_DESKTOP`.
Các đường dẫn bên dưới tính từ thư mục này. MiB = 1.048.576 byte.
Dung lượng là tổng độ dài file đọc được, không phải dung lượng cấp phát vật lý;
bao gồm file ẩn, Git và dependency. Dữ liệu đang chạy có thể thay đổi sau khảo sát.

## 1. Kết luận chính

- Tổng khảo sát: **2.252,56 MiB (~2,20 GiB)**.
- `artifacts/verification`: **1.199,66 MiB**, 49.919 file, chiếm khoảng 53%.
- `artifacts/desktop/dist`: **350,63 MiB**, 1.802 file.
- Môi trường làm việc hiện tại: Python `.venv` **200,33 MiB**,
  frontend `node_modules` **153,23 MiB**; không đề xuất dọn khi còn phát triển.
- `.git`: **210,35 MiB**; không được xóa thủ công để giảm dung lượng.
- Toàn bộ `docs`: **0,72 MiB**. Dọn tài liệu/prototype gần như không giải quyết
  vấn đề dung lượng, nhưng có thể làm hỏng test và mất lịch sử quyết định.

Nguyên nhân nặng chủ yếu là bản clone kiểm thử kèm môi trường riêng và binary
đóng gói. Chưa có cơ sở kết luận file mã nguồn nào là dead code chỉ từ tên/tuổi file.

## 2. Ứng viên giải phóng dung lượng lớn — cần duyệt từng mục

| Duyệt | Đường dẫn | MiB | Nhận định và điều kiện trước khi dọn |
|---|---|---:|---|
| [ ] | `artifacts/verification/clean-clone-v2.2.0-2841745` | 528,26 | Bản clone kiểm thử riêng chứa dependency/Git; kiểm tra trạng thái Git bên trong, log kết quả và không có tiến trình dùng trước khi bỏ |
| [ ] | `artifacts/verification/clean-source-5c1745f93b7d4afa961301cf5e186c36` | 352,12 | Source smoke-test có môi trường riêng; giữ kết quả/log cần điều tra, xác nhận không có sửa đổi duy nhất |
| [ ] | `artifacts/verification/clean-clone-v2.2.0-d35c34a` | 199,28 | Clone kiểm thử phiên bản cũ; điều kiện như clone đầu tiên |
| [ ] | `artifacts/desktop/dist` | 350,63 | Binary desktop được tài liệu xác định là đầu ra cục bộ, Git ignore; chỉ bỏ nếu không dùng Reporter.exe tại đây và không cần bản bàn giao này |
| [ ] | `artifacts/verification/github-release-v2.2.0` | 30,37 | Bản giải nén/kiểm tra release; đối chiếu manifest và giữ bằng chứng trước |
| [ ] | `artifacts/verification/clean-source-05b5e6b7ec784a99964d5f1cd1cffcdc` | 24,53 | Workspace smoke-test khác; chưa xác nhận vì sao được giữ lại |
| [ ] | `artifacts/verification/github-release-v2.2.1` | 22,83 | Kiểm thử release mới hơn; xác nhận không phải bản đối chiếu cuối cùng cần giữ |

Ba mục clone/source lớn nhất cộng **1.079,66 MiB (~1,05 GiB)**.
Nếu duyệt thêm desktop dist, tổng khoảng **1.430,29 MiB (~1,40 GiB)**,
~63,5% dung lượng hiện tại. Đây là ước tính có điều kiện, không phải lệnh xóa.

**Không duyệt xóa toàn bộ `artifacts/verification`.** Trong đó còn có:

- `clean-source-latest.json`: kết quả kiểm thử cần giữ.
- `reporter-before-template-path-migration-20260727-164741.db`: backup database,
  không thể tái tạo đơn giản từ mã nguồn.
- `default-heading-alignment-30-assets.docx`, `toc-refresh-probe.docx`,
  `Tracking_2_preview_20260727-165514.docx`, `Tracking_2_profile.docx`,
  `Tracking_2_report_20260727-165639.docx`: bản đối chiếu báo cáo cần duyệt riêng.

Script smoke-test có chủ ý giữ workspace nếu thất bại hoặc khi yêu cầu giữ lại.
Sự tồn tại của thư mục không chứng minh rằng nó đã test thành công hay vô giá trị.

## 3. Cache, kết quả thử nghiệm và lịch sử — mức ưu tiên thấp hơn

| Duyệt | Đường dẫn | MiB | Đề xuất |
|---|---|---:|---|
| [ ] | `apps/frontend/test-results` | 0,67 | Có thể dọn kết quả cũ sau khi đã đọc lỗi/trace; không chạy Playwright lúc dọn |
| [ ] | `.ruff_cache` | 0,02 | Cache lint tái tạo được; không đáng ưu tiên vì rất nhỏ |
| [ ] | `logs` | 1,45 | Chỉ chọn log cũ theo retention, giữ log phiên chạy gần nhất và log lỗi chưa xử lý; không xóa thư mục hàng loạt |
| [ ] | `artifacts/review` | 37,07 | PDF/ảnh render QA; giữ DOCX và bằng chứng nghiệm thu, cân nhắc lưu trữ ngoài workspace thay vì xóa |
| [ ] | `artifacts/releases` | 53,19 | Giữ release/checksum/baseline cần rollback; chỉ bỏ bản đã xác minh có bản lưu khác |
| [ ] | `artifacts/benchmarks` | 2,85 | **Ưu tiên giữ**: nguồn chứng minh hiệu năng thực tế; không phải file rác |
| [ ] | `artifacts/soak` | 0,01 | Giữ bằng chứng soak test, dung lượng không đáng kể |
| [ ] | `artifacts/golden-docx` | 0,04 | Chỉ bỏ diff cũ đã giải quyết; không nhầm với golden fixture trong tests |
| [ ] | `artifacts/template-backups` | 1,87 | Backup template heading cũ; cần duyệt riêng, không tự bỏ |
| [ ] | `artifacts/template-pack-fuzz` | <0,01 | Giữ failure/reproducer nếu có; rất nhỏ |
| [ ] | `.__atomic-write22e6d803` | 0,072 | Tên giống tệp ghi tạm, 75.281 byte, sửa cuối 10/08; chưa xác định nội dung/chủ sở hữu, cần so sánh trước |
| [ ] | `.__atomic-writeb721e1dd` | 0,072 | Điều kiện như trên; cùng kích thước không chứng minh cùng nội dung |

`apps/backend/.verification` không có file trong lượt khảo sát; không mang lại
lợi ích dung lượng. `__pycache__` có thể tái tạo nhưng chưa tổng hợp riêng,
không đưa con số ước đoán vào mức tiết kiệm.

## 4. UI/thử nghiệm cũ — chưa được coi là không dùng

| Nhóm | Bằng chứng tham chiếu | Cách xử lý đề xuất |
|---|---|---|
| `apps/frontend/src/features/template-studio-next/` | `App.jsx` vẫn lazy import, có route `?view=template-studio-next` | Hướng thiết kế đã dừng nhưng code còn được gọi; muốn gỡ phải sửa route/link/test rồi build, không xóa thư mục riêng lẻ |
| `docs/template-studio-prototype.html`, `template-studio-enterprise.html`, `template-studio-workbench.html` | `tests/test_template_studio_prototype.py` đọc trực tiếp; test được CI gọi | Giữ hoặc lập task loại bỏ prototype cùng test và tham chiếu CI/tài liệu |
| `docs/template-studio-workbench-v2.html` | `tests/test_template_studio_workbench_v2.py` đọc trực tiếp | Không xóa độc lập |
| `docs/template-studio-workspace-b.html`, `template-studio-b-design-review.html` | Các test `docs/design/workspace-b-*.test.cjs` và kế hoạch Stitch | Có thể chuyển lưu trữ sau khi cập nhật đường dẫn và test; không ưu tiên dung lượng |
| `docs/TEMPLATE_STUDIO_STITCH_PLAN.md`, `docs/skill-drafts/` | Hồ sơ thiết kế/skill; không chứng minh là runtime dependency | Đánh dấu lịch sử thay vì xóa; rà soát link trước nếu muốn chuyển thư mục |

## 5. Danh sách bảo vệ — không dọn trong đợt này

- `apps/backend/data/` (**28,55 MiB**): database, WAL/SHM, backup, generated,
  cache và kho `template_studio`. Không phân loại dữ liệu người dùng là file thừa.
  Không xóa riêng WAL/SHM của database đang dùng.
- `apps/backend/templates/` (**5,15 MiB**): template khách hàng đã chốt.
- `apps/backend/samples/`, bộ fixture/golden trong `tests/`, source/frontend/backend.
- `apps/frontend/dist/` (**0,89 MiB**): launcher cần production build;
  xóa có thể lặp lại lỗi “Frontend production build is missing”.
- `apps/backend/.venv/`: launcher/check script dùng Python tại đây.
- `apps/frontend/node_modules/`: cần cho test/build/dev; cài lại tốn thời gian
  và cần nguồn dependency. Không đưa vào đợt dọn an toàn hiện tại.
- `.git/`, lockfile Python/npm, cấu hình CI, setup/start scripts, `.env`.
- `docs/images/`: README đang dùng hình dashboard; không coi là ảnh thừa.
- `artifacts/README.md`: file duy nhất hiện được `git ls-files artifacts` liệt kê.
- Các thay đổi chưa commit và file untracked: chưa commit không có nghĩa là không dùng.

## 6. Checklist thực hiện sau khi người dùng duyệt

1. [ ] Chọn chính xác từng đường dẫn ở mục 2/3; không duyệt bằng wildcard toàn dự án.
2. [ ] Kiểm tra tiến trình đang dùng các bản clone/desktop; không tự tắt tool chính.
3. [ ] Với clone: xem Git status, commit và file untracked bên trong; giữ mọi thay đổi duy nhất.
4. [ ] Với kết quả test: đọc summary, log lỗi; lưu bằng chứng benchmark/release/QA cần thiết.
5. [ ] Ưu tiên chuyển sang nơi lưu trữ ngoài workspace nếu còn nghi ngờ; việc này chỉ
   giảm dung lượng thư mục, không giảm dung lượng ổ đĩa nếu vẫn cùng ổ.
6. [ ] Khi xóa: xác minh đường dẫn tuyệt đối nằm trong mục đã duyệt, tránh reparse point,
   không dùng lệnh xóa rộng ở workspace root. Thông báo khả năng phục hồi thực tế.
7. [ ] Đo lại dung lượng; chạy launcher health check. Nếu gỡ code/prototype, chạy thêm
   frontend tests/build và các test tài liệu liên quan.
8. [ ] Ghi lại danh sách đã xử lý và dung lượng thực tế; không sửa luồng template mặc định.

## 7. Giới hạn rà soát

Đã kiểm kê file/dung lượng và đối chiếu `.gitignore`, launcher, setup/check/release
scripts, CI, App route, test prototype và tài liệu smoke-test. Chưa thực hiện
kiểm toán dead-code toàn dự án, chưa đọc nội dung database/tệp atomic-write,
chưa kiểm tra thay đổi bên trong từng nested clone hoặc tiến trình giữ file.
Vì vậy các mục được gọi là **ứng viên**, không khẳng định tuyệt đối “không dùng”.

Không xóa, di chuyển, sửa mã nguồn, commit hoặc push trong lượt khảo sát này.
