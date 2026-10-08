#!/usr/bin/env python3
"""Deterministic keyword/tag search over the sound-effects and background-music catalogs.

Examples:
  python3 scripts/search_assets.py --skill sound-effects --query "subtle whoosh" --limit 5
  python3 scripts/search_assets.py --skill background-music --mood suspense --max-energy 3
  python3 scripts/search_assets.py --catalog path/to/catalog.json --query click --json

Only catalog entries whose audio file exists are returned as results. Entries with
missing files are reported separately and never presented as usable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_lib import SKILLS, load_catalog, resolve_asset_path, skill_dir  # noqa: E402

FIELD_WEIGHTS = {
    "title": 3.0, "tags": 3.0, "moods": 3.0, "category": 2.0, "use_cases": 2.0,
    "preferred_content_types": 2.0, "description": 1.0, "id": 1.0,
}
TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def stem(word: str) -> str:
    for suffix in ("ing", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def field_tokens(asset: dict, field: str) -> set[str]:
    value = asset.get(field)
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    return {stem(t) for t in tokens(str(value or ""))}


def score(asset: dict, query_terms: list[str]) -> float:
    if not query_terms:
        return 0.0
    total = 0.0
    for term in query_terms:
        best = max((w for f, w in FIELD_WEIGHTS.items() if term in field_tokens(asset, f)), default=0.0)
        total += best
    matched = sum(1 for t in query_terms if any(t in field_tokens(asset, f) for f in FIELD_WEIGHTS))
    return total + (2.0 if matched == len(query_terms) else 0.0)


def lower_set(values) -> set[str]:
    return {str(v).lower() for v in values or []}


def passes_filters(asset: dict, args: argparse.Namespace) -> bool:
    if args.category and asset.get("category") != args.category:
        return False
    if args.tag and not lower_set(args.tag) <= lower_set(asset.get("tags")):
        return False
    if args.mood and not lower_set(args.mood) & (lower_set(asset.get("moods")) | lower_set(asset.get("tags"))):
        return False
    for key, low, high in (("energy", args.min_energy, args.max_energy),
                           ("intensity", args.min_intensity, args.max_intensity),
                           ("duration_seconds", args.min_duration, args.max_duration)):
        value = asset.get(key)
        if (low is not None or high is not None) and not isinstance(value, (int, float)):
            return False
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
    for flag in ("instrumental", "loopable", "voiceover_friendly"):
        if getattr(args, flag) and asset.get(flag) is not True:
            return False
    return True


def search(catalog: dict, base: Path, args: argparse.Namespace) -> tuple[list[dict], list[dict]]:
    query_terms = [stem(t) for t in tokens(args.query or "")]
    ready, missing = [], []
    for asset in catalog.get("assets", []):
        if not passes_filters(asset, args):
            continue
        relevance = score(asset, query_terms)
        if query_terms and relevance == 0:
            continue
        path = resolve_asset_path(base, asset.get("file", ""))
        entry = {"score": relevance, "asset": asset, "path": str(path) if path else None}
        (ready if path and path.is_file() else missing).append(entry)
    order = lambda e: (-e["score"], e["asset"].get("id", ""))  # noqa: E731
    return sorted(ready, key=order), sorted(missing, key=order)


def format_result(entry: dict) -> str:
    a = entry["asset"]
    facts = [a.get("category", "?"), f"{a.get('duration_seconds', '?')}s"]
    for key in ("intensity", "energy"):
        if key in a:
            facts.append(f"{key} {a[key]}")
    if a.get("moods"):
        facts.append("moods: " + ", ".join(a["moods"]))
    for flag in ("loopable", "voiceover_friendly"):
        if a.get(flag) is True:
            facts.append(flag.replace("_", "-"))
    timing = a.get("timing") or {}
    if timing:
        facts.append(f"onset {timing.get('onset_seconds')}s, peak {timing.get('peak_seconds')}s, "
                     f"end {timing.get('end_seconds')}s")
    return (f"{a['id']} — {a.get('title', '')}\n"
            f"  {a.get('description', '')}\n"
            f"  [{' | '.join(facts)}]  tags: {', '.join(a.get('tags', []))}\n"
            f"  file: {a.get('file')}\n"
            f"  path: {entry['path']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--skill", choices=SKILLS)
    target.add_argument("--catalog", type=Path, help="path to a catalog.json (its directory is the skill root)")
    p.add_argument("--query", "-q", help="free-text keywords")
    p.add_argument("--category")
    p.add_argument("--tag", action="append", help="required tag (repeatable)")
    p.add_argument("--mood", action="append", help="mood to match (repeatable, any)")
    p.add_argument("--min-energy", type=int)
    p.add_argument("--max-energy", type=int)
    p.add_argument("--min-intensity", type=int)
    p.add_argument("--max-intensity", type=int)
    p.add_argument("--min-duration", type=float)
    p.add_argument("--max-duration", type=float)
    p.add_argument("--instrumental", action="store_true")
    p.add_argument("--loopable", action="store_true")
    p.add_argument("--voiceover-friendly", dest="voiceover_friendly", action="store_true")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog_path = args.catalog.resolve() if args.catalog else skill_dir(args.skill) / "catalog.json"
    base = catalog_path.parent
    name = args.skill or base.name
    if not catalog_path.is_file():
        print(f"error: catalog not found: {catalog_path}", file=sys.stderr)
        return 2
    try:
        catalog = load_catalog(catalog_path)
    except json.JSONDecodeError as exc:
        print(f"error: invalid catalog JSON in {catalog_path}: {exc}", file=sys.stderr)
        return 2

    ready, missing = search(catalog, base, args)
    ready = ready[: max(args.limit, 0)]
    total = len(catalog.get("assets", []))

    if args.json:
        print(json.dumps({
            "skill": name,
            "catalog_entries": total,
            "results": [{**e["asset"], "path": e["path"], "score": e["score"]} for e in ready],
            "missing_files": [{"id": e["asset"].get("id"), "file": e["asset"].get("file")} for e in missing],
        }, indent=2))
        return 0

    if total == 0:
        print(f"No assets are installed in the {name} catalog yet (0 entries). "
              "Nothing to return; do not reference any file from this library.")
        return 0
    if not ready:
        print(f"No installed {name} assets match this search ({total} catalog entries checked). "
              "Try fewer keywords or looser filters.")
    else:
        print(f"{len(ready)} {name} result(s):\n")
        print("\n\n".join(format_result(e) for e in ready))
    if missing:
        ids = ", ".join(e["asset"].get("id", "?") for e in missing)
        print(f"\nNote: {len(missing)} matching catalog entr{'y' if len(missing) == 1 else 'ies'} "
              f"have no audio file installed and were not returned: {ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
