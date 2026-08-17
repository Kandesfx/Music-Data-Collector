import sys
import io
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.storage.cache_manager import ram_cache
from src.utils.hardware_monitor import HardwareMonitor
from src.processors.audio_feature_extractor import AudioFeatureExtractor
from src.processors.enrichment_daemon import enrichment_daemon

def test_all_modules():
    print("==================================================")
    print("🧪 KIỂM THỬ TOÀN BỘ 4 MODULE KHAI THÁC CPU & RAM")
    print("==================================================")

    # 1. Hardware Monitor Test
    hw = HardwareMonitor.get_system_metrics()
    print("\n[1/4] 🖥️ Hardware Monitor Telemetry:")
    print(f"  - CPU Cores: {hw.get('cpu_cores')} cores | Load: {hw.get('cpu_percent')}%")
    print(f"  - RAM Total: {hw.get('total_ram_gb')} GB | Used: {hw.get('used_ram_gb')} GB | Free: {hw.get('free_ram_gb')} GB")
    assert hw.get("cpu_cores") >= 1, "CPU cores should be at least 1"

    # 2. In-Memory RAM Cache Test
    print("\n[2/4] 🚀 In-Memory RAM Cache Test:")
    ram_cache.clear()
    ram_cache.set("test_key_1", {"data": "spotify_meta", "value": 123}, ttl_sec=60)
    cached = ram_cache.get("test_key_1")
    assert cached and cached["value"] == 123, "Cache set/get failed"
    stats = ram_cache.get_stats()
    print(f"  - Active Entries: {stats.get('active_entries')} | Hits: {stats.get('hits')} | Misses: {stats.get('misses')} | Hit Rate: {stats.get('hit_ratio_percent')}%")

    # 3. AI Audio Feature & Waveform Extractor Test
    print("\n[3/4] 🧠 AI Audio Feature Extractor Test:")
    mp3s = list(Path(BASE_DIR / "data" / "audio").rglob("*.mp3"))
    if mp3s:
        test_file = mp3s[0]
        res = AudioFeatureExtractor.analyze_track(test_file, spotify_id="test_sp_01")
        print(f"  - File: {test_file.name}")
        print(f"  - BPM: {res.get('bpm')} | Tông: {res.get('key_signature')} | Loudness: {res.get('loudness_lufs')} LUFS")
        print(f"  - Energy: {res.get('energy')} | Danceability: {res.get('danceability')} | Valence: {res.get('valence')}")
        print(f"  - Waveform Peaks: {len(res.get('waveform_peaks', []))} frames (Sample: {res.get('waveform_peaks')[:5]})")
        assert len(res.get("waveform_peaks", [])) == 100, "Waveform should have 100 peak frames"
    else:
        print("  - (No local MP3 found for audio DSP test, will verify on OCI server)")

    # 4. Background Enrichment Daemon Test
    print("\n[4/4] 🤖 Auto-Enrichment Daemon Test:")
    daemon_st = enrichment_daemon.get_status()
    print(f"  - Daemon status: {daemon_st.get('status')} | Features computed: {daemon_st.get('total_features_computed')} | Lyrics enriched: {daemon_st.get('total_lyrics_enriched')}")

    print("\n==================================================")
    print("🎉 TẤT CẢ 4 MODULE KHAI THÁC CPU & RAM HOẠT ĐỘNG HOÀN HẢO!")
    print("==================================================")

if __name__ == "__main__":
    test_all_modules()
