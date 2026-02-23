import asyncio
import logging
import re
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from mutagen.mp3 import MP3
from openai import AsyncOpenAI

from backend.models import LevelContent, ProcessedStory

logger = logging.getLogger(__name__)

TTS_MAX_CHARS = 4096


def reencode_mp3(input_path: Path, output_path: Path) -> None:
    """Re-encode MP3 to mono 48kbps 22kHz using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ac", "1",       # mono
            "-ab", "48k",     # 48kbps
            "-ar", "22050",   # 22kHz sample rate
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def concat_mp3s(input_paths: list[Path], output_path: Path) -> None:
    """Concatenate multiple MP3 files using ffmpeg."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        list_path = Path(f.name)
        for p in input_paths:
            f.write(f"file '{p}'\n")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        list_path.unlink(missing_ok=True)


def chunk_text(text: str, max_chars: int = TTS_MAX_CHARS) -> list[str]:
    """Split text into chunks at sentence boundaries, respecting max_chars."""
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


def get_mp3_duration(path: Path) -> float:
    """Get duration of an MP3 file in seconds using mutagen."""
    audio = MP3(path)
    return audio.info.length


async def _generate_tts_chunk(
    client: AsyncOpenAI, voice: str, text: str, output_path: Path
) -> None:
    """Generate TTS for a single chunk of text."""
    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    response.stream_to_file(str(output_path))


async def generate_single_audio(
    client: AsyncOpenAI,
    voice: str,
    text_de: str,
    output_path: Path,
) -> tuple[str, float]:
    """Generate TTS audio for a text, chunking if needed, then re-encode."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = chunk_text(text_de)
    tmp_paths: list[Path] = []

    try:
        for i, chunk in enumerate(chunks):
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_path = Path(tmp.name)
            tmp.close()
            tmp_paths.append(tmp_path)
            await _generate_tts_chunk(client, voice, chunk, tmp_path)

        if len(tmp_paths) == 1:
            raw_path = tmp_paths[0]
        else:
            raw_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            raw_path = Path(raw_file.name)
            raw_file.close()
            tmp_paths.append(raw_path)
            concat_mp3s(tmp_paths[:-1], raw_path)

        reencode_mp3(raw_path, output_path)
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)

    duration = get_mp3_duration(output_path)
    logger.info("Generated audio: %s (%.1fs, %d chunks)", output_path.name, duration, len(chunks))
    return str(output_path), duration


async def generate_audio_for_story(
    story: ProcessedStory,
    client: AsyncOpenAI,
    voice: str,
    output_dir: Path,
) -> ProcessedStory:
    """Generate audio for all levels of a story in parallel."""
    tasks = {}
    for level_num, content in story.levels.items():
        output_path = output_dir / story.id / f"level-{level_num}.mp3"
        tasks[level_num] = generate_single_audio(
            client, voice, content.text_de, output_path,
        )

    results = await asyncio.gather(
        *[tasks[k] for k in sorted(tasks.keys())],
        return_exceptions=True,
    )

    updated_levels = dict(story.levels)
    for level_num, result in zip(sorted(tasks.keys()), results):
        if isinstance(result, Exception):
            logger.warning(
                "TTS failed for story %s level %d: %s",
                story.id, level_num, result,
            )
            continue

        audio_path, duration = result
        # Store relative path from content root for the JSON
        rel_path = str(Path(audio_path).relative_to(output_dir.parent))
        updated_levels[level_num] = replace(
            updated_levels[level_num],
            audio_url=rel_path,
            audio_duration_seconds=round(duration, 1),
        )

    return ProcessedStory(
        id=story.id,
        headline_de=story.headline_de,
        headline_en=story.headline_en,
        summary_en=story.summary_en,
        source_url=story.source_url,
        levels=updated_levels,
    )
