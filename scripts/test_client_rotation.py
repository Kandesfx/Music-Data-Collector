import yt_dlp
from pathlib import Path

url = "https://www.youtube.com/watch?v=rg2FNrBM5Yo"
temp_dir = Path("./data/temp/test_ios")
temp_dir.mkdir(parents=True, exist_ok=True)
out_tmpl = str(temp_dir / "audio.%(ext)s")

clients_tests = [
    ("ios_client_no_cookie", ["ios"], None),
    ("android_client_no_cookie", ["android"], None),
    ("tv_client_no_cookie", ["tv_embedded", "tv"], None),
    ("mweb_client_no_cookie", ["mweb"], None),
]

for name, clients, cookie in clients_tests:
    print(f"\n--- Testing: {name} (clients={clients}) ---")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "extractor_args": {
            "youtube": {
                "player_client": clients,
            }
        },
        "quiet": False,
        "no_warnings": False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(" SUCCESS!")
        break
    except Exception as e:
        print(" FAILED:", e)
