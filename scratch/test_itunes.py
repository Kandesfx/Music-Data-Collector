import urllib.request
import urllib.parse
import json

def test_itunes(query, limit=100):
    safe_q = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_q}&media=music&entity=song&limit={limit}&country=VN"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        print(f"iTunes found for '{query}': {len(results)} songs")
        for r in results[:5]:
            print(f"  - {r.get('trackName')} | {r.get('artistName')}")
        return len(results)

test_itunes("LoiChoi", 100)
test_itunes("Wren Evans", 100)
test_itunes("Son Tung M-TP", 100)
