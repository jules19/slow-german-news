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

# Qwen3-TTS reference audio for voice cloning
REF_AUDIO_PATH = Path(__file__).parent / "assets" / "ref_german_nova.wav"
REF_TEXT = (
    "Bundes-Regierung will mehr Geld für Wind-Räder und Lade-Säulen ausgeben. "
    "Die Bundes-Regierung will mehr Geld für neue Wind-Räder und Lade-Säulen "
    "für Elektro-Autos geben. Das steht in dem neuen Programm für den "
    "Klima-Schutz. Der Bundes-Kanzler und die Minister haben das Programm "
    "beschlossen."
)

# Lazily loaded Qwen model (module-level cache)
_qwen_model = None


def _get_qwen_model():
    """Lazily load the Qwen3-TTS model via mlx-audio."""
    global _qwen_model
    if _qwen_model is not None:
        return _qwen_model

    if not REF_AUDIO_PATH.exists():
        raise RuntimeError(
            f"Qwen TTS reference audio not found at {REF_AUDIO_PATH}. "
            "This file is required for voice cloning."
        )

    try:
        from mlx_audio.tts.generate import generate_audio  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "mlx-audio is not installed. Install it with: "
            "pip install mlx-audio (requires Apple Silicon Mac). "
            "Or set TTS_BACKEND=openai to use the OpenAI API instead."
        )

    # Return the generate_audio function as our "model"
    # The actual model weights are loaded lazily by mlx-audio on first call
    _qwen_model = generate_audio
    return _qwen_model


# German number words for normalization
_ONES = [
    "", "eins", "zwei", "drei", "vier", "f\u00fcnf", "sechs", "sieben",
    "acht", "neun", "zehn", "elf", "zw\u00f6lf", "dreizehn", "vierzehn",
    "f\u00fcnfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn",
]
_TENS = [
    "", "zehn", "zwanzig", "drei\u00dfig", "vierzig", "f\u00fcnfzig",
    "sechzig", "siebzig", "achtzig", "neunzig",
]


def _number_to_german(n: int) -> str:
    """Convert an integer (0-9999) to German words."""
    if n < 0 or n > 9999:
        return str(n)
    if n == 0:
        return "null"
    if n < 20:
        return _ONES[n]
    if n < 100:
        ones = n % 10
        tens = n // 10
        if ones == 0:
            return _TENS[tens]
        if ones == 1:
            return f"ein{'' if tens == 0 else 'und'}{_TENS[tens]}"
        return f"{_ONES[ones]}und{_TENS[tens]}"
    if n < 1000:
        hundreds = n // 100
        rest = n % 100
        prefix = f"{_ONES[hundreds]}hundert"
        if rest == 0:
            return prefix
        return prefix + _number_to_german(rest)
    # 1000-9999: e.g. 2045 → zweitausendfünfundvierzig
    thousands = n // 1000
    rest = n % 1000
    if thousands == 1:
        prefix = "eintausend"
    else:
        prefix = f"{_ONES[thousands]}tausend"
    if rest == 0:
        return prefix
    return prefix + _number_to_german(rest)


def normalize_for_speech(text: str) -> str:
    """Convert years and common numbers to German words for clearer TTS.

    Applied before TTS for both backends to ensure predictable pronunciation.
    Does not modify the display text stored in digest JSON.
    """
    # Convert 4-digit years (1900-2099) that appear as standalone numbers
    def replace_year(match):
        n = int(match.group(0))
        return _number_to_german(n)

    text = re.sub(r'\b(1[0-9]{3}|20[0-9]{2})\b', replace_year, text)
    return text


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
    """Generate TTS for a single chunk of text using OpenAI."""
    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    response.stream_to_file(str(output_path))


def _generate_tts_chunk_qwen(text: str, output_path: Path) -> None:
    """Generate TTS for a chunk of text using Qwen3-TTS via mlx-audio."""
    generate_audio = _get_qwen_model()
    generate_audio(
        text=text,
        model="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
        voice="vivian",
        lang_code="de",
        ref_audio=str(REF_AUDIO_PATH),
        ref_text=REF_TEXT,
        output_path=str(output_path.parent),
        file_prefix=output_path.stem,
        audio_format="wav",
        verbose=False,
    )
    # mlx-audio appends _000 to the filename
    generated = output_path.parent / f"{output_path.stem}_000.wav"
    if generated.exists():
        generated.rename(output_path)


async def generate_single_audio(
    client: AsyncOpenAI | None,
    voice: str,
    text_de: str,
    output_path: Path,
    *,
    tts_backend: str = "openai",
) -> tuple[str, float]:
    """Generate TTS audio for a text, chunking if needed, then re-encode."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text_for_tts = normalize_for_speech(text_de)
    chunks = chunk_text(text_for_tts)
    tmp_paths: list[Path] = []

    try:
        for i, chunk in enumerate(chunks):
            suffix = ".wav" if tts_backend == "qwen" else ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp_path = Path(tmp.name)
            tmp.close()
            tmp_paths.append(tmp_path)

            if tts_backend == "qwen":
                await asyncio.to_thread(_generate_tts_chunk_qwen, chunk, tmp_path)
            else:
                await _generate_tts_chunk(client, voice, chunk, tmp_path)

        if len(tmp_paths) == 1:
            raw_path = tmp_paths[0]
        else:
            raw_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
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
    client: AsyncOpenAI | None,
    voice: str,
    output_dir: Path,
    *,
    tts_backend: str = "openai",
) -> ProcessedStory:
    """Generate audio for all levels of a story.

    OpenAI backend runs levels in parallel. Qwen backend runs sequentially
    to avoid OOM (7-10 GB peak memory per inference).
    """
    sorted_levels = sorted(story.levels.keys())

    if tts_backend == "qwen":
        # Sequential: Qwen uses too much memory for parallel inference
        results = []
        for level_num in sorted_levels:
            content = story.levels[level_num]
            output_path = output_dir / story.id / f"level-{level_num}.mp3"
            try:
                result = await generate_single_audio(
                    client, voice, content.text_de, output_path,
                    tts_backend=tts_backend,
                )
                results.append(result)
            except Exception as e:
                results.append(e)
    else:
        # Parallel: OpenAI API calls benefit from concurrency
        coros = []
        for level_num in sorted_levels:
            content = story.levels[level_num]
            output_path = output_dir / story.id / f"level-{level_num}.mp3"
            coros.append(generate_single_audio(
                client, voice, content.text_de, output_path,
                tts_backend=tts_backend,
            ))
        results = await asyncio.gather(*coros, return_exceptions=True)

    updated_levels = dict(story.levels)
    for level_num, result in zip(sorted_levels, results):
        if isinstance(result, Exception):
            logger.warning(
                "TTS failed for story %s level %d: %s",
                story.id, level_num, result,
            )
            continue

        audio_path, duration = result
        output_root = output_dir.parent.parent  # output/content/{date} → output/
        rel_path = str(Path(audio_path).relative_to(output_root))
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
