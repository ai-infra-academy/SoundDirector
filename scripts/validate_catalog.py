#!/usr/bin/env python3
"""Validate skill catalogs: JSON, schema fields, unique IDs, categories, safe paths,
allowed formats, file existence, duplicate audio, and declared durations.

  python3 scripts/validate_catalog.py --all
  python3 scripts/validate_catalog.py --skill sound-effects
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_lib import SKILLS, load_catalog, skill_dir, validate_catalog  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true")
    target.add_argument("--skill", choices=SKILLS)
    p.add_argument("--skills-root", type=Path, help="override .claude/skills location (for tests)")
    p.add_argument("--no-audio-check", action="store_true", help="skip hashing and duration probing")
    args = p.parse_args(argv)

    failed = False
    for skill in (SKILLS if args.all else (args.skill,)):
        base = skill_dir(skill, args.skills_root)
        errors = validate_catalog(skill, base, check_audio=not args.no_audio_check)
        if errors:
            failed = True
            print(f"FAIL {skill}: {len(errors)} problem(s)")
            for err in errors:
                print(f"  - {err}")
        else:
            count = len(load_catalog(base / "catalog.json").get("assets", []))
            print(f"OK   {skill}: {count} asset(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
