import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

spotdl_test = """
rm -rf /tmp/test_spotdl
mkdir -p /tmp/test_spotdl
/opt/music-data-collector/.venv/bin/spotdl download "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT" --output /tmp/test_spotdl/ --format mp3 --cookie-file /opt/music-data-collector/config/cookies.txt
ls -lh /tmp/test_spotdl/
"""

ok, out = run_ssh_command(spotdl_test, timeout=60)
print("SpotDL test result:", ok)
