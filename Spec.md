# Spec.md — Open Audio Skills for Claude Code

**Status:** Implementation specification  
**Project concept:** Two independent, searchable, ready-to-use audio-library skills  
**Audience:** Claude Code users, creators, maintainers, and open-source contributors

## 1. Product vision
A developer asks Claude Code to build slides, edit a video, make a reel, or create an interactive application. Claude discovers ready-made audio files locally by their descriptions and selects suitable assets without the developer hunting for downloads or repeatedly calling generative services.

Ship exactly two small skills:

- **`sound-effects`** — one-shot sound effects for UI, animations, presentations, games, and video.
- **`background-music`** — instrumental beds for educational content, tutorials, suspense, vlogs, reels, and storytelling.

**Out of scope:** video editor, slide generator, audio mixing engine, automatic soundtrack planner, centralized coordinator, background generative service, cloud asset search backend, or a requirement that users have ElevenLabs/Suno accounts.

Claude Code owns creative decisions and project-specific file integration. The skills offer metadata and real files, nothing more.

## 2. Scope and target asset counts
### 2.1 Sound effects — initial target: 200
| Category | Count | Example descriptors |
|---|---:|---|
| UI clicks/interactions | 30 | light click, toggle on/off, keyboard tap, selection, switch |
| Transitions/whooshes | 30 | clean sweep, fast swipe, subtle slide, zoom, airy whoosh |
| Notifications/feedback | 25 | success, gentle alert, invalid input, progress finished |
| Technology and AI | 30 | data pulse, network packet, cache hit/miss, startup blip |
| Impacts/emphasis | 25 | soft pop, low thud, bright accent, subtle cinematic hit |
| Educational diagrams | 25 | connector draw, node activation, diagram reveal, arrow pass |
| Ambience | 15 | soft server room, atmospheric tech bed, rain room tone |
| Cinematic moments | 20 | rising tension, reveal accent, surprise, suspense sting |
| **Total** | **200** | |

Favor subtle, professional audio suited to educational presentations; no harsh click spam or overwhelming low-end by default. Include distinct variations only when they are audibly useful.

### 2.2 Background music — initial target: 80
| Category | Count | Example descriptors |
|---|---:|---|
| Educational/explainer | 15 | unobtrusive electronic, calm discovery, sustained focus |
| Futuristic/technology | 10 | soft synth, clean digital energy, thoughtful innovation |
| Suspense/mystery | 10 | restrained pulse, investigative tension, anticipation |
| Vlog/lifestyle | 10 | relaxed groove, warm acoustic, travel, coffee-shop mood |
| Reels/shorts | 10 | energetic rhythmic hook, modern upbeat, punchy opener |
| Cinematic/emotional | 10 | inspiring, hopeful, reflective, gentle dramatic build |
| Corporate/professional | 5 | polished, optimistic, minimal corporate instrumental |
| Comedy/playful | 5 | quirky, light, playful percussion, whimsical |
| Ambient/focus | 5 | minimal atmosphere, deep work, warm texture |
| **Total** | **80** | |

All tracks should be instrumental unless deliberately curated otherwise; make tracks voiceover-friendly where relevant. Plan short (15–30s), medium (~60s), and long (~2–3 min) versions as appropriate; avoid blindly duplicating tracks to meet a count. Do not claim a track loops seamlessly without testing the seam.

## 3. Skill behavior
### 3.1 `sound-effects`
Trigger examples: "find a soft UI click," "add a whoosh to this animation," "choose an effect for a diagram reveal." The skill tells Claude where its catalog is, how to search, and how to resolve an asset path. It **does not** itself edit slides or video.

### 3.2 `background-music`
Trigger examples: "find calm music behind an AI tutorial," "choose suspense music for a reel," "find an upbeat instrumental for a vlog." As above, the skill only supplies candidate assets and descriptions; Claude handles use in the current project.

### 3.3 Context rules
- During slide creation, Claude should normally invoke `sound-effects` only. Music requires an explicit request.
- During video work, both asset libraries may be consulted as needed.
- Selection is recommendation, not a forced action. Users can request a specific asset ID or ask for alternatives.
- Asset search must work without invoking music/SFX generation.

