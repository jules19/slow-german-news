---
title: "feat: Local cron deployment with 3-day rolling archive"
type: feat
status: completed
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-local-cron-deploy-requirements.md
---

# feat: Local cron deployment with 3-day rolling archive

## Overview

Add a local build-and-deploy script that runs daily at 6am via macOS launchd, generates content with free local Qwen TTS, maintains a 3-day rolling archive, and pushes to a `gh-pages` branch for GitHub Pages auto-deployment. The frontend gets date tabs to browse available days.

## Problem Statement / Motivation

The site has no daily automation. The CI cron is disabled and content only updates on manual trigger. This makes the daily news reader promise hollow. Local Qwen TTS is now free, so the only cost is ~$0.60/month in LLM calls. A local cron job eliminates all manual work. (see origin: `docs/brainstorms/2026-03-27-local-cron-deploy-requirements.md`)

## Proposed Solution

A shell script (`scripts/build-and-deploy.sh`) that:
1. Runs the Python pipeline (`TTS_BACKEND=qwen`)
2. Assembles the site (frontend + content + Tailwind CSS)
3. Manages a `gh-pages` worktree with a 3-day rolling window
4. Force-pushes to deploy

A launchd plist schedules this at 6am daily with catch-up on wake.

The frontend loads `archive.json` to discover available dates and renders date tabs.

## Technical Approach

### Resolved Deferred Questions

**Deployment mechanism conflict** (SpecFlow critical gap): The CI workflow currently uses artifact-based Pages deployment (`actions/deploy-pages`). The local script pushes to `gh-pages` branch. These are mutually exclusive in GitHub Pages config. **Resolution:** Switch GitHub Pages to deploy from `gh-pages` branch. Update the CI workflow's deploy step to also push to `gh-pages` instead of using artifact upload. This makes both paths compatible. (Contradicts the scope boundary "NOT modifying the existing CI workflow" — this is a necessary one-line change.)

**`latest.json` fate**: Keep it. `write_digest()` still writes it. Add `archive.json` alongside it. Frontend uses `archive.json` when available, falls back to `latest.json` for backward compat with CI builds.

**Multiple missed days**: Generate only today's content. Accept that the archive may have fewer than 3 dates after extended downtime. Simpler than multi-day catch-up (which would take 1-2 hours of TTS per missed day).

**Force-push to gh-pages**: Yes. No history needed for a deployment branch. Add a branch-name guard to prevent accidental force-push to `main`.

**`archive.json` schema**: `content/archive.json` containing `{"dates": ["2026-03-27", "2026-03-26", "2026-03-25"]}` sorted newest-first. Simple, sufficient for the frontend to render tabs and fetch per-date digests.

**Date tabs in detail view**: No — tabs only visible in list view. Tapping "back" from story detail returns to the current date's list. Keeps state management simple.

**Pruning**: Happens in the gh-pages working tree before commit. Also prune local `output/` for disk hygiene. Sequence: generate first → copy to gh-pages → prune old dates → generate archive.json → commit → push.

**Tailwind CSS**: Run `npx @tailwindcss/cli` in the build script. The npm deps are already locally available.

### Build Script Flow

```
scripts/build-and-deploy.sh
  1. Activate venv
  2. Run pipeline: TTS_BACKEND=qwen python -m backend.build
  3. Build Tailwind: npx @tailwindcss/cli -i frontend/input.css -o frontend/styles.css --minify
  4. Prepare gh-pages worktree (git worktree or temp clone)
  5. Copy frontend/* into worktree (minus input.css)
  6. Copy today's output/content/{date}/ into worktree/content/
  7. Prune content dirs older than 3 days from worktree/content/
  8. Generate archive.json from remaining date dirs
  9. Update latest.json to point to today's digest
  10. Commit and force-push gh-pages
  11. Prune old dates from local output/ for disk hygiene
```

### Frontend Changes

```
app.js changes:
  - fetchArchive() → loads content/archive.json
  - renderDateTabs() → creates date tab buttons above story list
  - loadDate(dateStr) → fetches content/{date}/digest.json, re-renders story list
  - Falls back to latest.json if archive.json not found (backward compat)

index.html changes:
  - Add #date-tabs container between header and level-selector nav
```

### Implementation Phases

#### Phase 1: Build-and-Deploy Script

Create the shell script that automates the full pipeline.

**Files to create:**
- `scripts/build-and-deploy.sh` — Main build/deploy automation

**Tasks:**
- [ ] Create `scripts/build-and-deploy.sh` with:
  - Venv activation (path configurable via env var or hardcoded)
  - Pipeline execution with `TTS_BACKEND=qwen`
  - Tailwind CSS build via npx
  - Site assembly into a gh-pages git worktree
  - 3-day content pruning in the worktree
  - `archive.json` generation from remaining date directories
  - `latest.json` copy from the most recent date's digest
  - Commit with date-stamped message, force-push to gh-pages
  - Branch-name safety guard (never push to main)
  - Local `output/` pruning for disk hygiene
