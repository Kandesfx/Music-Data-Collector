import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

cmd = """
/opt/music-data-collector/.venv/bin/pip install -U "yt-dlp[default]" curl_cffi pycryptodomex yt-dlp-ejs
echo "Testing yt-dlp version..."
/opt/music-data-collector/.venv/bin/yt-dlp --version
"""

ok, out = run_ssh_command(cmd, timeout=60)
print("Result:", ok)