## 4. Repository and installation
```
repo/
├── CLAUDE.md
├── Spec.md
├── README.md
├── LICENSE                   # code license
├── .gitignore
├── .claude/skills/
│   ├── sound-effects/
│   │   ├── SKILL.md
│   │   ├── catalog.json
│   │   └── assets/
│   └── background-music/
│       ├── SKILL.md
│       ├── catalog.json
│       └── assets/
├── schemas/asset.schema.json
├── scripts/
│   ├── catalog_lib.py        # shared helpers
│   ├── search_assets.py
│   ├── validate_catalog.py
│   ├── build_catalog.py      # staging → assets/ + catalog.json
│   ├── analyze_audio.py      # timing marks
│   ├── make_review_page.py   # audition page for staging/
│   ├── apply_review.py
│   └── build_site.py         # static site → _site/
├── planning/                 # inventories + backlog.json
├── site/                     # static browse/preview website
├── tests/
└── .github/workflows/        # ci.yml, pages.yml
```

Use `SKILL.md` YAML frontmatter containing meaningful `name` and `description` for each independently discoverable skill. Document project-scoped installation by cloning the repo with `.claude/skills`, and optional global installation by copying/symlinking the two skill directories to the user's global Claude skills directory (verify current Claude Code path). Keep CLI helpers minimal and portable; Python standard library preferred for search/validation.

A static website (`site/`, built by `scripts/build_site.py` and deployed to GitHub Pages) lets people browse, search and preview both catalogs and copy asset paths. It is generated from the catalogs, is read-only, and is never required by the skills.

## 5. Data contract
Illustrative `sound-effects/catalog.json` record:
```json
{
  "id": "ui-click-soft-001",
  "title": "Soft Digital Click",
  "description": "Short unobtrusive UI selection click for professional technical presentations.",
  "category": "ui-clicks",
  "tags": ["click", "selection", "subtle", "tutorial"],
  "use_cases": ["slide selection", "diagram node activation"],
  "duration_seconds": 0.21,
  "intensity": 1,
  "file": "assets/ui/click-soft-001.wav",
  "source": "elevenlabs",
  "generation_prompt": "A single soft, dry digital interface click with a gentle rounded transient, no music or speech."
}
```

Illustrative `background-music/catalog.json` record:
```json
{
  "id": "education-calm-001",
  "title": "Quiet Circuit",
  "description": "Minimal warm electronic instrumental that stays behind spoken educational narration.",
  "category": "education",
  "tags": ["educational", "tech", "ambient", "voiceover"],
  "moods": ["calm", "focused"],
  "energy": 2,
  "instrumental": true,
  "voiceover_friendly": true,
  "loopable": false,
  "duration_seconds": 90.0,
  "file": "assets/education/quiet-circuit-001.mp3",
  "source": "suno",
  "generation_prompt": "Instrumental minimal electronic background for a technical explainer, warm pads, sparse percussion, no vocals, no recognizable melody or artist reference."
}
```

These are **schema examples, not claims that files exist**. Do not include illustrative records as usable assets in production catalogs. Define an explicit `schema_version`, and optionally format, sample rate, channels, peaks, integrated LUFS, hash, BPM (only when measured), and review flags. Never claim `loopable` or `voiceover_friendly` without human/technical confirmation.

Every asset should retain generation provenance, including timestamp, provider model/version if available, and provider output ID.

## 6. Maintainer creation workflow
1. **Inventory:** Create a complete plan of 200 SFX and 80 music candidates: unique ID, name, category, description, prompt, target duration, and intended contexts.
2. **Integration check:** Discover currently available ElevenLabs MCP actions and Suno access mechanism. Do not invent tool names or pretend Suno MCP is connected.
3. **Pilot:** After explicit cost approval, generate around 10 SFX and 5 tracks and place them in a staging folder. Save original outputs and prompts.
4. **Evaluate:** Listen to each, reject poor/duplicative/harmful/clipped content, record qualitative feedback, measure length/format/loudness, and check for silence, abrupt endings, and unintended vocals.
5. **Catalog:** Record verdicts on the review page (`make_review_page.py` → export → `apply_review.py`), then `build_catalog.py` moves accepted assets into the skill's `assets/` directory and adds them to its catalog with measured duration, hash and timing marks.
6. **Expand:** Generate in reviewed batches, adjusting prompts based on evidence, not just chasing item count.
7. **Publish:** Ship the reviewed audio together with the metadata, search tooling, and guidance for users to generate their own local collection.

