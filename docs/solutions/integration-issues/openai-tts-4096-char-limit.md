---
title: "OpenAI TTS 4096 Character Input Limit"
date: 2026-02-24
category: integration-issues
module: backend/audio
tags: [openai, tts, ffmpeg, chunking, audio]
symptoms:
  - "TTS API returns 400 Bad Request for longer texts"
  - "string_too_long error from OpenAI speech endpoint"
  - "Audio generation fails for higher CEFR levels (B2/C1)"
severity: high
---

# OpenAI TTS 4096 Character Input Limit

## Problem

The OpenAI TTS API (`/v1/audio/speech`) enforces a **4096 character limit** on the `input` parameter. This is not prominently documented and was discovered during end-to-end testing with real Deutsche Welle articles.

**Error message:**
```
Error code: 400 - {'error': {'message': "[{'type': 'string_too_long',
'loc': ('body', 'input'), 'msg': 'String should have at most 4096 characters',
'ctx': {'max_length': 4096}}]", 'type': 'invalid_request_error'}}
```

**Impact:** CEFR levels B1, B2, and C1 (levels 3-5) regularly exceed 4096 characters for news articles. In our first test run, a Berlinale article produced:
- Level 1 (A1): 171 chars (OK)
- Level 2 (A2): 2,970 chars (OK)
- Level 3 (B1): 6,409 chars (FAILED)
- Level 4 (B2): 6,686 chars (FAILED)
- Level 5 (C1): 7,056 chars (FAILED)

## Root Cause

The OpenAI TTS API validates input length server-side and rejects any request where the text exceeds 4096 characters. There is no API parameter to override this limit. The limit applies to the `tts-1` and `tts-1-hd` models.

## Solution

Split long texts at **sentence boundaries**, generate TTS for each chunk separately, then **concatenate with ffmpeg** before the final re-encoding step.

### 1. Chunk text at sentence boundaries

```python
TTS_MAX_CHARS = 4096

def chunk_text(text: str, max_chars: int = TTS_MAX_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks
```

### 2. Generate TTS per chunk, concatenate, then re-encode

```python
chunks = chunk_text(text_de)
tmp_paths = []

# TTS each chunk
for chunk in chunks:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_paths.append(Path(tmp.name))
    await _generate_tts_chunk(client, voice, chunk, tmp_paths[-1])

# Concatenate if multiple chunks
if len(tmp_paths) > 1:
    concat_mp3s(tmp_paths, raw_path)  # ffmpeg -f concat -c copy
else:
    raw_path = tmp_paths[0]

# Re-encode once at the end (48kbps mono)
reencode_mp3(raw_path, output_path)
```

### 3. Concatenation uses ffmpeg stream copy (fast)

```python
def concat_mp3s(input_paths: list[Path], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in input_paths:
            f.write(f"file '{p}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_path), "-c", "copy", str(output_path),
    ], check=True, capture_output=True)
```

**Key efficiency insight:** Concatenate with `-c copy` (stream copy, no re-encoding), then re-encode the combined file once. This is faster than re-encoding each chunk individually.

## Prevention

- Always chunk text before calling OpenAI TTS API
- The `chunk_text()` function is the single point of control for this
- Test coverage in `tests/test_audio.py::TestChunkText` validates:
  - Short texts pass through as single chunk
  - Splits happen at sentence boundaries (not mid-sentence)
  - All chunks are under the limit
  - No text is lost during chunking (round-trip test)

## Related

- `backend/audio.py` — implementation
- `tests/test_audio.py` — test coverage
- [OpenAI TTS Guide](https://platform.openai.com/docs/guides/text-to-speech)
- Plan: `docs/plans/2026-02-23-feat-langsame-nachrichten-mvp-plan.md` (audio section)