- [ ] Create the `gh-pages` branch (orphan) with initial empty commit
- [ ] Set up git worktree for `gh-pages` at a stable local path

#### Phase 2: Frontend Date Tabs

Add date tab navigation to the frontend.

**Files to modify:**
- `frontend/index.html` — Add `#date-tabs` container
- `frontend/app.js` — Add archive loading, date tab rendering, date switching

**Tasks:**
- [ ] Add `#date-tabs` container in `index.html` between `</header>` and `<nav id="level-selector">`
- [ ] Add `fetchArchive()` in `app.js`:
  - Fetch `./content/archive.json`
  - On success: render date tabs, load most recent date
  - On failure (404): fall back to `./content/latest.json` (backward compat with CI)
- [ ] Add `renderDateTabs(dates)`:
  - Render pill-style buttons matching the level selector aesthetic
  - Labels: "Today" / "Yesterday" / formatted date (e.g. "25. Mär") based on user's local date
  - Highlight the active date tab
  - Hide tabs if only 1 date available
- [ ] Add `loadDate(dateStr)`:
  - Fetch `./content/{date}/digest.json`
  - Replace current `digest` with new data
  - Call `renderStoryList()`
  - Reset story detail view if open
- [ ] Fix service worker registration path: `"/sw.js"` → `"./sw.js"` (pre-existing bug, affects deployment)

#### Phase 3: CI Workflow Update

Make CI compatible with branch-based deployment.

**Files to modify:**
- `.github/workflows/build-and-deploy.yml` — Replace artifact deploy with gh-pages push

**Tasks:**
- [ ] Replace the `deploy` job's `actions/deploy-pages@v4` with a git push to `gh-pages`
- [ ] Or simpler: use `peaceiris/actions-gh-pages@v4` action which handles this in one step
- [ ] Configure GitHub Pages to deploy from `gh-pages` branch (manual step in repo settings)

#### Phase 4: launchd Plist

Schedule the build script to run daily at 6am.

**Files to create:**
- `scripts/com.langsame-nachrichten.build.plist` — launchd job definition

**Tasks:**
- [ ] Create launchd plist with:
  - `StartCalendarInterval` for Hour=6, Minute=0 (runs on wake if missed)
  - `ProgramArguments` pointing to `scripts/build-and-deploy.sh`
  - `EnvironmentVariables` for `OPENAI_API_KEY`, `TTS_BACKEND=qwen`, `PATH`
  - `StandardOutPath` / `StandardErrorPath` for logging
  - `WorkingDirectory` set to the project root
- [ ] Add install/uninstall instructions (symlink to `~/Library/LaunchAgents/`)

## Acceptance Criteria

- [ ] `scripts/build-and-deploy.sh` runs end-to-end: pipeline → assemble → prune → push to gh-pages
- [ ] GitHub Pages serves the site from `gh-pages` branch with fresh content
- [ ] Only the last 3 days of content exist in the gh-pages branch at any time
- [ ] `content/archive.json` lists available dates correctly
- [ ] Frontend shows date tabs and loads the correct digest when switching dates
- [ ] Frontend falls back gracefully to `latest.json` when `archive.json` is absent
- [ ] launchd job runs at 6am and catches up on wake if missed
- [ ] CI workflow still deploys successfully as a backup path
- [ ] Force-push is guarded against accidentally pushing to main

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| Mac off for multiple days → fewer than 3 dates | Accepted. "Up to 3" is the spec. |
| Pipeline fails mid-build | Generate before pruning. Old gh-pages state preserved on failure. |
| Git push fails (network/auth) | Log error. Next run retries. Old content stays deployed. |
| gh-pages branch grows with git history | Force-push means only one commit exists at any time. No history bloat. |
| Tailwind npm not installed locally | Build script checks for npx availability, exits with clear error. |
| launchd env vars missing | Plist explicitly sets required env vars. Script validates at startup. |

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-27-local-cron-deploy-requirements.md](docs/brainstorms/2026-03-27-local-cron-deploy-requirements.md) — Key decisions: date tabs UI, run-on-wake catchup, gh-pages branch deployment, prune in build script.

### Internal References

- Build pipeline: `backend/build.py:91-147` (run_pipeline)
- Digest output: `backend/build.py:75-88` (write_digest)
- Frontend content loading: `frontend/app.js:80` (fetchDigest)
- Story list rendering: `frontend/app.js:93` (renderStoryList)
- Date display: `frontend/app.js` (formatDateDE)
- Site assembly: `.github/workflows/build-and-deploy.yml:46-50`
- SW registration bug: `frontend/app.js:272` ("/sw.js" → "./sw.js")
- Ideation source: `docs/ideation/2026-03-27-enhancements-ideation.md` (idea #1)
