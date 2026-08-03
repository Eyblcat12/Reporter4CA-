# Chính sách bảo mật

## Báo cáo lỗ hổng

Không tạo public issue nếu thông tin có thể giúp khai thác lỗ hổng hoặc làm lộ dữ
liệu. Hãy gửi báo cáo riêng qua GitHub Security Advisories của repository. Nếu
tính năng đó chưa khả dụng, liên hệ maintainer qua
[GitHub profile](https://github.com/Eyblcat12) và chỉ gửi mô tả tối thiểu để thiết
lập kênh trao đổi riêng.

Báo cáo nên có phiên bản/commit, môi trường, bước tái hiện, ảnh hưởng dự kiến và
proof-of-concept đã loại bỏ dữ liệu nhạy cảm.

## Phạm vi

Reporter Pro là ứng dụng local-first. Maintainer ưu tiên các vấn đề về traversal,
upload độc hại, xử lý template/DOCX, lộ secret, plugin isolation, backup/restore
và truy cập API ngoài localhost.

Không đưa API key, dữ liệu tracking của khách hàng hoặc report thật vào issue,
test fixture hay log đính kèm.
