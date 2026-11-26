import subprocess

import imageio_ffmpeg
import librosa
import numpy as np


RATE = 16000
HOP = 256
MAX_DURATION = 3600
NOTES = ("C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B")
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PROFILES = np.array([np.roll(profile - profile.mean(), i) for profile in (MAJOR, MINOR) for i in range(12)])
PROFILES /= np.linalg.norm(PROFILES, axis=1, keepdims=True)
def decode_audio(path, rate, *, stereo=False, start=0, seconds=MAX_DURATION + 1):
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-ss", str(start), "-i", str(path),
               "-map", "0:a:0", "-t", str(seconds), "-f", "f32le",
               "-ac", "2" if stereo else "1", "-ar", str(rate), "pipe:1"]
    completed = subprocess.run(command, capture_output=True, timeout=120,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode or not completed.stdout:
        raise ValueError("无法解码音频文件。")
    signal = np.frombuffer(completed.stdout, dtype="<f4")
    if stereo:
        signal = signal.reshape(-1, 2).T
    if not np.isfinite(signal).all():
        raise ValueError("音频包含无效的采样值。")
    if not stereo and max(float(signal.max()), -float(signal.min())) < .0001:
        channels = decode_audio(path, rate, stereo=True, start=start, seconds=seconds)
        peaks = np.maximum(np.max(channels, axis=1), -np.min(channels, axis=1))
        # A phase-cancelled stereo mix can be audible even when its mono sum is silent.
        if peaks.max() >= .0001:
            return channels[int(np.argmax(peaks))].copy()
    return signal


def load_audio(path, rate=RATE, stereo=False):
    signal = decode_audio(path, rate, stereo=stereo)
    if signal.shape[-1] > MAX_DURATION * rate:
        raise ValueError("当前版本支持时长不超过 60 分钟的单个音频文件。")
    if signal.shape[-1] < rate:
        raise ValueError("请导入至少 1 秒的音频。")
    return signal


def export_stereo_audio(path, output, codec, rate=44100):
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
               "-t", str(MAX_DURATION + 1), "-ac", "2", "-ar", str(rate), "-c:a", codec, str(output)]
    completed = subprocess.run(command, capture_output=True, timeout=120,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        raise ValueError("无法转换立体声音频。")


def key_name(index):
    return f"{NOTES[index % 12]} {'小调' if index >= 12 else '大调'}"


def key_scores(values):
    centered = values - values.mean(axis=-1, keepdims=True)
    norms = np.maximum(np.linalg.norm(centered, axis=-1, keepdims=True), 1e-8)
    return (centered / norms) @ PROFILES.T


def evidence(scores, chosen, name):
    second = int(np.argmax(np.where(np.arange(len(scores)) == chosen, -np.inf, scores)))
    return {"score": round(float(scores[chosen]), 3), "alternative": name(second),
            "alternative_score": round(float(scores[second]), 3),
            "margin": round(float(scores[chosen] - scores[second]), 3)}


def boundary(start, end, label):
    return {"start": round(float(start), 3), "end": round(float(end), 3), "label": label}


def audible_portions(start, end, silences):
    for gap in silences:
        if gap["end"] <= start:
            continue
        if gap["start"] >= end:
            break
        if gap["start"] > start:
            yield start, gap["start"]
        start = max(start, gap["end"])
    if start < end:
        yield start, end


def energy_mask(levels):
    floor = max(.00008, float(np.quantile(levels, .90)) * .005)
    return levels >= floor


def silence_spans(active, duration):
    changes = np.flatnonzero(np.diff(np.r_[False, ~active, False]))
    return [(float(start * HOP / RATE), min(end * HOP / RATE, duration))
            for start, end in zip(changes[::2], changes[1::2])
            if (end - start) * HOP / RATE >= .40 and start * HOP / RATE < duration]


def harmony_summary(chroma, levels, active):
    scale = max(float(np.quantile(levels, .90)), 1e-6)
    weights = np.minimum(levels / scale, 1) ** .5 * active
    overall = key_scores(np.sum(chroma * weights, axis=1, dtype=np.float64))
    winner = int(np.argmax(overall))
    detail = evidence(overall, winner, key_name)
    return {"key": key_name(winner) if overall[winner] >= .38 else None,
            "strength": detail["score"], "key_evidence": detail, "source": "色度匹配"}


def estimated_tempo(intervals, minimum):
    periods = np.sort(intervals[(intervals > .2) & (intervals < 2)])
    if len(periods) < minimum:
        return None
    # Count time within a common tempo band so double-time beats cannot outvote by count alone.
    first = np.searchsorted(periods, periods / 1.08)
    last = np.searchsorted(periods, periods * 1.08, side="right")
    elapsed = np.r_[0, np.cumsum(periods, dtype=np.float64)]
    supported = np.where(last - first >= minimum, elapsed[last] - elapsed[first], 0.0)
    best = int(np.argmax(supported))
    if not supported[best]:
        return None
    return round(float(60 / np.median(periods[first[best]:last[best]])), 1)


def rhythm_and_harmony(y, positions=None, beat_source=None):
    duration = len(y) / RATE
    if np.max(np.abs(y)) < .0001:
        return ({"bpm": None, "beat_count": 0, "source": "静音"},
                {"key": None, "strength": None, "source": "静音"},
                [boundary(0, duration, "静音")])
    magnitude = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    power = np.square(magnitude)
    rms = librosa.feature.rms(S=magnitude, frame_length=2048)[0]
    beats, downbeats = np.empty(0), []
    source = "librosa"
    if positions is not None:
        beats, downbeats = positions
        beats = np.unique([float(x) for x in beats if 0 <= x <= duration])
        downbeats = sorted({round(float(x), 3) for x in downbeats if 0 <= x <= duration})
        source = beat_source or source
    if len(beats) < 4 and duration >= 4:
        mel = librosa.feature.melspectrogram(S=power, sr=RATE, n_mels=40)
        onset = librosa.onset.onset_strength(S=librosa.power_to_db(mel), sr=RATE, hop_length=HOP)
        _, frames = librosa.beat.beat_track(onset_envelope=onset, sr=RATE, hop_length=HOP)
        fallback = librosa.frames_to_time(frames, sr=RATE, hop_length=HOP)
        if len(fallback) > len(beats):
            beats, downbeats, source = fallback[fallback <= duration], [], "librosa"

    chroma = librosa.feature.chroma_stft(S=power, sr=RATE, n_fft=2048, hop_length=HOP, tuning=0.0)
    active = energy_mask(rms)
    silences = [boundary(start, end, "静音") for start, end in silence_spans(active, duration)]
    harmony = harmony_summary(chroma, rms, active)
    rhythm = {"bpm": estimated_tempo(np.diff(beats), 3), "source": source, "beat_count": len(beats)}
    if len(downbeats) > 3 and len(beats) > 3:
        bar_counts = [int(np.count_nonzero((beats >= a - .045) & (beats < b - .045)))
                      for a, b in zip(downbeats, downbeats[1:])]
        counts = {n: bar_counts.count(n) for n in set(bar_counts) if 2 <= n <= 12}
        if counts:
            n = max(counts, key=counts.get)
            if counts[n] > len(bar_counts) / 2:
                rhythm["beats_per_bar"] = n
    return rhythm, harmony, silences
