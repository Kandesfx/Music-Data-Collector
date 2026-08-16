import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

cookies_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "cookies.txt")
if os.path.exists(cookies_file):
    with open(cookies_file, "r", encoding="utf-8") as f:
        cookies_content = f.read()
else:
    cookies_content = "# Netscape HTTP Cookie File\n"

# Save cookies directly on remote server
save_and_test = f"""
cat <<'EOF' | sudo tee /opt/music-data-collector/config/cookies.txt > /dev/null
{cookies_content.strip()}
EOF
sudo cp /opt/music-data-collector/config/cookies.txt /opt/music-data-collector/data/cookies.txt
sudo chown -R ubuntu:ubuntu /opt/music-data-collector/config /opt/music-data-collector/data

echo "Testing yt-dlp download with uploaded cookies..."
/opt/music-data-collector/.venv/bin/python3 -c "
import yt_dlp
import os

ydl_opts = {{
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/test_song.%(ext)s',
    'postprocessors': [
        {{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }}
    ],
    'cookiefile': '/opt/music-data-collector/config/cookies.txt',
    'quiet': False
}}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(['ytsearch1:KICKCHEEZE Dung Hoi Em On Khong Vina Hard'])
    print('SUCCESS: Track downloaded and extracted to 320k MP3!')
"

sudo systemctl restart music-collector.service
"""

ok, out = run_ssh_command(save_and_test, timeout=60)
