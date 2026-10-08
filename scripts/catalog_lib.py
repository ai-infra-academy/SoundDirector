"""Shared, dependency-free helpers for the sound-effects and background-music catalogs.

Standard library only. ffprobe is used opportunistically for audio inspection
and is never required.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import wave
from pathlib import Path

SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
SKILLS = ("sound-effects", "background-music")

ALLOWED_FORMATS = {".wav": "wav", ".mp3": "mp3", ".ogg": "ogg", ".flac": "flac"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SOURCES = {"elevenlabs", "suno", "comfyui", "original", "other"}
REVIEW_STATUSES = {"approved", "pending", "rejected"}

CATEGORIES = {
    "sound-effects": (
        "ui-clicks", "transitions", "notifications", "tech-ai",
        "impacts", "edu-diagrams", "ambience", "cinematic",
    ),
    "background-music": (
        "education", "technology", "suspense", "vlog", "reels",
        "cinematic", "corporate", "playful", "ambient-focus",
    ),
}

COMMON_REQUIRED = {
    "id": str, "title": str, "description": str, "category": str, "tags": list,
    "file": str, "duration_seconds": (int, float), "format": str,
    "source": str, "generation_prompt": str,
}
SKILL_REQUIRED = {
    "sound-effects": {"intensity": int, "attack": str, "tail": str, "use_cases": list},
    "background-music": {
        "moods": list, "energy": int, "instrumental": bool,
        "loopable": bool, "voiceover_friendly": bool, "preferred_content_types": list,
    },
}
OPTIONAL_TYPES = {
    "sample_rate": int, "channels": int, "peak_dbfs": (int, float),
    "integrated_lufs": (int, float), "bpm": (int, float), "sha256": str,
    "provenance": dict, "review": dict, "version": int, "timing": dict,
}
TIMING_FIELDS = ("onset_seconds", "peak_seconds", "end_seconds")
ATTACKS = {"soft", "medium", "sharp"}
TAILS = {"dry", "short", "medium", "long"}
DURATION_TOLERANCE_SECONDS = 0.1
DURATION_TOLERANCE_RATIO = 0.02


def skill_dir(skill: str, skills_root: Path | None = None) -> Path:
    if skill not in SKILLS:
        raise ValueError(f"unknown skill {skill!r}; expected one of {', '.join(SKILLS)}")
    return (skills_root or SKILLS_ROOT) / skill


def load_catalog(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_catalog(path: Path, catalog: dict) -> None:
    catalog["assets"] = sorted(catalog.get("assets", []), key=lambda a: a["id"])
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_asset_path(base: Path, rel: str) -> Path | None:
    """Resolve `rel` against the skill directory; None if it is unsafe or escapes it."""
    if not rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or "\\" in rel:
        return None
    parts = Path(rel).parts
    if ".." in parts or not parts or parts[0] != "assets":
        return None
    resolved = (base / rel).resolve()
    try:
        resolved.relative_to((base / "assets").resolve())
    except ValueError:
        return None
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_audio(path: Path) -> dict | None:
    """Return duration/sample_rate/channels, via ffprobe or the wave module. None if unknown."""
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=sample_rate,channels:format=duration",
                 "-of", "json", str(path)],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout
            data = json.loads(out)
            stream = (data.get("streams") or [{}])[0]
            duration = data.get("format", {}).get("duration")
            if duration is not None:
                return {
                    "duration_seconds": round(float(duration), 3),
                    "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
                    "channels": stream.get("channels"),
                }
        except (subprocess.SubprocessError, ValueError, KeyError, OSError):
            pass
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path)) as wf:
                return {
                    "duration_seconds": round(wf.getnframes() / wf.getframerate(), 3),
                    "sample_rate": wf.getframerate(),
                    "channels": wf.getnchannels(),
                }
        except (wave.Error, EOFError, OSError):
            return None
    return None


def duration_matches(declared: float, measured: float) -> bool:
    tolerance = max(DURATION_TOLERANCE_SECONDS, declared * DURATION_TOLERANCE_RATIO)
    return abs(declared - measured) <= tolerance


def _type_name(expected) -> str:
    if isinstance(expected, tuple):
        return "number"
    return {str: "string", int: "integer", list: "array", dict: "object", bool: "boolean"}[expected]


def _is_type(value, expected) -> bool:
    if expected in (int, (int, float)) and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _timing_errors(label: str, timing: dict, duration) -> list[str]:
    errors = []
    marks = []
    for key in TIMING_FIELDS:
        value = timing.get(key)
        if not _is_type(value, (int, float)):
            errors.append(f"{label}: timing.{key} must be a number")
        else:
            marks.append(value)
    if not errors:
        limit = duration + DURATION_TOLERANCE_SECONDS if _is_type(duration, (int, float)) else math.inf
        if not 0 <= marks[0] <= marks[1] <= marks[2] <= limit:
            errors.append(f"{label}: timing must satisfy 0 <= onset <= peak <= end <= duration")
    return errors


def validate_catalog(skill: str, base: Path, check_audio: bool = True) -> list[str]:
    """Validate one skill's catalog.json and assets/ directory. Returns a list of errors."""
    errors: list[str] = []
    catalog_path = base / "catalog.json"
    if not catalog_path.is_file():
        return [f"{skill}: missing {catalog_path}"]
    try:
        catalog = load_catalog(catalog_path)
    except json.JSONDecodeError as exc:
        return [f"{skill}: catalog.json is not valid JSON: {exc}"]
    if not isinstance(catalog, dict):
        return [f"{skill}: catalog.json must be a JSON object"]

    if catalog.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{skill}: schema_version must be {SCHEMA_VERSION!r}")
    if catalog.get("skill") != skill:
        errors.append(f"{skill}: catalog 'skill' must be {skill!r}")
    assets = catalog.get("assets")
    if not isinstance(assets, list):
        return errors + [f"{skill}: 'assets' must be an array"]

    required = {**COMMON_REQUIRED, **SKILL_REQUIRED[skill]}
    seen_ids: set[str] = set()
    seen_files: dict[str, str] = {}
    hashes: dict[str, str] = {}
    catalogued: set[Path] = set()

    for index, asset in enumerate(assets):
        label = f"{skill}[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label}: asset must be an object")
            continue
        asset_id = asset.get("id")
        if isinstance(asset_id, str):
            label = f"{skill}:{asset_id}"

        for key, expected in required.items():
            if key not in asset:
                errors.append(f"{label}: missing required field '{key}'")
            elif not _is_type(asset[key], expected):
                errors.append(f"{label}: '{key}' must be {_type_name(expected)}")
        for key, expected in OPTIONAL_TYPES.items():
            if key in asset and asset[key] is not None and not _is_type(asset[key], expected):
                errors.append(f"{label}: '{key}' must be {_type_name(expected)}")

        if isinstance(asset_id, str):
            if not ID_PATTERN.match(asset_id):
                errors.append(f"{label}: id must be lowercase kebab-case")
            if asset_id in seen_ids:
                errors.append(f"{label}: duplicate id")
            seen_ids.add(asset_id)

        if asset.get("category") not in CATEGORIES[skill]:
            errors.append(f"{label}: unknown category {asset.get('category')!r}")
        if asset.get("source") not in SOURCES:
            errors.append(f"{label}: source must be one of {sorted(SOURCES)}")
        if isinstance(asset.get("tags"), list) and not all(isinstance(t, str) and t for t in asset["tags"]):
            errors.append(f"{label}: tags must be non-empty strings")
        if isinstance(asset.get("duration_seconds"), (int, float)) and asset["duration_seconds"] <= 0:
            errors.append(f"{label}: duration_seconds must be positive")
        timing = asset.get("timing")
        if isinstance(timing, dict):
            errors.extend(_timing_errors(label, timing, asset.get("duration_seconds")))
        review = asset.get("review")
        if isinstance(review, dict) and review.get("status") not in REVIEW_STATUSES:
            errors.append(f"{label}: review.status must be one of {sorted(REVIEW_STATUSES)}")

        if skill == "sound-effects":
            if _is_type(asset.get("intensity"), int) and not 1 <= asset["intensity"] <= 5:
                errors.append(f"{label}: intensity must be 1-5")
            if "attack" in asset and asset["attack"] not in ATTACKS:
                errors.append(f"{label}: attack must be one of {sorted(ATTACKS)}")
            if "tail" in asset and asset["tail"] not in TAILS:
                errors.append(f"{label}: tail must be one of {sorted(TAILS)}")
        else:
            if _is_type(asset.get("energy"), int) and not 1 <= asset["energy"] <= 5:
                errors.append(f"{label}: energy must be 1-5")
            bpm = asset.get("bpm")
            if _is_type(bpm, (int, float)) and bpm <= 0:
                errors.append(f"{label}: bpm must be positive when present")

        rel = asset.get("file")
        if not isinstance(rel, str):
            continue
        path = resolve_asset_path(base, rel)
        if path is None:
            errors.append(f"{label}: file {rel!r} must be a relative path inside assets/ without '..'")
            continue
        if rel in seen_files:
            errors.append(f"{label}: file {rel!r} already used by {seen_files[rel]}")
        seen_files[rel] = asset_id or label
        expected_format = ALLOWED_FORMATS.get(path.suffix.lower())
        if expected_format is None:
            errors.append(f"{label}: format {path.suffix!r} not allowed ({', '.join(ALLOWED_FORMATS)})")
        elif asset.get("format") != expected_format:
            errors.append(f"{label}: 'format' must be {expected_format!r} for {path.name}")
        if not path.is_file():
            errors.append(f"{label}: audio file not found: {rel}")
            continue
        catalogued.add(path)

        if not check_audio:
            continue
        digest = sha256_file(path)
        if asset.get("sha256") and asset["sha256"] != digest:
            errors.append(f"{label}: sha256 does not match file contents")
        if digest in hashes:
            errors.append(f"{label}: identical audio to {hashes[digest]}")
        hashes[digest] = asset_id or label
        info = probe_audio(path)
        declared = asset.get("duration_seconds")
        if info and isinstance(declared, (int, float)) and not duration_matches(declared, info["duration_seconds"]):
            errors.append(
                f"{label}: duration_seconds {declared} differs from measured {info['duration_seconds']}"
            )

    assets_dir = base / "assets"
    if assets_dir.is_dir():
        for path in sorted(assets_dir.rglob("*")):
            if path.is_file() and path.name != ".gitkeep" and path.resolve() not in catalogued:
                errors.append(f"{skill}: uncatalogued file in assets/: {path.relative_to(base)}")
    return errors
