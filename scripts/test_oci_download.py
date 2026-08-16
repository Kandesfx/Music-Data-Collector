import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

test_script = """
/opt/music-data-collector/.venv/bin/python3 -c "
import yt_dlp
import os

clients_to_test = [
    ['ios'],
    ['android'],
    ['android_creator'],
    ['mweb'],
    ['tv_embedded'],
    ['android', 'ios']
]

for c in clients_to_test:
    print(f'Testing player_client: {c}')
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/test_{c[0]}.%(ext)s',
        'extractor_args': {
            'youtube': {
                'player_client': c
            }
        },
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info('ytsearch1:Son Tung MTP Chung Ta Cua Hien Tai', download=True)
            print(f' SUCCESS with player_client: {c}!')
            break
    except Exception as e:
        print(f' Failed with {c}: {e}')
"
"""

ok, out = run_ssh_command(test_script, timeout=60)
