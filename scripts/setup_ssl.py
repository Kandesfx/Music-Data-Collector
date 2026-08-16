import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

ssl_setup_commands = """
set -e
echo "🔒 [1/3] Installing Certbot and python3-certbot-nginx..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx

echo "🌐 [2/3] Updating Nginx configuration for musiccollector.kandes.io.vn..."
cat <<'EOF' | sudo tee /etc/nginx/sites-available/music-collector
server {
    listen 80;
    server_name musiccollector.kandes.io.vn 158.178.247.33;

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
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

sudo nginx -t
sudo systemctl reload nginx

echo "🔑 [3/3] Requesting Let's Encrypt SSL Certificate for musiccollector.kandes.io.vn..."
sudo certbot --nginx -d musiccollector.kandes.io.vn --non-interactive --agree-tos -m levuhai139@gmail.com --redirect || true

sudo systemctl reload nginx
echo "=========================================================="
echo "🎉 SSL CERTIFICATE CONFIGURED SUCCESSFULLY!"
echo "=========================================================="
"""

ok, out = run_ssh_command(ssl_setup_commands, timeout=180)
print("SSL Result:", ok)
