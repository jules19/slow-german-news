---
title: "feat: Replace OpenAI TTS with local Qwen3-TTS via MLX"
type: feat
status: completed
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-local-tts-requirements.md
---

# feat: Replace OpenAI TTS with local Qwen3-TTS via MLX

## Overview

Replace the OpenAI `tts-1` API with local Qwen3-TTS inference via `mlx-audio` on Apple Silicon. This eliminates ~$22/month in TTS costs (97% of pipeline spend) while maintaining or improving German audio quality. OpenAI TTS remains available as a fallback via env var.

## Problem Statement / Motivation

The pipeline currently spends ~$0.70/run on OpenAI TTS ($22/month at daily cadence). TTS is 97% of total pipeline cost. Testing in this session confirmed that Qwen3-TTS 0.6B via MLX produces excellent German narration when using voice cloning from the existing OpenAI "nova" output — at zero API cost and 2.15x realtime on Apple Silicon. (see origin: `docs/brainstorms/2026-03-27-local-tts-requirements.md`)

## Proposed Solution

Add a `TTS_BACKEND` env var (`openai` | `qwen`) that routes TTS generation to either the existing OpenAI path or a new local Qwen3-TTS path. The swap happens at the narrowest point: `_generate_tts_chunk()` in `backend/audio.py`. Everything downstream (chunking, concatenation, ffmpeg re-encoding, duration extraction) stays unchanged.

## Technical Approach

### Architecture

```
build.py
  └── get_config() reads TTS_BACKEND env var, passes to audio functions

audio.py
  ├── _generate_tts_chunk()       → existing OpenAI path (unchanged)
  ├── _generate_tts_chunk_qwen()  → new: mlx-audio, voice cloning, outputs WAV
  ├── normalize_for_speech()      → new: years/numbers → German words
  ├── generate_single_audio()     → if/else dispatch based on backend
  ├── chunk_text()                → retained as safety net
  ├── concat_mp3s()               → unchanged
  ├── reencode_mp3()              → unchanged (handles WAV→MP3 too)
  └── get_mp3_duration()          → unchanged
```

### Key Design Decisions

1. **Default `TTS_BACKEND=openai`** — CI runs on Ubuntu (no MLX). Defaulting to `qwen` would break GitHub Actions. Local devs explicitly set `TTS_BACKEND=qwen`.

2. **Sequential inference for Qwen** — At 7-10 GB peak memory, parallel `asyncio.gather` across levels risks OOM. Qwen path loops sequentially. OpenAI path retains parallel execution.

3. **Number normalization for both backends** — `normalize_for_speech()` converts digits/years to German words (e.g. "2045" → "zweitausendvierundvierzig"). Applied before TTS for both backends — explicit is more predictable than relying on TTS to guess. Not stored in digest JSON (display text unchanged).

4. **Optional dependency group** — `mlx-audio` goes in `[project.optional-dependencies] local-tts = ["mlx-audio"]`. Main install stays lean. CI never installs this group.

5. **Reference audio committed to repo** — `ref_german_nova.wav` (10s, ~470KB) at `backend/assets/ref_german_nova.wav` with ref_text as a constant. Clear error if missing when `TTS_BACKEND=qwen`.

### Implementation Phases

#### Phase 1: Add Qwen3-TTS Backend

Add `_generate_tts_chunk_qwen()` alongside the existing `_generate_tts_chunk()` and dispatch between them based on a `TTS_BACKEND` config value. No protocols, no wrapper classes — just an if/else.

**Files to create/modify:**
- `backend/audio.py` — Add `_generate_tts_chunk_qwen()`, `normalize_for_speech()`, update `generate_single_audio()` with backend dispatch
- `backend/build.py` — Add `TTS_BACKEND` to `get_config()`, pass backend config to audio functions
- `backend/assets/ref_german_nova.wav` — Commit reference clip
- `pyproject.toml` — Add `[project.optional-dependencies] local-tts`

**Tasks:**
- [ ] Add `TTS_BACKEND` to `get_config()` (default: `openai`)
- [ ] Add `_generate_tts_chunk_qwen(text, output_path)` that:
  - On first call, lazily loads `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit` model (module-level cache)
  - Calls `mlx_audio.tts.generate.generate_audio()` with voice cloning params (voice=`vivian`, ref_audio, ref_text, lang_code=`de`)
  - Outputs WAV to `output_path` (ffmpeg re-encode handles WAV→MP3)
  - Wrap in `asyncio.to_thread()` since mlx inference is sync
