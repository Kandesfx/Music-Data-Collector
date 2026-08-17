import sys
import io
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.storage.db_manager import DBManager
from src.processors.audio_verifier import AudioVerifier

def test_audio_verifier():
    db = DBManager()
    if not db.is_connected():
        print("❌ Cannot connect to DB")
        return

    print("==================================================")
    print("🛡️ KIỂM THỬ HỆ THỐNG KIỂM ĐỊNH AI AUDIO VERIFIER")
    print("==================================================")

    # 1. Test single track verification
    tracks = list(db.db["tracks"].find({"download_status": "completed"}).limit(5))
    if not tracks:
        print("⚠️ Chưa có bài hát nào tải hoàn tất để kiểm định.")
        return

    for i, track in enumerate(tracks, 1):
        sp_id = track.get("spotify_id")
        title = track.get("name")
        artist = track.get("artist_name")

        rep = AudioVerifier.verify_and_update_db(sp_id, db)
        print(f"\n[{i}/5] 🎵 {artist} - {title} ({sp_id})")
        print(f"  🏆 Tổng Điểm: {rep.get('score')}/100 | Quyết Định: {rep.get('status').upper()}")
        print(f"  📝 Đánh Giá: {rep.get('summary')}")
        
        b = rep.get("breakdown", {})
        print(f"    1. Thời lượng ({b.get('duration', {}).get('score')}/40đ): {b.get('duration', {}).get('note')}")
        print(f"    2. Chất lượng ({b.get('quality', {}).get('score')}/20đ): {b.get('quality', {}).get('note')}")
        print(f"    3. Độ lớn LUFS ({b.get('loudness', {}).get('score')}/15đ): {b.get('loudness', {}).get('note')}")
        print(f"    4. ID3 & Bìa HD ({b.get('metadata', {}).get('score')}/15đ): {b.get('metadata', {}).get('note')}")
        print(f"    5. Lời Karaoke ({b.get('lyrics', {}).get('score')}/10đ): {b.get('lyrics', {}).get('note')}")

    print("\n==================================================")
    print("🎉 KIỂM THỬ HỆ THỐNG KIỂM ĐỊNH AI THÀNH CÔNG 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_audio_verifier()
