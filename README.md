# 🐢 Boring Grinder Funding Bot

Telegram bot tự động fetch và tổng hợp thông tin funding rounds trong crypto.

## Tính năng
- Tự động gửi báo cáo lúc **8:00 sáng** và **8:00 tối** (GMT+7)
- Lệnh `/funding` để fetch thủ công bất kỳ lúc nào
- Tổng hợp từ nhiều nguồn: RootData, Cryptorank, The Block, DLNews
- Đánh giá mức độ ưu tiên farm tự động (High/Medium/Low)
- Gợi ý hướng farm airdrop cho từng dự án

## Thông tin mỗi dự án
- Tên, số tiền gọi vốn, vòng gọi vốn, quỹ đầu tư, ngày
- Lĩnh vực và mô tả sản phẩm
- Trạng thái token (pre-launch hay đã có)
- Giai đoạn (Mainnet/Testnet)
- Mức độ ưu tiên farm + gợi ý cụ thể
- Links: Website, X/Twitter

## Setup

### Bước 1: Telegram
1. Tìm @BotFather trên Telegram
2. Nhắn `/newbot` và làm theo hướng dẫn
3. Copy **BOT_TOKEN** được cấp
4. Tìm @userinfobot → nhắn `/start` → copy **CHAT_ID**

### Bước 2: GitHub
1. Đăng ký tại github.com
2. Tạo repository mới tên `boring-grinder-bot`
3. Upload toàn bộ files trong thư mục này lên

### Bước 3: Railway
1. Đăng ký tại railway.app bằng tài khoản GitHub
2. Tạo project mới → chọn "Deploy from GitHub repo"
3. Chọn repo `boring-grinder-bot`
4. Vào tab **Variables**, thêm:
   - `BOT_TOKEN` = token từ BotFather
   - `CHAT_ID` = ID từ userinfobot
5. Deploy!

## Lệnh bot
- `/start` — Giới thiệu bot
- `/funding` — Fetch funding news ngay lập tức
- `/help` — Hướng dẫn sử dụng
