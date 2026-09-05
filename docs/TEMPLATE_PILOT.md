# Template Studio pilot evidence contract

TS-16 dùng một manifest máy đọc được cho từng template để tách rõ ba khái niệm:

- `draft`: hồ sơ đang thu thập, không đủ điều kiện pilot;
- `ready`: mapping, hai lượt validation, golden, visual, benchmark, recovery và
  quality evidence đều đạt; trạng thái này **chưa cấp quyền tích hợp**;
- `approved`: hồ sơ `ready` đã được người dùng phê duyệt opt-in.

Contract này chỉ kiểm tra offline, không publish, install, activate Template Pack
và không gọi Generate. Legacy Renderer cùng các template mặc định không bị tác động.

## Thành phần bắt buộc

Mỗi manifest pin chính xác pack/template/workspace bằng SHA-256 và revision, gắn
fixture đã ẩn danh, sau đó lưu kết quả của các gate:

1. mapping đúng 100%;
2. baseline run đầu đạt fixture/integrity, có `structuralPassed=false` do chưa có
   baseline và được reviewer phê duyệt đúng artifact;
3. verification run thứ hai có run ID khác, cùng template/workspace/structural
   identity và đạt fixture/integrity/structure;
4. golden diff không có khác biệt ngoài dự kiến và integrity đạt;
5. capability checklist đánh giá split-run token, bookmark, content control,
   header/footer, TOC, numbering, merge ngang/dọc, page/section break, image và
   relationship; mục không tồn tại phải ghi rõ `not_applicable`;
6. visual review pin đúng verification artifact;
7. benchmark có ít nhất 10 trial tương thích, không resource-limited, không dùng
   Legacy Renderer và phủ quy mô fixture;
8. recovery dry-run/rollback và full quality gate đạt;
9. chín evidence file có đường dẫn tương đối và checksum đúng.

Schema chính thức nằm tại
`apps/backend/config/template_pilot/pilot-manifest.schema.json`. File khởi tạo ở
`docs/examples/template-pilot-manifest.example.json` cố ý có trạng thái `draft`
và checksum placeholder, vì vậy chưa thể đạt cho tới khi evidence thật được điền.

## Kiểm tra offline

```powershell
apps\backend\.venv\Scripts\python.exe scripts\validate_template_pilot.py `
  C:\pilot\manifest.json `
  --evidence-root C:\pilot `
  --output C:\pilot\readiness.json
```

Kết quả không chứa nội dung evidence. `ready=true` chỉ xuất hiện khi toàn bộ
blocker được giải quyết. Với `status=ready`, `integrationApproved` vẫn có thể là
`false`; chỉ khi chuyển sang `approved` mới bắt buộc có phê duyệt opt-in.

Validator trên kiểm tra schema, quan hệ giữa các gate, đường dẫn và checksum. Sau
khi validator đạt, chạy evidence-derived preflight để đọc chín record JSON đã pin
và tự đối chiếu giá trị thật thay vì tin cờ `passed` do người vận hành nhập:

```powershell
apps\backend\.venv\Scripts\python.exe scripts\preflight_template_pilot.py `
  C:\pilot\manifest.json `
  --evidence-root C:\pilot `
  --output C:\pilot\preflight.json
```

Preflight đối chiếu revision và coverage mapping; identity của hai lượt
validation; liên kết verification với baseline; golden, feature và visual
artifact; các trial benchmark thô; recovery và quality gate. JSON evidence có
field lặp, số `NaN`/`Infinity`, quá sâu, quá lớn hoặc checksum sai đều bị chặn.

Sau khi có ba hồ sơ độc lập, chạy matrix offline:

```powershell
apps\backend\.venv\Scripts\python.exe scripts\preflight_template_pilot_matrix.py `
  --pilot C:\pilot-full\manifest.json C:\pilot-full `
  --pilot C:\pilot-server\manifest.json C:\pilot-server `
  --pilot C:\pilot-client\manifest.json C:\pilot-client `
  --output C:\pilot-matrix.json
```

Matrix chỉ đạt khi có tối thiểu ba template SHA và structural SHA khác nhau, phủ
`full`, `server_only`, `client_only`, dùng cùng quality-gated commit và hợp lại
chứng minh đủ 12 capability Word. `matrixReady=true` vẫn không publish, install,
activate hay nối pack vào Generate. `integrationApproved=true` chỉ xuất hiện khi
từng manifest đều có trạng thái `approved` với opt-in riêng.

## Quy tắc dữ liệu

- Không commit DOCX, fixture, report hoặc evidence khách hàng.
- Không dùng tên khách hàng trong `pilotId`, đường dẫn hoặc artifact CI.
- Author và reviewer phải là hai người khác nhau theo quy trình local/team.
- Không dùng golden của Legacy Renderer để khẳng định Template Pack khách hàng đạt.
- Nếu template có capability hiện chưa được Profile Renderer hỗ trợ, ghi blocker;
  không đánh dấu `not_applicable` để lách kiểm thử.

TS-16B đã cung cấp preflight và matrix offline. Pilot thực tế vẫn cần tối thiểu ba
template khác cấu trúc do người dùng cho phép sử dụng; fixture, golden, visual,
benchmark và recovery của chúng không được thay bằng evidence tổng hợp.
