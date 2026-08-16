import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

test_code = """
/opt/music-data-collector/.venv/bin/python3 -c "
import yt_dlp
import os

ydl_opts = {
    'format': 'ba/b/bestaudio/best',
    'outtmpl': '/tmp/test_download_fix.%(ext)s',
    'postprocessors': [
        {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }
    ],
    'cookiefile': '/opt/music-data-collector/config/cookies.txt',
    'js_runtimes': {'node': {'path': '/usr/bin/node'}},
    'extractor_args': {
        'youtube': {
            'player_client': ['web', 'mweb']
        }
    },
    'quiet': False
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(['https://www.youtube.com/watch?v=rlWfNB_iS9U'])
    print('DOWNLOAD SUCCEEDED 100%!')
except Exception as e:
    print('Failed with error:', e)
"
"""

ok, out = run_ssh_command(test_code, timeout=60)
