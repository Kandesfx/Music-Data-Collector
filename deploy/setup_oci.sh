#!/usr/bin/env bash
# ==============================================================================
# Music Data Collector & Streaming Platform - 1-Click OCI Setup Script
# Target OS: Ubuntu 22.04 / 24.04 LTS (ARM64 / x86_64) on Oracle Cloud Infrastructure
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 BẮT ĐẦU CẤU HÌNH TỰ ĐỘNG MÁY CHỦ ORACLE CLOUD (OCI)..."
echo "=========================================================="

# 1. Update system packages
echo "📦 [1/6] Cập nhật hệ điều hành và cài đặt các gói phụ thuộc..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    nginx \
    git \
    curl \
    sqlite3 \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    pkg-config

# 2. Configure Oracle Cloud Ubuntu Firewall (iptables / ufw) to allow Ports 80, 443, 5000
echo "🛡️ [2/6] Mở cổng tường lửa máy chủ (Ports: 80 HTTP, 443 HTTPS, 5000 API)..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT || true
sudo netfilter-persistent save || true

# 3. Create Project Directory & Virtualenv
PROJECT_DIR="/opt/music-data-collector"
echo "📁 [3/6] Thiết lập thư mục dự án tại: $PROJECT_DIR..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown -R $USER:$USER "$PROJECT_DIR"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "🐍 Tạo Python Virtual Environment (.venv)..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# 4. Install Python Dependencies
echo "⚡ [4/6] Cài đặt các thư viện Python (Gunicorn, Eventlet, Flask-SocketIO, yt-dlp, SpotDL)..."
source "$PROJECT_DIR/.venv/bin/activate"
pip install --upgrade pip setuptools wheel
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
fi
pip install gunicorn eventlet mutagen yt-dlp spotdl requests pymongo bcrypt pyjwt

# 5. Configure Systemd Service
echo "⚙️ [5/6] Cấu hình Systemd Service để chạy ngầm và tự khởi động lại..."
cat <<EOF | sudo tee /etc/systemd/system/music-collector.service
[Unit]
Description=Music Data Collector & Streaming Dashboard Service
After=network.target docker.service

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUTF8=1"
Environment="PYTHONIOENCODING=utf-8"
Environment="MONGO_URI=mongodb://127.0.0.1:27017/music_streaming"
ExecStart=$PROJECT_DIR/.venv/bin/python dashboard/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable music-collector.service
sudo systemctl restart music-collector.service

# 6. Configure Nginx Reverse Proxy
echo "🌐 [6/6] Cấu hình Nginx Reverse Proxy (WebSocket + Audio Stream)..."
cat <<EOF | sudo tee /etc/nginx/sites-available/music-collector
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    # Static Assets Fast Serving
    location /static/ {
        alias $PROJECT_DIR/dashboard/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # Audio Chunks Stream Direct
    location /data/audio/ {
        alias $PROJECT_DIR/data/audio/;
        mp4;
        mp4_buffer_size 1m;
        mp4_max_buffer_size 5m;
        expires 30d;
    }

    # Reverse Proxy to Flask App
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/music-collector /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

echo "=========================================================="
echo "🎉 HOÀN TẤT THIẾT LẬP MÁY CHỦ ORACLE CLOUD THÀNH CÔNG!"
echo "👉 Trạng thái Service: $(sudo systemctl is-active music-collector.service)"
echo "👉 Bạn có thể truy cập qua IP Public máy chủ OCI: http://$(curl -s ifconfig.me)"
echo "=========================================================="
