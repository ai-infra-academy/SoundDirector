---
name: background-music
description: Find ready-made, locally installed instrumental background music (educational/explainer, tech, suspense, vlog, reels/shorts, cinematic, corporate, playful, ambient focus) by mood, energy and description, and return real file paths. Use when a video, reel, vlog, tutorial or trailer needs a music bed — e.g. "find calm music behind an AI tutorial", "choose suspense music for a 30-second reel". Not for slide decks unless the user explicitly asks for music. Works offline; no API keys or generation.
---

# Background music library

This skill only **finds and supplies** existing audio files. You (Claude) decide what fits and do any integration (trimming, fades, ducking under narration) with the user's own tools.

## Rules
- Use this skill for video work, or when the user **explicitly** asks for music. Do not add music to slides by default.
- Only reference files returned by search (or listed in `catalog.json` *and* present on disk). Never invent IDs or paths. If nothing is installed or nothing matches, say so plainly.
- `voiceover_friendly` and `loopable` are true only when a reviewer confirmed them. Don't claim either property for a track where the flag is false. No track has either flag yet. Under narration, prefer energy 1–2 tracks whose description mentions narration or voiceover, and suggest the user ducks the music.
- Treat choices as suggestions. Offer alternatives, or use a specific ID if the user names one.
- Do not generate new music unless the user explicitly asks for library maintenance.

## Search
From the repository root, or from any project when the skill is installed globally:

`<skill-dir>` is this skill's directory, as shown when the skill is loaded. For example, it can be `.claude/skills/background-music` in the repo, or `~/.claude/skills/background-music` when the skill is installed globally as a symlink. The `../../..` path follows the symlink back to the cloned repository, so search works from any working directory.

```bash
python3 <skill-dir>/../../../scripts/search_assets.py --skill background-music --mood suspense --max-duration 40 --limit 5
python3 <skill-dir>/../../../scripts/search_assets.py --skill background-music --query "calm tutorial electronic" --max-energy 2
python3 <skill-dir>/../../../scripts/search_assets.py --skill background-music --category reels --min-energy 4 --json
```

If that path doesn't exist, for example when only this skill directory was copied, read `catalog.json` in this directory directly and filter by `description`, `moods`, `tags`, `energy` and `preferred_content_types`. Check that the file exists before you use it.

Filters: `--category`, `--mood` (repeatable, any), `--tag`, `--min/--max-energy`, `--min/--max-duration`, `--instrumental`, `--loopable`, `--voiceover-friendly`.

Categories: `education`, `technology`, `suspense`, `vlog`, `reels`, `cinematic`, `corporate`, `playful`, `ambient-focus`.

## Resolving paths
Each record's `file` is relative to **this skill directory**, for example `assets/education/education-calm-001.mp3` resolves to `.claude/skills/background-music/assets/education/education-calm-001.mp3`. Search output also prints the absolute `path`.

Useful record fields: `duration_seconds`, `energy` (1–5), `moods`, `bpm` (only if measured), `instrumental`, `loopable`, `voiceover_friendly`, `preferred_content_types`.

## Timing
When present, `timing.onset_seconds` and `timing.end_seconds` mark where audible music starts and ends; trim silence outside them. Tracks are often longer than a short video needs, so trim, then fade out over 1–3 s rather than cutting abruptly.
