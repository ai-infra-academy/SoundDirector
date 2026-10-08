"""Timing marks: analyze_audio measurement and catalog validation of `timing`."""

import math
import struct
import wave

from helpers import SAMPLE_RATE, SkillsTestCase, sfx_asset

import analyze_audio


def write_burst(path, silence_before=0.3, burst=0.2, silence_after=0.5, rate=SAMPLE_RATE):
    """Silence, a loud sine burst, then silence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    frames += [0] * int(silence_before * rate)
    frames += [int(20000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(int(burst * rate))]
    frames += [0] * int(silence_after * rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(struct.pack("<h", f) for f in frames))
    return path


class AnalyzeAudioTests(SkillsTestCase):
    def test_burst_marks(self):
        path = write_burst(self.env.root / "burst.wav")
        timing = analyze_audio.analyze(path)
        self.assertAlmostEqual(timing["onset_seconds"], 0.3, delta=0.02)
        self.assertTrue(0.3 <= timing["peak_seconds"] <= 0.5)
        self.assertAlmostEqual(timing["end_seconds"], 0.5, delta=0.02)
        self.assertEqual(timing["method"], "auto-envelope")

    def test_deterministic(self):
        path = write_burst(self.env.root / "burst.wav")
        self.assertEqual(analyze_audio.analyze(path), analyze_audio.analyze(path))

    def test_silent_file_is_rejected(self):
        path = self.env.root / "silent.wav"
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"\x00\x00" * SAMPLE_RATE)
        with self.assertRaisesRegex(ValueError, "no audible content"):
            analyze_audio.analyze(path)


class TimingValidationTests(SkillsTestCase):
    def _validate(self, timing):
        asset = sfx_asset(duration_seconds=0.5, timing=timing)
        self.env.install("sound-effects", [asset])
        return self.env.validate("sound-effects")

    def test_valid_timing(self):
        self.assertEqual(self._validate({"onset_seconds": 0.0, "peak_seconds": 0.1, "end_seconds": 0.4}), [])

    def test_out_of_order(self):
        errors = self._validate({"onset_seconds": 0.3, "peak_seconds": 0.1, "end_seconds": 0.4})
        self.assertErrorContains(errors, "timing must satisfy")

    def test_beyond_duration(self):
        errors = self._validate({"onset_seconds": 0.0, "peak_seconds": 0.1, "end_seconds": 2.0})
        self.assertErrorContains(errors, "timing must satisfy")

    def test_missing_mark(self):
        errors = self._validate({"onset_seconds": 0.0, "end_seconds": 0.4})
        self.assertErrorContains(errors, "timing.peak_seconds must be a number")
