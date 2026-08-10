# Formatter và Static Analysis

> **Trạng thái:** Đã triển khai baseline ngày 2026-08-10. Ruff, ESLint và Prettier
> hiện là quality gate bắt buộc trong local check, GitHub Actions và GitLab CI.

## Mục tiêu

Thiết lập Ruff cho Python và ESLint/Prettier cho React mà không thay đổi hành vi
report engine, không format file sinh tự động và không tạo một commit khổng lồ khó
review. Baseline đầu tiên chỉ bật nhóm rule có tín hiệu cao; các nhóm modernization
`UP`, `B`, `SIM` tiếp tục được giữ cho một đợt review riêng.

## Phạm vi đề xuất

### Python — Ruff

- Pin Ruff trong dependency development lock.
- Cấu hình trong `pyproject.toml`, target Python 3.12, line length 100.
- Giai đoạn đầu chặn `E4`, `E7`, `E9`, `F` và `I`: syntax, import sai/không dùng,
  biến không tồn tại và thứ tự import.
- Sau khi baseline sạch mới bật `UP`, `B`, `SIM`; review thủ công mọi autofix có
  thể thay đổi control flow.
- Chạy trên `apps/backend`, `scripts` và `tests`; loại trừ `.venv`, artifact,
  cache, generated report/template và lockfile.

### Frontend — ESLint và Prettier

- Dùng ESLint flat config, `eslint-plugin-react-hooks` và rule phù hợp React 18.
- Bật lỗi cho hook dependency, biến/import không dùng và code không thể chạy tới.
- Prettier chỉ quản lý định dạng; dự kiến single quote, dấu chấm phẩy, trailing
  comma và line width 100 để gần style hiện tại.
- Chạy trên `src`, test, Vite config và Playwright config; loại trừ `dist`,
  `node_modules`, report test, snapshot và file sinh tự động.

## Trình tự triển khai an toàn

1. **Audit không chặn CI:** cài tool đã pin, chạy read-only và lưu thống kê lỗi
   theo nhóm; không sửa code trong bước này.
2. **Cấu hình tối thiểu:** chỉ bật rule chắc chắn là lỗi; thêm lệnh `lint`,
   `format:check` và `format`.
3. **Commit format cơ học riêng:** format Python/frontend trong hai commit tách
   biệt, không trộn sửa logic để giữ khả năng review và blame.
4. **Sửa static finding theo nhóm:** import/unused trước, React hooks sau, rồi mới
   tới modernization. Mỗi nhóm chạy backend, frontend và production build.
5. **Bật CI bắt buộc:** Ruff check/format check, ESLint và Prettier check phải đạt
   trước test/build; developer có cùng lệnh trong `scripts/check.ps1`.
6. **Ngăn tái phát:** tài liệu contributor, editor config và pre-commit tùy chọn;
   CI vẫn là nguồn quyết định, không bắt buộc developer cài Git hook.

## Ảnh hưởng và kiểm soát rủi ro

| Thay đổi | Lợi ích | Rủi ro | Kiểm soát |
|---|---|---|---|
| Ruff format/import | Python đồng nhất, giảm import thừa | Diff lớn, xung đột branch | Commit format riêng, triển khai khi branch ít thay đổi |
| Ruff bug rules | Bắt undefined name và lỗi control flow | Một số false positive trong mock/plugin | Exclude hẹp, ignore theo dòng có giải thích |
| React Hooks lint | Bắt closure/dependency stale | Có thể làm lộ bug và buộc refactor hook | Sửa từng hook, bổ sung recovery/race tests |
| Prettier | JSX/CSS dễ review | Thay đổi nhiều dòng không liên quan | Chỉ format source, bỏ generated/snapshot |
| CI enforcement | Không tái phát nợ style | Pipeline tăng thời gian | Cache dependency, lint chạy trước test nặng |

Không bật `--fix` mù cho rule bảo mật, exception handling hoặc boolean/control-flow.
DOCX, CSV fixture, golden snapshot, dependency lock và release checksum không được
formatter chỉnh sửa.

## Điều kiện hoàn thành

- Ruff, ESLint và Prettier đều được pin và tái lập qua lockfile.
- `scripts/check.ps1`, GitHub Actions và GitLab CI dùng cùng rule/config.
- Không còn lint error; warning còn lại phải có lý do và owner xử lý.
- 100% backend/frontend tests, E2E và production build đạt sau commit format.
- Golden DOCX không thay đổi ngoài ý muốn và benchmark Preview không regression
  quá 5% P50/P95 nếu có sửa logic theo lint.

## Kết quả baseline

- Ruff audit ban đầu: 108 finding; đã xử lý toàn bộ bằng safe fix và review thủ công
  hai finding còn lại.
- Ruff format: 60 file được chuẩn hóa, không chạm DOCX/CSV/golden/lockfile.
- ESLint audit sau khi giới hạn rule đúng phạm vi: 21 finding; đã xử lý toàn bộ.
- Prettier: chuẩn hóa 65 file frontend; `npm audit --audit-level=moderate` không
  phát hiện vulnerability trong toàn bộ dependency tree.
- Các rule React compiler nâng cao như `set-state-in-effect` và `static-components`
  chưa được bật bắt buộc; chúng cần refactor UX riêng và test race/recovery tương ứng.
