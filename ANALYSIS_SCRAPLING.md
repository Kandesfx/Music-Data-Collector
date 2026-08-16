# 🔧 Phân tích Công cụ Tăng cường Pipeline — PHIÊN BẢN ĐẦY ĐỦ

> **Ngày:** 2026-08-16  
> **Trạng thái:** Chờ phê duyệt  
> **Mục tiêu:** Đánh giá & đề xuất tất cả công cụ có thể tăng tính ổn định cho pipeline

---

## MỤC LỤC

1. [Bản đồ Rủi ro Pipeline](#1-bản-đồ-rủi-ro-pipeline)
2. [Khảo sát Toàn bộ Công cụ](#2-khảo-sát-toàn-bộ-công-cụ)
3. [Đề xuất Cuối cùng: 4 Biện pháp](#3-đề-xuất-cuối-cùng-4-biện-pháp)
4. [Thay đổi Thiết kế Cụ thể](#4-thay-đổi-thiết-kế-cụ-thể)
5. [Danh sách Files Thay đổi](#5-danh-sách-files-thay-đổi)

---

## 1. Bản đồ Rủi ro Pipeline

Trước khi chọn công cụ, cần xác định **chính xác điểm nào có thể fail** trong pipeline:

```
                    ┌─────────────────────────────────────┐
                    │        PIPELINE OVERVIEW             │
                    └─────────────────────────────────────┘

[Tầng 1] Spotify API ─────────────────────────────── Rủi ro: THẤP
   │  spotipy → REST API → JSON
   │  ⚠ Rate limit ~100 req/30s
   │  ✅ Đã có: SimpleDelay(0.3s)
   │
   ▼
[Tầng 2] spotDL subprocess ──────────────────────── Rủi ro: CAO 🔴
   │  spotDL → yt-dlp → YouTube innertube API
   │  🔴 YouTube anti-bot (403, PO Token)
   │  🔴 Spotify auth thay đổi (2026 Dev Mode)
   │  🔴 spotDL crash/hang → subprocess timeout
   │  🔴 File download bị ngắt giữa chừng
   │
   ▼
[Tầng 2b] yt-dlp fallback ──────────────────────── Rủi ro: TRUNG BÌNH
   │  yt-dlp → YouTube search → download
   │  ⚠ Search sai bài (wrong match)
   │  ⚠ Cookies hết hạn → 403
   │  ⚠ Cần Deno runtime (2026)
   │
   ▼
[Tầng 3] Post-processing ──────────────────────── Rủi ro: THẤP
   │  mutagen → validate → tag → move file
   │  ✅ Local operations, ít fail
   │
   ▼
[Tầng 4] Database (MongoDB) ───────────────────── Rủi ro: THẤP
   │  pymongo → CRUD
   │  ✅ Local DB, stable
   │
   ▼
[Cross-cutting] Pipeline chạy dài ─────────────── Rủi ro: TRUNG BÌNH
      ⚠ Crash giữa chừng → mất tiến trình
      ⚠ Không biết đã download đến đâu
      ⚠ Phải chạy lại từ đầu
```

**Kết luận:** Rủi ro tập trung ở **Tầng 2 (Download)** và **Cross-cutting (Pipeline state)**.

---

## 2. Khảo sát Toàn bộ Công cụ

### 2.1 Công cụ Web Scraping

| Công cụ | Tầng hoạt động | Giúp pipeline? | Lý do |
|---------|---------------|----------------|-------|
| **Scrapling** | HTML/DOM scraping | ❌ Không | Pipeline dùng API, không scrape HTML |
| **Selenium/Playwright** | Browser automation | ❌ Không | yt-dlp không cần browser, dễ bị detect hơn |
| **BeautifulSoup** | HTML parsing | ❌ Không | Không có HTML cần parse |
| **curl_cffi** | TLS fingerprint | ⚠️ Có thể | Giả lập TLS browser, nhưng yt-dlp đã tự xử lý |

### 2.2 Công cụ Download

| Công cụ | Chức năng | Giúp pipeline? | Lý do |
|---------|----------|----------------|-------|
| **aria2c + aria2p** | Multi-segment parallel download | ✅ **CÓ** | yt-dlp hỗ trợ `--external-downloader aria2c`, download nhanh + resume tốt hơn |
| **pypdl** | Pure Python multi-segment download | ⚠️ Không cần | yt-dlp đã có downloader riêng |
| **pysmartdl2** | Smart download với retry | ⚠️ Không cần | Trùng chức năng yt-dlp |

### 2.3 Công cụ Pipeline / Task Queue

| Công cụ | Chức năng | Giúp pipeline? | Lý do |
|---------|----------|----------------|-------|
| **SQLite persistent queue** | Lưu trạng thái download, crash recovery | ✅ **CÓ** | Nếu script crash, biết chính xác đã download đến đâu |
| **Huey** | Lightweight task queue | ⚠️ Quá mức | Cần Redis/SQLite backend, overkill cho dự án này |
| **Celery** | Distributed task queue | ❌ Không | Quá phức tạp, cần RabbitMQ |
| **persist-queue** | Disk-backed queue | ⚠️ Có thể | Nhưng MongoDB đã đủ vai trò này |

### 2.4 Công cụ Anti-Detection

| Công cụ | Chức năng | Giúp pipeline? | Lý do |
|---------|----------|----------------|-------|
| **Deno runtime** | Giải JS signature cho yt-dlp | ✅ **BẮT BUỘC** | YouTube 2026 yêu cầu JS runtime bên ngoài |
| **cookies-from-browser** | Tự động lấy cookies fresh | ✅ **CÓ** | Thay vì export thủ công, luôn fresh |
| **Proxy rotation** | Đổi IP khi bị block | ⚠️ Không cần | Dự án nhỏ, 1 IP + rate limit đủ |

### 2.5 Công cụ Monitoring

| Công cụ | Chức năng | Giúp pipeline? | Lý do |
|---------|----------|----------------|-------|
| **HealthChecker** (tự viết) | Auto-pause khi fail nhiều | ✅ **CÓ** | Tránh waste khi bị block |
| **Prometheus/Grafana** | Monitoring metrics | ❌ Không | Overkill cho dự án ĐATN |

---

## 3. Đề xuất Cuối cùng: 4 Biện pháp

Sau khi khảo sát toàn bộ, đây là **4 biện pháp thực sự có giá trị**, xếp theo ưu tiên:

### ✅ Biện pháp 1: Deno Runtime (BẮT BUỘC)

**Vấn đề giải quyết:** YouTube 2026 chặn yt-dlp nếu không có JS runtime  
**Độ phức tạp:** 🟢 Rất thấp (cài 1 phần mềm)  
**Tác động:** 🟢 Rất cao — không có = 403 error hàng loạt

```
Cài đặt:
  Windows: winget install DenoLand.Deno
  macOS:   brew install deno
  Linux:   curl -fsSL https://deno.land/x/install/install.sh | sh

Không cần cấu hình gì thêm — yt-dlp tự detect và dùng Deno.
```

---

### ✅ Biện pháp 2: Cookies tự động từ Browser

**Vấn đề giải quyết:** File cookies.txt thủ công hết hạn sau vài giờ  
**Độ phức tạp:** 🟢 Thấp (thay 1 config trong yt-dlp)  
**Tác động:** 🟢 Cao — cookies luôn fresh, giảm 403 đáng kể

```python
# TRƯỚC (cookies file tĩnh — dễ hết hạn):
ydl_opts = {"cookiefile": "cookies.txt"}

# SAU (tự động đọc từ browser — luôn fresh):
ydl_opts = {"cookiesfrombrowser": ("chrome",)}
# Hỗ trợ: chrome, edge, firefox, opera, brave, vivaldi
```

**Lưu ý:** Yêu cầu browser (Chrome/Edge/Firefox) đang cài trên máy và user đã đăng nhập YouTube trên browser đó. Giữ file `cookies.txt` làm fallback khi chạy trên server không có browser.

---

### ✅ Biện pháp 3: HealthChecker — Auto-pause thông minh

**Vấn đề giải quyết:** Pipeline cứ chạy khi bị block, fail hàng loạt vô ích  
**Độ phức tạp:** 🟡 Trung bình (1 class mới ~50 dòng)  
**Tác động:** 🟢 Cao — tiết kiệm thời gian, tránh bị block nặng hơn

```
Logic:
  ┌─ Track kết quả 10 bài gần nhất ─┐
  │                                   │
  │  Nếu ≥ 5/10 bài fail liên tiếp:  │
  │    → Pause 10 phút               │
  │    → Log cảnh báo                 │
  │    → Reset counter               │
  │    → Thử lại                      │
  │                                   │
  │  Nếu pause 3 lần liên tiếp:      │
  │    → DỪNG pipeline               │
  │    → Thông báo user kiểm tra      │
  └───────────────────────────────────┘
```

**Class HealthChecker:**

```python
class HealthChecker:
    def __init__(self, fail_threshold=5, window_size=10, max_pauses=3):
        self.fail_threshold = fail_threshold   # 5 lỗi trong 10 bài → pause
        self.window_size = window_size
        self.max_pauses = max_pauses           # Pause 3 lần → dừng hẳn
        self.recent_results = []               # True/False
        self.pause_count = 0
    
    def record(self, success: bool): ...
    def should_pause(self) -> bool: ...
    def should_stop(self) -> bool: ...         # Đã pause quá 3 lần
    def get_status(self) -> dict: ...
```

---

### ✅ Biện pháp 4: Checkpoint/Resume với State File (SQLite)

**Vấn đề giải quyết:** Script crash/tắt máy → mất tiến trình, phải scan lại DB  
**Độ phức tạp:** 🟡 Trung bình (1 module mới ~80 dòng)  
**Tác động:** 🟢 Cao — resume chính xác từ bài cuối cùng, không bỏ sót

**Tại sao cần thêm SQLite khi đã có MongoDB?**

```
MongoDB đã track download_status (pending/completed/failed) → đúng!
NHƯNG:
  - Nếu script crash GIỮA CHỪNG download 1 bài → status vẫn "downloading"
    → Lần sau chạy lại, bài đó bị "kẹt" ở trạng thái downloading mãi mãi
  - Nếu DB disconnect tạm thời → mất khả năng track trạng thái
  - MongoDB là network service → thêm 1 điểm fail

SQLite checkpoint file:
  - File local, không cần server
  - ACID-compliant, crash-safe
  - Lưu: session_id, current_track_index, last_successful_download, timestamp
  - Khi script restart → đọc checkpoint → resume đúng chỗ
  - Backup cho MongoDB, không thay thế
```

**Module SessionManager:**

```python
import sqlite3
from datetime import datetime

class SessionManager:
    """Manage download sessions with crash-safe checkpointing."""
    
    def __init__(self, db_path="data/session.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_tables()
    
    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                status TEXT DEFAULT 'running',
                total_tracks INTEGER,
                completed INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                last_track_id TEXT,
                ended_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS download_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                spotify_id TEXT UNIQUE,
                status TEXT,
                method TEXT,
                file_path TEXT,
                error TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        self.conn.commit()
    
    def start_session(self, total_tracks) -> int:
        """Bắt đầu session mới, trả về session_id."""
        ...
    
    def checkpoint(self, session_id, spotify_id, status, method=None, error=None):
        """Ghi checkpoint sau mỗi bài download (crash-safe)."""
        ...
    
    def get_last_session(self) -> dict:
        """Lấy thông tin session gần nhất (để resume)."""
        ...
    
    def get_downloaded_ids(self, session_id=None) -> set:
        """Lấy danh sách spotify_id đã download thành công → skip khi resume."""
        ...
    
    def end_session(self, session_id):
        """Kết thúc session."""
        ...
```

**Tích hợp vào download_batch:**

```python
def download_batch(self, tracks, ...):
    session = SessionManager()
    
    # Resume: bỏ qua các bài đã download trong session trước
    downloaded = session.get_downloaded_ids()
    remaining = [t for t in tracks if t["spotify_id"] not in downloaded]
    
    sid = session.start_session(total_tracks=len(remaining))
    
    for track in remaining:
        ok, path, method = self.download_track(track)
        # Checkpoint ngay lập tức (crash-safe)
        session.checkpoint(sid, track["spotify_id"], 
                          "completed" if ok else "failed",
                          method=method)
    
    session.end_session(sid)
```

---

## 4. Thay đổi Thiết kế Cụ thể

### Kiến trúc mới (bổ sung 2 module):

```
src/
├── utils/
│   ├── logger.py
│   ├── rate_limiter.py
│   ├── retry_handler.py
│   ├── health_checker.py     ← [MỚI] Auto-pause khi fail nhiều
│   └── session_manager.py    ← [MỚI] Checkpoint/Resume với SQLite
├── downloaders/
│   └── download_manager.py   ← [SỬA] Tích hợp HealthChecker + SessionManager
│                                       + cookies-from-browser
└── ...
```

### Luồng Download mới:

```
download_batch():
  │
  ├── [1] SessionManager.start_session(total_tracks)
  │       └── Tạo session mới trong SQLite
  │
  ├── [2] SessionManager.get_downloaded_ids()
  │       └── Lấy các bài đã download → skip
  │
  ├── [3] Loop mỗi track:
  │   ├── HealthChecker.should_stop()? → DỪNG pipeline
  │   ├── HealthChecker.should_pause()? → Sleep 10 phút
  │   │
  │   ├── download_track(track)
  │   │   ├── spotDL (--cookies-from-browser chrome) ← Ưu tiên
  │   │   ├── spotDL (--cookie-file cookies.txt)     ← Fallback 1
  │   │   └── yt-dlp (cookiesfrombrowser: chrome)    ← Fallback 2
  │   │
  │   ├── HealthChecker.record(success)
  │   └── SessionManager.checkpoint(track_id, status)  ← Crash-safe
  │
  └── [4] SessionManager.end_session()
```

---

### ✅ Biện pháp 5: Proxy Rotation (TÙY CHỌN — Toggle bật/tắt)

**Vấn đề giải quyết:** Khi IP bị YouTube/Spotify tạm block, có thể xoay proxy để tiếp tục  
**Độ phức tạp:** 🟡 Trung bình (1 module mới ~60 dòng)  
**Tác động:** 🟡 Trung bình — hữu ích khi bị block, nhưng dự án nhỏ thường không cần  

**Thiết kế: Toggle ON/OFF qua .env**

```
# config/.env
PROXY_ENABLED=false                    ← Mặc định TẮT
PROXY_LIST=socks5://proxy1:1080,socks5://proxy2:1080
PROXY_ROTATION=round_robin             ← round_robin hoặc random
```

Khi `PROXY_ENABLED=false` → pipeline hoạt động bình thường (trực tiếp, không proxy).  
Khi `PROXY_ENABLED=true` → tự động xoay proxy cho mỗi bài download.

**Hỗ trợ cả yt-dlp lẫn spotDL:**

```python
# yt-dlp: native proxy support
ydl_opts = {"proxy": "socks5://host:port"}

# spotDL: qua flag --proxy
cmd.extend(["--proxy", "socks5://host:port"])
```

**Module ProxyManager:**

```python
from itertools import cycle
import random

class ProxyManager:
    """Quản lý proxy pool, hỗ trợ round-robin & random rotation."""
    
    def __init__(self, proxy_list=None, enabled=False, strategy="round_robin"):
        self.enabled = enabled
        self.strategy = strategy
        self.proxies = proxy_list or []
        self._pool = cycle(self.proxies) if self.proxies else None
        self._fail_counts = {}  # proxy → fail count
    
    def get_proxy(self) -> str | None:
        """Lấy proxy tiếp theo. Return None nếu disabled hoặc không có proxy."""
        if not self.enabled or not self.proxies:
            return None
        
        if self.strategy == "random":
            return random.choice(self.proxies)
        else:  # round_robin
            return next(self._pool)
    
    def report_fail(self, proxy: str):
        """Đánh dấu proxy fail → loại bỏ nếu fail quá 3 lần."""
        self._fail_counts[proxy] = self._fail_counts.get(proxy, 0) + 1
        if self._fail_counts[proxy] >= 3:
            self.proxies.remove(proxy)
            self._pool = cycle(self.proxies)
    
    def report_success(self, proxy: str):
        """Reset fail count khi proxy hoạt động tốt."""
        self._fail_counts[proxy] = 0
    
    @property
    def available_count(self) -> int:
        return len(self.proxies)
```

**Tích hợp vào DownloadManager:**

```python
def download_track(self, track):
    proxy = self.proxy_manager.get_proxy()  # None nếu disabled
    
    # spotDL
    if proxy:
        cmd.extend(["--proxy", proxy])
    
    # yt-dlp fallback
    if proxy:
        ydl_opts["proxy"] = proxy
```

**Nguồn Proxy:**
- **Miễn phí (không khuyến nghị):** Proxy list công khai — chậm, không ổn định, hay bị block sẵn
- **Giá rẻ (khuyến nghị nếu cần):** IPRoyal, Webshare — ~$1-5/tháng cho proxy xoay residential
- **Tự dùng VPN:** Nếu có VPN (NordVPN, ExpressVPN) → dùng SOCKS5 proxy endpoint của VPN

> **Lưu ý:** Đối với dự án ĐATN (download ~1000 bài trong 1 tuần), thường **KHÔNG CẦN proxy**. Chỉ bật khi thực sự bị block liên tục.

---

### ✅ Biện pháp 6: Dashboard UI Giám sát (Flask + WebSocket)

**Vấn đề giải quyết:** User muốn đọc, kiểm soát, nắm bắt hệ thống trực quan  
**Độ phức tạp:** 🟡 Trung bình (1 app Flask nhỏ + 1 trang HTML)  
**Tác động:** 🟢 Cao — trải nghiệm sử dụng tốt hơn nhiều so với CLI thuần

**Tại sao chọn Flask + WebSocket (không phải Streamlit)?**

| | Streamlit | Flask + SocketIO |
|---|---|---|
| Real-time live update | ⚠️ Phải polling, giật lag | ✅ WebSocket, mượt mà |
| Start/Stop/Pause pipeline | ❌ Khó control | ✅ Gửi command qua WS |
| Custom UI design | ❌ Giới hạn | ✅ Full HTML/CSS/JS |
| Phù hợp ĐATN stack (React) | ❌ | ✅ Dễ tích hợp React sau |
| Dependencies | streamlit (~100MB) | flask-socketio (~2MB) |

**Giao diện Dashboard bao gồm:**

```
┌─────────────────────────────────────────────────────────────────┐
│  🎵 Music Data Collector — Dashboard                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 TỔNG QUAN PIPELINE                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 1,234    │ │  856     │ │  123     │ │  45      │          │
│  │ Tổng     │ │ Hoàn thành│ │ Đang chờ │ │ Thất bại │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  📈 TIẾN ĐỘ DOWNLOAD                                           │
│  [████████████████░░░░░░░░] 69% (856/1234)                     │
│  ⏱️ Tốc độ: 12 bài/giờ | ETA: ~4 giờ                          │
│                                                                 │
│  🔄 SESSION HIỆN TẠI                                            │
│  Bắt đầu: 14:30 | Đã download: 45 | Failed: 2 | Method: spotDL│
│  Đang tải: "Ed Sheeran - Perfect"                               │
│  [▶ Start] [⏸ Pause] [⏹ Stop] [🔄 Retry Failed]               │
│                                                                 │
│  🏥 HEALTH STATUS: 🟢 HEALTHY (2/10 fails)                     │
│  🌐 PROXY: ⚪ Disabled | 📍 Direct IP                          │
│                                                                 │
│  📊 PHÂN BỐ GENRE                    📋 LOG GẦN NHẤT           │
│  ┌────────────────────┐              ┌──────────────────────┐  │
│  │ pop     ████ 150   │              │ 14:32 ✅ Perfect     │  │
│  │ rock    ███  120   │              │ 14:31 ✅ Bohemian... │  │
│  │ hiphop  ██   80    │              │ 14:30 ❌ Bad Guy     │  │
│  │ kpop    ██   75    │              │ 14:29 ✅ Dynamite   │  │
│  │ vpop    █    50    │              │ 14:28 ✅ Để Mị...   │  │
│  └────────────────────┘              └──────────────────────┘  │
│                                                                 │
│  💾 DISK: 2.3 GB / 10 GB | 🗄️ DB: Connected | 🍪 Cookies: OK  │
└─────────────────────────────────────────────────────────────────┘
```

**Kiến trúc kỹ thuật:**

```
┌──────────────┐     WebSocket (SocketIO)     ┌──────────────────┐
│  Browser     │◄────────────────────────────►│  Flask Server    │
│  (HTML/JS)   │  - progress_update           │  (app.py)        │
│              │  - log_entry                 │                  │
│              │  - health_status             │  ┌──────────────┐│
│  Actions:    │  - stats_update              │  │ Pipeline     ││
│  start/stop  │                              │  │ Thread       ││
│  pause/resume│  Commands:                   │  │ (background) ││
│  retry_failed│  - start_crawl               │  └──────────────┘│
│  toggle_proxy│  - start_download            │                  │
│              │  - pause/resume              │  ┌──────────────┐│
│              │  - stop                      │  │ SQLite       ││
│              │  - toggle_proxy              │  │ (sessions)   ││
│              │                              │  └──────────────┘│
└──────────────┘                              └──────────────────┘
```

**Module Dashboard:**

```python
# dashboard/app.py

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

class PipelineController:
    """Điều khiển pipeline từ Dashboard."""
    
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.current_track = None
        self.thread = None
    
    def start_crawl(self, playlists):
        """Bắt đầu crawl metadata (chạy background thread)."""
        ...
    
    def start_download(self, limit, delay):
        """Bắt đầu download audio (chạy background thread)."""
        ...
    
    def pause(self): self.is_paused = True
    def resume(self): self.is_paused = False
    def stop(self): self.is_running = False
    
    def emit_progress(self, data):
        """Gửi progress update về Dashboard qua WebSocket."""
        socketio.emit("progress_update", data)
    
    def emit_log(self, message, level="info"):
        """Gửi log entry về Dashboard."""
        socketio.emit("log_entry", {"message": message, "level": level})

# WebSocket event handlers
@socketio.on("start_download")
def handle_start(data):
    controller.start_download(limit=data.get("limit", 50), delay=data.get("delay", 5))

@socketio.on("pause")
def handle_pause():
    controller.pause()

@socketio.on("stop")
def handle_stop():
    controller.stop()

@socketio.on("get_stats")
def handle_stats():
    stats = db.get_statistics()
    emit("stats_update", stats)
```

**API endpoints cho Dashboard:**

| Event (WebSocket) | Hướng | Mô tả |
|---|---|---|
| `start_crawl` | Client → Server | Bắt đầu crawl metadata |
| `start_download` | Client → Server | Bắt đầu download (kèm limit, delay) |
| `pause` / `resume` | Client → Server | Tạm dừng / tiếp tục pipeline |
| `stop` | Client → Server | Dừng hẳn pipeline |
| `retry_failed` | Client → Server | Retry các bài failed |
| `toggle_proxy` | Client → Server | Bật/tắt proxy |
| `get_stats` | Client → Server | Yêu cầu cập nhật thống kê |
| `progress_update` | Server → Client | Tiến độ (current track, %, ETA) |
| `log_entry` | Server → Client | Dòng log mới |
| `health_status` | Server → Client | Trạng thái health check |
| `stats_update` | Server → Client | Thống kê tổng hợp |

**Khởi chạy Dashboard:**

```bash
# Chạy dashboard (thay vì CLI scripts)
python dashboard/app.py
# → Mở browser: http://localhost:5000
```

---

## 5. Danh sách Files Thay đổi (ĐẦY ĐỦ)

### Files MỚI:

| File | Mô tả |
|------|-------|
| `src/utils/health_checker.py` | HealthChecker class — auto-pause/stop |
| `src/utils/session_manager.py` | SessionManager class — SQLite checkpoint/resume |
| `src/utils/proxy_manager.py` | ProxyManager class — proxy rotation toggle ON/OFF |
| `dashboard/app.py` | Flask + SocketIO backend cho dashboard |
| `dashboard/templates/index.html` | Giao diện HTML dashboard |
| `dashboard/static/css/style.css` | Style cho dashboard |
| `dashboard/static/js/main.js` | JS client-side logic + SocketIO |

### Files SỬA:

| File | Thay đổi |
|------|----------|
| `src/downloaders/download_manager.py` | Tích hợp HealthChecker + SessionManager + ProxyManager + cookies-from-browser + emit events cho dashboard |
| `config/settings.py` | Thêm: `COOKIES_FROM_BROWSER`, `PROXY_*`, `HEALTH_*`, `SESSION_DB_PATH`, `DASHBOARD_PORT` |
| `config/.env.example` | Thêm biến mới cho proxy, cookies, dashboard |
| `scripts/setup_check.py` | Thêm kiểm tra Deno runtime |
| `scripts/download_audio.py` | Tích hợp session resume |
| `requirements.txt` | Thêm: `flask-socketio` |
| `SYSTEM_DESIGN.md` | Cập nhật kiến trúc |

### Files KHÔNG thay đổi:
- `src/collectors/spotify_collector.py` — Đã ổn
- `src/processors/*` — Đã ổn
- `src/storage/db_manager.py` — Đã ổn
- `src/storage/file_manager.py` — Đã ổn

---

## 6. Cấu trúc Dự án Hoàn chỉnh (sau khi bổ sung)

```
music-data-collector/
├── SYSTEM_DESIGN.md
├── ANALYSIS_SCRAPLING.md          ← Tài liệu này
├── README.md
├── requirements.txt
├── config/
│   ├── .env.example
│   ├── .env                       ← (gitignored)
│   ├── settings.py
│   ├── playlists.json
│   └── cookies.txt                ← (gitignored, fallback)
├── src/
│   ├── collectors/
│   │   └── spotify_collector.py
│   ├── downloaders/
│   │   └── download_manager.py    ← Tích hợp tất cả biện pháp
│   ├── processors/
│   │   ├── post_processor.py
│   │   ├── data_cleaner.py
│   │   ├── deduplicator.py
│   │   └── genre_mapper.py
│   ├── storage/
│   │   ├── db_manager.py
│   │   ├── file_manager.py
│   │   └── export_manager.py
│   └── utils/
│       ├── logger.py
│       ├── rate_limiter.py
│       ├── retry_handler.py
│       ├── health_checker.py      ← [MỚI]
│       ├── session_manager.py     ← [MỚI]
│       └── proxy_manager.py       ← [MỚI]
├── dashboard/                     ← [MỚI] Web UI
│   ├── app.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── scripts/
│   ├── setup_check.py
│   ├── crawl_metadata.py
│   ├── download_audio.py
│   ├── process_files.py
│   └── export_seed.py
├── data/                          ← (gitignored)
│   ├── audio/
│   ├── images/
│   ├── raw/
│   ├── exports/
│   ├── temp/
│   └── session.db                 ← SQLite checkpoint
└── logs/
```

---

## Tổng kết Quyết định

| # | Biện pháp | Cần cài thêm? | Tác động | Bật/tắt? | Quyết định |
|---|-----------|--------------|----------|----------|------------|
| 1 | **Deno Runtime** | ✅ Cài 1 lần | Hết lỗi 403 YouTube | — | ✅ Làm |
| 2 | **Cookies từ Browser** | ❌ Không | Cookies luôn fresh | Fallback sang file | ✅ Làm |
| 3 | **HealthChecker** | ❌ Tự viết | Auto-pause khi block | Luôn bật | ✅ Làm |
| 4 | **SessionManager** | ❌ SQLite built-in | Resume sau crash | Luôn bật | ✅ Làm |
| 5 | **Proxy Rotation** | ❌ Tự viết | Xoay IP khi bị block | ✅ Toggle ON/OFF | ✅ Làm |
| 6 | **Dashboard UI** | ✅ flask-socketio | Giám sát + điều khiển | — | ✅ Làm |
| — | ~~Scrapling~~ | — | — | — | ❌ Không cần |
| — | ~~Celery/Huey~~ | — | — | — | ❌ Quá mức |

> **Chờ phê duyệt:** Bạn đồng ý toàn bộ **6 biện pháp** trên không? Tôi sẽ triển khai code ngay sau khi được duyệt.
