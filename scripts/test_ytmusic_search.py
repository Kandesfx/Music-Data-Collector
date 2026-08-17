from ytmusicapi import YTMusic
import yt_dlp

ytmusic = YTMusic()
results = ytmusic.search("Xesi, Hoaprox - Vô Tình", filter="songs")
print(f"Found {len(results)} songs:")
for r in results[:5]:
    vid = r.get("videoId")
    title = r.get("title")
    artists = ", ".join(a.get("name", "") for a in r.get("artists", []))
    dur = r.get("duration")
    print(f"- {title} | {artists} | {dur} -> videoId: {vid} (https://music.youtube.com/watch?v={vid})")

# Test downloading each videoId
cookie_file = "/opt/music-data-collector/config/cookies.txt"
for r in results[:3]:
    vid = r.get("videoId")
    url = f"https://music.youtube.com/watch?v={vid}"
    print(f"\nTesting download for {vid}: {url}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/test_{vid}.%(ext)s',
        'cookiefile': cookie_file,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"SUCCESS for {vid}!")
    except Exception as e:
        print(f"FAILED for {vid}: {e}")
