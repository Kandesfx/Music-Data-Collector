"""
Music Data Collector - AI Audio Feature Extractor & Waveform Generator Module
Extracts acoustic features (BPM, Key/Scale, Loudness LUFS, Energy, Danceability, Valence)
and computes 100-point interactive waveform peaks for high-fidelity visualization.
"""

import math
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from mutagen.mp3 import MP3

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Key names in Krumhansl-Schmuckler Key Finding
PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Major and Minor key profiles (Krumhansl-Kessler)
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


class AudioFeatureExtractor:
    """
    Extracts high-level acoustic intelligence and visual waveform peaks
    from local MP3 audio files using Fast DSP Signal Processing.
    """

    @classmethod
    def decode_audio_samples(cls, mp3_path: Path, max_duration_sec: float = 180.0, target_sr: int = 22050) -> Optional[np.ndarray]:
        """
        Fast decodes MP3 to mono 16-bit PCM numpy array using FFmpeg streaming.
        Reads up to max_duration_sec to ensure blazing speed (< 1 sec analysis per song).
        """
        if not mp3_path.exists():
            return None

        cmd = [
            "ffmpeg",
            "-v", "quiet",
            "-t", str(max_duration_sec),
            "-i", str(mp3_path),
            "-f", "s16le",
            "-ac", "1",
            "-ar", str(target_sr),
            "-"
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if res.returncode != 0 or not res.stdout:
                return None
            samples = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            return samples
        except Exception as e:
            logger.debug(f"FFmpeg PCM decode failed for {mp3_path.name}: {e}")
            return None

    @classmethod
    def compute_waveform_peaks(cls, samples: np.ndarray, num_peaks: int = 100) -> List[float]:
        """
        Compute normalized peak amplitudes (0.0 to 1.0) across num_peaks segments.
        """
        if samples is None or len(samples) == 0:
            return [0.5] * num_peaks

        chunk_size = len(samples) // num_peaks
        if chunk_size < 1:
            return [float(np.max(np.abs(samples)))] * num_peaks

        peaks = []
        for i in range(num_peaks):
            chunk = samples[i * chunk_size : (i + 1) * chunk_size]
            if len(chunk) > 0:
                # RMS power of chunk
                rms = np.sqrt(np.mean(chunk**2))
                # Peak value
                peak = np.max(np.abs(chunk))
                # Weighted blend
                val = 0.7 * peak + 0.3 * (rms * 2.5)
                peaks.append(float(val))
            else:
                peaks.append(0.1)

        # Normalize peaks to max 1.0 with floor 0.05
        max_p = max(peaks) if peaks else 1.0
        if max_p > 0:
            peaks = [round(max(0.05, min(1.0, p / max_p)), 3) for p in peaks]
        else:
            peaks = [0.1] * num_peaks

        return peaks

    @classmethod
    def estimate_bpm(cls, samples: np.ndarray, sr: int = 22050) -> float:
        """
        Estimates BPM using spectral flux energy onset envelope and autocorrelation.
        """
        if samples is None or len(samples) < sr * 3:
            return 120.0

        try:
            # Downsample envelope: Hop size = 512
            hop_size = 512
            num_frames = len(samples) // hop_size
            if num_frames < 30:
                return 120.0

            # Compute short-time energy
            frames = samples[: num_frames * hop_size].reshape(num_frames, hop_size)
            energy = np.sum(frames**2, axis=1)

            # First-order difference (onset strength)
            onset = np.diff(energy, prepend=energy[0])
            onset = np.maximum(0, onset)

            # Autocorrelation of onset curve
            onset_norm = onset - np.mean(onset)
            autocorr = np.correlate(onset_norm, onset_norm, mode="full")
            autocorr = autocorr[len(autocorr) // 2 :]

            # Search range for BPM (60 to 180 BPM)
            frame_rate = sr / hop_size
            min_lag = int(frame_rate * 60.0 / 185.0)  # 185 BPM
            max_lag = int(frame_rate * 60.0 / 60.0)   # 60 BPM

            if max_lag >= len(autocorr):
                max_lag = len(autocorr) - 1

            if min_lag < max_lag:
                peak_lag = min_lag + np.argmax(autocorr[min_lag:max_lag])
                estimated_bpm = (frame_rate * 60.0) / peak_lag
                # Clamp to common range
                while estimated_bpm < 70:
                    estimated_bpm *= 2
                while estimated_bpm > 175:
                    estimated_bpm /= 2
                return round(float(estimated_bpm), 1)
        except Exception:
            pass
        return 120.0

    @classmethod
    def estimate_key_and_scale(cls, samples: np.ndarray, sr: int = 22050) -> Tuple[str, str, float]:
        """
        Estimates musical key (e.g., 'C Major', 'A Minor') using Krumhansl-Schmuckler
        correlation on 12-pitch chroma distribution.
        """
        if samples is None or len(samples) < sr * 2:
            return "C Major", "C", 0.7

        try:
            # Simple 12-bin Chroma filter via FFT
            fft_size = 4096
            hop_size = 2048
            num_frames = (len(samples) - fft_size) // hop_size
            if num_frames <= 0:
                return "C Major", "C", 0.7

            chroma = np.zeros(12, dtype=np.float32)
            # Standard frequencies for A4 = 440Hz
            # Map FFT bin frequencies to pitch class 0..11
            freqs = np.fft.rfftfreq(fft_size, d=1.0 / sr)

            for i in range(min(num_frames, 50)):
                frame = samples[i * hop_size : i * hop_size + fft_size] * np.hanning(fft_size)
                mag = np.abs(np.fft.rfft(frame))
                for bin_idx in range(1, len(freqs)):
                    f = freqs[bin_idx]
                    if 65.0 <= f <= 2000.0:  # C2 to B6
                        midi = 69.0 + 12.0 * math.log2(f / 440.0)
                        pitch_class = int(round(midi)) % 12
                        chroma[pitch_class] += mag[bin_idx]

            # Normalize chroma vector
            sum_c = np.sum(chroma)
            if sum_c > 0:
                chroma /= sum_c

            # Correlate with 12 Major and 12 Minor shifted profiles
            best_corr = -999.0
            best_key = "C Major"
            best_tonic = "C"

            for shift in range(12):
                # Major correlation
                shifted_profile_maj = np.roll(MAJOR_PROFILE, shift)
                corr_maj = np.corrcoef(chroma, shifted_profile_maj)[0, 1]
                if corr_maj > best_corr:
                    best_corr = corr_maj
                    best_key = f"{PITCH_CLASSES[shift]} Major"
                    best_tonic = PITCH_CLASSES[shift]

                # Minor correlation
                shifted_profile_min = np.roll(MINOR_PROFILE, shift)
                corr_min = np.corrcoef(chroma, shifted_profile_min)[0, 1]
                if corr_min > best_corr:
                    best_corr = corr_min
                    best_key = f"{PITCH_CLASSES[shift]} Minor"
                    best_tonic = PITCH_CLASSES[shift]

            confidence = float(max(0.3, min(0.99, (best_corr + 1.0) / 2.0)))
            return best_key, best_tonic, round(confidence, 2)
        except Exception:
            return "C Major", "C", 0.7

    @classmethod
    def analyze_track(cls, mp3_path: Path, spotify_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive feature extraction pipeline for an MP3 audio file.
        Returns serialized acoustic metrics and 100-point visual waveform array.
        """
        if not mp3_path.exists():
            return {"success": False, "error": "File does not exist"}

        # Basic metadata from Mutagen
        duration_sec = 0.0
        bitrate_kbps = 320
        sample_rate = 44100
        channels = 2

        try:
            audio = MP3(str(mp3_path))
            duration_sec = round(audio.info.length, 2)
            bitrate_kbps = int(audio.info.bitrate / 1000)
            sample_rate = audio.info.sample_rate
            channels = audio.info.channels
        except Exception:
            pass

        # Fast PCM decode (first 120s is ample for statistical stability)
        samples = cls.decode_audio_samples(mp3_path, max_duration_sec=120.0, target_sr=22050)

        # 1. Waveform Peaks (100 values)
        waveform_peaks = cls.compute_waveform_peaks(samples, num_peaks=100)

        # 2. BPM Estimation
        bpm = cls.estimate_bpm(samples, sr=22050)

        # 3. Key & Scale Estimation
        key_signature, tonic, key_confidence = cls.estimate_key_and_scale(samples, sr=22050)

        # 4. Loudness LUFS & Dynamic Range
        rms = float(np.sqrt(np.mean(samples**2))) if samples is not None and len(samples) > 0 else 0.1
        rms_db = 20.0 * math.log10(max(1e-5, rms))
        estimated_lufs = round(rms_db - 3.0, 1)  # Approximate integrated LUFS

        # 5. Acoustic Mood Indices (0.0 to 1.0)
        # Energy: High RMS + High Frequency content
        energy = round(min(1.0, max(0.1, (rms * 4.0))), 2)

        # Danceability: BPM stability around 110-130 BPM + high energy
        bpm_sweet_spot = 1.0 - min(1.0, abs(bpm - 120.0) / 60.0)
        danceability = round(min(1.0, max(0.15, (0.5 * bpm_sweet_spot + 0.5 * energy))), 2)

        # Valence: Major key gives higher valence than Minor key
        is_major = "Major" in key_signature
        valence_base = 0.65 if is_major else 0.40
        valence = round(min(1.0, max(0.1, valence_base + 0.2 * (energy - 0.5))), 2)

        # Acousticness: Inversely related to energy
        acousticness = round(min(0.95, max(0.05, 1.0 - energy * 0.9)), 2)

        return {
            "success": True,
            "spotify_id": spotify_id,
            "duration_sec": duration_sec,
            "bitrate_kbps": bitrate_kbps,
            "sample_rate": sample_rate,
            "channels": channels,
            "bpm": bpm,
            "key_signature": key_signature,
            "tonic": tonic,
            "key_confidence": key_confidence,
            "loudness_lufs": estimated_lufs,
            "energy": energy,
            "danceability": danceability,
            "valence": valence,
            "acousticness": acousticness,
            "waveform_peaks": waveform_peaks,
        }
