"""Shared fixtures for the catalog script tests (standard library only)."""

from __future__ import annotations

import contextlib
import io
import json
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import catalog_lib  # noqa: E402

SAMPLE_RATE = 8000


def write_wav(path: Path, duration: float = 0.5, freq: float | None = 440.0,
              sample_rate: int = SAMPLE_RATE) -> Path:
    """Write a mono 16-bit WAV of exactly `duration` seconds (sine, or silence if freq is None)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(duration * sample_rate))
    if freq is None:
        data = b"\x00\x00" * frames
    else:
        data = b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / sample_rate)))
            for i in range(frames)
        )
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data)
    return path


def sfx_asset(asset_id: str = "ui-click-soft-001", **overrides) -> dict:
    asset = {
        "id": asset_id,
        "title": "Soft Digital Click",
        "description": "Short unobtrusive UI selection click for technical presentations.",
        "category": "ui-clicks",
        "tags": ["click", "subtle", "selection"],
        "use_cases": ["slide selection"],
        "file": f"assets/ui-clicks/{asset_id}.wav",
        "duration_seconds": 0.5,
        "format": "wav",
        "intensity": 1,
        "attack": "sharp",
        "tail": "dry",
        "source": "original",
        "generation_prompt": "test fixture",
    }
    asset.update(overrides)
    return asset


def music_asset(asset_id: str = "education-calm-001", **overrides) -> dict:
    asset = {
        "id": asset_id,
        "title": "Quiet Circuit",
        "description": "Minimal warm electronic instrumental behind narration.",
        "category": "education",
        "tags": ["educational", "ambient"],
        "moods": ["calm", "focused"],
        "energy": 2,
        "instrumental": True,
        "loopable": False,
        "voiceover_friendly": True,
        "preferred_content_types": ["tutorial"],
        "file": f"assets/education/{asset_id}.wav",
        "duration_seconds": 1.0,
        "format": "wav",
        "source": "original",
        "generation_prompt": "test fixture",
    }
    asset.update(overrides)
    return asset


class TempSkills:
    """A temporary skills root with sound-effects/ and background-music/ dirs."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.skills_root = self.root / "skills"
        self._freq = 300.0
        for skill in catalog_lib.SKILLS:
            (self.skills_root / skill / "assets").mkdir(parents=True)
            self.write_catalog(skill, [])

    def cleanup(self) -> None:
        self._tmp.cleanup()

    def base(self, skill: str) -> Path:
        return self.skills_root / skill

    def catalog_path(self, skill: str) -> Path:
        return self.base(skill) / "catalog.json"

    def write_catalog(self, skill: str, assets: list, /, **top) -> Path:
        data = {"schema_version": catalog_lib.SCHEMA_VERSION, "skill": skill, "assets": assets}
        data.update(top)
        path = self.catalog_path(skill)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def read_catalog(self, skill: str) -> dict:
        return json.loads(self.catalog_path(skill).read_text(encoding="utf-8"))

    def next_freq(self) -> float:
        self._freq += 37.0
        return self._freq

    def add_audio(self, skill: str, asset: dict, duration: float | None = None, freq: float | None = -1.0) -> Path:
        """Create the asset's audio file (unique sine per call unless freq given)."""
        if freq == -1.0:
            freq = self.next_freq()
        if duration is None:
            declared = asset.get("duration_seconds")
            duration = declared if isinstance(declared, (int, float)) and not isinstance(declared, bool) and declared > 0 else 0.5
        return write_wav(self.base(skill) / asset["file"], duration, freq)

    def install(self, skill: str, assets: list, with_audio: bool = True) -> None:
        if with_audio:
            for asset in assets:
                self.add_audio(skill, asset)
        self.write_catalog(skill, assets)

    def validate(self, skill: str, check_audio: bool = True) -> list[str]:
        return catalog_lib.validate_catalog(skill, self.base(skill), check_audio=check_audio)


class SkillsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.env = TempSkills()
        self.addCleanup(self.env.cleanup)

    def assertErrorContains(self, errors: list[str], fragment: str) -> None:
        self.assertTrue(any(fragment in e for e in errors),
                        f"expected an error containing {fragment!r}; got {errors}")


def run_main(main, argv: list[str]) -> tuple[int, str, str]:
    """Call a script's main(argv) capturing stdout/stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()
