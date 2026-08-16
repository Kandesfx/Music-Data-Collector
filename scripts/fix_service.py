import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

service_update = """
cat <<'EOF' | sudo tee /etc/systemd/system/music-collector.service
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
ExecStart=/opt/music-data-collector/.venv/bin/python dashboard/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart music-collector.service
sleep 3
sudo systemctl status music-collector.service --no-pager
curl -s -I http://127.0.0.1:5000/login
"""

ok, out = run_ssh_command(service_update)
print("Result:", ok)
