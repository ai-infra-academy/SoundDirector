# SoundDirector: audio asset skills for Claude Code

There are two small, independent [Claude Code skills](https://platform.claude.com/docs/en/managed-agents/skills). Claude uses them to find ready-made audio by description and get back real file paths, offline, with no API keys.

| Skill | What it holds | Planned | **Shipped** |
|---|---|---:|---:|
| `sound-effects` | UI clicks, whooshes, notifications, tech/AI blips, impacts, diagram reveals, ambience, cinematic stings | 200 | **180** |
| `background-music` | Instrumental beds for explainers, tech, suspense, vlogs, reels, cinematic, corporate, playful, focus | 80 | **80** (128 min) |

"Shipped" means files that are actually in `assets/` and the catalog. The 20 planned sound effects that aren't shipped yet are listed in [`planning/backlog.json`](planning/backlog.json).

The skills only **find and supply** audio. Claude Code does the slide, video or app integration itself. Slide tasks use `sound-effects` only, and music is added only when you ask for it.

## Browse and preview
The repository includes a static website (`site/`) for searching the library, playing every file with a waveform preview, and copying asset paths. It is deployed to GitHub Pages by `.github/workflows/pages.yml`.

To preview it locally:
```bash
python3 scripts/build_site.py              # assembles _site/
python3 -m http.server -d _site 8000       # then open http://localhost:8000
```

## Quick start
```bash
git clone --depth 1 <this repo> SoundDirector && cd SoundDirector
python3 scripts/search_assets.py --skill sound-effects --query "gentle whoosh" --limit 5
python3 scripts/search_assets.py --skill background-music --mood suspense --max-duration 40
```
Then ask Claude Code something like *"add a soft click to each bullet reveal"* or *"find calm music for this tutorial video"*. It picks up the skills from `.claude/skills/`.

Requires Python 3.9+ and nothing else. `ffprobe` and `ffmpeg` are optional: they're used for duration checks on non-WAV files and for timing analysis.

The audio is about 220 MB, so `--depth 1` keeps the clone small.

## Installation
- **Project-scoped:** work inside this repo, or copy `.claude/skills/` into your project. Claude Code discovers `.claude/skills/*/SKILL.md` automatically.
- **Global:** copy or symlink either skill directory into your personal skills folder (currently `~/.claude/skills/`):
  ```bash
  ln -s "$PWD/.claude/skills/sound-effects" ~/.claude/skills/sound-effects
  ln -s "$PWD/.claude/skills/background-music" ~/.claude/skills/background-music
  ```
  Each skill works independently. Without `scripts/`, Claude reads the skill's `catalog.json` directly.

## Search options
`--query`, `--category`, `--tag` (all must match), `--mood` (any), `--min/--max-energy`, `--min/--max-intensity`, `--min/--max-duration`, `--instrumental`, `--loopable`, `--voiceover-friendly`, `--limit`, `--json`, `--catalog <path>`.

Results are deterministic, and only entries whose audio file exists are returned. Entries with a missing file are listed separately and never offered as usable.

Each result carries timing marks: `onset_seconds`, `peak_seconds` and `end_seconds`. To land an effect's hit on a visual event at time T, start the clip at T − `peak_seconds`.

Formats: WAV (sound effects, 44.1 kHz stereo) and MP3 (music). OGG and FLAC are also accepted.

## What the flags mean
- **`instrumental`:** no vocals were found during review. Every shipped track is marked instrumental.
- **`voiceover_friendly`** and **`loopable`:** set only when a reviewer has confirmed them under narration, or tested the loop seam. No track has these flags yet, so pick low-energy tracks (energy 1–2) for narration, and trim with a fade rather than looping.
- **`bpm`:** present only when it has been measured.

## Layout
```
.claude/skills/<skill>/SKILL.md      skill entrypoint (frontmatter + search directions)
.claude/skills/<skill>/catalog.json  asset records (schemas/asset.schema.json)
.claude/skills/<skill>/assets/       audio files referenced by the catalog
scripts/search_assets.py             search (stdlib only)
scripts/validate_catalog.py          catalog validation (used by CI)
scripts/build_catalog.py             promote reviewed staging assets into a skill
scripts/analyze_audio.py             timing marks: onset, peak, end
scripts/make_review_page.py          local audition page for staged candidates
scripts/apply_review.py              apply exported review decisions
scripts/build_site.py                build the static browse site into _site/
site/                                website source (HTML, CSS, JS, cached waveforms)
planning/                            planned inventories and the regeneration backlog
tests/                               unittest suite
.github/workflows/                   CI (validate + tests) and GitHub Pages deploy
staging/                             gitignored generated candidates awaiting review
```

## Maintainer workflow
Generation is optional and never needed by users.

1. **Generate** candidates for planned items into `staging/<skill>/<id>/`. Each gets a `record.json` holding the prompt, provider, date and output ID. The sound effects so far were made with ElevenLabs. The music was made with ElevenLabs (67 tracks) and Suno (13).
2. **Review** every candidate:
   - Run `python3 scripts/make_review_page.py && open staging/review.html`. On the page, approve or reject each item, pick a music take, and tick the vocals, narration and loop checks.
   - Click **Export decisions**, then run `python3 scripts/apply_review.py ~/Downloads/review-decisions.json`.
3. **Build** with `python3 scripts/build_catalog.py --skill <skill>`. It copies approved audio into `assets/` and measures duration, sample rate, hash and timing.
4. **Check** with `python3 scripts/validate_catalog.py --all` and `python3 -m unittest discover -s tests`.
5. **Refresh the site** with `python3 scripts/build_site.py`, then commit the updated `site/waveforms.json`.

### Backlog
[`planning/backlog.json`](planning/backlog.json) lists the planned assets that aren't shipped yet:
- Each entry carries its prompt, the reason it was rejected, and a suggested prompt change.
- So far all 20 are sound effects that came out too quiet to use.
- Their `planning/sfx-inventory.json` status is `needs-regeneration`.
- To fill one: regenerate the item, review it, and build it as above. Then remove it from the backlog.

## Deploying the site
1. Push to GitHub.
2. Under **Settings → Pages**, set **Source** to **GitHub Actions**.
3. Each push to `main` then rebuilds and deploys the site.

## Contributing
Code and catalog fixes are welcome on their own. Audio contributions need provenance (source, prompt or method), category, description, tags, a checksum, and a human listening review.

## License
Code is MIT; see `LICENSE`.
