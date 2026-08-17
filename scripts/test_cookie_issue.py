import yt_dlp
import os

print("=== Testing yt-dlp on y3o7Dg9Ikpc ===")
cookie_file = "/opt/music-data-collector/config/cookies.txt"
print("Cookie file exists:", os.path.exists(cookie_file))

# Test A: standard with web,mweb
ydl_opts_a = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/test_y3o_a.%(ext)s',
    'cookiefile': cookie_file,
    'quiet': False
}

try:
    with yt_dlp.YoutubeDL(ydl_opts_a) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=y3o7Dg9Ikpc", download=True)
    print("Test A SUCCESS! Title:", info.get('title'))
except Exception as e:
    print("Test A FAILED:", e)

# Test B: without player_client override
ydl_opts_b = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/test_y3o_b.%(ext)s',
    'cookiefile': cookie_file,
    'extractor_args': {'youtube': {'player_client': ['web', 'mweb', 'android', 'ios']}},
    'quiet': False
}

try:
    with yt_dlp.YoutubeDL(ydl_opts_b) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=y3o7Dg9Ikpc", download=True)
    print("Test B SUCCESS! Title:", info.get('title'))
except Exception as e:
    print("Test B FAILED:", e)
