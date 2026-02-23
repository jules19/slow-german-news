import asyncio
import logging
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from mutagen.mp3 import MP3
from openai import AsyncOpenAI

from backend.models import LevelContent, ProcessedStory

logger = logging.getLogger(__name__)


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


def get_mp3_duration(path: Path) -> float:
    """Get duration of an MP3 file in seconds using mutagen."""
    audio = MP3(path)
    return audio.info.length


async def generate_single_audio(
    client: AsyncOpenAI,
    voice: str,
    text_de: str,
    output_path: Path,
) -> tuple[str, float]:
    """Generate TTS audio for a single text, re-encode, and return (path, duration)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text_de,
        )
        response.stream_to_file(str(tmp_path))
        reencode_mp3(tmp_path, output_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    duration = get_mp3_duration(output_path)
    logger.info("Generated audio: %s (%.1fs)", output_path.name, duration)
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
