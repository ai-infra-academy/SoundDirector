#!/usr/bin/env python3
"""Measure timing marks in an audio file from its loudness envelope.

  onset_seconds  first moment the sound is clearly audible
  peak_seconds   the loudest moment (the hit/accent to sync to a visual event)
  end_seconds    when the tail decays below audibility

WAV is decoded with the standard library; other formats need ffmpeg.

  python3 scripts/analyze_audio.py path/to/file.wav [more files...]
"""

from __future__ import annotations

import array
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

WINDOW_SECONDS = 0.01
ONSET_BELOW_PEAK_DB = 30.0
END_BELOW_PEAK_DB = 40.0
FLOOR_DB = -60.0


def _decode_wav(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path)) as wf:
        width, channels, rate = wf.getsampwidth(), wf.getnchannels(), wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if width == 1:
        values = [(b - 128) / 128.0 for b in raw]
    elif width == 2:
        values = [v / 32768.0 for v in array.array("h", raw)]
    elif width == 3:
        values = [int.from_bytes(raw[i:i + 3], "little", signed=True) / 8388608.0
                  for i in range(0, len(raw), 3)]
    elif width == 4:
        values = [v / 2147483648.0 for v in array.array("i", raw)]
    else:
        raise ValueError(f"unsupported WAV sample width {width}")
    if sys.byteorder == "big" and width in (2, 4):
        raise ValueError("big-endian hosts are not supported")
    mono = [max(abs(s) for s in values[i:i + channels]) for i in range(0, len(values), channels)]
    return mono, rate


def _decode_ffmpeg(path: Path, rate: int = 22050) -> tuple[list[float], int]:
    if not shutil.which("ffmpeg"):
        raise ValueError(f"ffmpeg is required to analyze {path.suffix} files")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"],
        capture_output=True, check=True, timeout=120,
    ).stdout
    return [abs(v) / 32768.0 for v in array.array("h", raw)], rate


def envelope_db(samples: list[float], rate: int) -> list[float]:
    size = max(1, int(rate * WINDOW_SECONDS))
    out = []
    for start in range(0, len(samples), size):
        chunk = samples[start:start + size]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        out.append(20 * math.log10(rms) if rms > 0 else -120.0)
    return out


def analyze(path: Path) -> dict:
    samples, rate = _decode_wav(path) if path.suffix.lower() == ".wav" else _decode_ffmpeg(path)
    if not samples:
        raise ValueError(f"{path} contains no audio")
    env = envelope_db(samples, rate)
    duration = len(samples) / rate
    peak_index = max(range(len(env)), key=lambda i: env[i])
    peak_db = env[peak_index]
    if peak_db < FLOOR_DB:
        raise ValueError(f"{path} has no audible content (peak {peak_db:.1f} dBFS)")
    onset_threshold = max(peak_db - ONSET_BELOW_PEAK_DB, FLOOR_DB)
    end_threshold = max(peak_db - END_BELOW_PEAK_DB, FLOOR_DB)
    onset_index = next(i for i, v in enumerate(env) if v >= onset_threshold)
    end_index = max(i for i, v in enumerate(env) if v >= end_threshold)
    step = WINDOW_SECONDS
    return {
        "onset_seconds": round(onset_index * step, 3),
        "peak_seconds": round(min((peak_index + 0.5) * step, duration), 3),
        "end_seconds": round(min((end_index + 1) * step, duration), 3),
        "method": "auto-envelope",
    }


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print(__doc__.strip())
        return 2
    status = 0
    for name in paths:
        try:
            print(json.dumps({"file": name, **analyze(Path(name))}))
        except (ValueError, OSError, wave.Error, subprocess.SubprocessError) as exc:
            print(f"error: {name}: {exc}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
