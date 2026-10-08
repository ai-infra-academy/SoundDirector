#!/usr/bin/env python3
"""Apply review-decisions.json (exported from staging/review.html) to staged record.json files.

  python3 scripts/apply_review.py ~/Downloads/review-decisions.json
  python3 scripts/build_catalog.py --skill sound-effects
  python3 scripts/build_catalog.py --skill background-music

Only the review fields (and, for music, the chosen take) are changed. Records not
mentioned in the decisions file are left untouched.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_lib import ID_PATTERN, REPO_ROOT, SKILLS  # noqa: E402


def apply(decisions: list[dict], staging: Path, reviewer: str, today: str) -> tuple[int, list[str]]:
    changed, problems = 0, []
    for d in decisions:
        skill, asset_id, status = d.get("skill"), d.get("id"), d.get("status")
        if skill not in SKILLS or not isinstance(asset_id, str) or not ID_PATTERN.match(asset_id):
            problems.append(f"invalid decision entry: {d!r}")
            continue
        if status not in ("approved", "rejected"):
            problems.append(f"{asset_id}: status must be approved or rejected")
            continue
        path = staging / skill / asset_id / "record.json"
        if not path.is_file():
            problems.append(f"{asset_id}: no staged record at {path}")
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        review = record.setdefault("review", {})
        review.update({"status": status, "reviewer": reviewer, "reviewed_at": today,
                       "notes": str(d.get("notes", ""))})
        if record.get("takes"):
            take = d.get("take", 1)
            if not isinstance(take, int) or not 1 <= take <= len(record["takes"]):
                problems.append(f"{asset_id}: take {take!r} does not exist")
                continue
            chosen = record["takes"][take - 1]
            record["staged_file"] = chosen["file"]
            record.setdefault("provenance", {})["output_id"] = chosen.get("output_id")
        if skill == "background-music":
            review["vocals_detected"] = bool(d.get("vocals"))
            review["voiceover_checked"] = bool(d.get("voiceover"))
            review["loop_tested"] = bool(d.get("loop"))
        elif record.get("loop_intended"):
            review["loop_tested"] = bool(d.get("loop"))
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        changed += 1
    return changed, problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("decisions", type=Path)
    p.add_argument("--staging", type=Path, default=REPO_ROOT / "staging")
    p.add_argument("--reviewer", default="maintainer")
    args = p.parse_args(argv)
    data = json.loads(args.decisions.read_text(encoding="utf-8"))
    decisions = data.get("decisions", []) if isinstance(data, dict) else []
    changed, problems = apply(decisions, args.staging, args.reviewer, dt.date.today().isoformat())
    for line in problems:
        print(f"skip  {line}")
    print(f"updated {changed} record(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
