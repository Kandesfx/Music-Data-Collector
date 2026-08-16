"""
Script to automate deployment to Oracle Cloud Infrastructure (OCI) server via SSH.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

SSH_EXE = r"C:\Windows\System32\OpenSSH\ssh.exe"
KEY_PATH = os.path.expanduser(r"~/.ssh/oci_key.pem")
HOST = "158.178.247.33"
USER = "ubuntu"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_ssh_command(cmd_str: str, timeout: int = 180):
    print(f"\n🚀 [OCI SSH] Executing: {cmd_str[:80]}...")
    full_cmd = [
        SSH_EXE,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-i", KEY_PATH,
        f"{USER}@{HOST}",
        cmd_str
    ]
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    output_lines = []
    for line in p.stdout:
        print(line, end="")
        output_lines.append(line)
    p.wait(timeout=timeout)
    if p.returncode != 0:
        print(f"❌ Command exited with code: {p.returncode}")
        return False, "".join(output_lines)
    return True, "".join(output_lines)

def main():
    print("==========================================================")
    print(f"🚀 BẮT ĐẦU TỰ ĐỘNG CÀI ĐẶT MÁY CHỦ ORACLE ({USER}@{HOST})...")
    print("==========================================================")

    # 1. Update OS & Install Dependencies
    setup_commands = """
    set -e
    echo "📦 [1/5] Updating packages and installing FFmpeg, Nginx, Python, Docker..."
    sudo apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-venv ffmpeg nginx git curl sqlite3 build-essential net-tools docker.io docker-compose-v2

    echo "🛡️ [2/5] Configuring Oracle Linux iptables firewall..."
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT || true
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 27017 -j ACCEPT || true

    echo "🍃 [3/5] Starting MongoDB Docker container..."
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo docker run -d --name mongodb --restart unless-stopped -p 27017:27017 -v /var/lib/mongodb/data:/data/db mongo:7.0 || true

    echo "📁 [4/5] Cloning / Updating project from GitHub..."
    sudo mkdir -p /opt/music-data-collector
    sudo chown -R ubuntu:ubuntu /opt/music-data-collector
    if [ ! -d "/opt/music-data-collector/.git" ]; then
        git clone https://github.com/Kandesfx/Music-Data-Collector.git /opt/music-data-collector
    else
        cd /opt/music-data-collector
        git fetch --all
        git reset --hard origin/main
    fi

    echo "⚡ [5/5] Building Python Virtualenv & Service..."
    cd /opt/music-data-collector
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip setuptools wheel
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install gunicorn eventlet

    # Configure Systemd
    cat <<EOF | sudo tee /etc/systemd/system/music-collector.service
[Unit]
Description=Music Data Collector Dashboard Service
After=network.target docker.service

[Service]
User=ubuntu
WorkingDirectory=/opt/music-data-collector
Environment="PATH=/opt/music-data-collector/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUTF8=1"
Environment="PYTHONIOENCODING=utf-8"
Environment="MONGO_URI=mongodb://127.0.0.1:27017/music_streaming"
ExecStart=/opt/music-data-collector/.venv/bin/gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 dashboard.app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable music-collector.service
    sudo systemctl restart music-collector.service

    # Configure Nginx
    cat <<EOF | sudo tee /etc/nginx/sites-available/music-collector
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location /static/ {
        alias /opt/music-data-collector/dashboard/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    location /data/audio/ {
        alias /opt/music-data-collector/data/audio/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \\$host;
        proxy_set_header X-Real-IP \\$remote_addr;
        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\$scheme;
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
    echo "🎉 SERVER DEPLOYED SUCCESSFULLY!"
    echo "Service Status: $(sudo systemctl is-active music-collector.service)"
    echo "MongoDB Status: $(sudo docker ps | grep mongo)"
    echo "=========================================================="
    """

    ok, out = run_ssh_command(setup_commands, timeout=300)
    if ok:
        print("\n🎉 ALL SETUP COMPLETED SUCCESSFULLY!")
    else:
        print("\n❌ Setup encountered errors.")

if __name__ == "__main__":
    main()
