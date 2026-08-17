import yt_dlp

queries = [
    "ytsearch5:Xesi Hoaprox Vô Tình Official",
    "ytsearch5:Vô Tình Xesi Audio",
    "ytsearch5:Vô Tình Hoaprox Xesi",
]

cookie_file = "/opt/music-data-collector/config/cookies.txt"

for q in queries:
    print(f"\n=== Searching query: {q} ===")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/test_search_%(id)s.%(ext)s',
        'cookiefile': cookie_file,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(q, download=False)
            entries = res.get('entries', [])
            print(f"Found {len(entries)} entries:")
            for e in entries:
                vid = e.get('id')
                title = e.get('title')
                print(f"  - [{vid}] {title}")
                # Try downloading this entry
                try:
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                    print(f"    ✅ DOWNLOAD SUCCESS FOR [{vid}] {title}!")
                    break
                except Exception as ex:
                    print(f"    ❌ Download failed for [{vid}]: {ex}")
    except Exception as e:
        print(f"Search failed for {q}: {e}")
