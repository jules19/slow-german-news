---
title: "feat: Build Langsame Nachrichten MVP"
type: feat
date: 2026-02-23
deepened: 2026-02-23
---

# Build Langsame Nachrichten MVP

## Enhancement Summary

**Deepened on:** 2026-02-23
**Research agents used:** 8 (architecture, performance, security, simplicity, python-review, LLM-prompts, DW-API, frontend-design)

### Critical Discoveries

1. **DW has a public JSON API** (`api.dw.com/api/detail/article/{id}`) — returns full article text. No scraping needed. This resolves Open Question #1.
2. **Tailwind v4 CDN is not production-ready** — it's a runtime JS compiler. Must pre-build CSS instead for <2s load target.
3. **OpenAI TTS outputs ~1-1.2 MB/min, not 0.5 MB/min** — add ffmpeg re-encoding to 48kbps mono to hit size targets.
4. **CEFR-aligned prompting with grammar inventories** produces far more consistent difficulty levels than vague "make it simpler" instructions.
5. **Content persistence gap in CI** — each GitHub Actions run starts clean, so pruning logic needs rethinking (simplified to today-only deployment).

### Simplifications Applied (per simplicity review)

- **Removed pluggable provider abstraction** — use OpenAI for both LLM and TTS. Switch by editing code, not configuring interfaces.
- **Reduced config surface** from 10 env vars to 4.
- **Simplified service worker** to app-shell-only caching for MVP.
- **Kept 5 difficulty levels** (user explicitly requested this in brainstorm) but mapped them to CEFR (A1-C1) for precision.

---

## Overview

Build a fully static Progressive Web App that delivers a daily digest of 3-5 German news stories at 5 CEFR-aligned difficulty levels, with audio playback and text/translation toggles. The entire content pipeline runs as a daily Python batch job via GitHub Actions, publishing static JSON + MP3 files to GitHub Pages. No running backend.

**Brainstorm:** `docs/brainstorms/2026-02-23-langsame-nachrichten-brainstorm.md`

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│               GitHub Actions (Daily Cron)                │
│                6 AM AEDT / 19:23 UTC                     │
│                                                          │
│  1. Fetch DW RSS → extract article IDs                   │
│  2. Fetch full text via DW JSON API                      │
│  3. LLM: 5 CEFR levels per story (top-down C1→A1)       │
│  4. LLM: English translation per level                   │
│  5. TTS: Audio per level → ffmpeg re-encode to 48kbps    │
│  6. Build Tailwind CSS (npx @tailwindcss/cli)            │
│  7. Publish to GitHub Pages                              │
└──────────────────────────┬───────────────────────────────┘
                           │ Static files
                           ▼
┌─────────────────────────────────────────────────────────┐
│               GitHub Pages (Static Host)                 │
│                                                          │
│  content/                                                │
│    latest.json  ← copy of today's digest                 │
│    2026-02-23/                                           │
│      digest.json                                         │
│      story-1/level-1.mp3 ... level-5.mp3                 │
│      story-2/...                                         │
│                                                          │
│  index.html, app.js, sw.js, manifest.json, styles.css    │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS fetch
                           ▼
