from spotdl.utils.spotify import SpotifyClient
import json

sp = SpotifyClient.init("", "")
pid = "37i9dQZEVXbLdGSmz6xilI"

pl = sp.playlist(pid)
content = pl.get("content", {})
print("content keys:", content.keys() if isinstance(content, dict) else type(content))
items = content.get("items", []) if isinstance(content, dict) else []
print(f"Items in content: {len(items)}")
if items:
    first = items[0]
    print("first item keys:", first.keys() if isinstance(first, dict) else first)
    itemV2 = first.get("itemV2", {})
    print("itemV2 keys:", itemV2.keys() if isinstance(itemV2, dict) else itemV2)
    data = itemV2.get("data", {})
    print("itemV2.data keys:", data.keys() if isinstance(data, dict) else data)
    print("Track name:", data.get("name"))
    print("Artist names:", [a.get("profile", {}).get("name") for a in data.get("artists", {}).get("items", [])])
    print("Album name:", data.get("albumOfTrack", {}).get("name"))
    print("Duration ms:", data.get("trackDuration", {}).get("totalMilliseconds"))
