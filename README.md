# 🎵 Music Data Collector v3.5 (Streaming Master & Network Shield Pipeline)

> **Công cụ Thu thập & Xử lý Dữ liệu Âm nhạc Tự động Chuẩn Phòng Thu (Spotify + YTMusic Precision + LRCLIB + 320k MP3 + Cloudflare WARP Shield + Team RBAC + Dashboard UI)**  
> Phục vụ cho Đồ Án Tốt Nghiệp: *Xây dựng Hệ Thống Nghe Nhạc Trực Tuyến*

🌐 **Production Live URL:** [https://musiccollector.kandes.io.vn](https://musiccollector.kandes.io.vn)  
🚀 **CI/CD Pipeline:** GitHub Actions + Oracle Cloud Infrastructure (OCI) Always Free Auto-Deploy

---

## 🌟 Tính Năng Nổi Bật v3.5

1. **Thu thập Metadata Chuẩn từ Spotify API + Free Guest Fallback:** Lấy thông tin bài hát (track), nghệ sĩ (artist), album, ảnh bìa HD, năm phát hành, popularity và tự động chuẩn hóa thể loại (genres) — có sẵn fallback `FreeSpotify` không bị chặn 403 khi dùng tài khoản Free.
2. **YTMusic Precision Matcher & In-process Downloader (320kbps):**
   - Lọc chỉ lấy bản thu âm phòng thu chính thức (Official Studio Audio/Album Track), loại bỏ các video ca nhạc có tiếng thoại mở đầu/kết thúc (MV dialogue), bản hát live, fan cover, remix.
   - Thuật toán so khớp thời lượng ($\le 2$ giây), tên bài hát và nghệ sĩ chính xác.
   - Tốc độ tải vượt trội: **3 – 6 giây / bài** với bitrate cao nhất **320 kbps MP3**.
3. **Tự động Lấy Lời Bài Hát & Lời Karaoke (.lrc) qua LRCLIB:**
   - Tự động xuất file lời đồng bộ `.lrc` từng mili-giây đặt cạnh file MP3 (phục vụ tính năng Karaoke chạy chữ theo nhạc trên Web App).
   - Nhúng lời bài hát dạng văn bản vào thẻ `USLT` trong file MP3.
4. **🛡️ Network Shield & Ẩn IP Datacenter (Anti-Detection Architecture):**
   - **Cloudflare WARP Anycast SOCKS5 Gateway (127.0.0.1:40000):** Định tuyến toàn bộ lưu lượng tải qua mạng Anycast của Cloudflare (`104.28.x.x`), ẩn hoàn toàn IP Datacenter Oracle (`158.178.247.33`).
   - **Browser & TLS Fingerprint Spoofing (`FingerprintGenerator`):** Tự động sinh `User-Agent`, `Sec-CH-UA`, `Sec-CH-UA-Platform` và `Accept-Language` chuẩn Windows 11 Desktop thật.
   - **Multi-Strategy Proxy Rotation (`ProxyManager`):** Hỗ trợ 4 chiến lược xoay vòng (Round-Robin, Lowest-Latency, Failover-Only, Random) và tự động cách ly (Auto-Quarantine) proxy chết.
5. **🍪 Kho Cookies Pool Tập Trung & Cơ Chế Kiểm Tra Chủ Động (Active Probe):**
   - Lưu trữ cookies Netscape vĩnh viễn trong MongoDB (`db.cookie_pool`).
   - Tự động thẩm định sống/chết trực tiếp trước khi báo lỗi, loại bỏ hoàn toàn các cảnh báo nhầm khi gặp video bị thử nghiệm GVS PO-Token của YouTube.
6. **👥 Quản Trị Nhóm, Phân Quyền (RBAC) & Bảng Đóng Góp:**
   - Phân cấp 3 vai trò: `Admin`, `Collector`, `Viewer`.
   - Bảng xếp hạng đóng góp (Leaderboard) theo thời gian thực và nhật ký kiểm toán (Audit Logs).
7. **❓ Hướng Dẫn Hệ Thống Tương Tác:** Popup hướng dẫn từng bước lấy Spotify API keys, cookie SP_DC, cookie YouTube, Proxy và vận hành hệ thống.
8. **Master Audio Post-Processing & Crash-Safe Recovery:**
   - Kiểm tra tính toàn vẹn file MP3 và nhúng toàn bộ thẻ ID3v2.3 (APIC HD, USLT, TRCK, TPE2, TCON) qua `mutagen`.
   - SQLite SessionManager lưu checkpoint từng bài hát.

---

## 🏗️ Cấu Trúc Thư Mục

```
music-data-collector/
├── config/
│   ├── .env.example             # Template cấu hình môi trường
│   ├── settings.py              # Central config
│   ├── playlists.json           # Danh sách playlist Spotify được tuyển chọn
│   └── cookies.txt              # File cookie dự phòng (tùy chọn)
├── src/
│   ├── collectors/
│   │   ├── spotify_collector.py # Thu thập metadata từ Spotify API + FreeSpotify Fallback
│   │   ├── lyrics_collector.py  # Lấy lời bài hát đồng bộ .lrc từ LRCLIB
│   │   └── trend_manager.py     # Quản lý nguồn nhạc trending & tuyển chọn
│   ├── downloaders/
│   │   ├── ytmusic_matcher.py   # Bộ so khớp âm thanh chuẩn phòng thu trên YTMusic
│   │   └── download_manager.py  # Bộ điều phối tải audio tốc độ cao (320kbps)
│   ├── processors/
│   │   ├── post_processor.py    # Kiểm tra MP3, nhúng thẻ ID3 tags & xuất file .lrc
│   │   ├── data_cleaner.py      # Chuẩn hóa Unicode NFC, tiêu đề, ngày tháng
│   │   ├── deduplicator.py      # Loại bỏ bài hát trùng lặp
│   │   └── genre_mapper.py      # Chuẩn hóa thể loại âm nhạc
│   ├── storage/
│   │   ├── db_manager.py        # Quản lý Database MongoDB (Tracks, Proxies, Cookies)
│   │   ├── auth_manager.py      # Quản lý xác thực, RBAC & Leaderboard nhóm
│   │   ├── file_manager.py      # Quản lý thư mục & file audio/ảnh/.lrc
│   │   └── export_manager.py    # Xuất JSON, SQL seed & Collection Report
│   └── utils/
│       ├── logger.py            # Hệ thống ghi log
│       ├── rate_limiter.py      # Điều tiết tần suất gọi API
│       ├── health_checker.py    # Giám sát tỷ lệ lỗi & auto-pause
│       ├── session_manager.py   # Quản lý checkpoint SQLite crash-safe
│       ├── proxy_manager.py     # Quản lý pool proxy xoay vòng đa chiến lược
│       ├── cookie_checker.py    # Kiểm tra sức khỏe & hạn dùng Netscape cookies
│       ├── warp_controller.py   # Điều khiển Cloudflare WARP SOCKS5 Gateway
│       ├── tailscale_controller.py # Điều khiển Tailscale Mesh Exit Node Gateway
│       └── fingerprint_generator.py # Giả lập dấu vân tay trình duyệt Desktop
├── dashboard/
│   ├── app.py                   # Flask + Socket.IO Server điều khiển Dashboard
│   ├── templates/index.html     # Giao diện HTML Dashboard (Settings, Team, Cookies, Guide)
│   └── static/
│       ├── css/style.css        # Giao diện Glassmorphism Dark Mode
│       └── js/main.js           # Client Socket.IO & Modal controllers
├── scripts/
│   ├── setup_check.py           # Kiểm tra toàn bộ môi trường & công cụ
│   ├── install_warp.py          # Script cài đặt Cloudflare WARP trên OCI
│   ├── install_tailscale.py     # Script cài đặt Tailscale Mesh Daemon trên OCI
│   ├── test_network_shield.py   # Script kiểm thử IP Masking & Fingerprint
│   ├── deploy_to_oci.py         # Script tự động deploy SSH lên OCI Server
│   ├── crawl_metadata.py        # Script cào metadata từ Spotify
│   ├── download_audio.py        # Script tải audio MP3 hàng loạt
│   ├── process_files.py         # Script quét & sửa lỗi file MP3
│   └── export_seed.py           # Script xuất dữ liệu sang seed JSON/SQL
├── data/                        # Thư mục chứa dữ liệu đầu ra
│   ├── audio/                   # File nhạc MP3 theo từng nghệ sĩ
│   ├── images/                  # Ảnh bìa album & avatar nghệ sĩ
│   ├── exports/                 # Dữ liệu xuất (JSON, SQL, Markdown)
│   └── session.db               # Database SQLite lưu checkpoint
├── requirements.txt
├── SYSTEM_DESIGN.md             # Tài liệu thiết kế hệ thống chi tiết v3.5
└── README.md                    # Hướng dẫn sử dụng & cài đặt v3.5
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy

### 1. Cài đặt Python Dependencies

Khuyến nghị sử dụng môi trường ảo (virtualenv):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Cài đặt các công cụ hỗ trợ
```bash
# Tải FFmpeg tự động thông qua spotDL:
spotdl --download-ffmpeg

# (Khuyến nghị cho YouTube 2026) Cài đặt Deno:
# Windows (PowerShell):
winget install DenoLand.Deno
```

### 3. Cấu hình file `.env`
Sao chép `config/.env.example` thành `config/.env` và điền thông tin Spotify API:
```ini
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
COOKIES_FROM_BROWSER=chrome
DB_ENGINE=mongodb
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=music_streaming
```

### 4. Kiểm tra môi trường
Chạy script kiểm tra xem mọi thứ đã sẵn sàng:
```bash
python scripts/setup_check.py
```

---

## 🎮 Cách Vận Hành

### Cách 1: Sử dụng Web Dashboard Trực Quan (Khuyên dùng)
Khởi động giao diện điều khiển trung tâm:
```bash
python dashboard/app.py
```
Mở trình duyệt truy cập: **`http://127.0.0.1:5000`**
- Tại khung **🎯 Custom Crawl Studio**:
  - Chọn chế độ mong muốn: `12 Curated Playlists`, `Nghệ Sĩ / Nhạc Sĩ`, `Album`, `Tìm Kiếm Từ Khóa`, `Custom Spotify URL`.
  - Nhập tên ca sĩ/nhạc sĩ (ví dụ: *Sơn Tùng M-TP, Vũ., Đen Vâu, Trịnh Công Sơn...*) hoặc từ khóa / URL.
  - Chọn thể loại: `V-Pop, Pop, Indie, Ballad, Rock, R&B...`
  - Nhấn **🚀 Crawl Metadata** $\rightarrow$ Hệ thống tự động cào và lọc trùng lặp qua 4 tầng.
- Nhấn **▶ Start Download** để tiến hành tải nhạc nền chất lượng 320kbps + file lời Karaoke `.lrc`.
- Các nút **⏸ Pause**, **⏹ Stop**, **🔄 Retry Failed**, **📦 Export Seed** cho phép bạn kiểm soát hoàn toàn hệ thống.

---

### Cách 2: Sử dụng các CLI Scripts độc lập

#### Bước 1: Thu thập metadata bài hát (Custom Studio v3)
```bash
# 1a. Thu thập từ 12 playlist thể loại mặc định trong config/playlists.json:
python scripts/crawl_metadata.py --mode curated --limit 50

# 1b. Thu thập theo tên Ca sĩ / Nhạc sĩ (Ví dụ: Trịnh Công Sơn, Sơn Tùng M-TP, Vũ.):
python scripts/crawl_metadata.py --mode artist --query "Trinh Cong Son" --genre vpop --limit 20

# 1c. Thu thập theo từ khóa tìm kiếm (Ví dụ: Nhạc Trẻ 2026, Acoustic Chill):
python scripts/crawl_metadata.py --mode search --query "Nhac Tre 2026" --genre vpop --limit 30

# 1d. Thu thập từ một Spotify Playlist URL cụ thể:
python scripts/crawl_metadata.py --mode playlist --query "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M" --limit 50
```

#### Bước 2: Tải file nhạc MP3 (320kbps Studio Quality + Lời Karaoke .lrc)
```bash
# Tải 50 bài hát tiếp theo trong danh sách chờ (Tốc độ ~4-6s/bài):
python scripts/download_audio.py --limit 50 --delay 2.0

# Tải lại các bài hát từng bị lỗi trước đó:
python scripts/download_audio.py --retry-failed --limit 50
```

#### Bước 3: Kiểm tra tính hợp lệ & Nhúng thẻ ID3 Tags
```bash
python scripts/process_files.py --fix-tags --delete-invalid
```

#### Bước 4: Xuất dữ liệu Seed cho Backend dự án chính
```bash
python scripts/export_seed.py --format all
```
Kết quả xuất ra tại `data/exports/`:
- `artists.json`, `albums.json`, `tracks.json`, `genres.json`, `playlists.json`
- `seed_data.sql` (PostgreSQL / Relational database insert statements)
- `COLLECTION_REPORT.md` (Báo cáo tổng hợp số lượng & phân bố thể loại)

---

## 🛡️ Khắc Phục Sự Cố Thường Gặp (Troubleshooting)

1. **Lỗi `403 Forbidden` hoặc `Sign in to confirm you're not a bot` khi tải YouTube:**
   - Đảm bảo bạn đã cài `Deno` (`winget install DenoLand.Deno`).
   - Đảm bảo trong file `.env` đã có `COOKIES_FROM_BROWSER=chrome` (hoặc `edge`/`firefox`) và bạn đã từng đăng nhập YouTube trên trình duyệt đó.
2. **Lỗi Spotify API `Invalid client secret`:**
   - Kiểm tra `SPOTIFY_CLIENT_ID` và `SPOTIFY_CLIENT_SECRET` trong `config/.env`. Đăng ký miễn phí tại [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
3. **Không kết nối được MongoDB:**
   - Đảm bảo MongoDB đang chạy ở `localhost:27017` hoặc cập nhật `MONGO_URI` trong file `.env`. Nếu không có MongoDB, hệ thống vẫn lưu tiến trình qua `data/session.db` (SQLite).
