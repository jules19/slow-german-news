"""Build orchestrator — main entry point for the content pipeline.

Usage:
    python -m backend.build

Environment variables:
    OPENAI_API_KEY  — required
    LLM_MODEL       — default: gpt-4o-mini
    TTS_VOICE       — default: nova
    MAX_STORIES     — default: 5
"""

import asyncio
import json
import logging
import os
from datetime import date
from pathlib import Path

from openai import AsyncOpenAI, OpenAI

from backend.audio import generate_audio_for_story
from backend.levels import generate_levels
from backend.models import ProcessedStory
from backend.sources import fetch_stories

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")


def get_config() -> dict:
    """Read configuration from environment variables."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")
    return {
        "api_key": api_key,
        "llm_model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "tts_voice": os.environ.get("TTS_VOICE", "nova"),
        "max_stories": int(os.environ.get("MAX_STORIES", "5")),
    }


def story_to_dict(story: ProcessedStory) -> dict:
    """Convert a ProcessedStory to a JSON-serializable dict."""
    return {
        "id": story.id,
        "headline_de": story.headline_de,
        "headline_en": story.headline_en,
        "summary_en": story.summary_en,
        "source_url": story.source_url,
        "levels": {
            str(level): {
                "text_de": content.text_de,
                "text_en": content.text_en,
                "audio_url": content.audio_url,
                "audio_duration_seconds": content.audio_duration_seconds,
            }
            for level, content in sorted(story.levels.items())
        },
    }


def build_digest(stories: list[ProcessedStory], today: str) -> dict:
    """Build the digest JSON structure."""
    return {
        "schema_version": 1,
        "date": today,
        "generated_at": f"{today}T00:00:00Z",
        "stories": [story_to_dict(s) for s in stories],
    }


def write_digest(digest: dict, content_dir: Path) -> None:
    """Write digest.json and latest.json."""
    content_dir.mkdir(parents=True, exist_ok=True)

    digest_path = content_dir / "digest.json"
    with open(digest_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", digest_path)

    # latest.json is a copy at the content root
    latest_path = content_dir.parent / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s", latest_path)


async def run_pipeline(config: dict) -> None:
    """Run the full content pipeline."""
    today = date.today().isoformat()
    content_dir = OUTPUT_DIR / "content" / today
    content_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch stories
    logger.info("Fetching stories from DW...")
    raw_stories = fetch_stories(max_stories=config["max_stories"])
    if not raw_stories:
        raise RuntimeError("No stories fetched from DW. Aborting.")
    logger.info("Fetched %d stories", len(raw_stories))

    # Step 2: Generate difficulty levels
    llm_client = OpenAI(api_key=config["api_key"])
    processed_stories: list[ProcessedStory] = []
    for raw in raw_stories:
        try:
            logger.info("Generating levels for story %s: %s", raw.id, raw.title)
            processed = generate_levels(raw, llm_client, config["llm_model"])
            processed_stories.append(processed)
        except Exception:
            logger.exception("Failed to generate levels for story %s", raw.id)

    if not processed_stories:
        raise RuntimeError("No stories processed successfully. Aborting.")

    # Step 3: Generate audio
    tts_client = AsyncOpenAI(api_key=config["api_key"])
    stories_with_audio: list[ProcessedStory] = []
    for story in processed_stories:
        try:
            logger.info("Generating audio for story %s", story.id)
            with_audio = await generate_audio_for_story(
                story, tts_client, config["tts_voice"], content_dir,
            )
            stories_with_audio.append(with_audio)
        except Exception:
            logger.exception("Failed to generate audio for story %s", story.id)
            stories_with_audio.append(story)

    # Step 4: Write output
    digest = build_digest(stories_with_audio, today)
    write_digest(digest, content_dir)

    # Summary
    total_audio = sum(
        1
        for s in stories_with_audio
        for c in s.levels.values()
        if c.audio_url
    )
    logger.info(
        "Pipeline complete: %d stories, %d audio files",
        len(stories_with_audio),
        total_audio,
    )


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = get_config()
    asyncio.run(run_pipeline(config))


if __name__ == "__main__":
    main()