Generation should be idempotent and resumable; track complete, failed, duplicate, rejected, and published states. Never silently spend credits or run a huge batch.

Planned assets that fail review and cannot be regenerated yet (for example, provider credits exhausted) go into `planning/backlog.json` with the reason and a suggested prompt fix; their inventory status is `needs-regeneration`.

## 7. Quality bar
**SFX:** A clear purpose, clean transient, no unrequested speech/music, meaningful variations, consistent naming, and reasonable loudness. Include clean, subtle sounds for instructional work.

**Music:** Strong category identity, vocals absent unless intentionally stated, minimal distraction behind narration, smooth endings, appropriate duration, no accidental copyrighted melodies, and audibly varied tracks. Test any loop claim at the join.

Both: inspect file encoding and duration, detect clipping/silence, reject exact/near duplicates (hash + listening), record reviewer approval, avoid unnecessarily large binary distributions. Consider releases or Git LFS for large assets while ensuring users can actually download assets via installation instructions.

## 8. CLI and tests
Minimal commands (names can vary if consistently documented):
```
python scripts/search_assets.py --skill sound-effects --query "subtle whoosh" --limit 5
python scripts/search_assets.py --skill background-music --mood suspense --limit 5
python scripts/validate_catalog.py --all
python scripts/build_site.py
python -m unittest discover -s tests
```

CI (`.github/workflows/ci.yml`) runs validation and tests on every push; `.github/workflows/pages.yml` builds and deploys the site from `main`.

Tests must verify: valid schema; unique IDs; categories and paths; no traversal beyond skill directory; audio files actually exist before an asset is described as ready; allowed media formats; accurate duration within tolerance; sensible empty-results behavior; no hard requirement for external API access; and that the site build publishes only catalogued files that exist.

## 9. Documentation / contributor experience
README should contain quick start, optional global/project installation, real examples, screenshots only when available, format support, contribution guidelines, and transparent status of how many **actually included** assets are available. Provide a one-command search example and clearly distinguish planned counts from shipped counts.

Contributions should require audio-file provenance, category/description/tags, checksums, and a human review. Accept useful code/catalog fixes independently of binary audio donations.

## 10. Milestones and definition of done
**M0 — Design:** two skills, exact category inventories, metadata schema, generation prompts.

**M1 — Working prototype:** searchable/validated skill structure and a limited pilot; no external call needed to use installed assets.

**M2 — Personal-ready:** curated library with 200 reviewed SFX and 80 reviewed music tracks (targets, not a mandate to generate wasteful duplicates), searchable by Claude Code.

**M3 — Public-ready:** open-source repository, tests, docs, the reviewed audio assets, and the browse site.

**Current status (2026-10-08):** M0, M1 and M3 are done. M2 is at 260 of 280: all 80 music tracks and 180 of 200 SFX are shipped, and the other 20 SFX are in `planning/backlog.json`.

### Acceptance tests
- "Find a gentle whoosh for a slide transition" returns real, existing SFX paths.
- "Create slides and add suitable sound effects" does not cause the music skill to activate by default.
- "Choose suspense music for a 30-second reel" returns suitable instrumental candidates where available.
- "Work offline" succeeds without provider credentials or generative endpoints.
- Search never fabricates missing assets, and public docs disclose actual shipped counts.

## 11. References
- Claude skill documentation: https://platform.claude.com/docs/en/managed-agents/skills

**Implementation direction:** Keep the two skills boring and portable. Excellent filenames, rich descriptions, real audio, and simple search are the product.
