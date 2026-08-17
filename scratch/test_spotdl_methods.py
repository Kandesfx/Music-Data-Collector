from spotdl.utils.spotify import SpotifyClient
import json

sp = SpotifyClient.init("", "")
pid = "37i9dQZEVXbLdGSmz6xilI"

print("--- Testing sp.playlist ---")
try:
    pl = sp.playlist(pid)
    print("pl keys:", pl.keys() if isinstance(pl, dict) else type(pl))
    tracks = pl.get("tracks", {})
    items = tracks.get("items", []) if isinstance(tracks, dict) else []
    print(f"Items in playlist: {len(items)}")
    for it in items[:5]:
        t = it.get("track", it)
        print("  -", t.get("name"), "|", (t.get("artists") or [{}])[0].get("name"))
except Exception as e:
    print("sp.playlist error:", e)

print("--- Testing sp.playlist_items ---")
try:
    items_res = sp.playlist_items(pid)
    print("playlist_items keys:", items_res.keys() if isinstance(items_res, dict) else type(items_res))
    items = items_res.get("items", []) if isinstance(items_res, dict) else []
    print(f"Items from playlist_items: {len(items)}")
    for it in items[:5]:
        t = it.get("track", it)
        print("  -", t.get("name"), "|", (t.get("artists") or [{}])[0].get("name"))
except Exception as e:
    print("sp.playlist_items error:", e)
