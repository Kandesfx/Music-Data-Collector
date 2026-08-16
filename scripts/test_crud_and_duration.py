import urllib.request
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test():
    # 1. Test Duration in Completed Tracks
    print("=== 1. VERIFY DURATION IN COMPLETED TRACKS LIST ===")
    res = urllib.request.urlopen("http://127.0.0.1:5000/api/tracks?page=1&limit=5&download_status=completed")
    data = json.loads(res.read().decode("utf-8"))
    for t in data.get("items", []):
        print(f"Track: {t.get('name')} | Duration fmt: {t.get('duration_formatted')} | Duration ms: {t.get('duration_ms')} | Local: {t.get('local_path')}")

    # 2. Test ADD Track
    print("\n=== 2. TEST ADD TRACK API ===")
    add_req = urllib.request.Request(
        "http://127.0.0.1:5000/api/tracks/add",
        data=json.dumps({
            "name": "Bài Hát Test Thêm Mới 2026",
            "artist_name": "Nghệ Sĩ Test",
            "album_name": "Album Test",
            "duration_sec": 225,
            "genres": ["vpop", "ballad"],
            "popularity": 85
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    add_res = urllib.request.urlopen(add_req)
    add_data = json.loads(add_res.read().decode("utf-8"))
    test_id = add_data.get("track", {}).get("spotify_id")
    print(f"Add Result: {add_data.get('success')} | New Track ID: {test_id} | Name: {add_data.get('track', {}).get('name')}")

    # 3. Test EDIT Track
    print("\n=== 3. TEST EDIT TRACK API ===")
    edit_req = urllib.request.Request(
        f"http://127.0.0.1:5000/api/tracks/{test_id}",
        data=json.dumps({
            "name": "Bài Hát Đã Sửa Metadata Thành Công",
            "artist_name": "Nghệ Sĩ Đã Sửa",
            "popularity": 95,
            "lyrics_synced": "[00:01.00]Lời bài hát test đã sửa..."
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    edit_res = urllib.request.urlopen(edit_req)
    edit_data = json.loads(edit_res.read().decode("utf-8"))
    print(f"Edit Result: {edit_data.get('success')}")

    # 4. Verify Inspect on Edited Track
    insp_res = urllib.request.urlopen(f"http://127.0.0.1:5000/api/tracks/{test_id}/inspect")
    insp_data = json.loads(insp_res.read().decode("utf-8"))
    print(f"Inspect Track Name: {insp_data.get('track', {}).get('name')} | Popularity: {insp_data.get('track', {}).get('popularity')}")

    # 5. Test DELETE Track
    print("\n=== 5. TEST DELETE TRACK API ===")
    del_req = urllib.request.Request(f"http://127.0.0.1:5000/api/tracks/{test_id}", method="DELETE")
    del_res = urllib.request.urlopen(del_req)
    del_data = json.loads(del_res.read().decode("utf-8"))
    print(f"Delete Result: {del_data.get('success')}")

    # 6. Test AUDIT LOGS
    print("\n=== 6. VERIFY AUDIT LOGS ===")
    logs_res = urllib.request.urlopen("http://127.0.0.1:5000/api/logs?page=1&limit=5")
    logs_data = json.loads(logs_res.read().decode("utf-8"))
    print(f"Total audit logs stored in MongoDB: {logs_data.get('total_items')}")
    for l in logs_data.get("items", [])[:4]:
        print(f"[{l.get('timestamp_formatted')}] User: @{l.get('username')} | Action: {l.get('action')} | Status: {l.get('status')} | Details: {l.get('details')}")

if __name__ == "__main__":
    test()