┌─────────────────────────────────────────────────────────┐
│        PWA (Vanilla JS + Pre-built Tailwind CSS)         │
│                                                          │
│  • Story list (today's headlines)                        │
│  • Audio player with speed controls                      │
│  • German text toggle                                    │
│  • English translation toggle                            │
│  • Global difficulty level selector (1-5)                │
└─────────────────────────────────────────────────────────┘
```

### Key Architectural Change: Today-Only Deployment

Each GitHub Actions run deploys a **complete, self-contained site**. The `_site/` directory contains the frontend files plus today's content only. No persistence between runs, no pruning logic needed. If the batch fails, yesterday's deployment remains live on GitHub Pages until the next successful deploy.

This eliminates the content persistence gap identified in the architecture review.

## Content Schema

### `content/latest.json`

Always contains today's digest. The PWA fetches this single URL.

```json
{
  "schema_version": 1,
  "date": "2026-02-23",
  "generated_at": "2026-02-23T19:23:00Z",
  "stories": [
    {
      "id": "76083226",
      "headline_de": "Bundeskanzler kündigt neue Klimapolitik an",
      "headline_en": "Chancellor announces new climate policy",
      "summary_en": "Germany's chancellor unveiled a comprehensive climate reform package today...",
      "source_url": "https://www.dw.com/de/a-76083226",
      "levels": {
        "1": {
          "text_de": "Der Bundeskanzler hat heute über das Klima gesprochen. Er will neue Regeln machen.",
          "text_en": "The chancellor spoke about the climate today. He wants to make new rules.",
          "audio_url": "content/2026-02-23/76083226/level-1.mp3",
          "audio_duration_seconds": 15
        },
        "2": { },
        "3": { },
        "4": { },
        "5": { }
      }
    }
  ]
}
```

Changes from original plan:
- **Added `schema_version: 1`** — future-proofs the client (architecture review)
- **Story IDs are DW article IDs** (from the JSON API), not sequential numbers
- **`latest.json` is a copy**, not a symlink (GitHub Pages doesn't support symlinks)

### Audio files

- Format: MP3, mono, **48kbps** (re-encoded via ffmpeg from TTS output)
- Expected size: **~0.36 MB per minute** of speech (after re-encoding)
- TTS speech rate: Same across all levels. Speed controlled by user via `playbackRate`.
- Daily total: ~25 files, **~10-15 MB total** (after re-encoding)

### Research Insight: MP3 Size Correction

OpenAI TTS outputs MP3 at ~1.0-1.2 MB/min (not the 0.5 MB/min originally estimated). The API doesn't expose a bitrate parameter. **Must add a ffmpeg post-processing step** to re-encode to mono 48kbps (perfectly adequate for speech, cuts size by ~65%):

```python
subprocess.run([
    "ffmpeg", "-i", "raw.mp3",
    "-ac", "1",        # mono
    "-ab", "48k",      # 48kbps
    "-ar", "22050",    # 22kHz sample rate (speech doesn't need 44.1kHz)
    "output.mp3"
], check=True)
```

## Difficulty Levels — CEFR-Aligned Definition

Levels are mapped to the Common European Framework of Reference (CEFR) for precise, research-backed difficulty control.

| Level | CEFR | Label | Grammar Inventory | Example |
|-------|------|-------|-------------------|---------|
| **1** | A1 | Einfach | Present tense only, SVO main clauses, und/oder/aber, basic vocabulary. 2-3 sentences. Max ~8 words/sentence. | *"Die Regierung macht neue Regeln für das Klima. Die Regeln sind wichtig."* |
| **2** | A2 | Leicht | Perfekt tense, weil/dass clauses, modal verbs (können, müssen), separable verbs. Max ~12 words/sentence. | *"Die Regierung hat neue Klimaregeln gemacht, weil sie die Industrie verändern will."* |
| **3** | B1 | Mittel | Präteritum, passive voice (Vorgangspassiv), relative clauses, common Konjunktiv II (wäre, hätte). Max ~18 words/sentence. | *"Die Regierung hat ein Reformpaket zur Klimapolitik verabschiedet. Es wird Auswirkungen auf die Industrie haben."* |
| **4** | B2 | Schwer | Full Konjunktiv II, genitive prepositions (trotz, wegen), two-part connectors (sowohl...als auch), domain vocabulary. Max ~25 words/sentence. | *"Die Bundesregierung hat am Mittwoch ein Reformpaket verabschiedet, das weitreichende Auswirkungen auf die Industrie haben dürfte."* |
| **5** | C1 | Original | Konjunktiv I (indirect speech), extended participial constructions, nominalization, full news register. Lightly edited original. | *"Die Bundesregierung hat am Mittwoch ein umfassendes Reformpaket zur Klimapolitik verabschiedet, das weitreichende Auswirkungen auf die Industrie haben wird."* |

### Research Insight: CEFR Prompting Strategy

Research ("From Tarzan to Tolkien", 2024) shows that including **explicit CEFR descriptors with concrete grammar inventories** in each prompt reduces control error from 0.57 to 0.28 compared to just saying "write at A1 level."

**Generation order: Top-down, sequential, one level per step.**
- Start from original article → generate C1 (Level 5) as lightly edited version
- C1 → B2 → B1 → A2 → A1, each step simplifying by exactly one CEFR level
- Each prompt specifies **what to remove/replace** and **what's still allowed** at the target level

This produces more coherent progressive layers than generating all levels at once or jumping directly from C1 to A1.

### Research Insight: Output Validation

Use German readability metrics to verify monotonic difficulty:

| Metric | Level 1 (A1) | Level 3 (B1) | Level 5 (C1) |
|--------|:---:|:---:|:---:|
| LIX score | < 25 | 35-45 | 55+ |
| Avg sentence length | 5-8 words | 12-18 words | 20-30 words |
| Subordinate clause ratio | 0 | 0.15-0.30 | 0.35+ |

The **Wiener Sachtextformel** (via `textacy` library) provides a German-specific grade level metric. All metrics should increase monotonically from Level 1 to 5; flag and regenerate any level that violates ordering.

## Implementation Phases

### Phase 1: Content Pipeline (Python batch job)

Build and test the entire content generation pipeline locally before touching the frontend.

**Development environment:**
- Python 3.12 in a **virtual environment** (`python -m venv .venv`)
- All dependencies installed in the venv, never globally
- `pyproject.toml` for project metadata and dependency management

**Deliverables:**
- `backend/` directory with typed Python modules
- `pyproject.toml` with pinned dependencies
- Locally runnable: `python -m backend.build` produces `output/` directory

#### Project Structure

```
backend/
    __init__.py
    models.py        # Dataclasses: RawStory, LevelContent, ProcessedStory, Digest
    sources.py       # fetch_stories() -> list[RawStory]
    levels.py        # generate_levels(story: RawStory) -> ProcessedStory
    audio.py         # generate_audio(story: ProcessedStory) -> ProcessedStory
    build.py         # main() orchestrator + config
    prompts.py       # LLM prompt templates (these will be long)
pyproject.toml
```

#### 0. Project Setup — `pyproject.toml`

```toml
[project]
name = "langsame-nachrichten"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "feedparser>=6.0",
    "openai>=1.0",
    "httpx>=0.27",
    "mutagen>=1.47",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.9",
]

