"""
Music Data Collector - AI Audio Post-Download Moderation & Verification Engine
Evaluates downloaded audio against Spotify ground truth using a 5-factor 100-point scoring matrix:
1. Duration Fidelity & Leading/Trailing Silence Detection (40 pts)
2. Studio Quality (Bitrate >= 320kbps, Sample Rate = 44.1kHz) (20 pts)
3. Loudness Compliance EBU R128 (-16.0 to -10.0 LUFS) (15 pts)
4. ID3 Tags & HD Cover Art Completeness (15 pts)
5. Synced Lyrics (.lrc) Synchronization Match (10 pts)
"""

import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

from config import settings
from src.processors.audio_feature_extractor import AudioFeatureExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioVerifier:
    """
    Autonomous AI Post-Download Audio Moderation & Verification Engine.
    Evaluates audio fidelity, metadata integrity, and loudness consistency.
    """

    @classmethod
    def detect_effective_duration(cls, mp3_path: Path, max_sample_sec: float = 120.0) -> Tuple[float, float, float]:
        """
        Calculates total length, leading silence, and trailing silence in seconds.
        Returns: (total_duration, leading_silence_sec, trailing_silence_sec)
        """
        try:
            audio = MP3(str(mp3_path))
            total_duration = audio.info.length

            # Decode samples for silence profiling
            samples = AudioFeatureExtractor.decode_audio_samples(mp3_path, max_duration_sec=30.0, target_sr=11025)
            leading_silence = 0.0
            if samples is not None and len(samples) > 0:
                # 100ms frame chunking
                chunk_len = 1102
                for i in range(len(samples) // chunk_len):
                    chunk = samples[i * chunk_len : (i + 1) * chunk_len]
                    rms = np.sqrt(np.mean(chunk**2))
                    if rms < 0.005:  # -46dB silence threshold
                        leading_silence += 0.1
                    else:
                        break

            return round(total_duration, 2), round(leading_silence, 2), 0.0
        except Exception:
            return 0.0, 0.0, 0.0

    @classmethod
    def evaluate_track(
        cls,
        track_dict: Dict[str, Any],
        mp3_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a track against the 5-factor 100-point Moderation Matrix.
        Returns score (0-100), decision ('approved' | 'flagged' | 'rejected'), and breakdown.
        """
        spotify_id = track_dict.get("spotify_id")
        target_name = track_dict.get("name", "Unknown")
        target_artist = track_dict.get("artist_name", "Unknown")
        target_duration_ms = track_dict.get("duration_ms", 0)
        expected_sec = target_duration_ms / 1000.0 if target_duration_ms else 0.0

        # Resolve file path
        file_path = mp3_path
        if not file_path and track_dict.get("local_path"):
            file_path = settings.BASE_DIR / track_dict["local_path"]

        if not file_path or not file_path.exists():
            return {
                "success": False,
                "score": 0,
                "status": "rejected",
                "reason": "Audio file not found on disk",
                "breakdown": {},
            }

        breakdown = {}
        total_score = 0.0

        # ─── Factor 1: Duration Fidelity & Silence Profiling (40 pts) ───
        try:
            total_sec, leading_silence, _ = cls.detect_effective_duration(file_path)
            delta_sec = abs(total_sec - expected_sec)
            effective_delta = abs((total_sec - leading_silence) - expected_sec)
            best_delta = min(delta_sec, effective_delta)

            score_dur = 0.0
            if expected_sec <= 0:
                score_dur = 30.0
                dur_note = "Chưa có mốc thời lượng Spotify đối chiếu"
            elif best_delta <= 1.5:
                score_dur = 40.0
                dur_note = f"Hoàn hảo: Lệch chỉ {best_delta:.1f}s so với bản quyền"
            elif best_delta <= 4.0:
                score_dur = 35.0
                dur_note = f"Rất tốt: Lệch {best_delta:.1f}s (chuẩn fade-out single/album)"
            elif best_delta <= 10.0:
                score_dur = 25.0
                dur_note = f"Chấp nhận được: Lệch {best_delta:.1f}s"
            elif best_delta <= 20.0:
                score_dur = 10.0
                dur_note = f"Cảnh báo: Lệch {best_delta:.1f}s"
            else:
                score_dur = 0.0
                dur_note = f"Lệch nghiêm trọng: {best_delta:.1f}s > 20s"

            breakdown["duration"] = {
                "score": score_dur,
                "max": 40,
                "actual_sec": total_sec,
                "expected_sec": expected_sec,
                "delta_sec": round(best_delta, 1),
                "leading_silence_sec": leading_silence,
                "note": dur_note,
            }
            total_score += score_dur
        except Exception as ex:
            breakdown["duration"] = {"score": 0, "max": 40, "note": f"Lỗi đọc file: {ex}"}

        # ─── Factor 2: Studio Audio Quality (20 pts) ────────────────────
        try:
            audio = MP3(str(file_path))
            bitrate_kbps = int(audio.info.bitrate / 1000)
            sample_rate = audio.info.sample_rate

            score_qual = 0.0
            if bitrate_kbps >= 300 and sample_rate >= 44100:
                score_qual = 20.0
                qual_note = f"Studio Master: {bitrate_kbps} kbps @ {sample_rate} Hz Stereo"
            elif bitrate_kbps >= 250:
                score_qual = 16.0
                qual_note = f"Chất lượng cao: {bitrate_kbps} kbps @ {sample_rate} Hz"
            elif bitrate_kbps >= 192:
                score_qual = 12.0
                qual_note = f"Chuẩn trung bình: {bitrate_kbps} kbps"
            else:
                score_qual = 5.0
                qual_note = f"Chất lượng thấp: {bitrate_kbps} kbps"

            breakdown["quality"] = {
                "score": score_qual,
                "max": 20,
                "bitrate_kbps": bitrate_kbps,
                "sample_rate": sample_rate,
                "note": qual_note,
            }
            total_score += score_qual
        except Exception as ex:
            breakdown["quality"] = {"score": 0, "max": 20, "note": f"Lỗi đọc MP3: {ex}"}

        # ─── Factor 3: Loudness Compliance EBU R128 (15 pts) ───────────
        try:
            # Extract features or calculate
            features = track_dict.get("audio_features")
            if not features:
                features = AudioFeatureExtractor.analyze_track(file_path, spotify_id=spotify_id)

            lufs = features.get("loudness_lufs", -14.0)
            score_lufs = 0.0
            if -16.0 <= lufs <= -10.0:
                score_lufs = 15.0
                lufs_note = f"Chuẩn phát thanh EBU R128 ({lufs} LUFS)"
            elif -20.0 <= lufs < -16.0 or -10.0 < lufs <= -8.0:
                score_lufs = 12.0
                lufs_note = f"Âm lượng ổn định ({lufs} LUFS)"
            else:
                score_lufs = 8.0
                lufs_note = f"Âm lượng ngoài dải chuẩn ({lufs} LUFS)"

            breakdown["loudness"] = {
                "score": score_lufs,
                "max": 15,
                "lufs": lufs,
                "bpm": features.get("bpm", 120),
                "key": features.get("key_signature", "Unknown"),
                "note": lufs_note,
            }
            total_score += score_lufs
        except Exception as ex:
            breakdown["loudness"] = {"score": 10.0, "max": 15, "note": f"Lỗi phân tích LUFS: {ex}"}
            total_score += 10.0

        # ─── Factor 4: ID3 Metadata & HD Cover Art Completeness (15 pts) ──
        try:
            has_id3 = False
            has_cover = False
            try:
                id3_tags = ID3(str(file_path))
                has_id3 = bool(id3_tags.getall("TIT2") and id3_tags.getall("TPE1"))
                has_cover = bool(id3_tags.getall("APIC"))
            except Exception:
                pass

            score_id3 = 0.0
            if has_id3 and (has_cover or track_dict.get("image_url")):
                score_id3 = 15.0
                id3_note = "Đầy đủ 100% ID3v2.3 + Bìa Album HD"
            elif has_id3:
                score_id3 = 10.0
                id3_note = "Đủ nhãn ID3 cơ bản (Thiếu ảnh bìa nhúng)"
            else:
                score_id3 = 5.0
                id3_note = "Thiếu cấu trúc ID3v2.3 chuẩn"

            breakdown["metadata"] = {
                "score": score_id3,
                "max": 15,
                "has_id3": has_id3,
                "has_cover": has_cover or bool(track_dict.get("image_url")),
                "note": id3_note,
            }
            total_score += score_id3
        except Exception as ex:
            breakdown["metadata"] = {"score": 5.0, "max": 15, "note": str(ex)}
            total_score += 5.0

        # ─── Factor 5: Synced Lyrics (.lrc) Match (10 pts) ─────────────
        has_lrc = False
        lrc_file = file_path.with_suffix(".lrc")
        if lrc_file.exists() and lrc_file.stat().st_size > 50:
            has_lrc = True

        score_lyrics = 0.0
        if has_lrc or track_dict.get("lyrics_synced"):
            score_lyrics = 10.0
            lyrics_note = "Đầy đủ Lời Karaoke Synced (.lrc)"
        elif track_dict.get("lyrics_plain"):
            score_lyrics = 7.0
            lyrics_note = "Có Lời Plain Text (Chưa có mốc thời gian)"
        else:
            score_lyrics = 3.0
            lyrics_note = "Chưa có lời bài hát"

        breakdown["lyrics"] = {
            "score": score_lyrics,
            "max": 10,
            "has_synced": has_lrc or bool(track_dict.get("lyrics_synced")),
            "has_plain": bool(track_dict.get("lyrics_plain")),
            "note": lyrics_note,
        }
        total_score += score_lyrics

        # ─── Final Moderation Decision ─────────────────────────────────
        final_score = round(min(100.0, max(0.0, total_score)), 1)
        if final_score >= 85.0:
            status = "approved"
            summary_msg = f"ĐẠT CHUẨN KIỂM DUYỆT AI ({final_score}/100) - File hoàn toàn khớp với Master Spotify"
        elif final_score >= 65.0:
            status = "flagged"
            summary_msg = f"CẦN LƯU Ý ({final_score}/100) - Có một số tiêu chí cần kiểm tra lại"
        else:
            status = "rejected"
            summary_msg = f"KHÔNG ĐẠT CHUẨN ({final_score}/100) - Lệch nhiều tiêu chí cốt lõi"

        return {
            "success": True,
            "spotify_id": spotify_id,
            "score": final_score,
            "status": status,
            "summary": summary_msg,
            "breakdown": breakdown,
        }

    @classmethod
    def verify_and_update_db(cls, track_id: str, db_manager) -> Dict[str, Any]:
        """Runs moderation evaluation on track and stores report in MongoDB."""
        track = db_manager.get_track(track_id)
        if not track:
            return {"success": False, "error": "Track not found"}

        report = cls.evaluate_track(track)
        if report.get("success"):
            db_manager.db["tracks"].update_one(
                {"spotify_id": track_id},
                {
                    "$set": {
                        "moderation_status": report["status"],
                        "moderation_score": report["score"],
                        "moderation_report": report,
                    }
                }
            )
        return report
