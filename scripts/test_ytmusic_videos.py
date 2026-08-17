from ytmusicapi import YTMusic
import yt_dlp

ytmusic = YTMusic()
results = ytmusic.search("Xesi Vô Tình", filter="videos")
print(f"Found {len(results)} videos:")
cookie_file = "/opt/music-data-collector/config/cookies.txt"

for r in results[:10]:
    vid = r.get("videoId")
    title = r.get("title")
    print(f"Video: [{vid}] {title}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/test_vid_{vid}.%(ext)s',
        'cookiefile': cookie_file,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={vid}"])
        print(f"  --> ✅ SUCCESS for [{vid}] {title}!")
        break
    except Exception as e:
        print(f"  --> ❌ FAILED for [{vid}]: {e}")
