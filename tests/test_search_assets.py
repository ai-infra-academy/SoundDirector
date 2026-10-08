import json
from pathlib import Path

from helpers import SkillsTestCase, music_asset, run_main, sfx_asset

import search_assets

SFX, MUSIC = "sound-effects", "background-music"


class SearchTestCase(SkillsTestCase):
    def search(self, skill, *argv, as_json=True):
        args = ["--catalog", str(self.env.catalog_path(skill)), *argv]
        if as_json:
            args.append("--json")
        code, out, err = run_main(search_assets.main, args)
        self.assertEqual(code, 0, err)
        return json.loads(out) if as_json else out

    def ids(self, result):
        return [r["id"] for r in result["results"]]


class SfxSearchTests(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.assets = [
            sfx_asset("whoosh-soft-002", title="Soft Whoosh", category="transitions",
                      tags=["whoosh", "subtle"], intensity=2, file="assets/transitions/whoosh-soft-002.wav"),
            sfx_asset("whoosh-soft-001", title="Soft Whoosh", category="transitions",
                      tags=["whoosh", "subtle"], intensity=2, file="assets/transitions/whoosh-soft-001.wav"),
            sfx_asset("impact-heavy-001", title="Heavy Impact", category="impacts",
                      description="Big boom with a subtle whoosh lead-in.",
                      tags=["boom", "hit"], intensity=5, file="assets/impacts/impact-heavy-001.wav"),
            sfx_asset("ui-click-soft-001", tags=["click", "subtle"], intensity=1),
        ]
        self.env.install(SFX, self.assets)

    def test_query_ranking_deterministic_with_id_ties(self):
        first = self.search(SFX, "--query", "subtle whoosh")
        self.assertEqual(self.ids(first)[:3], ["whoosh-soft-001", "whoosh-soft-002", "impact-heavy-001"])
        scores = [r["score"] for r in first["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(scores[0], scores[1])
        for _ in range(3):
            self.assertEqual(self.search(SFX, "--query", "subtle whoosh"), first)

    def test_stemming_matches_plural(self):
        self.assertIn("whoosh-soft-001", self.ids(self.search(SFX, "--query", "whooshes")))

    def test_limit(self):
        self.assertEqual(len(self.search(SFX, "--query", "subtle", "--limit", "2")["results"]), 2)

    def test_no_query_returns_all_sorted_by_id(self):
        self.assertEqual(self.ids(self.search(SFX, "--limit", "10")),
                         sorted(a["id"] for a in self.assets))

    def test_category_filter(self):
        self.assertEqual(self.ids(self.search(SFX, "--category", "impacts")), ["impact-heavy-001"])

    def test_tag_filter_requires_all(self):
        self.assertEqual(self.ids(self.search(SFX, "--tag", "subtle", "--tag", "click")), ["ui-click-soft-001"])
        self.assertEqual(self.search(SFX, "--tag", "SUBTLE", "--limit", "10")["results"].__len__(), 3)

    def test_max_intensity(self):
        ids = self.ids(self.search(SFX, "--max-intensity", "2", "--limit", "10"))
        self.assertNotIn("impact-heavy-001", ids)
        self.assertEqual(len(ids), 3)
        self.assertEqual(self.ids(self.search(SFX, "--min-intensity", "5")), ["impact-heavy-001"])

    def test_returned_paths_exist(self):
        for r in self.search(SFX, "--limit", "10")["results"]:
            self.assertTrue(Path(r["path"]).is_file(), r["path"])
            self.assertTrue(Path(r["path"]).resolve().is_relative_to(self.env.base(SFX).resolve()))

    def test_no_match_message(self):
        out = self.search(SFX, "--query", "xylophone", as_json=False)
        self.assertIn("No installed sound-effects assets match this search", out)
        self.assertEqual(self.search(SFX, "--query", "xylophone")["results"], [])

    def test_text_output_lists_results(self):
        out = self.search(SFX, "--query", "click", as_json=False)
        self.assertIn("ui-click-soft-001", out)
        self.assertIn("path: ", out)

    def test_missing_files_not_returned(self):
        ghost = sfx_asset("whoosh-ghost-001", title="Ghost Whoosh", tags=["whoosh"],
                          category="transitions", file="assets/transitions/whoosh-ghost-001.wav")
        unsafe = sfx_asset("whoosh-escape-001", title="Escape Whoosh", tags=["whoosh"], file="../x.wav")
        self.env.write_catalog(SFX, self.assets + [ghost, unsafe])
        result = self.search(SFX, "--query", "whoosh", "--limit", "10")
        self.assertNotIn("whoosh-ghost-001", self.ids(result))
        self.assertNotIn("whoosh-escape-001", self.ids(result))
        missing = {m["id"] for m in result["missing_files"]}
        self.assertEqual(missing, {"whoosh-ghost-001", "whoosh-escape-001"})
        out = self.search(SFX, "--query", "whoosh", as_json=False)
        self.assertIn("have no audio file installed and were not returned", out)
        self.assertIn("whoosh-ghost-001", out.split("Note:")[1])

    def test_only_missing_files(self):
        self.env.write_catalog(SFX, [sfx_asset("ui-click-gone-001")])
        out = self.search(SFX, "--query", "click", as_json=False)
        self.assertIn("No installed sound-effects assets match", out)
        self.assertIn("1 matching catalog entry have no audio file installed", out)


class MusicSearchTests(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.env.install(MUSIC, [
            music_asset("education-calm-001", energy=2, moods=["calm"], voiceover_friendly=True),
            music_asset("suspense-dark-001", category="suspense", energy=4, moods=["suspense", "dark"],
                        voiceover_friendly=False, file="assets/suspense/suspense-dark-001.wav"),
            music_asset("vlog-bright-001", category="vlog", energy=3, moods=["happy"], tags=["suspense"],
                        voiceover_friendly=False, loopable=True, file="assets/vlog/vlog-bright-001.wav"),
        ])

    def test_mood_filter_matches_moods_or_tags(self):
        self.assertEqual(self.ids(self.search(MUSIC, "--mood", "suspense")),
                         ["suspense-dark-001", "vlog-bright-001"])
        self.assertEqual(self.ids(self.search(MUSIC, "--mood", "calm", "--mood", "happy")),
                         ["education-calm-001", "vlog-bright-001"])

    def test_max_energy(self):
        self.assertEqual(self.ids(self.search(MUSIC, "--max-energy", "3")),
                         ["education-calm-001", "vlog-bright-001"])

    def test_voiceover_and_loopable_flags(self):
        self.assertEqual(self.ids(self.search(MUSIC, "--voiceover-friendly")), ["education-calm-001"])
        self.assertEqual(self.ids(self.search(MUSIC, "--loopable")), ["vlog-bright-001"])

    def test_intensity_filter_excludes_music(self):
        self.assertEqual(self.search(MUSIC, "--max-intensity", "5")["results"], [])

    def test_combined_filters_and_query(self):
        self.assertEqual(self.ids(self.search(MUSIC, "--query", "dark", "--category", "suspense")),
                         ["suspense-dark-001"])


class EmptyAndErrorTests(SearchTestCase):
    def test_empty_catalog_message(self):
        out = self.search(SFX, "--query", "click", as_json=False)
        self.assertIn("No assets are installed in the sound-effects catalog yet (0 entries)", out)
        result = self.search(SFX, "--query", "click")
        self.assertEqual((result["catalog_entries"], result["results"], result["missing_files"]), (0, [], []))

    def test_missing_catalog_path(self):
        code, _, err = run_main(search_assets.main, ["--catalog", str(self.env.root / "none.json")])
        self.assertEqual(code, 2)
        self.assertIn("catalog not found", err)

    def test_invalid_catalog_json(self):
        self.env.catalog_path(SFX).write_text("{oops")
        code, _, err = run_main(search_assets.main, ["--catalog", str(self.env.catalog_path(SFX))])
        self.assertEqual(code, 2)
        self.assertIn("invalid catalog JSON", err)

    def test_real_repo_skill_mode_runs(self):
        for skill in (SFX, MUSIC):
            code, out, _ = run_main(search_assets.main, ["--skill", skill, "--query", "subtle", "--json"])
            self.assertEqual(code, 0)
            for r in json.loads(out)["results"]:
                self.assertTrue(Path(r["path"]).is_file())
