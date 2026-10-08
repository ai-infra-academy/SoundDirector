import json
import unittest
from collections import Counter

from helpers import REPO_ROOT

import catalog_lib

EXPECTED = {
    "sound-effects": ("sfx-inventory.json", {
        "ui-clicks": 30, "transitions": 30, "notifications": 25, "tech-ai": 30,
        "impacts": 25, "edu-diagrams": 25, "ambience": 15, "cinematic": 20}),
    "background-music": ("music-inventory.json", {
        "education": 15, "technology": 10, "suspense": 10, "vlog": 10, "reels": 10,
        "cinematic": 10, "corporate": 5, "playful": 5, "ambient-focus": 5}),
}


def load_items(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("items", "assets", "candidates", "inventory"):
            if isinstance(data.get(key), list):
                return data[key]
        raise AssertionError(f"{path.name}: no list of items found (keys: {sorted(data)})")
    return data


class PlanningInventoryTests(unittest.TestCase):
    def check(self, skill):
        filename, expected = EXPECTED[skill]
        path = REPO_ROOT / "planning" / filename
        if not path.is_file():
            self.skipTest(f"planning/{filename} not present")
        items = load_items(path)
        ids = [item["id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        bad = [i for i in ids if not catalog_lib.ID_PATTERN.match(i)]
        self.assertEqual(bad, [], "ids not matching ID_PATTERN")
        counts = Counter(item["category"] for item in items)
        self.assertEqual(set(counts), set(catalog_lib.CATEGORIES[skill]))
        self.assertEqual(dict(counts), expected)
        self.assertEqual(sum(expected.values()), 200 if skill == "sound-effects" else 80)

    def test_sfx_inventory(self):
        self.check("sound-effects")

    def test_music_inventory(self):
        self.check("background-music")

    def test_expected_categories_match_catalog_lib(self):
        for skill, (_, expected) in EXPECTED.items():
            self.assertEqual(set(expected), set(catalog_lib.CATEGORIES[skill]))


if __name__ == "__main__":
    unittest.main()
