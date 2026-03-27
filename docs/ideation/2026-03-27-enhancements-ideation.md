---
date: 2026-03-27
topic: enhancements
focus: local cron deployment and general product improvements
---

# Ideation: Product Enhancements

## Codebase Context

- Python batch pipeline (DW news → OpenAI LLM for CEFR levels → TTS audio → GitHub Pages)
- 3 stories/day x 3 difficulty levels (A1, B1, C1) with German audio + English translation
- Frontend: vanilla JS PWA with audio player, service worker for offline shell
- Just added local Qwen3-TTS (free on Apple Silicon, voice cloning)
- CI cron disabled, only manual trigger. No local automation exists.
- User wants: local cron at 6am → git push → GitHub Pages, keep 3-day rolling window

## Ranked Ideas

### 1. Local Cron + Push + 3-Day Prune Script
**Description:** A launchd plist that runs at 6am: pipeline with TTS_BACKEND=qwen → prune content older than 3 days → git commit + push to gh-pages → GitHub Pages auto-deploys.
**Rationale:** Everything else depends on this. Without daily automation, the product promise is broken.
**Downsides:** Mac must be on/awake at 6am. No fallback if it fails silently.
**Confidence:** 95%
**Complexity:** Low
**Status:** Explored (brainstorm 2026-03-27)

### 2. 3-Day Browsable Archive in Frontend
**Description:** Build step writes an archive.json listing available dates. Frontend adds a date-switcher. Falls back to most recent if today's build hasn't run.
**Rationale:** The 3-day window is useless if the frontend can only load latest.json.
**Downsides:** Minor frontend complexity.
**Confidence:** 90%
**Complexity:** Low-Medium
**Status:** Unexplored

### 3. Story Deduplication Across Days
**Description:** Track processed story IDs in seen_ids.json. Skip DW articles that appeared in the last 3 days.
**Rationale:** DW's RSS repeats stories. Hearing near-identical rewrites erodes the daily habit.
**Downsides:** Requires persistent state file.
**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

### 4. Offline Audio Pre-Caching in Service Worker
**Description:** Extend sw.js to cache latest.json and all .mp3 files after first load. Commute listening works offline.
**Rationale:** PWA install prompt currently misleads — shell loads but no content offline.
**Downsides:** Cache management complexity. Need eviction for old audio.
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

### 5. Idempotent Pipeline (Skip Existing Content)
**Description:** Check if output already exists before generating. Makes re-runs safe and fast.
**Rationale:** Failed or re-triggered cron regenerates everything, wasting time and credits.
**Downsides:** Need to handle partial failures.
**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

### 6. Resume Playback Position
**Description:** Store currentTime per story+level in localStorage. Restore on re-open. Pure frontend.
**Rationale:** C1 audio is 3-7 minutes. Navigating away loses progress.
**Downsides:** None meaningful. ~20 lines of JS.
**Confidence:** 90%
**Complexity:** Very Low
**Status:** Unexplored

### 7. Vocabulary Extraction as Free LLM Byproduct
**Description:** Add key_words field to LLM prompt response. Surface 3-5 vocab items per level in frontend.
**Rationale:** The LLM already processes each article — vocabulary data is generated and discarded.
**Downsides:** Prompt changes need testing. Frontend needs vocab UI.
**Confidence:** 75%
**Complexity:** Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Use fiction instead of news | Changes product identity fundamentally |
| 2 | Browser TTS (Web Speech API) | German voice quality is terrible |
| 3 | Audio-first, text as reveal | Risky UX change, could frustrate users |
| 4 | Adaptive single text (on-demand API) | Requires a server, violates static architecture |
| 5 | Reader-triggered builds | Over-engineered vs simple cron |
| 6 | Personal letter register | Changes product identity |
| 7 | Invert difficulty order C1->B1->A1 | Already implemented |
| 8 | Karaoke sentence highlighting | Requires timestamp pipeline, high complexity |
| 9 | Tap-to-translate | Requires external API + CSP changes |
| 10 | Build metrics/logging | Nice-to-have, low leverage |
| 11 | Distinct voice per CEFR level | Low priority |
| 12 | Cross-story vocab recycling | Complex for low payoff |
| 13 | Default text visibility | Too small for ideation |
| 14 | OPENAI_API_KEY guard fix | Bug fix, not a feature |
| 15 | Shadowing loop mode | Complex for niche use case |

## Session Log
- 2026-03-27: Initial ideation — 30 candidates generated, 7 survived. Idea #1 selected for brainstorm.
