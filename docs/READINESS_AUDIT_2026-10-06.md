# Kiểm định sẵn sàng sử dụng Reporter Pro — 06/10/2026

## Quyết định

**NO-GO cho việc xác nhận toàn bộ tool đã sẵn sàng sử dụng chính thức, và chưa qua điều kiện để chốt kế hoạch nhánh Threat Intelligence / Malware Analysis / MCP.**

Luồng báo cáo hiện có có thể tiếp tục dùng trong phạm vi local/team có người kiểm tra đầu ra. Tuy nhiên, đã tái hiện lỗi mất IoC, gộp sai URL và lỗi sinh báo cáo với URL không hợp lệ. Backup chưa bao trọn dữ liệu Studio; bản source mới nhất và release Windows đang khác baseline. CI xanh không phủ định các phát hiện này.

“Sẵn sàng” trong kiểm định này nghĩa là đáp ứng các tiêu chí nghiệm thu xác định cho Windows local/team và các chức năng đang công bố. Không có một lượt kiểm thử nào chứng minh phần mềm không còn mọi lỗi hoặc an toàn tuyệt đối. Chưa đánh giá vận hành server công cộng, multi-tenant hoặc phân tích mã độc thực tế.

Theo thứ tự người dùng yêu cầu, tài liệu này là kiểm định và danh sách điều kiện cần đóng của bản hiện tại; **không phải kế hoạch triển khai tính năng API/MCP**, không mở nhánh phát triển mới, không sửa nghiệp vụ, commit, push hoặc phát hành.

## 1. Đúng repository, đúng phiên bản

Repository được xác định từ Git remote của dự án Reporter Pro: https://github.com/Eyblcat12/Reporter4CA- . PR `web-security-labs/pull/1` gắn với ngữ cảnh chat thuộc repository khác, không được dùng làm nguồn đánh giá.

