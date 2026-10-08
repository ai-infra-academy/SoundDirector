# CLAUDE.md — Reusable Audio Asset Skills

## Mission
Build and maintain an open-source, Claude Code-native repository containing exactly **two independent asset-library skills**:

1. `sound-effects`: descriptions, searchable metadata, and sound-effect audio files.
2. `background-music`: descriptions, searchable metadata, and instrumental background music files.

Claude Code itself decides which assets suit the user's task and performs integration. **Do not build** a video editor, slide creator, soundtrack director, multi-skill orchestrator, or mandatory external service. The skills must work offline after asset installation.

## User workflows
- Slide creation/animation: use `sound-effects` only by default. Do not add music unless explicitly requested.
- Video editing/reels/vlogs/tutorials: Claude Code may use both skills as appropriate.
- Both skills only discover, describe, preview (via file references), and provide existing audio assets. They **do not** edit timelines, mix audio, duck narration, or alter third-party projects themselves.
- Default to selecting existing assets. Generate new assets only when explicitly requested for library maintenance.

## Asset generation tools available to the maintainer
- ElevenLabs MCP for generating candidate sound effects.
- Suno access for generating candidate background music. Verify the actual available integration and its capabilities; do not assume a Suno MCP exists.
- Generation is an optional **maintainer workflow**, never a requirement for downstream users.
- Do not hardcode MCP tool names: discover actual connected tools and verify supported options before use.
- Save provider, prompt, generation date, and output ID for each asset.
- Do not run bulk paid generation until the user approves the anticipated cost and batch size. Begin with a small proof-of-concept batch.
- Avoid generating imitations of named artists, recordings, or branded sonic identities.

## Preferred repository layout
```
README.md
CLAUDE.md
Spec.md
LICENSE                 # code license
.gitignore
.claude/skills/
  sound-effects/
    SKILL.md
    catalog.json
    assets/
  background-music/
    SKILL.md
    catalog.json
    assets/
scripts/
  catalog_lib.py          # shared loading/validation helpers
  search_assets.py
  validate_catalog.py
  build_catalog.py
  analyze_audio.py        # timing marks (onset/peak/end)
  make_review_page.py     # local audition page for staging/
  apply_review.py         # apply exported review decisions
  build_site.py           # static browse site -> _site/
  publish_github.sh       # one-shot GitHub publish + Pages setup
schemas/
  asset.schema.json
planning/
  sfx-inventory.json      # all 200 planned SFX with prompts and status
  music-inventory.json    # all 80 planned tracks with prompts and status
  backlog.json            # planned assets not shipped yet (to regenerate)
site/                     # static website source (GitHub Pages)
tests/
.github/workflows/        # ci.yml (validate + tests), pages.yml (site deploy)
```

`staging/` (generated candidates) and `_site/` (built website) are gitignored.

The static site in `site/` is a read-only browser and previewer for the two catalogs. It is built from `catalog.json`, so never edit asset data in the site. The skills must never depend on the site.

Keep the `.claude/skills/<skill-name>/SKILL.md` entrypoints immediately discoverable by Claude Code. Each skill must have brief YAML frontmatter with `name` and a trigger-friendly `description`, followed by concise directions explaining how to search the catalog and resolve audio paths. Avoid embedding all asset records into SKILL.md.

## Catalog and search requirements
For each asset store: stable `id`, `title`, `description` (natural language), `category`, `tags`, `file`, `duration_seconds`, format, loudness/technical info where available, `source`, and `generation_prompt` or other provenance reference.

Music adds: `moods`, `energy` (1–5), `instrumental`, `bpm` if measured, `loopable` (tested), `voiceover_friendly` (reviewed), and preferred content types. SFX adds: `intensity` (1–5), `attack`/`tail` characteristics, and suggested use cases.

Implement one tiny shared, deterministic search script that can filter by skill/category/keywords/tags/mood and return top matching assets with description and path. No vector database, hosted inference, or mandatory dependency-heavy server. Files must be referenceable using paths relative to their respective skill directories. Never invent non-existent asset IDs or file paths.

## Quality and generation discipline
1. First produce the full planning catalog with descriptive names, prompts, intended durations, and categories.
2. Build minimal valid skills and catalog/search/validation tests.
3. Create a proof-of-concept batch (e.g., 10 SFX + 5 music tracks) only after obtaining approval for paid generation.
4. Listen to every asset or conduct a human audition/review. Automated duration and peak checks alone are insufficient.
5. Reject clipping, long silence, abrupt endings, voices in instrumental tracks, recognizable copied tunes, near duplicates, and effects too aggressive for educational content.
6. Maintain stable IDs, version catalogs, avoid filename collisions, and preserve generation prompts so replacements are reproducible.
7. Expand incrementally toward the target counts only if quality is verified.
8. Record planned assets that fail review and can't be regenerated yet in `planning/backlog.json`, with the reason, and set their inventory status to `needs-regeneration`. Remove an entry once a reviewed replacement ships.

## Acceptance criteria
- Exactly two skills, independently usable and independently installable.
- Skill lookup returns actual, existing files when audio is installed; absent files produce a clear message, not fabricated paths.
- Both skills can be used with no API key or generation call at inference/use time.
- Slide tasks use SFX without implicitly introducing background music.
- Videos can use SFX and music, while integration remains Claude Code's responsibility.
- CI validates JSON, unique IDs, file existence for catalog entries, and allowed formats.

## Execution order
Read `Spec.md`; check actual MCP/integration capabilities; report blockers; implement repository skeleton and catalogs; validate; then make a small generation proposal. Ask for cost approval before bulk generation or fee-bearing actions. Do not push to GitHub or publish a release without explicit user authorization.
