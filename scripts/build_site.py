#!/usr/bin/env python3
"""Build the static browse-and-preview site (GitHub Pages) from both skill catalogs.

  python3 scripts/build_site.py                 # writes _site/
  python3 -m http.server -d _site 8000          # preview at http://localhost:8000

The site is site/ (HTML, CSS, JS) plus a generated data.js and a copy of each
catalogued audio file at skills/<skill>/<file>. Waveform previews are cached in
site/waveforms.json, keyed by sha256, so CI can build without ffmpeg. Run this
locally after adding assets and commit the updated cache.
"""

from __future__ import annotations

import argparse
import array
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_lib import REPO_ROOT, SKILLS, load_catalog, resolve_asset_path, skill_dir  # noqa: E402

SITE_SRC = REPO_ROOT / "site"
WAVE_CACHE = SITE_SRC / "waveforms.json"
BINS = 96
RATE = 8000
PUBLIC_FIELDS = (
    "id", "title", "description", "category", "tags", "duration_seconds", "format", "source",
    "generation_prompt", "sample_rate", "channels", "timing",
    "intensity", "attack", "tail", "use_cases",
    "moods", "energy", "instrumental", "loopable", "voiceover_friendly", "preferred_content_types", "bpm",
)


def _samples(path: Path) -> array.array | None:
    """Mono 16-bit samples at RATE Hz via ffmpeg, or the stdlib wave module for 16-bit WAV."""
    if shutil.which("ffmpeg"):
        proc = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
            capture_output=True, check=False)
        if proc.returncode == 0 and proc.stdout:
            data = array.array("h")
            data.frombytes(proc.stdout[: len(proc.stdout) // 2 * 2])
            return data
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                if wf.getsampwidth() != 2:
                    return None
                channels = wf.getnchannels()
                data = array.array("h")
                data.frombytes(wf.readframes(wf.getnframes()))
                return data[::channels] if channels > 1 else data
        except (wave.Error, EOFError):
            return None
    return None


def waveform(path: Path, bins: int = BINS) -> list[float] | None:
    """Peak per bin, scaled to the file's own maximum (0..1, two decimals)."""
    samples = _samples(path)
    if not samples:
        return None
    step = max(1, len(samples) // bins)
    peaks = [max((abs(s) for s in samples[i * step:(i + 1) * step]), default=0) for i in range(bins)]
    top = max(peaks) or 1
    return [round(p / top, 2) for p in peaks]


def build(out: Path, repo_url: str | None = None, skills_root: Path | None = None,
          copy_audio: bool = True, cache_path: Path = WAVE_CACHE) -> dict:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    used: dict[str, list[float]] = {}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in SITE_SRC.iterdir():
        if item.name != WAVE_CACHE.name and item.is_file():
            shutil.copy2(item, out / item.name)

    library: dict = {"repo_url": repo_url, "skills": {}}
    for skill in SKILLS:
        base = skill_dir(skill, skills_root)
        catalog = load_catalog(base / "catalog.json")
        assets = []
        for asset in catalog["assets"]:
            src = resolve_asset_path(base, asset["file"])
            if src is None or not src.is_file():
                continue
            public = {k: asset[k] for k in PUBLIC_FIELDS if k in asset}
            public["file"] = f"skills/{skill}/{asset['file']}"
            public["repo_path"] = f".claude/skills/{skill}/{asset['file']}"
            digest = asset.get("sha256")
            peaks = cache.get(digest) if digest else None
            if peaks is None:
                peaks = waveform(src)
            if peaks is not None and digest:
                used[digest] = peaks
            public["waveform"] = peaks
            if copy_audio:
                dest = out / public["file"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            assets.append(public)
        library["skills"][skill] = assets

    data = json.dumps(library, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (out / "data.js").write_text(f"window.SOUND_LIBRARY = {data};\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    if used != cache:
        cache_path.write_text(json.dumps(used, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return library


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=REPO_ROOT / "_site")
    p.add_argument("--repo-url", help="link shown in the site header, e.g. https://github.com/<you>/SoundDirector")
    p.add_argument("--skills-root", type=Path)
    p.add_argument("--no-audio", action="store_true", help="skip copying audio (metadata-only build)")
    args = p.parse_args(argv)
    library = build(args.out, args.repo_url, args.skills_root, copy_audio=not args.no_audio)
    counts = ", ".join(f"{k} {len(v)}" for k, v in library["skills"].items())
    missing = sum(1 for v in library["skills"].values() for a in v if a["waveform"] is None)
    print(f"wrote {args.out} ({counts}); {missing} asset(s) without waveform")
    return 0


if __name__ == "__main__":
    sys.exit(main())
