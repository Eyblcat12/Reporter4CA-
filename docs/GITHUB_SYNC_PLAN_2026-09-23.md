# Kế hoạch đồng bộ GitHub — 23/09/2026

Đích duy nhất: `github` → https://github.com/Eyblcat12/Reporter4CA-.git, nhánh main.
Không push origin (GitLab), không force-push, không xóa dữ liệu hay đổi template mặc định.
Baseline trước cập nhật: `41fc19aec4603c4e6a94103cd17aaf3122632f03`.

## Trình tự và điều kiện qua cổng

1. Kiểm kê tracked/untracked, loại data, DB, .env, build, log, báo cáo khách hàng.
   Thêm ignore kho runtime; chỉ stage danh sách source/tài liệu đã rà soát.
2. Sửa E2E mock cho hợp đồng autosave; vẫn bắt buộc save → approve → retire.
   Không hạ assertion để vượt test. Không mở rộng chức năng Studio trong đợt này.
3. Commit backend/frontend tích hợp cùng nhau vì có phụ thuộc API/runtime;
   mô tả chi tiết nội dung, giới hạn và đường rollback trong commit/release notes.
   Commit gate/docs riêng khi phù hợp. Không đổi semantic version để giả là release
   nghiệm thu hoàn chỉnh; các tính năng mới vẫn thuộc Unreleased.
4. Clone commit ứng viên vào thư mục kiểm chứng cách ly. Cài dependencies từ lock
   bằng setup -Development; không copy venv/node_modules/dist/data từ bản đang dùng.
   Chạy backend gate, frontend lint/format/tests/build, E2E và API thật kho tạm.
5. Chỉ push fast-forward khi gate ứng viên đạt. Nếu remote đã đổi, dừng đối chiếu;
   không ghi đè commit người khác. Không push dữ liệu/secret hoặc prototype không liên quan.
6. Đọc SHA từ GitHub sau push, clone từ chính URL GitHub vào thư mục độc lập,
   đối chiếu commit/tree và kiểm thử source nhận được. Ghi rõ cổng nào đã chạy,
   cổng nào chưa chạy, không gán kết quả working tree cho remote.

## Phạm vi bàn giao

- Import Tracking theo định dạng thực; mapping/anchor/validation.
- Profile Renderer + pack selection, thư viện/chuẩn hóa nguồn.
- SQLite editor checkpoint, autosave/restore/retry/retire và regression.
- UI hiện hành; giữ dependency của route so sánh hiện có để source clone build được,
  không quảng bá prototype như luồng production mới.
- Hướng dẫn Studio, báo cáo readiness, checklist và test harness.

## Giới hạn phải công bố

Backup hiện tại chưa bao trọn Studio; chưa nghiệm thu recovery draft hai tab/restart
và mọi template khách hàng. Không thay thế kiểm tra DOCX trong Word. Không gọi lần
đồng bộ source này là đã hoàn thành toàn bộ C01–C15 hoặc enterprise/server readiness.

## Rollback

Giữ SHA trước/sau, không reset cứng thư mục có dữ liệu. Có thể checkout baseline
trong thư mục khác sau khi backup; database Studio mới giữ riêng, không xóa hay
downgrade. Muốn đảo commit trên nhánh chung dùng revert có review và test, không
force-push. `AUTO_REPORT_TEMPLATE_PACKS=0` là cách cô lập API Studio khẩn cấp,
không phải khôi phục dữ liệu và không dùng được cho pack đã chọn.

## Tiến độ

- Commit tính năng: `4653a83` — integration, source library/normalization, editor
  checkpoints, sửa Tracking/mapping, test và tài liệu. Không thay templates/Legacy Renderer.
- Commit dependency: `2144f1d` — pin Vitest 4.1.11 và dependency kiểm thử đi kèm;
  phát hiện khi cài mới, npm audit sau cập nhật có 0 advisory tại thời điểm chạy.
  Nguồn: https://github.com/advisories/GHSA-82fw-gwwq-j7x9.
- Export source `4653a83`: clean-source contract đạt, không có runtime data/.env.
- Clone ứng viên: tạo từ Git bằng `--no-hardlinks`, không copy môi trường hay data.
  Setup -Development dùng Python Windows 3.12.13, cài hash-locked Python dependencies,
  npm ci, chuẩn bị 6 template và production build đều đạt. pip check đạt.
- Clone đã fast-forward lên `2144f1d`, npm ci lại: 134 frontend tests/27 files đạt
  với Vitest 4.1.11; lint, format và production build đạt.
- Launcher `-NoBrowser -ExitAfterReady`: production health/UI/lease đạt.
- E2E cuối trên clone: **7/7 đạt**, gồm 4 API mock và 3 backend thật kho tạm.
  Lượt trước có một ECONNRESET ở proxy test khi mở phiên browser; backend vẫn sống.
  Đã chạy lại toàn suite với test server/kho tạm mới và không tái hiện. Không sửa
  test bằng blind retry hoặc bỏ assertion; chưa kết luận nguyên nhân reset.
- Backend gate trên clone `2144f1d`: **402/402 đạt**, 387,079 giây; Ruff check/format
  và merge boundary đạt. Frontend **134/134**, E2E **7/7** như trên.
- Đã đủ cổng push source; bước kế tiếp là push fast-forward và clone từ URL GitHub
  để kiểm tra SHA/tree cùng smoke tests. Chưa có xác nhận GitHub CI từ tài liệu này.
- Log kiểm chứng được giữ local tại artifacts/verification/github-candidate-20260923/;
  không đưa log runtime hoặc dữ liệu test sinh ra lên GitHub.
