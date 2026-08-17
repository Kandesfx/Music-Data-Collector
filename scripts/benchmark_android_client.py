import time
import yt_dlp
from pathlib import Path

urls = [
    ("HIEUTHUHAI - Bật Nhạc Lên", "https://www.youtube.com/watch?v=rg2FNrBM5Yo"),
    ("Sơn Tùng M-TP - Đừng Làm Trái Tim Anh Đau", "https://www.youtube.com/watch?v=abPmFU4m3wE"),
]

proxies_to_test = [
    ("Tailscale SOCKS5 (Port 1055)", "socks5://127.0.0.1:1055"),
    ("WARP SOCKS5 (Port 40000)", "socks5://127.0.0.1:40000"),
    ("Direct Connection", None),
]

clients_to_test = [
    ("Android Music & Android Client (Recommended)", ["android_music", "android"]),
    ("Android VR Client", ["android_vr"]),
    ("iOS Music & iOS Client", ["ios_music", "ios"]),
    ("Web Client", ["web"]),
]

temp_base = Path("./data/temp/benchmark_clients")
temp_base.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("🚀 BENCHMARK: YouTube Player Clients & Tailscale Proxy Performance")
print("=" * 70)

for title, url in urls[:1]:
    print(f"\n🎵 Testing Song: {title} ({url})")
    
    for proxy_name, proxy_url in proxies_to_test:
        print(f"\n--- [NETWORK ROUTE: {proxy_name}] ---")
        
        for client_name, client_list in clients_to_test:
            out_file = temp_base / f"test_{client_name.split()[0].lower()}.mp3"
            if out_file.exists():
                out_file.unlink()
                
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": str(temp_base / "audio.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ],
                "extractor_args": {
                    "youtube": {
                        "player_client": client_list,
                    }
                },
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "socket_timeout": 15,
            }
            if proxy_url:
                ydl_opts["proxy"] = proxy_url
                
            start_t = time.perf_counter()
            success = False
            error_msg = None
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                
                # Check generated mp3
                mp3s = list(temp_base.glob("*.mp3"))
                size_kb = int(mp3s[0].stat().st_size / 1024) if mp3s else 0
                for f in mp3s:
                    f.unlink()
                    
                print(f"  ✅ [{client_name}]: THÀNH CÔNG! Thời gian: {dur_ms}ms ({dur_ms/1000:.1f}s) | Dung lượng: {size_kb} KB")
                success = True
            except Exception as e:
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                err_clean = str(e).split("\n")[0][:80]
                print(f"  ❌ [{client_name}]: THẤT BẠI ({dur_ms}ms) -> {err_clean}")
