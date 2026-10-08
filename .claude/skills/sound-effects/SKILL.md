---
name: sound-effects
description: Find ready-made, locally installed sound effects (UI clicks, toggles, whooshes/transitions, notifications, tech/AI blips, impacts, diagram reveals, ambience, cinematic stings) by description and return real file paths. Use when adding sound to slides, slide animations, presentations, UI, games, or video edits — e.g. "find a soft UI click", "add a whoosh to this transition", "pick a sound for a diagram reveal". Works offline; no API keys or generation.
---

# Sound effects library

This skill only **finds and supplies** existing audio files. You (Claude) decide what fits and do any integration in the user's project yourself.

## Rules
- **Slides/presentations:** use this skill only. Do **not** add background music unless the user explicitly asks for music.
- Only reference files returned by search (or listed in `catalog.json` *and* present on disk). Never invent IDs or paths. If nothing is installed or nothing matches, say so plainly.
- Prefer subtle effects (intensity 1–2) for educational and professional content.
- Treat choices as suggestions. Offer alternatives, or use a specific ID if the user names one.
- Do not generate new sounds unless the user explicitly asks for library maintenance.

## Search
From the repository root, or from any project when the skill is installed globally:

`<skill-dir>` is this skill's directory, as shown when the skill is loaded. For example, it can be `.claude/skills/sound-effects` in the repo, or `~/.claude/skills/sound-effects` when the skill is installed globally as a symlink. The `../../..` path follows the symlink back to the cloned repository, so search works from any working directory.

```bash
python3 <skill-dir>/../../../scripts/search_assets.py --skill sound-effects --query "gentle whoosh" --limit 5
python3 <skill-dir>/../../../scripts/search_assets.py --skill sound-effects --category ui-clicks --max-intensity 2
python3 <skill-dir>/../../../scripts/search_assets.py --skill sound-effects --query "success chime" --json
```

If that path doesn't exist, for example when only this skill directory was copied, read `catalog.json` in this directory directly and filter by `description`, `tags`, `category`, `use_cases` and `intensity`. Check that the file exists before you use it.

Filters: `--category`, `--tag` (repeatable, all must match), `--min/--max-intensity`, `--min/--max-duration`.

Categories: `ui-clicks`, `transitions`, `notifications`, `tech-ai`, `impacts`, `edu-diagrams`, `ambience`, `cinematic`.

## Resolving paths
Each record's `file` is relative to **this skill directory**, for example `assets/ui-clicks/ui-click-soft-001.wav` resolves to `.claude/skills/sound-effects/assets/ui-clicks/ui-click-soft-001.wav`. Search output also prints the absolute `path`. Copy or reference the file into the user's project as their tooling requires.

Useful record fields: `duration_seconds`, `intensity` (1–5), `attack` (soft/medium/sharp), `tail` (dry/short/medium/long), `use_cases`, `format`.

## Timing and sync
Records carry `timing` marks, in seconds from the start of the file:
- `onset_seconds`: when the sound becomes audible. Anything before it is near-silence, so you can trim it.
- `peak_seconds`: the hit or accent moment. **To sync with a visual event at time T, start the clip at `T − peak_seconds`.** For example, a reveal at 12.0 s with a peak of 0.65 s starts at 11.35 s.
- `end_seconds`: when the tail fades out. Treat `end_seconds − onset_seconds` as how long the sound occupies.

For ambience beds the peak isn't meaningful. Use them as continuous background instead. Only call a bed seamlessly loopable if `review` says the loop was tested.
