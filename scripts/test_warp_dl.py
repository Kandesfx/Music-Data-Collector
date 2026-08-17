import yt_dlp
from pathlib import Path

url = "https://www.youtube.com/watch?v=rg2FNrBM5Yo"
temp_dir = Path("./data/temp/test_warp")
temp_dir.mkdir(parents=True, exist_ok=True)
out_tmpl = str(temp_dir / "audio.%(ext)s")

print("Testing download via WARP SOCKS5 (socks5://127.0.0.1:40000)...")
ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": out_tmpl,
    "proxy": "socks5://127.0.0.1:40000",
    "quiet": False,
    "no_warnings": False,
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("✅ SUCCESS via WARP!")
except Exception as e:
    print("❌ FAILED via WARP:", e)
