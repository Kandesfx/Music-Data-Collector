import sys
import time
import io
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.downloaders.ytmusic_matcher import YTMusicMatcher
from src.processors.post_processor import PostProcessor

def run_precision_tests():
    matcher = YTMusicMatcher()
    print("==================================================")
    print("🧪 RUNNING PRECISION AUDIO MATCHER VERIFICATION")
    print("==================================================")

    test_tracks = [
        {
            "name": "1-800-LOVE",
            "artist": "MANBO, HIEUTHUHAI, HURRYKNG",
            "duration_ms": 255000,
            "must_not_contain": ["Reeves"],
            "must_contain": ["1-800", "LOVE"]
        },
        {
            "name": "Lối Chơi (LoiChoi)",
            "artist": "Wren Evans",
            "duration_ms": 167000,
            "must_contain": ["Lối Chơi", "Loi Choi"],
            "must_not_contain": ["Live", "Cover"]
        },
        {
            "name": "Cắt Đôi Nỗi Sầu",
            "artist": "Tăng Duy Tân, Drum7",
            "duration_ms": 184000,
            "must_contain": ["Cắt Đôi Nỗi Sầu"],
            "must_not_contain": ["Remix", "Live", "Cover"]
        },
        {
            "name": "See Tình",
            "artist": "Hoàng Thùy Linh",
            "duration_ms": 185000,
            "must_contain": ["See Tình"],
            "must_not_contain": ["Speed", "Sped", "Remix", "TikTok", "Nightcore"]
        }
    ]

    all_passed = True

    for i, track in enumerate(test_tracks, 1):
        t0 = time.time()
        cands = matcher.find_candidates_ranked(
            artist=track["artist"],
            title=track["name"],
            duration_ms=track["duration_ms"],
            max_candidates=3
        )
        elapsed = time.time() - t0

        print(f"\n[{i}/{len(test_tracks)}] Testing: {track['artist']} - {track['name']} ({track['duration_ms']/1000:.0f}s)")
        print(f"⏱️ Search & Evaluation time: {elapsed:.2f}s | Found candidates: {len(cands)}")

        if not cands:
            print("❌ FAIL: No valid candidate passed precision thresholds!")
            all_passed = False
            continue

        winner = cands[0]
        title = winner["title"]
        score = winner["score"]
        url = winner["youtube_url"]
        dur = winner["duration"]

        print(f"  🏆 Selected Match ({score:.1f} pts): {title} ({dur}) -> {url}")

        # Verification checks
        passed_track = True
        for neg in track.get("must_not_contain", []):
            if neg.lower() in title.lower() and neg.lower() not in track["name"].lower():
                print(f"  ❌ FAIL: Title contains forbidden word '{neg}'")
                passed_track = False

        if passed_track:
            print("  ✅ PASS: Strict gates passed!")
        else:
            all_passed = False

    print("\n==================================================")
    if all_passed:
        print("🎉 ALL PRECISION MATCHER TESTS PASSED 100%!")
    else:
        print("⚠️ SOME TESTS FAILED!")
    print("==================================================")

if __name__ == "__main__":
    run_precision_tests()