| Đối tượng | Phiên bản đã kiểm tra |
|---|---|
| GitHub default branch | `main` |
| SHA remote xác nhận bằng GitHub API và clone độc lập | `faeb5415219c239ae4daa51fd561785e3f729e16` |
| GitHub CI của đúng SHA | [35876650440 — success](https://github.com/Eyblcat12/Reporter4CA-/actions/runs/35876650440) |
| Ba job CI | Backend regression, Frontend test and build, Main workflow E2E: success |
| Release mới nhất | [v2.2.1](https://github.com/Eyblcat12/Reporter4CA-/releases/tag/v2.2.1), công bố 17/08/2026 |
| Commit của gói Windows theo BUNDLE-MANIFEST.json | `3381bf7d8b50a0809dd589d36831b8faaf74ad82` |
| Windows artifact | `reporter-pro-v2.2.1-windows-prebuilt.zip` |
| SHA-256 Windows artifact | `b5542ad5842c2ec7bc147627e305622687b334d7e2e142a5a4d6bc30a683e22d` — khớp SHA256SUMS.txt tải từ release |

Working tree ban đầu có sửa `docs/TEMPLATE_STUDIO_STATUS.md`, cùng tài liệu pilot và skill draft chưa track. Các thay đổi đó được giữ nguyên. Kiểm thử source thực hiện trên clone mới từ GitHub, không lấy chúng làm bằng chứng của bản remote.

## 2. Môi trường và cách kiểm tra

- Windows trên máy hiện tại; Python 3.12.14, Node 25.9.0, npm 11.12.1. Đây là một tổ hợp môi trường, không phải toàn bộ ma trận phiên bản được hỗ trợ.
- Clone GitHub mới và gói Windows giải nén riêng trong `artifacts/verification/readiness-20261006/`.
- Cài Python dependencies bằng lockfile và `--require-hashes`; frontend dùng `npm ci`. Không copy venv, node_modules, dist hoặc dữ liệu khách hàng từ bản đang dùng. Cache download của trình quản lý package có thể được tái sử dụng.
- Backend E2E dùng `serve_studio_test_backend.py` với database, template và Studio trong kho tạm; không kết nối database khách hàng.
- Một số lượt đầu trong sandbox thất bại do Windows chặn CIM, tạo database tạm hoặc đổi tên file tạm của Vitest. Các lỗi môi trường này không được tính là lỗi sản phẩm. Kiểm tra tương ứng được chạy lại với quyền truy cập Windows thông thường và ghi log riêng `*-native.log`.
- Không chạy mẫu mã độc, không đăng ký dịch vụ TI, không upload mẫu hoặc dữ liệu khách hàng.

## 3. Kết quả kiểm chứng

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Clone remote đúng SHA | Đạt | GitHub API, clone `github-source` |
| Source archive boundary | Đạt | Export `git archive`, `validate_clean_source.py` |
| Cài mới source từ lockfile | Đạt | `source-setup.log` |
| Warmup template của source | 6 prepared / 0 deferred | `source-setup.log` |
| Frontend production build | Đạt | `source-setup.log` |
| Python dependency consistency | Đạt | `pip check` |
| Ruff lint/format và merge boundary | Đạt, 130 file đã đúng format | `backend-gate-native.log` |
| Backend gate đầy đủ | 402/402 đạt, 427,466 giây | `backend-gate-native.log` |
| Frontend lint/format | Đạt | `frontend-lint.log`, `frontend-format.log` |
| Frontend unit/component | 134/134, 27 file đạt | `frontend-tests-native.log` |
| E2E Chromium | 8/8 đạt, retries=0; 4 mock + 4 backend thật | `e2e-live.log` |
| Test bổ sung ngoài check.ps1 | 14/14 đạt: 8 publish + 6 workbench prototype | `supplemental-tests.log` |
| Launcher source production | Đạt health/UI readiness và lease; tự dừng sau kiểm tra | `source-launcher-native.log` |
| Release artifact checksum | Khớp | `SHA256SUMS.txt` và hash ZIP |
| Setup gói Windows qua PowerShell -File | Exit 0; có cảnh báo warmup ở đường dẫn dài | `prebuilt-setup-process.log` |
| Launcher gói Windows production | Đạt readiness và lease; tự dừng | `prebuilt-launcher-native.log` |
| npm audit lockfile source | 2 package mức high, đều dev dependency | `source-npm-audit.json` |
| npm audit lockfile release | 4 package: 2 high + 2 moderate, đều dev dependency | `prebuilt-npm-audit.json` |
| OSV querybatch backend runtime lock | 32 package/version, không trả về advisory | `python-osv-queries.json`, `python-osv-results.json` |
| Microsoft Word visual/TOC với mẫu khách hàng | Chưa nghiệm thu trong lượt này | Không suy từ test XML/golden |
| Soak / 3.000 asset và tải lớn | Không chạy lại trong lượt này | Không dùng số liệu cũ như kết quả mới |

Không gán bộ test source mới cho gói release cũ: với release chỉ kiểm chứng download/hash, setup, pip check, launcher và dependency lock; chưa chạy toàn bộ hồi quy hoặc nghiệm thu Word riêng của release.

## 4. Phát hiện đã xác nhận

### R01 — P1: IoC có cấu trúc bị biến thành chuỗi, mất khỏi DOCX Technical

- Vị trí: `apps/backend/core/input_parser.py:234`, đặc biệt dòng 266; API đi qua `_payload_from_rows` ở `api/routes.py:518`.
- Đầu vào tổng hợp: một asset có `extras.iocs = [{type: domain, value: audit-evidence.example, source: synthetic EDR}]`.
- `build_payload_from_rows` giữ danh sách; `normalize_payload` đổi nó thành `str`.
- Technical renderer chỉ xử lý IoC dạng list. Khi đưa payload chưa chuẩn hóa trực tiếp vào renderer, domain xuất hiện; khi đi qua chuỗi chuẩn hóa như API, domain không còn trong DOCX.
- **Tác động:** báo cáo vẫn sinh được nhưng thiếu chỉ dấu đầu vào. Đây là lỗi tính đầy đủ của bằng chứng, không chỉ là phần còn thiếu của ý tưởng MCP tương lai.
- Bằng chứng: `probes-source/probe-results.json`, `technical-structured_direct.docx` và `technical-web_normalized.docx`.
- Điều kiện đóng: giữ kiểu dữ liệu bằng schema rõ ràng cho trường hỗ trợ; kiểm thử import/API → snapshot → Preview → Export → mở lại DOCX, đối chiếu IoC và nguồn. Không khôi phục cấu trúc bằng `eval` chuỗi đầu vào.

### R02 — P1: Backup hiện tại không khôi phục được toàn bộ Template Studio

- Vị trí: `apps/backend/core/workspace_backup.py:29`; các kho Studio được khởi tạo riêng tại `api/routes.py:254`.
- Reproduction tạo một marker workspace trong `data/template_studio`, database chính và một template DOCX. ZIP chỉ có database chính, DOCX và manifest; marker Studio không được đóng gói.
- Phạm vi thiếu bao gồm nguồn Studio, workspace/mapping, catalog/pack, validation history và editor drafts. Test backup hiện có kiểm chứng phạm vi database/template đã định nghĩa, không chứng minh phục hồi toàn Studio.
- **Tác động:** có thể phục hồi backup hiện tại mà vẫn thiếu pack hoặc công việc Studio cần để tiếp tục dự án.
- Đây là giới hạn đã công bố trong README/docs, không phải giả định rằng tác giả đã hứa backup Studio. Tuy nhiên, nó vẫn chặn nghiệm thu toàn bộ sản phẩm có Studio.
- Điều kiện đóng: backup nhất quán mọi kho trong phạm vi hỗ trợ; restore sang thư mục/máy sạch; mở lại draft, pack và tạo lại báo cáo. Kiểm thử rollback khi đĩa/lưu trữ lỗi. Nếu chưa hỗ trợ, phải có phạm vi bàn giao giới hạn rõ và cơ chế sao lưu Studio đã kiểm chứng.

### R03 — P2: Chuẩn hóa IoC làm sai dữ liệu hoặc để lỗi đầu vào đến lúc sinh báo cáo

- Vị trí: `apps/backend/core/threat_intelligence.py:25` và `:51`; readiness check trong `core/incident_validation.py`.
- `https://example.com/Payload` và `https://example.com/payload` bị gộp thành một vì khóa dedup lowercase toàn URL. Path có thể phân biệt hoa/thường, nên không được mặc định coi chúng là cùng chỉ dấu.
- `https://example.com:bad/path` qua readiness check IR với `valid=True`, nhưng `normalize_iocs` ném `ValueError` khi đọc `parsed.port`. Đã gọi `generate_report` loại IR và tái hiện lỗi tại dòng chuẩn hóa IoC.
- **Tác động:** mất phân biệt chỉ dấu hoặc thất bại tạo báo cáo sau khi UI/backend đã báo sẵn sàng.
- Bằng chứng: `probes-source/probe-results.json`, `invalid-url-report.log`.
- Điều kiện đóng: canonicalize theo từng loại; giữ nguyên semantics path/query; URL sai phải thành lỗi validation có vị trí, không exception ngoài dự kiến. Bao phủ port sai, IPv6, fragment/query, domain/file name và nguồn của bản ghi trùng.

### R04 — Giới hạn sản phẩm: Báo cáo mặc định vẫn cần hoàn thiện điều tra/IoC thủ công

- `core/report_generator.py:1856` chèn “Nội dung phân tích điều tra do người thực hiện bổ sung.”
- `core/report_generator.py:1926` tạo bảng IoC trống cho renderer mặc định Full/Server/Client.
- Probe Full với IoC dạng list hợp lệ vẫn không có domain đầu vào và có placeholder điều tra.
- Đây là hành vi hiện tại, không gọi toàn bộ chức năng malware chưa được xây dựng là regression. Nhưng không thể nghiệm thu sản phẩm như một hệ thống tự hoàn thiện báo cáo an ninh đầu cuối.
- Điều kiện đóng: chốt rõ nội dung tự động và nội dung cần analyst bổ sung; kiểm tra trước xuất để người dùng thấy phần chưa hoàn thiện. Tách việc sửa mất dữ liệu đã hỗ trợ khỏi việc phát triển phân tích malware mới.

### R05 — P2: Dependency phát triển cần cập nhật hoặc có quyết định chấp nhận rủi ro

- Source: `brace-expansion@5.0.9` và `source-map-js@1.2.1`, lockfile đánh dấu `dev: true`.
- Release: ngoài hai package trên còn `vitest` và `@vitest/mocker` ở dải bị ảnh hưởng bởi advisory đã được sửa trên main.
- npm đếm package bị ảnh hưởng, không phải số CVE độc lập. Vitest và mocker liên quan cùng advisory.
- Advisory tham chiếu: [brace-expansion recursion](https://github.com/advisories/GHSA-qhr7-859c-m2p7), [source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q), [Vitest mocker](https://github.com/advisories/GHSA-82fw-gwwq-j7x9). JSON lưu đầy đủ các advisory trả về.
- **Phạm vi:** phát triển/build/test; chưa có bằng chứng các advisory này khai thác được từ giao diện production đóng gói. Không trình bày chúng như RCE đã xác nhận của Reporter.
- Điều kiện đóng: cập nhật tối thiểu lockfile, chạy lại build/test và audit; xác định khả năng tiếp cận của advisory tồn dư. Không chạy `npm audit fix --force` không kiểm soát.
- OSV không có kết quả cho 32 runtime dependency chỉ có nghĩa không tìm được advisory tương ứng lúc truy vấn; không chứng minh backend không có lỗ hổng.

### R06 — Khoảng trống gate: CI xanh chưa bao phủ những điều kiện bàn giao quan trọng

- CI E2E không khởi chạy backend tạm hoặc đặt `REPORTER_LIVE_API` / `REPORTER_STUDIO_TEST_API`. Bốn E2E backend thật có `test.skip` khi thiếu các biến này. Lượt kiểm định này đã bật chúng và 8/8 test toàn suite đạt.
- `scripts/check.ps1` liệt kê tường minh các module nhưng bỏ `test_template_pack_publish` và `test_template_studio_workbench_v2`. Đã chạy bổ sung 14 test, đạt.
- `test_excel.py` và `test_integration.py` là script thủ công với file/port giả định; không coi chúng là unit test bị lỗi vì không đưa vào gate.
- Backend đã có unit test restart, mất response, idempotency và hai writer cho draft. Chưa có nghiệm thu trình duyệt đầy đủ cho reload/restart/hai tab xung đột và chọn bản phục hồi. Không biến khoảng trống kiểm chứng thành kết luận đã xảy ra mất draft.
- Chưa xác minh thực tế trong Microsoft Word các bảng dài, ngắt trang, TOC, số trang, header/footer và template khách hàng; golden XML không thay thế việc này.
- Điều kiện đóng: gate live E2E tự động, đưa test publish vào gate, bổ sung kịch bản recovery đầu cuối; có hồ sơ nghiệm thu Word và workload đại diện.

### R07 — Release và source chưa cùng baseline bàn giao

- Main đã có thay đổi sau `v2.2.1`, bao gồm Studio và cập nhật test dependency; release Windows mới nhất vẫn gắn commit `3381bf7`.
- Source và frontend vẫn khai báo version 2.2.1; CHANGELOG để thay đổi mới ở Unreleased. Điều này được tài liệu hóa, không phải bằng chứng release bị hỏng.
- **Tác động:** người clone main và người tải release nhận khác tính năng/sửa lỗi dù dễ nhìn thấy cùng số version. Không thể dùng kết quả của main chứng nhận toàn bộ gói tải hiện tại.
- Điều kiện đóng: chọn commit baseline đã nghiệm thu; phát hành version/tag/artifact/checksum tương ứng; kiểm tra cài mới, nâng cấp dữ liệu, backup/restore và rollback; release notes mô tả đúng phạm vi.

### R08 — Quan sát vận hành: warmup cache release cũ thất bại ở đường dẫn Windows dài

- Trong thư mục audit lồng sâu, warmup prebuilt trả 0 prepared / 6 deferred, lỗi `FileNotFoundError` tại tên file tạm dài trong `prepared_template.py`.
- Setup qua đúng cơ chế PowerShell -File vẫn exit 0; launcher production đạt readiness. Không gọi đây là cài đặt thất bại. Lượt wrapper ban đầu bắt `$LASTEXITCODE` từ bước warmup nội bộ đã được đối chiếu lại bằng process exit thực.
- Main warmup 6/6 đạt tại đường dẫn clone kiểm tra; code main đã rút ngắn tên file tạm. Chưa đánh giá toàn bộ ranh giới độ dài path hoặc đo hiệu năng fallback của release.
- Cần đưa đường dẫn có khoảng trắng/đường dẫn dài vào kiểm thử gói Windows mới.

## 5. Điều kiện mở nhánh tính năng lớn

Đây là các gate của baseline hiện tại, chưa phải backlog triển khai API/MCP.

| Gate | Công việc | Điều kiện chấp nhận |
|---|---|---|
| G1 — Tính toàn vẹn báo cáo | Đóng R01/R03, chốt phạm vi R04 | Không mất/đổi IoC; lỗi đầu vào bị chặn đúng vị trí; Preview/Export cùng dữ liệu; nội dung cần bổ sung được thể hiện rõ |
| G2 — Phục hồi dữ liệu | Đóng R02 và nghiệm thu recovery của R06 | Restore sang workspace sạch phục hồi đủ chức năng đã cam kết; không mất draft khi reload/hai tab; rollback không hỏng kho |
| G3 — Chất lượng và dependency | Xử lý R05/R06 | Static checks, unit, integration, live E2E tự động đạt; advisory tồn dư được phân loại và quyết định rõ |
| G4 — Nghiệm thu đầu ra | Word và workload thực tế | Đối chiếu số asset/finding/IoC, nguồn, TOC, số trang và layout trên bộ dữ liệu đại diện; tải được giới hạn theo mức đã kiểm chứng |
| G5 — Bàn giao tái lập | Đóng R07, kiểm tra R08 | Release mới đúng commit/tag; cài sạch và nâng cấp đạt; checksum, release notes và rollback đầy đủ |

Thứ tự thực hiện đề nghị: G1 → G2 → G3 → G4 → G5. Không cần chờ làm xong tính năng malware/API để sửa các lỗi đúng đắn dữ liệu đang tồn tại.

Chỉ sau khi các gate đạt hoặc người dùng chủ động thu hẹp phạm vi nghiệm thu, mới lập và chốt kế hoạch chi tiết cho nhánh mới. Hồ sơ nhánh mới khi đó cần xác định ranh giới tin cậy, schema bằng chứng, adapter API và quota, cache/snapshot, bảo vệ API key, MCP/VM, quyền thao tác, đánh giá chất lượng suy luận, rollout theo feature flag và điều kiện merge/rollback. Các hạng mục này chưa được thiết kế hoặc triển khai trong lượt kiểm định.

## 6. Hồ sơ kiểm chứng và giới hạn

- Log, ZIP, clone và probe: `artifacts/verification/readiness-20261006/` — artifact local được ignore, không đưa lên GitHub.
- Probe độc lập: `probe_readiness.py`; chỉ dùng dữ liệu giả, lưu các DOCX đối chứng và JSON kết quả.
- GitHub CI evidence: `github-ci-jobs.json`; release metadata: `github-latest-release.json`.
- Các server do lượt kiểm định tạo trên 8000/8011/4173 đã được dừng; đã kiểm tra không còn listener trên ba cổng này.
- Chưa thực hiện penetration test toàn diện, kiểm toán toàn lịch sử Git/secret, chứng nhận khách hàng, nghiệm thu phân tích malware hoặc đo hiệu năng dài hạn. Quét pattern secret giới hạn trong source/script/workflow không phát hiện match, nhưng không thay thế secret scanning đầy đủ.
- Không có thay đổi mã nghiệp vụ, template khách hàng hay cấu hình hoạt động của workspace chính. Chỉ thêm báo cáo kiểm định và artifact thử nghiệm độc lập.
