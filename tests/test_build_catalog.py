import json

from helpers import SkillsTestCase, run_main, write_wav

import build_catalog
import catalog_lib

SFX, MUSIC = "sound-effects", "background-music"


class BuildCatalogTests(SkillsTestCase):
    def setUp(self):
        super().setUp()
        self.staging = self.env.root / "staging"

    def stage(self, skill, record, duration=0.75, freq=None, staged_file="take.wav"):
        folder = self.staging / skill / record["id"]
        folder.mkdir(parents=True, exist_ok=True)
        record = {"staged_file": staged_file, **record}
        (folder / "record.json").write_text(json.dumps(record))
        write_wav(folder / staged_file, duration, freq or self.env.next_freq())
        return folder

    def sfx_record(self, asset_id="ui-click-soft-001", status="approved", **extra):
        rec = {
            "id": asset_id, "title": "Soft Click", "description": "A soft click.",
            "category": "ui-clicks", "tags": ["click"], "source": "elevenlabs",
            "generation_prompt": "a soft click", "intensity": 1, "attack": "sharp", "tail": "dry",
            "use_cases": ["slides"], "duration_seconds": 99.0, "sha256": "f" * 64,
            "provenance": {"provider": "elevenlabs", "output_id": "abc", "api_key": "SECRET"},
            "review": {"status": status, "reviewer": "me"},
        }
        rec.update(extra)
        return rec

    def music_record(self, asset_id="education-calm-001", review=None, **extra):
        rec = {
            "id": asset_id, "title": "Calm", "description": "Calm bed.", "category": "education",
            "tags": ["calm"], "source": "suno", "generation_prompt": "calm instrumental",
            "moods": ["calm"], "energy": 2, "preferred_content_types": ["tutorial"],
            "instrumental": True, "loopable": True, "voiceover_friendly": True,
            "review": {"status": "approved", **(review or {})},
        }
        rec.update(extra)
        return rec

    def build(self, skill, *extra):
        return run_main(build_catalog.main, ["--skill", skill, "--staging", str(self.staging / skill),
                                             "--skills-root", str(self.env.skills_root), *extra])

    def test_approved_record_imported_and_measured(self):
        self.stage(SFX, self.sfx_record(), duration=0.75)
        code, out, _ = self.build(SFX)
        self.assertEqual(code, 0, out)
        self.assertIn("imported 1 asset(s): ui-click-soft-001", out)
        target = self.env.base(SFX) / "assets" / "ui-clicks" / "ui-click-soft-001.wav"
        self.assertTrue(target.is_file())
        asset = self.env.read_catalog(SFX)["assets"][0]
        self.assertEqual(asset["file"], "assets/ui-clicks/ui-click-soft-001.wav")
        self.assertAlmostEqual(asset["duration_seconds"], 0.75, places=2)
        self.assertEqual(asset["sha256"], catalog_lib.sha256_file(target))
        self.assertEqual(asset["format"], "wav")
        self.assertEqual(asset["sample_rate"], 8000)
        self.assertNotIn("api_key", asset["provenance"])
        self.assertEqual(self.env.validate(SFX), [])

    def test_pending_and_rejected_skipped(self):
        self.stage(SFX, self.sfx_record("ui-click-pending-001", status="pending"))
        self.stage(SFX, self.sfx_record("ui-click-rejected-001", status="rejected"))
        self.stage(SFX, self.sfx_record("ui-click-ok-001"))
        code, out, _ = self.build(SFX)
        self.assertEqual(code, 0, out)
        self.assertIn("skip  ui-click-pending-001", out)
        self.assertIn("skip  ui-click-rejected-001", out)
        self.assertEqual([a["id"] for a in self.env.read_catalog(SFX)["assets"]], ["ui-click-ok-001"])
        self.assertFalse((self.env.base(SFX) / "assets/ui-clicks/ui-click-pending-001.wav").exists())

    def test_missing_staged_audio_skipped(self):
        folder = self.stage(SFX, self.sfx_record())
        (folder / "take.wav").unlink()
        code, out, _ = self.build(SFX)
        self.assertEqual(code, 0)
        self.assertIn("staged audio missing", out)
        self.assertEqual(self.env.read_catalog(SFX)["assets"], [])

    def test_unsafe_id_or_category_not_copied(self):
        self.stage(SFX, self.sfx_record("evil", category="../../../escape"))
        code, out, _ = self.build(SFX)
        self.assertEqual(code, 0, out)
        self.assertIn("skip  evil", out)
        self.assertEqual(list(self.env.root.rglob("escape")), [])
        self.assertEqual(self.env.read_catalog(SFX)["assets"], [])

    def test_ids_filter(self):
        self.stage(SFX, self.sfx_record("ui-click-a"))
        self.stage(SFX, self.sfx_record("ui-click-b"))
        code, out, _ = self.build(SFX, "--ids", "ui-click-b")
        self.assertEqual(code, 0, out)
        self.assertEqual([a["id"] for a in self.env.read_catalog(SFX)["assets"]], ["ui-click-b"])

    def test_dry_run_writes_nothing(self):
        self.stage(SFX, self.sfx_record())
        before = self.env.catalog_path(SFX).read_bytes()
        code, out, _ = self.build(SFX, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would import 1 asset(s)", out)
        self.assertEqual(self.env.catalog_path(SFX).read_bytes(), before)
        self.assertEqual([p for p in (self.env.base(SFX) / "assets").rglob("*")], [])

    def test_music_flags_require_review_confirmation(self):
        self.stage(MUSIC, self.music_record("education-unreviewed-001"))
        self.stage(MUSIC, self.music_record("education-vocals-001",
                                            review={"vocals_detected": True, "loop_tested": "yes",
                                                    "voiceover_checked": 1}))
        self.stage(MUSIC, self.music_record("education-reviewed-001",
                                            review={"vocals_detected": False, "loop_tested": True,
                                                    "voiceover_checked": True, "bpm_measured": 92}))
        code, out, _ = self.build(MUSIC)
        self.assertEqual(code, 0, out)
        assets = {a["id"]: a for a in self.env.read_catalog(MUSIC)["assets"]}
        for asset_id in ("education-unreviewed-001", "education-vocals-001"):
            a = assets[asset_id]
            self.assertIs(a["instrumental"], False, asset_id)
            self.assertIs(a["loopable"], False, asset_id)
            self.assertIs(a["voiceover_friendly"], False, asset_id)
            self.assertNotIn("bpm", a)
        r = assets["education-reviewed-001"]
        self.assertIs(r["instrumental"], True)
        self.assertIs(r["loopable"], True)
        self.assertIs(r["voiceover_friendly"], True)
        self.assertEqual(r["bpm"], 92)
        self.assertEqual(self.env.validate(MUSIC), [])

    def test_rebuild_is_idempotent(self):
        self.stage(SFX, self.sfx_record())
        self.build(SFX)
        first = self.env.catalog_path(SFX).read_bytes()
        code, _, _ = self.build(SFX)
        self.assertEqual(code, 0)
        self.assertEqual(self.env.catalog_path(SFX).read_bytes(), first)
