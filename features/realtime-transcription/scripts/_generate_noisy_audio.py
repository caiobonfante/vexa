#!/usr/bin/env python3
"""
Generate noisy test audio files for transcription pipeline testing.

Dependencies: numpy (+ Python stdlib: struct, wave, os)
No scipy, no external audio packages.

Outputs (all 16kHz mono 16-bit PCM WAV):
  audio/noise-office.wav          -- 90s simulated office noise
  audio/noise-cafe.wav            -- 90s simulated cafe ambience
  audio/noisy-monologue-office.wav -- long-monologue.wav mixed with office noise @ SNR=10dB
  audio/noisy-monologue-cafe.wav   -- long-monologue.wav mixed with cafe noise  @ SNR=10dB
  audio/noisy-with-silence.wav     -- medium-paragraph.wav with 30s noise-only gap in middle @ SNR=10dB
  + corresponding .txt ground-truth files
"""

import os
import struct
import wave
import numpy as np

RATE = 16000
DURATION_NOISE = 90  # seconds for standalone noise files
SNR_DB = 10


# ---------------------------------------------------------------------------
# WAV I/O helpers (struct-based, no external packages)
# ---------------------------------------------------------------------------

def read_wav(path: str) -> tuple:
    """Read a WAV file and return (samples_float64, sample_rate)."""
    with wave.open(path, "r") as wf:
        assert wf.getnchannels() == 1, f"Expected mono, got {wf.getnchannels()} channels"
        assert wf.getsampwidth() == 2, f"Expected 16-bit, got {wf.getsampwidth()*8}-bit"
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = np.array(struct.unpack(f"<{n}h", raw), dtype=np.float64) / 32768.0
    return samples, sr


def write_wav(path: str, samples: np.ndarray, rate: int = RATE):
    """Write float64 samples to a 16-bit mono WAV using struct."""
    # Clip and convert to int16
    clipped = np.clip(samples, -1.0, 1.0)
    int_samples = (clipped * 32767).astype(np.int16)
    raw = struct.pack(f"<{len(int_samples)}h", *int_samples)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(raw)
    dur = len(int_samples) / rate
    size_kb = os.path.getsize(path) / 1024
    print(f"  wrote {path}  ({dur:.1f}s, {size_kb:.0f} KB)")


# ---------------------------------------------------------------------------
# Resampling (simple linear interpolation -- no scipy required)
# ---------------------------------------------------------------------------

