import subprocess
import sys

print("=== Testing yt-dlp oauth2 plugin ===")
cmd = [
    "yt-dlp",
    "https://www.youtube.com/watch?v=h_D3VFfhvs4",
    "--username", "oauth2",
    "--password", "",
    "-F",
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
print("OAuth2 test output:", (res.stdout + res.stderr)[:400])

print("\n=== Testing pytubefix for audio stream extraction ===")
try:
    from pytubefix import YouTube
    yt = YouTube("https://www.youtube.com/watch?v=h_D3VFfhvs4", client="ANDROID")
    print(f"pytubefix title: {yt.title}")
    audio = yt.streams.get_audio_only()
    print(f"pytubefix audio stream: {audio.url[:60]}... (bitrate: {audio.bitrate})")
except Exception as e:
    print("pytubefix error:", e)
