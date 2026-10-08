#!/usr/bin/env python3
"""Promote human-approved staged assets into a skill's assets/ folder and catalog.json.

Staging layout (gitignored), one folder per asset:
  staging/<skill>/<asset-id>/record.json
  staging/<skill>/<asset-id>/<audio file named by record.json "staged_file">

Only records with review.status == "approved" are imported. Audio is copied to
assets/<category>/<asset-id>.<ext>; duration, sample rate, channels and sha256 are
measured, never trusted from the record. Music flags `loopable` and
`voiceover_friendly` are true only when the reviewer confirmed them in `review`.

  python3 scripts/build_catalog.py --skill sound-effects
  python3 scripts/build_catalog.py --skill background-music --ids education-calm-001 --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_audio import analyze  # noqa: E402
from catalog_lib import (  # noqa: E402
    TIMING_FIELDS,
    ALLOWED_FORMATS, CATEGORIES, ID_PATTERN, REPO_ROOT, SCHEMA_VERSION, SKILLS, load_catalog, probe_audio,
    save_catalog, sha256_file, skill_dir, validate_catalog,
)

COPY_FIELDS = {
    "sound-effects": ("intensity", "attack", "tail", "use_cases"),
    "background-music": ("moods", "energy", "preferred_content_types"),
}


def to_catalog_record(skill: str, record: dict, audio: Path, rel: str) -> dict:
    info = probe_audio(audio)
    if info is None:
        raise ValueError(f"cannot read audio duration for {audio} (install ffprobe for non-WAV files)")
    review = record.get("review", {})
    asset = {
        "id": record["id"],
        "title": record["title"],
        "description": record["description"],
        "category": record["category"],
        "tags": record["tags"],
        "file": rel,
        "format": ALLOWED_FORMATS[audio.suffix.lower()],
        "duration_seconds": info["duration_seconds"],
        "sample_rate": info["sample_rate"],
        "channels": info["channels"],
        "sha256": sha256_file(audio),
        "source": record["source"],
        "generation_prompt": record["generation_prompt"],
        "version": int(record.get("version", 1)),
    }
    for key in COPY_FIELDS[skill]:
        asset[key] = record[key]
    if skill == "background-music":
        asset["instrumental"] = review.get("vocals_detected") is False
        asset["loopable"] = review.get("loop_tested") is True
        asset["voiceover_friendly"] = review.get("voiceover_checked") is True
        if isinstance(review.get("bpm_measured"), (int, float)):
            asset["bpm"] = review["bpm_measured"]
    for key in ("peak_dbfs", "integrated_lufs"):
        if isinstance(review.get(key), (int, float)):
            asset[key] = review[key]
    timing = analyze(audio)
    timing.update({k: v for k, v in (record.get("timing") or {}).items()
                   if k in TIMING_FIELDS and isinstance(v, (int, float))})
    if record.get("timing"):
        timing["method"] = "manual-override"
    asset["timing"] = timing
    provenance = record.get("provenance", {})
    asset["provenance"] = {k: provenance[k] for k in
                           ("provider", "tool", "model", "generated_at", "output_id") if k in provenance}
    asset["review"] = {k: review[k] for k in ("status", "reviewer", "reviewed_at", "notes") if k in review}
    return asset


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skill", choices=SKILLS, required=True)
    p.add_argument("--staging", type=Path, help="default: staging/<skill>")
    p.add_argument("--skills-root", type=Path)
    p.add_argument("--ids", nargs="*", help="only import these asset ids")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    base = skill_dir(args.skill, args.skills_root)
    staging = args.staging or REPO_ROOT / "staging" / args.skill
    catalog_path = base / "catalog.json"
    catalog = (load_catalog(catalog_path) if catalog_path.is_file()
               else {"schema_version": SCHEMA_VERSION, "skill": args.skill, "assets": []})
    by_id = {a["id"]: a for a in catalog["assets"]}

    imported, skipped = [], []
    for record_path in sorted(staging.glob("*/record.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        asset_id = record.get("id", record_path.parent.name)
        if args.ids and asset_id not in args.ids:
            continue
        if record.get("review", {}).get("status") != "approved":
            skipped.append(f"{asset_id}: review.status is not 'approved'")
            continue
        if not (isinstance(asset_id, str) and ID_PATTERN.match(asset_id)
                and record.get("category") in CATEGORIES[args.skill]):
            skipped.append(f"{asset_id}: invalid id or unknown category {record.get('category')!r}")
            continue
        audio = record_path.parent / record.get("staged_file", "")
        if not audio.is_file() or audio.suffix.lower() not in ALLOWED_FORMATS:
            skipped.append(f"{asset_id}: staged audio missing or unsupported format")
            continue
        rel = f"assets/{record['category']}/{asset_id}{audio.suffix.lower()}"
        try:
            asset = to_catalog_record(args.skill, record, audio, rel)
        except (KeyError, ValueError) as exc:
            skipped.append(f"{asset_id}: {exc}")
            continue
        if not args.dry_run:
            target = base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(audio, target)
        by_id[asset_id] = asset
        imported.append(asset_id)

    for line in skipped:
        print(f"skip  {line}")
    print(f"{'would import' if args.dry_run else 'imported'} {len(imported)} asset(s): {', '.join(imported) or '-'}")
    if args.dry_run or not imported:
        return 0
    catalog["assets"] = list(by_id.values())
    save_catalog(catalog_path, catalog)
    errors = validate_catalog(args.skill, base)
    for err in errors:
        print(f"  - {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
