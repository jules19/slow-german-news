---
date: 2026-03-27
topic: local-cron-deploy
---

# Local Cron Deployment with 3-Day Archive

## Problem Frame

The site has no daily automation. The CI cron is disabled and the pipeline only runs on manual trigger. Content goes stale silently. The user wants a fully local, zero-cost daily pipeline: generate content with free local Qwen TTS at 6am, push to GitHub Pages, and keep the last 3 days of stories browsable.

## Requirements

- R1. A launchd job runs the pipeline daily at 6am with `TTS_BACKEND=qwen`. If the Mac was asleep at 6am, it runs on wake as catchup.
- R2. After generating today's content, the build prunes content directories older than 3 days from the site output.
- R3. The build commits the assembled site (frontend + last 3 days of content) and pushes to a `gh-pages` branch. GitHub Pages auto-deploys from this branch.
- R4. The build produces an `archive.json` listing the available dates (up to 3), so the frontend knows what content exists.
- R5. The frontend shows date tabs above the story list (e.g. "Today", "Yesterday", "Mar 25"). Default tab is the most recent available date.
- R6. If today's build hasn't run yet, the frontend loads the most recent available date without error.

## Success Criteria

- The site updates daily with fresh content without any manual intervention
- Users can browse the last 3 days of stories via date tabs
- Opening the app on a day with no build shows the previous day's content gracefully
- Zero TTS cost (local Qwen), only LLM cost (~$0.60/month)
- Git repo (`gh-pages` branch) stays manageable in size (only 3 days of audio at any time)

## Scope Boundaries

- NOT adding story deduplication across days (separate enhancement)
- NOT adding offline audio caching in the service worker (separate enhancement)
- NOT modifying the existing CI workflow (it continues to work as a backup with `TTS_BACKEND=openai`)
- NOT adding notifications or alerting for failed builds
- The `gh-pages` branch is deployment-only — no source code, just the assembled site

## Key Decisions

- **Date tabs UI**: Three tabs above the story list showing available dates. Simpler and clearer than a scrollable feed or hidden "older" link.
- **Run on wake**: launchd catches up on missed builds. Ensures content stays fresh even with irregular Mac use.
- **gh-pages branch deployment**: Separate branch keeps the main branch clean. GitHub Pages natively supports branch-based deployment.
- **Prune in the build script**: Content older than 3 days is deleted before committing. This keeps the branch small and avoids git history bloat from audio binaries.

## Dependencies / Assumptions

- Mac is used regularly enough that missed builds catch up within a day
- `TTS_BACKEND=qwen` and `OPENAI_API_KEY` are set in the launchd environment
- GitHub Pages is configured to deploy from the `gh-pages` branch
- The `.venv-qwen-tts` venv (or equivalent with both project deps + mlx-audio) is available

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] Exact launchd plist configuration for `StartCalendarInterval` + catchup-on-wake behavior
- [Affects R3][Technical] Should the build script force-push to `gh-pages` (simpler) or do incremental commits (preserves some history)?
- [Affects R3][Technical] How to handle the Tailwind CSS build step in the local script — npm/npx dependency
- [Affects R4][Technical] Shape of `archive.json` — list of date strings, or richer metadata?
- [Affects R5][Needs research] How does the frontend date tab UI interact with the existing story detail view and back navigation?

## Next Steps

→ `/ce:plan` for structured implementation planning