def resample_linear(samples: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    """Resample using linear interpolation. Good enough for test audio."""
    if orig_rate == target_rate:
        return samples
    duration = len(samples) / orig_rate
    n_out = int(duration * target_rate)
    x_old = np.linspace(0, duration, len(samples), endpoint=False)
    x_new = np.linspace(0, duration, n_out, endpoint=False)
    return np.interp(x_new, x_old, samples)


# ---------------------------------------------------------------------------
# Noise generators
# ---------------------------------------------------------------------------

def pink_noise(n_samples: int, rng: np.random.RandomState) -> np.ndarray:
    """Generate pink noise (1/f) using the Voss-McCartney algorithm."""
    # Use 16 rows for good quality
    n_rows = 16
    n_cols = n_samples
    # Generate white noise rows, each updated at different rates
    out = np.zeros(n_cols, dtype=np.float64)
    rows = rng.randn(n_rows)
    row_sum = rows.sum()
    out[0] = row_sum
    for i in range(1, n_cols):
        # Find which row to update (trailing zeros of index)
        idx = 0
        x = i
        while x & 1 == 0 and idx < n_rows - 1:
            idx += 1
            x >>= 1
        row_sum -= rows[idx]
        rows[idx] = rng.randn()
        row_sum += rows[idx]
        out[i] = row_sum + rng.randn()  # add white component
    # Normalize
    out /= np.abs(out).max() + 1e-10
    return out


def brownian_noise(n_samples: int, rng: np.random.RandomState) -> np.ndarray:
    """Generate brownian (red) noise by integrating white noise."""
    white = rng.randn(n_samples)
    brown = np.cumsum(white)
    # High-pass filter to remove DC drift: subtract running mean
    window = min(RATE, n_samples)
    if window > 1:
        kernel = np.ones(window) / window
        # Pad and convolve manually
        padded = np.concatenate([np.zeros(window // 2), brown, np.zeros(window // 2)])
        running_mean = np.convolve(padded, kernel, mode="valid")[:n_samples]
        brown = brown - running_mean
    brown /= np.abs(brown).max() + 1e-10
    return brown


def keyboard_clicks(n_samples: int, rng: np.random.RandomState) -> np.ndarray:
    """Simulate sporadic keyboard click sounds."""
    out = np.zeros(n_samples, dtype=np.float64)
    # Average ~3 clicks per second
    n_clicks = int(3 * n_samples / RATE)
    positions = rng.randint(0, n_samples, size=n_clicks)
    click_len = int(0.003 * RATE)  # 3ms click
    for pos in positions:
        end = min(pos + click_len, n_samples)
        t = np.arange(end - pos) / RATE
        # Short burst at ~2kHz with exponential decay
        click = np.sin(2 * np.pi * 2000 * t) * np.exp(-t * 1500)
        # Randomize amplitude
        click *= rng.uniform(0.02, 0.08)
        out[pos:end] += click
    return out


def low_hum(n_samples: int) -> np.ndarray:
    """Generate low-frequency electrical hum (50/60 Hz + harmonics)."""
    t = np.arange(n_samples, dtype=np.float64) / RATE
    hum = (0.3 * np.sin(2 * np.pi * 50 * t) +
           0.15 * np.sin(2 * np.pi * 100 * t) +
           0.08 * np.sin(2 * np.pi * 150 * t))
    return hum * 0.05  # Keep it subtle


def random_bursts(n_samples: int, rng: np.random.RandomState) -> np.ndarray:
    """Simulate random ambient bursts (clinking, murmur swells)."""
    out = np.zeros(n_samples, dtype=np.float64)
    # ~0.5 bursts per second
    n_bursts = max(1, int(0.5 * n_samples / RATE))
    positions = rng.randint(0, max(1, n_samples - RATE), size=n_bursts)
    for pos in positions:
        burst_len = rng.randint(int(0.05 * RATE), int(0.4 * RATE))
        end = min(pos + burst_len, n_samples)
        actual_len = end - pos
        t = np.arange(actual_len, dtype=np.float64) / RATE
        # Filtered noise burst with envelope
        envelope = np.sin(np.pi * np.arange(actual_len) / actual_len)  # smooth rise/fall
        freq = rng.uniform(300, 1500)
        burst = np.sin(2 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))
        burst += 0.5 * rng.randn(actual_len)
        burst *= envelope * rng.uniform(0.01, 0.06)
        out[pos:end] += burst
    return out


# ---------------------------------------------------------------------------
# Composite noise generators
# ---------------------------------------------------------------------------

def generate_office_noise(n_samples: int, seed: int = 42) -> np.ndarray:
    """Office: pink noise + keyboard clicks + low electrical hum."""
    rng = np.random.RandomState(seed)
    pink = pink_noise(n_samples, rng) * 0.4
    keys = keyboard_clicks(n_samples, rng)
    hum = low_hum(n_samples)
    combined = pink + keys + hum
    combined /= np.abs(combined).max() + 1e-10
    return combined


def generate_cafe_noise(n_samples: int, seed: int = 123) -> np.ndarray:
    """Cafe: brownian noise + random ambient bursts."""
    rng = np.random.RandomState(seed)
    brown = brownian_noise(n_samples, rng) * 0.5
    bursts = random_bursts(n_samples, rng)
    # Add a gentle murmur layer (band-limited noise around speech frequencies)
    murmur_rng = np.random.RandomState(seed + 1)
    murmur = murmur_rng.randn(n_samples)
    # Simple low-pass: running average
    window = int(RATE / 800)  # ~800 Hz cutoff
    if window > 1:
        kernel = np.ones(window) / window
        murmur = np.convolve(murmur, kernel, mode="same")
    murmur *= 0.3
    combined = brown + bursts + murmur
    combined /= np.abs(combined).max() + 1e-10
    return combined


# ---------------------------------------------------------------------------
# Mixing
# ---------------------------------------------------------------------------

def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Mix speech and noise at the given SNR (dB). Noise is scaled to match."""
    # Compute RMS of speech (only non-silent parts)
    speech_rms = np.sqrt(np.mean(speech ** 2) + 1e-20)
    noise_rms = np.sqrt(np.mean(noise ** 2) + 1e-20)
    # Desired noise RMS
    target_noise_rms = speech_rms / (10 ** (snr_db / 20))
    scale = target_noise_rms / noise_rms
    mixed = speech + noise * scale
    # Normalize to prevent clipping
    peak = np.abs(mixed).max()
    if peak > 0.95:
        mixed *= 0.95 / peak
    return mixed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw", "synthetic", "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # --- Step 1: Generate standalone noise files ---
    print("Generating noise backgrounds (90s each)...")
    n_noise = DURATION_NOISE * RATE

    office = generate_office_noise(n_noise)
    write_wav(os.path.join(audio_dir, "noise-office.wav"), office)

    cafe = generate_cafe_noise(n_noise)
    write_wav(os.path.join(audio_dir, "noise-cafe.wav"), cafe)

    # --- Step 2: Load source speech files ---
    print("\nLoading source speech files...")
    mono_path = os.path.join(audio_dir, "long-monologue.wav")
    para_path = os.path.join(audio_dir, "medium-paragraph.wav")

    mono_samples, mono_sr = read_wav(mono_path)
    para_samples, para_sr = read_wav(para_path)

    # Resample to 16kHz
    mono_16k = resample_linear(mono_samples, mono_sr, RATE)
    para_16k = resample_linear(para_samples, para_sr, RATE)

    print(f"  long-monologue: {len(mono_16k)/RATE:.1f}s @ {RATE}Hz")
    print(f"  medium-paragraph: {len(para_16k)/RATE:.1f}s @ {RATE}Hz")

    # --- Step 3: Mix speech + noise at SNR=10dB ---
    print(f"\nMixing speech + noise at SNR={SNR_DB}dB...")

    # noisy-monologue-office: monologue + office noise
    office_for_mono = generate_office_noise(len(mono_16k), seed=42)
    noisy_mono_office = mix_at_snr(mono_16k, office_for_mono, SNR_DB)
    write_wav(os.path.join(audio_dir, "noisy-monologue-office.wav"), noisy_mono_office)

    # noisy-monologue-cafe: monologue + cafe noise
    cafe_for_mono = generate_cafe_noise(len(mono_16k), seed=123)
    noisy_mono_cafe = mix_at_snr(mono_16k, cafe_for_mono, SNR_DB)
    write_wav(os.path.join(audio_dir, "noisy-monologue-cafe.wav"), noisy_mono_cafe)

    # --- Step 4: noisy-with-silence (speech + 30s noise gap + speech) ---
    print("\nCreating noisy-with-silence (speech + 30s noise gap + speech)...")
    silence_samples = 30 * RATE  # 30 seconds of silence (noise only)

    # Split paragraph roughly in half
    half = len(para_16k) // 2
    first_half = para_16k[:half]
    second_half = para_16k[half:]

    # Build speech track: first_half + silence + second_half
    speech_track = np.concatenate([
        first_half,
        np.zeros(silence_samples),
        second_half
    ])

    # Generate cafe noise for the full length
    cafe_for_silence = generate_cafe_noise(len(speech_track), seed=456)
    noisy_silence = mix_at_snr(speech_track, cafe_for_silence, SNR_DB)
    write_wav(os.path.join(audio_dir, "noisy-with-silence.wav"), noisy_silence)

    # --- Step 5: Ground truth text files ---
    print("\nWriting ground truth text files...")

    mono_txt = os.path.join(audio_dir, "long-monologue.txt")
    para_txt = os.path.join(audio_dir, "medium-paragraph.txt")

    # Read existing ground truth
    with open(mono_txt, "r") as f:
        mono_text = f.read().strip()
    with open(para_txt, "r") as f:
        para_text = f.read().strip()

    gt_files = {
        "noisy-monologue-office.txt": (
            f"[Source: long-monologue.wav mixed with office noise @ SNR={SNR_DB}dB]\n\n{mono_text}"
        ),
        "noisy-monologue-cafe.txt": (
            f"[Source: long-monologue.wav mixed with cafe noise @ SNR={SNR_DB}dB]\n\n{mono_text}"
        ),
        "noisy-with-silence.txt": (
            f"[Source: medium-paragraph.wav split with 30s noise-only gap @ SNR={SNR_DB}dB]\n"
            f"[Gap inserted at {half/RATE:.1f}s, resumes at {(half + silence_samples)/RATE:.1f}s]\n\n"
            f"{para_text}"
        ),
    }

    for fname, content in gt_files.items():
        path = os.path.join(audio_dir, fname)
        with open(path, "w") as f:
            f.write(content + "\n")
        print(f"  wrote {path}")

    print("\nDone. All files generated in", audio_dir)


if __name__ == "__main__":
    main()
