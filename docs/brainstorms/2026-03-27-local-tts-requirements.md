---
date: 2026-03-27
topic: local-tts-qwen3
---

# Local TTS with Qwen3-TTS

## Problem Frame

The project currently uses OpenAI `tts-1` API for text-to-speech, costing ~$22/month if run daily (3 stories × 3 levels, ~45K chars/run at $15/1M chars). TTS is 97% of the pipeline cost. Switching to a local open-source model eliminates this cost while potentially improving German pronunciation quality and removing the OpenAI dependency for audio.

## Requirements

- R1. Replace OpenAI TTS with Qwen3-TTS for audio generation
- R2. Support running locally on Mac (Apple Silicon via MLX)
- R3. Maintain current audio output format (MP3, 48kbps mono, 22kHz) for compatibility with existing frontend
- R4. Handle texts of any length (current chunking at 4096 chars may not be needed — verify Qwen3-TTS input limits)
- R5. Keep OpenAI TTS as a fallback option via environment variable (e.g. `TTS_BACKEND=qwen3|openai`)
- R6. Audio quality for German news narration should be equal to or better than current OpenAI tts-1 output

## Success Criteria

- Pipeline runs end-to-end with Qwen3-TTS generating all audio locally
- Generated German audio is natural and clearly spoken (subjective listen test)
- Zero API cost for TTS when running locally
- No regression in frontend audio playback

## Scope Boundaries

- NOT migrating LLM calls away from OpenAI (separate concern)
- NOT adding voice cloning or custom voices in this iteration (Qwen3-TTS supports it, but defer)
- NOT optimizing for CI/GitHub Actions yet — Mac-local first, CI viability evaluated after
- NOT changing audio player UI or format

## Key Decisions

- **Qwen3-TTS over alternatives**: Apache 2.0 license, top German benchmarks, MLX port exists for Apple Silicon, 0.6B variant available for constrained environments
- **Start with 0.6B model**: Smaller footprint (~1.2GB), faster inference, evaluate quality before considering 1.7B
- **Backend abstraction via env var**: Avoids ripping out OpenAI TTS — can switch back instantly if quality disappoints

## Dependencies / Assumptions

- Apple Silicon Mac (M1/M2/M3/M4) for MLX inference
- `qwen-tts` Python package or MLX port installable in the existing venv
- ffmpeg still used for final re-encoding step (same as today)
- `transformers==4.57.3` pin from Qwen3-TTS may conflict with other deps — needs verification

## Outstanding Questions

### Resolve Before Planning
- [Affects R1][Needs testing] Does Qwen3-TTS 0.6B produce acceptable German news narration quality, or is 1.7B required?

### Deferred to Planning
- [Affects R2][Technical] What is the actual inference time for a full pipeline run (9 audio files) on Apple Silicon?
- [Affects R4][Technical] What are Qwen3-TTS input length limits — can we remove the 4096-char chunking logic?
- [Affects R5][Technical] Best way to structure the TTS backend abstraction — strategy pattern, simple if/else, or separate modules?
- [Affects R1][Technical] Does `transformers==4.57.3` pin conflict with any existing project dependencies?
- [Affects R2][Needs research] Is the MLX port (`kapi2800/qwen3-tts-apple-silicon`) stable, or should we use the official `qwen-tts` package with PyTorch MPS?

## Next Steps

→ Quick quality test: install Qwen3-TTS 0.6B locally, generate one sample with German news text, listen and evaluate before committing to planning.
