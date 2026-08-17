import yt_dlp
import os

url = "https://www.youtube.com/watch?v=1DMrZA1jfeQ"
cookie = "/opt/music-data-collector/config/cookies.txt"

clients_to_test = [
    ["tv"],
    ["tv_embedded"],
    ["web_creator"],
    ["android_creator"],
    ["android_music"],
    ["ios_music"],
    ["mweb"],
    ["web"],
    ["web_safari"],
    ["tv", "web"],
    ["android", "ios"],
    ["mweb", "android"],
]

print(f"=== Testing Client Matrix for: {url} ===")

for c in clients_to_test:
    client_str = ",".join(c)
    print(f"\n--- Testing client: {client_str} (WITH COOKIE) ---")
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/test_client_{client_str[:10]}.%(ext)s',
        'cookiefile': cookie,
        'extractor_args': {'youtube': {'player_client': c}},
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        print(f"✅ SUCCESS with {client_str} (with cookie)")
        break
    except Exception as e:
        print(f"❌ Failed: {e}")

for c in clients_to_test:
    client_str = ",".join(c)
    print(f"\n--- Testing client: {client_str} (NO COOKIE) ---")
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/test_nocookie_{client_str[:10]}.%(ext)s',
        'extractor_args': {'youtube': {'player_client': c}},
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        print(f"✅ SUCCESS with {client_str} (NO cookie)")
        break
    except Exception as e:
        print(f"❌ Failed: {e}")
