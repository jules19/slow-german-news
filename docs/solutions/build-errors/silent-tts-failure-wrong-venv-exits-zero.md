---
title: Silent TTS failure — pipeline exits 0 with no audio, deploys broken site
category: build-errors
severity: critical
module: backend/build.py, scripts/build-and-deploy.sh, backend/audio.py
tags: tts, audio, venv, silent-failure, idempotency, deployment, mlx-audio
date: 2026-03-28
---

# Silent TTS failure — pipeline exits 0 with no audio, deploys broken site

## Problem

The build pipeline exited 0 and deployed to GitHub Pages even when every TTS audio generation call failed. Users saw a live site with story text but no working audio. Multiple debugging sessions went in circles because there was no error signal — the pipeline considered itself successful.

## Root Cause

Two bugs compounded each other:

1. **Wrong venv:** `VENV_PATH` in `build-and-deploy.sh` defaulted to `.venv` instead of `.venv-qwen-tts`. The activated venv didn't have `mlx-audio`, so every TTS call threw `ImportError`.

2. **Silent failure cascade:** Exception handlers in `audio.py` (per-level) and `build.py` (per-story) caught all exceptions and continued. The pipeline wrote `digest.json` with `audio_url: null` for all stories and exited 0. The build script saw exit 0 and deployed. The idempotency check (`if digest.json exists, skip`) prevented re-running.

## Investigation

- Inspected deployed `digest.json` — all `audio_url` fields were `null`.
- Ran `python -m backend.build` directly with `TTS_BACKEND=qwen` — audio generated fine. Build script was the problem.
- Traced the 3.5-minute pipeline run time (vs 10+ min expected for TTS) — confirmed TTS was being skipped entirely.
- After adding proper error handling, saw the clear error: `mlx-audio is not installed`.
- Traced to `VENV_PATH` defaulting to `.venv` in the build script.

## Fix

Four changes:

**1. `backend/build.py` — fail when no stories have audio:**
```python
# Filter out stories where no levels have audio
stories_with_audio = [
    s for s in stories_with_audio
    if any(c.audio_url for c in s.levels.values())
]
if not stories_with_audio:
    raise RuntimeError("No stories have audio. Aborting.")
```

**2. `scripts/build-and-deploy.sh` — fix venv default:**
```bash
VENV_PATH="${VENV_PATH:-.venv-qwen-tts}"
```

**3. `scripts/build-and-deploy.sh` — idempotency checks for audio files:**
```bash
AUDIO_COUNT=$(find "$TODAY_CONTENT" -name '*.mp3' 2>/dev/null | wc -l | tr -d ' ' || echo 0)
if [ -d "$TODAY_CONTENT" ] && [ -f "$TODAY_CONTENT/digest.json" ] && [ "$AUDIO_COUNT" -gt 0 ]; then
    log "Content exists ($AUDIO_COUNT audio files) — skipping."
```

**4. `scripts/build-and-deploy.sh` — pre-deploy validation:**
```bash
AUDIO_COUNT=$(find "$TODAY_CONTENT" -name '*.mp3' 2>/dev/null | wc -l | tr -d ' ' || echo 0)
if [ "$AUDIO_COUNT" -eq 0 ]; then
    die "Pipeline produced no audio files — refusing to deploy"
fi
```

## Prevention

- **Never swallow all exceptions in a batch pipeline.** Partial failure (1 of 3 stories) is fine; total failure must exit non-zero.
- **Validate outputs before deploying.** Check that the artifacts you expect (mp3 files) actually exist, not just metadata files (digest.json).
- **Idempotency checks should verify real outputs**, not intermediate files that get written regardless of success.
- **Make venv paths explicit** and consider a preflight import check at script startup.
- **Note:** `find` on a non-existent directory returns exit code 1 — with `set -euo pipefail`, this silently kills the script. Always add `|| echo 0` fallback.
