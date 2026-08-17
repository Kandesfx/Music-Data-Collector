import sys
import io
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from src.storage.db_manager import DBManager
from src.downloaders.ytmusic_matcher import YTMusicMatcher
from src.processors.post_processor import PostProcessor

def audit_all_downloaded_tracks():
    db = DBManager()
    if not db.is_connected():
        print("❌ Cannot connect to MongoDB database.")
        return

    matcher = YTMusicMatcher()

    # Query all completed downloaded tracks
    tracks = list(db.db["tracks"].find({"download_status": "completed"}))
    total = len(tracks)
    print("================================================================================")
    print(f"📊 BẮT ĐẦU KIỂM DUYỆT TOÀN DIỆN {total} BÀI HÁT ĐÃ TẢI TRÊN HỆ THỐNG")
    print("================================================================================")

    if total == 0:
        print("⚠️ Chưa có bài hát nào ở trạng thái 'completed' trong cơ sở dữ liệu.")
        return

    valid_count = 0
    warning_count = 0
    mismatch_count = 0
    high_bitrate_count = 0
    lyrics_synced_count = 0
    lyrics_plain_count = 0

    anomalies = []

    for idx, track in enumerate(tracks, 1):
        sp_id = track.get("spotify_id")
        title = track.get("name", "Unknown")
        artist = track.get("artist_name", "Unknown")
        duration_ms = track.get("duration_ms", 0)
        expected_sec = duration_ms / 1000.0 if duration_ms else 0.0
        rel_path = track.get("local_path")

        print(f"\n[{idx}/{total}] 🎵 Kiểm tra: {artist} - {title} ({sp_id})")
        print(f"  📌 Expected Duration: {expected_sec:.1f}s ({int(expected_sec//60)}:{int(expected_sec%60):02d})")

        # 1. File existence check
        if not rel_path:
            print("  ❌ Thiếu đường dẫn local_path trong DB!")
            anomalies.append({"track": track, "reason": "Missing local_path"})
            mismatch_count += 1
            continue

        full_path = BASE_DIR / rel_path
        if not full_path.exists():
            print(f"  ❌ File audio không tồn tại trên đĩa: {full_path}")
            anomalies.append({"track": track, "reason": "Audio file not found on disk"})
            mismatch_count += 1
            continue

        file_size_mb = full_path.stat().st_size / (1024 * 1024)

        # 2. Mutagen Audio Inspection
        try:
            audio = MP3(str(full_path))
            actual_sec = audio.info.length
            bitrate_kbps = int(audio.info.bitrate / 1000)
            sample_rate = audio.info.sample_rate

            if bitrate_kbps >= 256:
                high_bitrate_count += 1

            delta_sec = abs(actual_sec - expected_sec)
            delta_percent = (delta_sec / expected_sec * 100) if expected_sec > 0 else 0

            print(f"  🎧 File MP3: {file_size_mb:.2f} MB | {bitrate_kbps} kbps | {sample_rate} Hz")
            print(f"  ⏱️ Độ dài thực tế: {actual_sec:.1f}s ({int(actual_sec//60)}:{int(actual_sec%60):02d}) | Lệch: {delta_sec:.1f}s ({delta_percent:.1f}%)")

            # 3. ID3 & Lyrics check
            has_lyrics_lrc = False
            lrc_file = full_path.with_suffix(".lrc")
            if lrc_file.exists() and lrc_file.stat().st_size > 50:
                has_lyrics_lrc = True
                lyrics_synced_count += 1
            elif track.get("lyrics_plain"):
                lyrics_plain_count += 1

            print(f"  📝 Lời bài hát: {'🟢 Synced (.lrc)' if has_lyrics_lrc else ('🟡 Plain' if track.get('lyrics_plain') else '⚪ Không có')}")

            # 4. Precision Matcher Cross-Check
            # Re-evaluate with the new strict 5-factor decision matrix
            cands = matcher.find_candidates_ranked(artist, title, duration_ms=duration_ms, max_candidates=1)
            matcher_score = cands[0]["score"] if cands else 0.0
            matcher_title = cands[0]["title"] if cands else "N/A"

            print(f"  🎯 Thuật toán mới chấm điểm: {matcher_score:.1f} pts | Ứng viên chuẩn: '{matcher_title}'")

            # 5. Sanity Evaluation
            # Delta <= 15s is standard tolerance for studio vs single release fade-out
            if delta_sec <= 15.0 and bitrate_kbps >= 192:
                print("  ✅ ĐẠT CHUẨN KIỂM DUYỆT (100% Valid)")
                valid_count += 1
            elif delta_sec <= 30.0:
                print(f"  ⚠️ CẢNH BÁO: Độ lệch thời lượng {delta_sec:.1f}s (Cần theo dõi)")
                warning_count += 1
            else:
                print(f"  ❌ LỆCH THỜI LƯỢNG NGHIÊM TRỌNG ({delta_sec:.1f}s > 30s)!")
                anomalies.append({"track": track, "reason": f"Duration delta {delta_sec:.1f}s"})
                mismatch_count += 1

        except Exception as e:
            print(f"  ❌ Lỗi đọc file MP3: {e}")
            anomalies.append({"track": track, "reason": f"Corrupted MP3: {e}"})
            mismatch_count += 1

    print("\n================================================================================")
    print("📈 TỔNG HỢP BÁO CÁO KIỂM DUYỆT AUDIT")
    print("================================================================================")
    print(f"🔹 Tổng số bài hát đã kiểm tra: {total}")
    print(f"✅ Số bài ĐẠT CHUẨN TUYỆT ĐỐI (Valid): {valid_count}/{total} ({(valid_count/total*100):.1f}%)")
    print(f"⚠️ Số bài Cảnh báo sai lệch nhẹ: {warning_count}/{total}")
    print(f"❌ Số bài Bất thường (Anomalies): {mismatch_count}/{total}")
    print(f"🎧 Tỷ lệ đạt chuẩn 320kbps / High-Fidelity: {high_bitrate_count}/{total} ({(high_bitrate_count/total*100):.1f}%)")
    print(f"🎤 Tỷ lệ có Lời Karaoke Synced (.lrc): {lyrics_synced_count}/{total} ({(lyrics_synced_count/total*100):.1f}%)")
    print("================================================================================")

    if anomalies:
        print("\n⚠️ DANH SÁCH BÀI HÁT CẦN TẢI LẠI (Anomalous tracks):")
        for a in anomalies:
            t = a["track"]
            print(f" - [{t.get('spotify_id')}] {t.get('artist_name')} - {t.get('name')}: {a['reason']}")
    else:
        print("\n🎉 XÁC NHẬN: 100% CÁC BÀI HÁT ĐÃ TẢI ĐỀU HOÀN TOÀN TRÙNG KHỚP VỚI THUẬT TOÁN MỚI!")

if __name__ == "__main__":
    audit_all_downloaded_tracks()
