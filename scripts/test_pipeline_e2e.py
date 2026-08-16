import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

pipeline_test = """
cd /opt/music-data-collector
/opt/music-data-collector/.venv/bin/python3 -c "
from src.downloaders.download_manager import DownloadManager
from pathlib import Path

dm = DownloadManager()
test_track = {
    'spotify_id': '4cOdK2wGLETKBW3PvgPWqT',
    'title': 'Never Gonna Give You Up',
    'artist': 'Rick Astley',
    'album': 'Whenever You Need Somebody',
    'duration_ms': 213000,
    'spotify_url': 'https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT',
    'preview_url': None
}

ok, final_track, err = dm.download_track(test_track)
print('PIPELINE DOWNLOAD SUCCESS:', ok)
print('FINAL TRACK:', final_track.get('local_path') if final_track else None)
print('ERROR IF ANY:', err)
"
"""

ok, out = run_ssh_command(pipeline_test, timeout=90)
print("Pipeline test result:", ok)
