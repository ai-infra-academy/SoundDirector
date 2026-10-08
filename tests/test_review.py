"""Review page generation and applying exported decisions to staged records."""

import json

from helpers import SkillsTestCase, run_main

import apply_review
import make_review_page


class ReviewTests(SkillsTestCase):
    def setUp(self):
        super().setUp()
        self.staging = self.env.root / "staging"

    def stage(self, skill, asset_id, **record):
        folder = self.staging / skill / asset_id
        folder.mkdir(parents=True)
        base = {"id": asset_id, "title": "T", "category": "c", "description": "d",
                "status": "generated", "review": {"status": "pending", "notes": ""}}
        base.update(record)
        (folder / "record.json").write_text(json.dumps(base), encoding="utf-8")
        return folder / "record.json"

    def decide(self, *decisions):
        path = self.env.root / "decisions.json"
        path.write_text(json.dumps({"version": 1, "decisions": list(decisions)}), encoding="utf-8")
        return run_main(apply_review.main, [str(path), "--staging", str(self.staging)])

    def music_record(self, asset_id="education-calm-001"):
        return self.stage("background-music", asset_id, staged_file=f"{asset_id}-take1.mp3",
                          provenance={"output_id": "a"},
                          takes=[{"file": f"{asset_id}-take1.mp3", "output_id": "a"},
                                 {"file": f"{asset_id}-take2.mp3", "output_id": "b"}])

    def test_page_lists_pending_only(self):
        self.stage("sound-effects", "ui-click-soft-001", staged_file="ui-click-soft-001.wav")
        self.stage("sound-effects", "ui-click-done-002", staged_file="x.wav", review={"status": "approved"})
        self.stage("sound-effects", "ui-click-fail-003", status="failed")
        code, out, _ = run_main(make_review_page.main, ["--staging", str(self.staging)])
        self.assertEqual(code, 0)
        self.assertIn("1 item(s)", out)
        page = (self.staging / "review.html").read_text(encoding="utf-8")
        self.assertIn("sound-effects/ui-click-soft-001/ui-click-soft-001.wav", page)
        self.assertNotIn("ui-click-done-002", page)

    def test_page_escapes_script_close(self):
        self.stage("sound-effects", "ui-click-soft-001", staged_file="a.wav", description="</script><b>")
        run_main(make_review_page.main, ["--staging", str(self.staging)])
        page = (self.staging / "review.html").read_text(encoding="utf-8")
        self.assertNotIn("</script><b>", page)

    def test_music_take_and_flags(self):
        path = self.music_record()
        code, out, _ = self.decide({"skill": "background-music", "id": "education-calm-001",
                                    "status": "approved", "take": 2, "voiceover": True})
        self.assertEqual(code, 0)
        r = json.loads(path.read_text())
        self.assertEqual(r["staged_file"], "education-calm-001-take2.mp3")
        self.assertEqual(r["provenance"]["output_id"], "b")
        self.assertEqual(r["review"]["status"], "approved")
        self.assertIs(r["review"]["vocals_detected"], False)
        self.assertIs(r["review"]["voiceover_checked"], True)
        self.assertIs(r["review"]["loop_tested"], False)

    def test_bad_take_rejected(self):
        path = self.music_record()
        code, out, _ = self.decide({"skill": "background-music", "id": "education-calm-001",
                                    "status": "approved", "take": 3})
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(path.read_text())["review"]["status"], "pending")

    def test_reject_and_untouched(self):
        rejected = self.stage("sound-effects", "ui-click-soft-001", staged_file="a.wav")
        untouched = self.stage("sound-effects", "ui-click-other-002", staged_file="b.wav")
        before = untouched.read_text()
        self.decide({"skill": "sound-effects", "id": "ui-click-soft-001", "status": "rejected", "notes": "harsh"})
        r = json.loads(rejected.read_text())
        self.assertEqual((r["review"]["status"], r["review"]["notes"]), ("rejected", "harsh"))
        self.assertEqual(untouched.read_text(), before)

    def test_invalid_entries(self):
        code, out, _ = self.decide({"skill": "sound-effects", "id": "../evil", "status": "approved"},
                                   {"skill": "sound-effects", "id": "ui-x-001", "status": "maybe"},
                                   {"skill": "sound-effects", "id": "ui-missing-001", "status": "approved"})
        self.assertEqual(code, 1)
        self.assertIn("updated 0 record(s)", out)
