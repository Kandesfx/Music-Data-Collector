import yt_dlp
from pathlib import Path

url = "https://www.youtube.com/watch?v=rg2FNrBM5Yo"
cookie_file = "/opt/music-data-collector/config/cookies.txt"
temp_dir = Path("./data/temp/test_cookie")
temp_dir.mkdir(parents=True, exist_ok=True)
out_tmpl = str(temp_dir / "audio.%(ext)s")

print(f"Testing yt-dlp download with cookiefile: {cookie_file}")
ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": out_tmpl,
    "cookiefile": cookie_file,
    "quiet": False,
    "no_warnings": False,
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("✅ SUCCESS! Cookie is working!")
except Exception as e:
    print("❌ FAILED:", e)
