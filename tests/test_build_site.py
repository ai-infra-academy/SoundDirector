"""Static site build: only existing files are published, data is escaped, waveforms cached."""

import json

from helpers import SkillsTestCase, music_asset, sfx_asset

import build_site


class BuildSiteTests(SkillsTestCase):
    def build(self, **kw):
        self.out = self.env.root / "_site"
        self.cache = self.env.root / "waveforms.json"
        return build_site.build(self.out, skills_root=self.env.skills_root, cache_path=self.cache, **kw)

    def data(self):
        text = (self.out / "data.js").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("window.SOUND_LIBRARY = "))
        return text, json.loads(text[len("window.SOUND_LIBRARY = "):].rstrip().rstrip(";"))

    def test_publishes_existing_assets_with_audio(self):
        ok = sfx_asset("ui-click-soft-001", sha256="a" * 64, description="</script> soft")
        missing = sfx_asset("ui-click-gone-002")
        self.env.install("sound-effects", [ok])
        self.env.write_catalog("sound-effects", [ok, missing])
        self.env.install("background-music", [music_asset()])
        lib = self.build(repo_url="https://github.com/example/SoundDirector")
        self.assertEqual([a["id"] for a in lib["skills"]["sound-effects"]], ["ui-click-soft-001"])
        text, data = self.data()
        self.assertNotIn("</script>", text)
        asset = data["skills"]["sound-effects"][0]
        self.assertEqual(asset["file"], "skills/sound-effects/assets/ui-clicks/ui-click-soft-001.wav")
        self.assertEqual(asset["repo_path"], ".claude/skills/sound-effects/assets/ui-clicks/ui-click-soft-001.wav")
        self.assertTrue((self.out / asset["file"]).is_file())
        self.assertEqual(len(asset["waveform"]), build_site.BINS)
        self.assertEqual(max(asset["waveform"]), 1.0)
        self.assertEqual(data["repo_url"], "https://github.com/example/SoundDirector")
        self.assertIn("a" * 64, json.loads(self.cache.read_text()))
        for name in ("index.html", "app.js", "style.css", ".nojekyll"):
            self.assertTrue((self.out / name).is_file(), name)
        self.assertFalse((self.out / "waveforms.json").exists())

    def test_cached_waveform_is_reused_and_no_audio_mode(self):
        a = sfx_asset("ui-click-soft-001", sha256="b" * 64)
        self.env.install("sound-effects", [a])
        self.env.root.joinpath("waveforms.json").write_text(json.dumps({"b" * 64: [0.5, 1.0]}))
        lib = self.build(copy_audio=False)
        self.assertEqual(lib["skills"]["sound-effects"][0]["waveform"], [0.5, 1.0])
        self.assertFalse((self.out / "skills").exists())