- [ ] Add `normalize_for_speech(text: str) -> str` in `audio.py` — converts years (1900-2099) and common numbers to German words. Applied for both backends (more predictable than relying on TTS to guess).
- [ ] Update `generate_single_audio()`: if backend is `qwen`, call `_generate_tts_chunk_qwen()`; else call existing `_generate_tts_chunk()`
- [ ] Update `generate_audio_for_story()`: if backend is `qwen`, loop sequentially instead of `asyncio.gather` (7-10 GB memory prevents parallel inference)
- [ ] Move `ref_german_nova.wav` to `backend/assets/`, add ref_text constant
- [ ] Catch `ImportError` for mlx-audio at runtime with clear error message
- [ ] Add `local-tts` optional dependency group to `pyproject.toml`: `local-tts = ["mlx-audio"]`
- [ ] Add tests for `normalize_for_speech()`

#### Phase 2: CI & Cleanup

Ensure CI still works and clean up test artifacts.

**Files to modify:**
- `.github/workflows/build-and-deploy.yml` — Explicitly set `TTS_BACKEND=openai`
- `.gitignore` — Add `.venv-qwen-tts/` and test audio files

**Tasks:**
- [ ] Add `TTS_BACKEND: openai` to CI workflow env vars
- [ ] Add `.venv-qwen-tts/` and `german_tts_*.wav` to `.gitignore`
- [ ] Test full pipeline end-to-end with `TTS_BACKEND=qwen`
- [ ] Test full pipeline end-to-end with `TTS_BACKEND=openai` (regression check)

## System-Wide Impact

- **Interaction graph**: `build.py` creates provider → passes to `generate_audio_for_story()` → calls provider per chunk. No callbacks, no middleware. Clean linear flow.
- **Error propagation**: Qwen errors (OOM, missing model, missing ref_audio) surface as exceptions in `generate_audio_for_story()`, caught by existing try/except per-story handler. Same error recovery as OpenAI path.
- **State lifecycle risks**: None — audio generation is stateless. Each run produces fresh files. No database, no caches.
- **API surface parity**: Only `build.py` creates the provider. No other code paths need updating.

## Acceptance Criteria

- [ ] Pipeline runs end-to-end with `TTS_BACKEND=qwen` generating all 9 audio files locally
- [ ] Pipeline still runs end-to-end with `TTS_BACKEND=openai` (default, unchanged)
- [ ] CI workflow passes without `mlx-audio` installed
- [ ] Generated MP3 files play correctly in the frontend audio player
- [ ] Numbers/years in German text are pronounced correctly
- [ ] Clear error message when `TTS_BACKEND=qwen` but `mlx-audio` not installed
- [ ] Clear error message when ref_audio file is missing
- [ ] All existing tests pass; new tests cover provider abstraction and normalization

## Success Metrics

- Zero TTS API cost when running locally with `TTS_BACKEND=qwen`
- Audio quality subjectively equal to or better than OpenAI tts-1 for German news
- Full pipeline build time under 15 minutes on Apple Silicon (vs ~30s with OpenAI API)
- No regression in CI build

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| MLX only works on Apple Silicon | Default to OpenAI; CI always uses OpenAI |
| 7-10 GB memory usage | Sequential inference; document minimum 16 GB RAM |
| Model download on first run (~2 GB) | mlx-audio auto-downloads to ~/.cache/huggingface; add note in setup docs |
| Number pronunciation | normalize_for_speech() preprocessing; can improve incrementally |
| Quality degradation on very long texts | Keep chunking logic as safety net; test C1 level (~7000 chars) without chunking |

## Outstanding Questions (Deferred from Origin)

- **Qwen3-TTS input length limit**: Test with longest C1 text (~7000 chars). If quality degrades, keep chunking with adjusted threshold. (origin R4)
- **`TTS_VOICE` semantics with Qwen**: Ignored when using voice cloning — voice comes from ref_audio. Document this. (SpecFlow #9)

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-27-local-tts-requirements.md](docs/brainstorms/2026-03-27-local-tts-requirements.md) — Key decisions carried forward: Qwen3-TTS over alternatives (Apache 2.0, top German benchmarks), 0.6B model, backend abstraction via env var.

### Internal References

- TTS generation: `backend/audio.py:87-96` (swap point)
- Config: `backend/build.py:32-42`
- Tests: `tests/test_audio.py`
- OpenAI TTS chunking solution: `docs/solutions/integration-issues/openai-tts-4096-char-limit.md`
- MVP decision against provider abstraction: `docs/plans/2026-02-23-feat-langsame-nachrichten-mvp-plan.md`

### External References

- mlx-audio: `pip install mlx-audio` ([GitHub](https://github.com/Blaizzy/mlx-audio))
- Model: `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit` on HuggingFace
- Qwen3-TTS technical report: [arxiv.org/abs/2601.15621](https://arxiv.org/abs/2601.15621)

### Validated Test Results (this session)

- Voice cloning from existing OpenAI nova output: **excellent quality**
- Inference speed: **2.15x realtime** (52s audio in 24s) on Apple Silicon
- Peak memory: **7-10 GB** for 0.6B 8-bit model
- Number/year pronunciation: **needs normalization** (years spoken as digits)
