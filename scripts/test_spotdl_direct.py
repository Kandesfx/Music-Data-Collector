import subprocess
import os

os.makedirs("/tmp/test_spotdl_vo_tinh", exist_ok=True)
cmd = [
    "/opt/music-data-collector/.venv/bin/python",
    "-m", "spotdl",
    "download", "https://open.spotify.com/track/6UelLqGlWMcVH1E5c4H77Y",
    "--output", "/tmp/test_spotdl_vo_tinh",
    "--format", "mp3",
    "--bitrate", "320k",
    "--headless"
]
print("Running spotDL...")
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("Returncode:", res.returncode)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("Output dir files:", os.listdir("/tmp/test_spotdl_vo_tinh"))
