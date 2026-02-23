# Langsame Nachrichten — Brainstorm

**Date:** 2026-02-23
**Status:** Complete — MVP implemented 2026-02-24

## What We're Building

A beautiful Progressive Web App called **Langsame Nachrichten** that delivers a daily digest of 3-5 world news stories spoken in German at 5 difficulty levels. Built for a language learner preparing for a holiday — someone with high-school German who wants to rebuild listening comprehension through daily exposure to real news content.

The core experience: open the app each morning, pick a story, listen to it in German at your chosen difficulty level, optionally reveal the German text or English translation to check understanding. Like a morning newspaper you listen to in German.

## Why This Approach

### Fully Static Architecture

The entire app is **serverless with no running backend**. A Python batch job runs daily via GitHub Actions, fetching news from Deutsche Welle, generating 5 difficulty levels of each story via LLM, synthesizing audio via TTS, and publishing everything as static files to GitHub Pages. The PWA simply fetches pre-built JSON and audio files.

**Why this works:**
- Zero hosting cost (GitHub Actions + Pages free tier)
- No server to maintain, monitor, or secure
- Content works even if the backend breaks (today's files are already published)
- Simplest possible client — just a static site that reads JSON

### Deutsche Welle as Primary Source

DW is a German public broadcaster that already publishes news for international audiences, including a "langsam gesprochene Nachrichten" (slowly spoken news) program. Their RSS feeds provide reliable, freely available world news content. Supplemented by Tagesschau RSS if DW's daily selection feels thin.

Using authentic German sources means the LLM **simplifies** rather than **translates**, preserving natural German idiom and phrasing.

### Progressive Difficulty Layers

The 5 difficulty levels are **vocabulary and grammar based** (not speed-based). They're structured as progressive layers:

- **Level 1:** Simple present tense, basic vocabulary, short sentences. Conversational register. A 2-3 sentence core summary.
- **Level 2:** Adds common subordinate clauses, past tense, slightly expanded vocabulary.
- **Level 3:** Introduces passive voice, more complex sentence structures, news-specific vocabulary.
- **Level 4:** Near-native news register with relative clauses, subjunctive mood, domain terms.
- **Level 5:** Authentic/lightly edited version of the original DW article. Full complexity.

Each level **builds on the previous one** — a learner moving from Level 2 to Level 3 recognizes the same story structure with added complexity. This is pedagogically stronger than independent rewrites.

Speed control is **separate** — the HTML5 audio player provides playback rate adjustment (0.5x–2x) via a simple UI toggle.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **App type** | PWA | Installable on iPhone home screen, no App Store, fastest to build, works everywhere |
| **Backend** | Python + GitHub Actions (daily cron) | Free hosting, no running server, outputs static files |
| **Hosting** | GitHub Pages | Free, simple, serves static JSON + audio files |
| **News source** | Deutsche Welle (primary) + Tagesschau (secondary) | Authentic German, free, international-audience content |
| **LLM provider** | OpenAI directly (gpt-4o-mini) | No abstraction for MVP — switch by editing code. Model configurable via `LLM_MODEL` env var |
| **TTS provider** | OpenAI TTS directly (tts-1, nova) | No abstraction for MVP — voice configurable via `TTS_VOICE` env var |
| **Difficulty model** | 5 levels, vocabulary/grammar based, progressive layers | Each level expands on the previous. Speed is a separate control |
| **Content cadence** | Daily digest, 3-5 stories | Runs at 6 AM AEDT (Melbourne timezone). Like a morning newspaper |
| **Content retention** | Today only, full site redeploy | Each build deploys a complete self-contained site. No persistence between runs |
| **User state** | None | Radio model — open, pick a level, listen. No accounts, no tracking, no persistence |
| **Level selection** | Global setting | One level selector at the top applies to all stories |
| **Text display** | Hidden by default, toggle to reveal | Audio-first experience. German text and English translation each behind separate toggles |
| **Translation** | Full article translation, simple toggle | Reference tool for checking understanding, not a teaching gate |
| **Design** | Beautiful, premium, feels special | This is a gift — should feel polished and delightful, not utilitarian |
| **Name** | Langsame Nachrichten | "Slow News" in German. Playful, ties to the German learning theme |

## Architecture Overview

```
[Deutsche Welle RSS] ──> [Python Batch Job (GitHub Actions, 6 AM AEDT)]
                              │
                              ├── Fetch top 3-5 stories
                              ├── LLM: Generate 5 progressive difficulty levels per story
                              ├── LLM: Generate English translation per level
                              ├── TTS: Generate audio for each level (25 audio files)
                              ├── Prune content older than 7 days
                              └── Publish static JSON + audio to GitHub Pages
                                       │
                                       ▼
                              [PWA (Static Site)]
                              ├── Fetches today's digest JSON
                              ├── Displays story list with headlines
                              ├── Audio player with speed controls
                              ├── German text toggle
                              ├── English translation toggle
                              └── Global difficulty level selector
```

### Daily Batch Output Structure

```
output/
  content/
    latest.json            # Copy of today's digest (PWA fetches this)
    2026-02-23/
      digest.json          # All story text + metadata in one file
      {article-id}/
        level-1.mp3        # TTS audio per level (48kbps mono)
        level-2.mp3
        ...
        level-5.mp3
      {article-id}/
        ...
```

## Open Questions (Resolved)

- ~~**LLM prompt design:**~~ Resolved — top-down CEFR-aligned sequential prompting (C1→A1) with explicit grammar inventories per level. See `backend/prompts.py`.
- ~~**TTS voice selection:**~~ Using OpenAI `nova` voice. Configurable via `TTS_VOICE` env var.
- ~~**DW RSS feed reliability:**~~ Verified — RSS `id` field gives article IDs directly, DW JSON API returns full text. Feed consistently has ~85 entries.
- ~~**Audio file size budget:**~~ OpenAI TTS outputs ~1 MB/min. ffmpeg re-encodes to 48kbps mono (~0.36 MB/min). TTS has 4096 char limit — handled by sentence-boundary chunking.
- ~~**PWA icon and branding:**~~ SVG favicon with "LN" typographic mark in Fraunces. PNG icons still needed for full PWA install.

## Future Extensions (Not in v1)

- **Comprehension questions:** On-demand LLM-generated questions after listening (requires a lightweight API proxy for secure LLM calls)
- **Vocabulary hints:** Tap difficult words for inline definitions/translations
- **Per-story level switching:** Override the global level for individual stories
- **Past content browsing:** Browse the previous 7 days of stories
- **Push notifications:** "Your daily German news is ready" morning notification
- **Offline support:** Service worker caching for true offline playback
- **Progress tracking:** Remember which stories were listened to, track streaks