[project.scripts]
build-news = "backend.build:main"
```

**Setup commands (local development):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### 1.1 Data Models — `backend/models.py`

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawStory:
    id: str
    title: str
    link: str
    full_text: str
    published_date: datetime


@dataclass(frozen=True, slots=True)
class LevelContent:
    text_de: str
    text_en: str
    audio_url: str | None = None
    audio_duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ProcessedStory:
    id: str
    headline_de: str
    headline_en: str
    summary_en: str
    source_url: str
    levels: dict[int, LevelContent]
```

- [x] Define typed dataclasses for all pipeline data
- [x] All functions accept and return these types, not raw dicts

#### 1.2 RSS Fetcher + DW API — `backend/sources.py`

**Key discovery: DW has a public JSON API.** No web scraping needed.

```python
# Two-step fetch:
# 1. RSS feed (https://rss.dw.com/xml/rss-de-all) for article discovery
# 2. DW JSON API (https://api.dw.com/api/detail/article/{id}) for full text
#
# Dependencies: feedparser, httpx
# Output: list[RawStory]
```

- [x] Fetch DW RSS feed using `feedparser` — use `rss-de-all` (84 items, reliable)
- [x] Extract article IDs from `<guid>` fields
- [x] Fetch full article text from `api.dw.com/api/detail/article/{id}` using `httpx`
- [x] Use the API's `text` field (plain text) or `body` array (structured paragraphs)
- [x] Select top 3-5 stories by recency
- [x] Set explicit timeouts on all HTTP requests (30 seconds)
- [x] Handle failure: log error, exit gracefully (yesterday's deployment stays live)

```python
import httpx

async def fetch_article_text(article_id: str) -> str:
    """Fetch full article text from DW's public JSON API."""
    url = f"https://api.dw.com/api/detail/article/{article_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data["text"]  # Full plain-text article body
```

#### 1.3 LLM Difficulty Generator — `backend/levels.py`

```python
# Takes a German news article and generates 5 CEFR-aligned levels
# Uses OpenAI API directly (no abstraction layer)
#
# Dependencies: openai
# Output: ProcessedStory
```

- [x] Use `openai` SDK directly — model set via `LLM_MODEL` env var (default: `gpt-4o-mini`)
- [x] Implement top-down sequential prompting: C1 → B2 → B1 → A2 → A1
- [x] Each prompt includes explicit CEFR grammar inventory and concrete "CHANGES TO MAKE" operations
- [x] Generate English translations for each level (can be done in same prompt or separate call)
- [x] Consider using OpenAI structured output (`response_format={"type": "json_schema", ...}`) for reliable parsing
- [x] Validate: all 5 levels present, text non-empty, strip any HTML tags from output
- [x] Handle partial failure: skip story on LLM error, log and continue with remaining stories

#### 1.4 TTS Audio Generator — `backend/audio.py`

```python
# Takes German text for each level and generates MP3 audio
# Uses OpenAI TTS directly, then re-encodes via ffmpeg
#
# Dependencies: openai, subprocess (ffmpeg)
# Output: MP3 files + audio_duration_seconds
```

- [x] Use OpenAI `tts-1` model, `nova` voice (configurable via env var)
- [x] **Re-encode all TTS output via ffmpeg**: mono, 48kbps, 22kHz sample rate
- [x] Calculate `audio_duration_seconds` using `mutagen` library after encoding
- [x] Parallelize TTS calls across levels using `asyncio.gather()` (5 concurrent per story)
- [x] Handle TTS failure per level: mark as unavailable in JSON (`audio_url: null`)

```python
import asyncio
from mutagen.mp3 import MP3

async def generate_audio_for_story(story: ProcessedStory) -> ProcessedStory:
    """Generate audio for all levels in parallel."""
    tasks = [generate_single_audio(story.id, level, content)
             for level, content in story.levels.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... update story with audio URLs and durations
```

#### 1.5 Build Orchestrator — `backend/build.py`

```python
# Main entry point. Orchestrates the full pipeline.
# Config is inline (4 env vars), not a separate module.

import os

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
TTS_VOICE = os.environ.get("TTS_VOICE", "nova")
MAX_STORIES = int(os.environ.get("MAX_STORIES", "5"))
```

- [x] Fetch stories via `sources.py`
- [x] Generate difficulty levels via `levels.py`
- [x] Generate audio via `audio.py` (parallelized)
- [x] Assemble `digest.json` with all metadata
- [x] Copy `digest.json` → `latest.json`
- [x] Write all output to `output/content/{date}/` directory
- [x] Log summary: stories processed, levels generated, audio files created, total size
- [x] Use `pathlib.Path` throughout (not `os.path`)

### Phase 2: Frontend PWA

Build the static PWA that consumes the content pipeline output.

**Deliverables:**
- `frontend/` directory with static files
- CSS pre-built via Tailwind CLI (added to GitHub Actions build step)
- Locally testable with any static file server

#### File structure

```
frontend/
  index.html              # Single HTML file
  app.js                  # All application logic
  sw.js                   # Service worker (minimal, app-shell only)
  manifest.json           # PWA manifest
  input.css               # Tailwind source (compiled to styles.css during build)
  icons/
    apple-touch-icon-180.png
    icon-192.png
    icon-512.png
    favicon.svg
```

#### 2.1 HTML Shell — `frontend/index.html`

- [x] **Pre-built Tailwind CSS** (NOT CDN) — compiled during GitHub Actions build via `npx @tailwindcss/cli`
- [x] Google Fonts: Fraunces (headlines), Source Serif 4 (body), Source Sans 3 (UI) with `<link rel="preconnect">`
- [x] PWA meta tags: viewport, theme-color, apple-mobile-web-app-capable, apple-mobile-web-app-status-bar-style
- [x] `<link rel="manifest" href="/manifest.json">`
- [x] `<link rel="apple-touch-icon" href="/icons/apple-touch-icon-180.png">`
- [x] Safe area handling via `viewport-fit=cover` and `env(safe-area-inset-*)`
- [x] Service worker registration
- [x] **Meta CSP tag** restricting script sources: `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com; media-src 'self'; img-src 'self'">`

### Research Insight: Why Not Tailwind CDN

The `@tailwindcss/browser` package is explicitly **not for production** (Tailwind team's own docs). It's a full JS compiler (~hundreds of KB) that runs on every page load, causing:
- 500ms-2s of main-thread blocking on mobile
- Visible Flash of Unstyled Content (FOUC)
- Fails the plan's own "loads in under 2 seconds on 4G" requirement

**Solution:** Pre-build CSS via Tailwind CLI. Add one command to the GitHub Actions build:
```bash
npx @tailwindcss/cli -i frontend/input.css -o frontend/styles.css --minify
```
Output: ~5-15 KB static CSS file. Zero runtime cost.

#### 2.2 PWA Manifest — `frontend/manifest.json`

```json
{
  "name": "Langsame Nachrichten",
  "short_name": "Nachrichten",
  "description": "Daily German news at your level",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#FAF7F2",
  "theme_color": "#1C1917",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Updated `background_color` and `theme_color` to match the design system.

#### 2.3 Application Logic — `frontend/app.js`

**Views (single-page, no router needed):**

1. **Story List View** (default)
   - Masthead: "Langsame Nachrichten" in Fraunces 24px + date in German format ("23. Februar 2026")
   - Global difficulty level selector: 5 circle buttons with German labels (Einfach, Leicht, Mittel, Schwer, Original)
   - List of stories separated by thin horizontal rules (editorial style, no cards)
   - Each story: `headline_en` (Fraunces 20px), `summary_en` (Source Serif 15px), listening time
   - Tap a story → fade transition to Story Detail View
   - Staggered entrance animation on load (0.1s between elements)

2. **Story Detail View**
   - "← Zurück" to return to list
   - `headline_de` at current difficulty level (Fraunces 26px)
   - "Show German Text" and "Show English" toggle buttons — outlined when off, filled when on
   - German text in Source Serif 18px at line-height 1.7 (generous for reading German)
   - English translation in Source Serif 18px italic, muted color (visually distinct from German)
   - Text reveals with slide-down + fade animation
   - Audio player (sticky bottom bar, dark charcoal `#292524`):
     - Play/pause button (terracotta circle, 48px, scale-down on press)
     - Progress bar (thin 4px, terracotta fill, scrub handle appears on touch)
     - Current time / total time (tabular numbers)
     - Speed selector: 0.75x, 1x, 1.25x, 1.5x (dim when inactive, terracotta when active)
   - **120px bottom padding** on scroll container so text isn't hidden behind player

**Security: Content rendering rules:**
- **NEVER use `innerHTML`** to render content from `digest.json`
- Use `textContent` or `createTextNode()` exclusively for all LLM-generated fields
- This neutralizes the entire XSS-via-LLM-output attack chain

**State management:**
- `localStorage` for exactly two preferences:
  - `difficulty` (1-5, default: 2)
  - `speed` (0.5-2.0, default: 1.0)
- **Validate on read**: `Math.max(1, Math.min(5, parseInt(val, 10) || 2))`

**Data fetching:**
- On app open, fetch `/content/latest.json`
- If fetch fails: *"Keine Nachrichten verfügbar."* / *"No news available. Please try again later."* (Source Serif italic, centered)
- No polling, no background refresh

**Audio playback:**
- Standard HTML5 `<audio>` element with `playbackRate`
- `audio.preservesPitch = true`
- **Preload audio when entering Story Detail View** (don't wait for user to tap Play):
  ```javascript
  const audio = new Audio();
  audio.preload = 'auto';
  audio.src = story.levels[currentLevel].audio_url;
  ```
- When user changes difficulty level mid-playback: pause, load new audio, restart from beginning
- Media Session API for lock screen controls

#### 2.4 Service Worker — `frontend/sw.js`

Simplified to **app-shell caching only** for MVP. No audio caching, no content caching.

```javascript
const CACHE = 'shell-v1';
const SHELL = ['/', '/index.html', '/app.js', '/styles.css', '/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (SHELL.includes(url.pathname)) {
    // Stale-while-revalidate for app shell
    e.respondWith(
      caches.match(e.request).then(cached => {
        const fetchPromise = fetch(e.request).then(response => {
          caches.open(CACHE).then(cache => cache.put(e.request, response.clone()));
          return response;
        });
        return cached || fetchPromise;
      })
    );
  }
});
```

Key decisions:
- **Stale-while-revalidate** for app shell (not cache-first) — prevents stale HTML after deploys
- **`skipWaiting()` + `clients.claim()`** for immediate activation
- **No audio/content caching** — she uses this over wifi at home; offline audio is a future extension
- This is ~20 lines, not 60+

#### 2.5 Design System

The design should feel **premium and thoughtful** — this is a gift.

**Color Palette:**

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#FAF7F2` | Warm cream — paper-like, not clinical white |
| Surface | `#F0EBE3` | Cards, secondary surfaces |
| Text Primary | `#1C1917` | Headlines, body (warm near-black) |
| Text Secondary | `#78716C` | Metadata, timestamps |
| Accent | `#C2410C` | Active pill, play button, interactive highlights (terracotta) |
| Accent Soft | `#FFF7ED` | Selected state backgrounds |
| Border | `#E7E5E4` | Thin rules between stories |
| Player BG | `#292524` | Dark charcoal audio player bar |
| Player Text | `#FAFAF9` | Text on dark player |

**Typography:**

| Element | Font | Size | Weight |
|---------|------|------|--------|
| App title | Fraunces | 24px | 700 |
| Story headline (list) | Fraunces | 20px | 600 |
| Story headline (detail) | Fraunces | 26px | 600 |
| Body text (German/English) | Source Serif 4 | 18px | 400, line-height 1.7 |
| Summary text | Source Serif 4 | 15px | 400 |
| UI labels, difficulty pills | Source Sans 3 | 13-14px | 600 |
| Audio time display | Source Sans 3 | 13px | 400 (tabular nums) |

**Layout Principles:**
- 24px horizontal padding (generous, magazine-like)
- No cards — stories separated by thin horizontal rules (editorial)
- Date displayed in German: "23. Februar 2026"
- Difficulty levels labeled in German: Einfach, Leicht, Mittel, Schwer, Original
- Faint paper-noise SVG texture on background (2% opacity)
- Masthead double-rule below app title
- Staggered entrance animation (0.1s delay per element)
- Text reveals with slide-down + fade (max-height + opacity transition)
- Play button: scale(0.93) on press for tactile feedback

**App Icon:** Typographic mark — warm cream square with "LN" in Fraunces Bold, ink color.

### Phase 3: GitHub Actions & Deployment

#### 3.1 GitHub Actions Workflow — `.github/workflows/build-and-deploy.yml`

```yaml
name: Build and Deploy Langsame Nachrichten

on:
  schedule:
    - cron: '23 19 * * *'  # 19:23 UTC ≈ 6:23 AM AEDT
  workflow_dispatch:        # Manual trigger for testing

concurrency:
  group: "pages"
  cancel-in-progress: false

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install Python dependencies
        run: pip install -e .

      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Build today's content
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python -m backend.build

      - name: Build Tailwind CSS
        run: npx @tailwindcss/cli -i frontend/input.css -o frontend/styles.css --minify

      - name: Assemble site
        run: |
          mkdir -p _site
          cp -r frontend/* _site/
          rm -f _site/input.css
          cp -r output/content _site/content

      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v4
        with:
          path: '_site'

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

Changes from original:
- Added **ffmpeg installation** step (for audio re-encoding)
- Added **Tailwind CSS build** step (replaces CDN)
- Removed `input.css` from `_site` (source file, not needed in deploy)
- Uses `pip install -e .` (from `pyproject.toml`) instead of `pip install -r requirements.txt`

#### 3.2 Content Strategy

Each deploy is a **complete site replacement**. No content accumulates across runs:
- Today's content is generated fresh
- The `_site/` artifact contains frontend + today's content only
- If the build fails, yesterday's deployment persists on GitHub Pages
- Total deployed size: ~15-20 MB (well under 1 GB limit)

#### 3.3 Monitoring

- [x] GitHub Actions emails on workflow failure (default)
- [x] Build script logs to stdout: stories processed, errors encountered, total audio size
- [x] Inactive repo warning: GitHub disables scheduled workflows after 60 days of no commits — push a keep-alive commit or re-enable manually

#### 3.4 API Key Security

- [x] Create a **dedicated OpenAI project** for this application
- [x] Set a **monthly spending limit** ($10/month is generous for this usage)
- [x] API key is scoped to the single build step (not the whole job) — already correct in workflow
- [x] Enable GitHub Dependabot for automated vulnerability alerts on Python dependencies

## Acceptance Criteria

### Functional Requirements

- [x] Daily batch job fetches 3-5 DW news stories and publishes content by 6:30 AM AEDT
- [x] Each story has 5 CEFR-aligned difficulty levels (A1-C1) of German text
- [x] Each level has an English translation
- [x] Each level has a TTS audio file in MP3 format (48kbps mono)
- [x] PWA loads on iPhone Safari and displays today's story headlines
- [x] User can select a global difficulty level (1-5)
- [x] User can tap a story to listen to its audio at the selected level
- [x] User can adjust playback speed (0.75x, 1x, 1.25x, 1.5x)
- [x] User can toggle German text display
- [x] User can toggle English translation display
- [x] PWA is installable on iPhone home screen
- [x] All LLM-generated content rendered via `textContent` (never `innerHTML`)

### Non-Functional Requirements

- [x] Audio files are mono MP3 at 48kbps after ffmpeg re-encoding
- [x] PWA loads in under 2 seconds on 4G (no Tailwind CDN; pre-built CSS)
- [x] Total daily content payload is under 15 MB
- [x] Design feels premium and polished on iPhone
- [x] All Python code uses type hints and dataclasses

### Quality Gates

- [x] Batch job runs successfully end-to-end locally before deploying
- [x] LLM output validated: all 5 levels present, readability metrics increase monotonically
- [x] Audio plays correctly in iOS Safari with speed adjustment
- [x] Audio preloads when entering story detail view (no dead air on play)

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| DW RSS feed or API changes | No new content | API is stable public endpoint; yesterday's deployment stays live |
| LLM produces poor progressive layers | Bad learning experience | CEFR-aligned prompts with grammar inventories; validate with readability metrics |
| iOS Safari `playbackRate` issues | Speed control broken | Test on real iPhone early; Web Audio API as fallback |
| GitHub Pages bandwidth (100 GB/mo) | Site goes down | Single user ~0.5 GB/mo; move audio to CDN if shared |
| Audio stops on iOS screen lock | Poor listening UX | Media Session API; document limitation |
| DW content licensing | Legal risk | Public broadcaster, non-commercial use, attribution provided |
| GitHub Actions cron delays | Content late some mornings | `workflow_dispatch` for manual trigger if needed |
| OpenAI API key leak | Cost exposure | Scoped project key with $10/month spending limit |

## Resolved Questions

1. **DW article full text**: Use the DW JSON API at `api.dw.com/api/detail/article/{id}`. Returns full plain text in the `text` field. No scraping needed.
2. **LLM prompt strategy**: Top-down sequential CEFR-aligned prompting (C1→B2→B1→A2→A1) with explicit grammar inventories per level.
3. **Audio file sizes**: OpenAI TTS outputs ~1 MB/min. Re-encode via ffmpeg to 48kbps mono (~0.36 MB/min).
4. **`playbackRate` on iOS**: Likely works on iOS 17+ per caniuse data, but Apple's archived docs say unsupported. **Must test on real iPhone before building full player.** Web Audio API fallback exists.

## Remaining Open Questions

1. **Which TTS voice sounds best for German news?** Generate samples with OpenAI `nova`, `echo`, and `onyx` voices and compare. Can be done as first implementation task.
2. **Exact CEFR prompt wording**: The grammar inventories per level need iterative tuning. Start with the research-provided templates and adjust based on output quality.

## Future Extensions (Not in MVP)

- Comprehension questions (on-demand LLM generation via serverless proxy)
- Vocabulary hints (tap words for definitions)
- Per-story difficulty override
- Past content browsing (previous 7 days)
- Push notifications
- Offline audio caching (enhanced service worker)
- Progress tracking / streaks
- Content validation pipeline (automated readability metric checks)

## References

### Key Discovery: DW JSON API

```
https://api.dw.com/api/detail/article/{ARTICLE_ID}
```
- No authentication required
- Returns: `name` (headline), `text` (full plain text), `body` (structured paragraphs), `displayDate`, `categoryName`
- Article IDs come from RSS `<guid>` field

### Research Sources

- [From Tarzan to Tolkien: CEFR Control in LLMs](https://arxiv.org/html/2406.03030v1) — CEFR prompting strategies
- [Step by Step: Sequential Simplification](https://arxiv.org/html/2602.07499v1) — Per-level transitions outperform direct jumps
- [Progressive Document Simplification](https://arxiv.org/html/2501.03857v1) — Top-down simplification preserves meaning
- [Kapitel Zwei: German Course Content A1-C2](https://kapitel-zwei.de/en/course-content/) — Grammar inventories per CEFR level
- [Tailwind CSS v4 CDN Docs](https://tailwindcss.com/docs/installation/play-cdn) — "designed for development only"
- [GitHub Pages Limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) — 1 GB site, 100 GB/mo bandwidth
- [OpenAI TTS Guide](https://platform.openai.com/docs/guides/text-to-speech) — API reference, pricing
- [textacy: Wiener Sachtextformel](https://textacy.readthedocs.io/) — German readability metric

### Key Libraries

| Library | Purpose |
|---------|---------|
| `feedparser` | RSS parsing |
| `httpx` | HTTP client for DW API (async, timeouts) |
| `openai` | LLM calls + TTS generation |
| `mutagen` | MP3 duration calculation |
| `ffmpeg` (system) | Audio re-encoding to 48kbps mono |
| Tailwind CSS CLI | Pre-built CSS (build step, not runtime) |
| Fraunces / Source Serif 4 / Source Sans 3 | Typography (Google Fonts) |
