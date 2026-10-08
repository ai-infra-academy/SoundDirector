import json
import unittest

from helpers import SkillsTestCase, music_asset, run_main, sfx_asset, write_wav, REPO_ROOT

import catalog_lib
import validate_catalog

SFX, MUSIC = "sound-effects", "background-music"


class ValidCatalogTests(SkillsTestCase):
    def test_empty_catalogs_pass(self):
        self.assertEqual(self.env.validate(SFX), [])
        self.assertEqual(self.env.validate(MUSIC), [])

    def test_valid_catalogs_with_audio_pass(self):
        self.env.install(SFX, [sfx_asset("ui-click-soft-001"), sfx_asset("ui-click-soft-002", intensity=5)])
        self.env.install(MUSIC, [music_asset()])
        self.assertEqual(self.env.validate(SFX), [])
        self.assertEqual(self.env.validate(MUSIC), [])

    def test_cli_all_ok(self):
        self.env.install(SFX, [sfx_asset()])
        code, out, _ = run_main(validate_catalog.main, ["--all", "--skills-root", str(self.env.skills_root)])
        self.assertEqual(code, 0, out)
        self.assertIn("OK   sound-effects: 1 asset(s)", out)
        self.assertIn("OK   background-music: 0 asset(s)", out)

    def test_cli_single_skill_failure(self):
        self.env.install(SFX, [sfx_asset()], with_audio=False)
        code, out, _ = run_main(validate_catalog.main,
                                ["--skill", SFX, "--skills-root", str(self.env.skills_root)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL sound-effects", out)
        self.assertIn("audio file not found", out)

    def test_gitkeep_ignored(self):
        (self.env.base(SFX) / "assets" / ".gitkeep").write_text("")
        self.assertEqual(self.env.validate(SFX), [])


class StructureTests(SkillsTestCase):
    def test_invalid_json(self):
        self.env.catalog_path(SFX).write_text("{not json", encoding="utf-8")
        self.assertErrorContains(self.env.validate(SFX), "not valid JSON")

    def test_top_level_not_object(self):
        self.env.catalog_path(SFX).write_text("[]", encoding="utf-8")
        self.assertErrorContains(self.env.validate(SFX), "must be a JSON object")

    def test_missing_catalog(self):
        self.env.catalog_path(SFX).unlink()
        self.assertErrorContains(self.env.validate(SFX), "missing")

    def test_wrong_schema_version(self):
        self.env.write_catalog(SFX, [], schema_version="0.9")
        self.assertErrorContains(self.env.validate(SFX), "schema_version")

    def test_wrong_skill_name(self):
        self.env.write_catalog(SFX, [], skill=MUSIC)
        self.assertErrorContains(self.env.validate(SFX), "catalog 'skill'")

    def test_assets_not_array(self):
        self.env.write_catalog(SFX, {})
        self.assertErrorContains(self.env.validate(SFX), "'assets' must be an array")

    def test_asset_not_object(self):
        self.env.write_catalog(SFX, ["nope"])
        self.assertErrorContains(self.env.validate(SFX), "asset must be an object")


class FieldTests(SkillsTestCase):
    def check(self, skill, asset, fragment, with_audio=True):
        self.env.install(skill, [asset], with_audio=with_audio)
        errors = self.env.validate(skill)
        self.assertErrorContains(errors, fragment)
        return errors

    def test_missing_common_required_fields(self):
        for field in catalog_lib.COMMON_REQUIRED:
            if field in ("file", "id"):
                continue
            with self.subTest(field=field):
                asset = sfx_asset()
                del asset[field]
                self.check(SFX, asset, f"missing required field '{field}'")

    def test_missing_skill_specific_fields(self):
        for skill, factory in ((SFX, sfx_asset), (MUSIC, music_asset)):
            for field in catalog_lib.SKILL_REQUIRED[skill]:
                with self.subTest(skill=skill, field=field):
                    asset = factory()
                    del asset[field]
                    self.check(skill, asset, f"missing required field '{field}'")

    def test_missing_file_field(self):
        asset = sfx_asset()
        del asset["file"]
        self.env.write_catalog(SFX, [asset])
        self.assertErrorContains(self.env.validate(SFX), "missing required field 'file'")

    def test_wrong_types(self):
        cases = [
            (SFX, sfx_asset, "title", 5, "'title' must be string"),
            (SFX, sfx_asset, "tags", "click", "'tags' must be array"),
            (SFX, sfx_asset, "duration_seconds", "0.5", "'duration_seconds' must be number"),
            (SFX, sfx_asset, "duration_seconds", True, "'duration_seconds' must be number"),
            (SFX, sfx_asset, "intensity", True, "'intensity' must be integer"),
            (SFX, sfx_asset, "intensity", 2.5, "'intensity' must be integer"),
            (SFX, sfx_asset, "sample_rate", True, "'sample_rate' must be integer"),
            (MUSIC, music_asset, "energy", False, "'energy' must be integer"),
            (MUSIC, music_asset, "instrumental", 1, "'instrumental' must be boolean"),
            (MUSIC, music_asset, "loopable", "yes", "'loopable' must be boolean"),
            (MUSIC, music_asset, "moods", "calm", "'moods' must be array"),
            (MUSIC, music_asset, "bpm", "fast", "'bpm' must be number"),
            (MUSIC, music_asset, "provenance", [], "'provenance' must be object"),
        ]
        for skill, factory, field, value, fragment in cases:
            with self.subTest(field=field, value=value):
                self.check(skill, factory(**{field: value}), fragment)

    def test_bad_tags(self):
        self.check(SFX, sfx_asset(tags=["ok", ""]), "tags must be non-empty strings")

    def test_nonpositive_duration(self):
        self.check(SFX, sfx_asset(duration_seconds=0), "duration_seconds must be positive")

    def test_duplicate_ids(self):
        a = sfx_asset("ui-click-soft-001")
        b = sfx_asset("ui-click-soft-001", file="assets/ui-clicks/other.wav")
        self.env.install(SFX, [a, b])
        self.assertErrorContains(self.env.validate(SFX), "duplicate id")

    def test_bad_id_pattern(self):
        for bad in ("UI-Click", "ui_click", "-ui", "ui--click", "ui click", "ui-"):
            with self.subTest(id=bad):
                self.check(SFX, sfx_asset(bad, file="assets/ui-clicks/x.wav"), "kebab-case")

    def test_unknown_category(self):
        self.check(SFX, sfx_asset(category="explosions"), "unknown category")
        self.check(MUSIC, music_asset(category="ui-clicks"), "unknown category")

    def test_unknown_source(self):
        self.check(SFX, sfx_asset(source="freesound"), "source must be one of")

    def test_bad_attack_tail_review(self):
        self.check(SFX, sfx_asset(attack="instant"), "attack must be one of")
        self.check(SFX, sfx_asset(tail="forever"), "tail must be one of")
        self.check(SFX, sfx_asset(review={"status": "maybe"}), "review.status")

    def test_intensity_range(self):
        for value in (0, 6, -1):
            with self.subTest(intensity=value):
                self.check(SFX, sfx_asset(intensity=value), "intensity must be 1-5")
        for value in (1, 5):
            self.env.install(SFX, [sfx_asset(intensity=value)])
            self.assertEqual(self.env.validate(SFX), [])

    def test_energy_range(self):
        for value in (0, 6):
            with self.subTest(energy=value):
                self.check(MUSIC, music_asset(energy=value), "energy must be 1-5")
        for value in (1, 5):
            self.env.install(MUSIC, [music_asset(energy=value)])
            self.assertEqual(self.env.validate(MUSIC), [])

    def test_bpm_must_be_positive(self):
        self.check(MUSIC, music_asset(bpm=0), "bpm must be positive")
        self.env.install(MUSIC, [music_asset(bpm=96)])
        self.assertEqual(self.env.validate(MUSIC), [])


class PathTests(SkillsTestCase):
    def test_path_traversal_rejected(self):
        outside = self.env.base(SFX).parent / "x.wav"
        write_wav(outside, 0.5)
        for rel in ("../x.wav", "/abs.wav", "assets/../../x.wav", "assets/../catalog.wav",
                    "other/x.wav", "x.wav", "assets\\x.wav", "C:/x.wav", ""):
            with self.subTest(rel=rel):
                self.env.write_catalog(SFX, [sfx_asset(file=rel)])
                self.assertErrorContains(self.env.validate(SFX), "must be a relative path inside assets/")

    def test_resolve_asset_path_directly(self):
        base = self.env.base(SFX)
        self.assertIsNone(catalog_lib.resolve_asset_path(base, "../x.wav"))
        self.assertIsNone(catalog_lib.resolve_asset_path(base, "/abs.wav"))
        self.assertIsNone(catalog_lib.resolve_asset_path(base, "assets/../../x.wav"))
        self.assertIsNone(catalog_lib.resolve_asset_path(base, "notassets/x.wav"))
        good = catalog_lib.resolve_asset_path(base, "assets/ui-clicks/a.wav")
        self.assertEqual(good, (base / "assets/ui-clicks/a.wav").resolve())

    def test_symlink_escaping_assets_rejected(self):
        outside = self.env.root / "outside"
        outside.mkdir()
        write_wav(outside / "a.wav", 0.5)
        link = self.env.base(SFX) / "assets" / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.env.write_catalog(SFX, [sfx_asset(file="assets/link/a.wav")])
        self.assertErrorContains(self.env.validate(SFX), "must be a relative path inside assets/")

    def test_disallowed_formats(self):
        for ext in (".txt", ".aiff", ".m4a"):
            with self.subTest(ext=ext):
                rel = f"assets/ui-clicks/a{ext}"
                path = self.env.base(SFX) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"data")
                self.env.write_catalog(SFX, [sfx_asset(file=rel)])
                self.assertErrorContains(self.env.validate(SFX), "not allowed")
                path.unlink()

    def test_format_field_mismatch(self):
        self.env.install(SFX, [sfx_asset(format="mp3")])
        self.assertErrorContains(self.env.validate(SFX), "'format' must be 'wav'")

    def test_uppercase_extension_maps_format(self):
        asset = sfx_asset(file="assets/ui-clicks/a.WAV")
        self.env.install(SFX, [asset])
        self.assertEqual(self.env.validate(SFX), [])

    def test_missing_audio_file(self):
        self.env.install(SFX, [sfx_asset()], with_audio=False)
        errors = self.env.validate(SFX)
        self.assertErrorContains(errors, "audio file not found: assets/ui-clicks/ui-click-soft-001.wav")
        # file existence is checked even when audio inspection is skipped
        self.assertErrorContains(self.env.validate(SFX, check_audio=False), "audio file not found")

    def test_uncatalogued_file(self):
        self.env.install(SFX, [sfx_asset()])
        write_wav(self.env.base(SFX) / "assets" / "stray" / "stray.wav", 0.2)
        self.assertErrorContains(self.env.validate(SFX), "uncatalogued file in assets/: assets/stray/stray.wav")

    def test_same_file_used_twice(self):
        a = sfx_asset("ui-click-a")
        b = sfx_asset("ui-click-b", file=a["file"])
        self.env.add_audio(SFX, a)
        self.env.write_catalog(SFX, [a, b])
        self.assertErrorContains(self.env.validate(SFX), "already used by ui-click-a")


class AudioCheckTests(SkillsTestCase):
    def test_identical_audio_detected(self):
        a = sfx_asset("ui-click-a")
        b = sfx_asset("ui-click-b")
        self.env.add_audio(SFX, a, freq=500.0)
        self.env.add_audio(SFX, b, freq=500.0)
        self.env.write_catalog(SFX, [a, b])
        errors = self.env.validate(SFX)
        self.assertErrorContains(errors, "ui-click-b: identical audio to ui-click-a")
        self.assertEqual(self.env.validate(SFX, check_audio=False), [])

    def test_sha256_match_and_mismatch(self):
        asset = sfx_asset()
        path = self.env.add_audio(SFX, asset)
        asset["sha256"] = catalog_lib.sha256_file(path)
        self.env.write_catalog(SFX, [asset])
        self.assertEqual(self.env.validate(SFX), [])
        asset["sha256"] = "0" * 64
        self.env.write_catalog(SFX, [asset])
        self.assertErrorContains(self.env.validate(SFX), "sha256 does not match")

    def test_probe_audio_wav(self):
        path = write_wav(self.env.root / "probe.wav", 1.25)
        info = catalog_lib.probe_audio(path)
        self.assertAlmostEqual(info["duration_seconds"], 1.25, places=2)
        self.assertEqual(info["sample_rate"], 8000)
        self.assertEqual(info["channels"], 1)

    def test_duration_within_tolerance(self):
        # 1.0 s file; tolerance is max(0.1 s, 2 %)
        for declared in (1.0, 1.05, 0.95, 1.09):
            with self.subTest(declared=declared):
                asset = music_asset(duration_seconds=declared)
                self.env.add_audio(MUSIC, asset, duration=1.0)
                self.env.write_catalog(MUSIC, [asset])
                self.assertEqual(self.env.validate(MUSIC), [])

    def test_duration_outside_tolerance(self):
        for declared in (1.2, 0.8, 2.0):
            with self.subTest(declared=declared):
                asset = music_asset(duration_seconds=declared)
                self.env.add_audio(MUSIC, asset, duration=1.0)
                self.env.write_catalog(MUSIC, [asset])
                self.assertErrorContains(self.env.validate(MUSIC), "differs from measured")
        # skipped when audio checks are disabled
        self.assertEqual(self.env.validate(MUSIC, check_audio=False), [])

    def test_ratio_tolerance_for_long_audio(self):
        self.assertTrue(catalog_lib.duration_matches(100.0, 101.9))
        self.assertFalse(catalog_lib.duration_matches(100.0, 102.5))
        self.assertTrue(catalog_lib.duration_matches(0.2, 0.29))
        self.assertFalse(catalog_lib.duration_matches(0.2, 0.31))


class RealRepoSmokeTest(unittest.TestCase):
    def test_repo_catalogs_validate_without_audio_check(self):
        code, out, _ = run_main(validate_catalog.main, ["--all", "--no-audio-check"])
        self.assertEqual(code, 0, out)

    def test_repo_catalogs_are_json(self):
        for skill in catalog_lib.SKILLS:
            data = json.loads((REPO_ROOT / ".claude" / "skills" / skill / "catalog.json").read_text())
            self.assertEqual(data["skill"], skill)


if __name__ == "__main__":
    unittest.main()
