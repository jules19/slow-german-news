import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.build import (
    build_digest,
    get_config,
    run_pipeline,
    story_to_dict,
    write_digest,
)
from backend.models import LevelContent, ProcessedStory, RawStory


SAMPLE_STORY = ProcessedStory(
    id="12345",
    headline_de="Test Schlagzeile",
    headline_en="Test Headline",
    summary_en="A test summary.",
    source_url="https://dw.com/a-12345",
    levels={
        1: LevelContent(
            text_de="Einfach.",
            text_en="Simple.",
            audio_url="content/2026-02-23/12345/level-1.mp3",
            audio_duration_seconds=10.5,
        ),
        5: LevelContent(
            text_de="Komplex.",
            text_en="Complex.",
            audio_url="content/2026-02-23/12345/level-5.mp3",
            audio_duration_seconds=25.0,
        ),
    },
)


class TestGetConfig:
    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("TTS_VOICE", "echo")
        monkeypatch.setenv("MAX_STORIES", "3")

        config = get_config()
        assert config["api_key"] == "test-key"
        assert config["llm_model"] == "gpt-4o"
        assert config["tts_voice"] == "echo"
        assert config["max_stories"] == 3

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("TTS_VOICE", raising=False)
        monkeypatch.delenv("MAX_STORIES", raising=False)

        config = get_config()
        assert config["llm_model"] == "gpt-4o-mini"
        assert config["tts_voice"] == "nova"
        assert config["max_stories"] == 5

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_config()


class TestStoryToDict:
    def test_serializes_correctly(self):
        result = story_to_dict(SAMPLE_STORY)
        assert result["id"] == "12345"
        assert result["headline_de"] == "Test Schlagzeile"
        assert "1" in result["levels"]
        assert "5" in result["levels"]
        assert result["levels"]["1"]["text_de"] == "Einfach."
        assert result["levels"]["1"]["audio_url"] == "content/2026-02-23/12345/level-1.mp3"
        assert result["levels"]["1"]["audio_duration_seconds"] == 10.5


class TestBuildDigest:
    def test_structure(self):
        digest = build_digest([SAMPLE_STORY], "2026-02-23")
        assert digest["schema_version"] == 1
        assert digest["date"] == "2026-02-23"
        assert len(digest["stories"]) == 1
        assert digest["stories"][0]["id"] == "12345"


class TestWriteDigest:
    def test_writes_both_files(self):
        digest = {"schema_version": 1, "date": "2026-02-23", "stories": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "content" / "2026-02-23"
            write_digest(digest, content_dir)

            digest_path = content_dir / "digest.json"
            latest_path = Path(tmpdir) / "content" / "latest.json"

            assert digest_path.exists()
            assert latest_path.exists()

            with open(digest_path) as f:
                assert json.load(f)["schema_version"] == 1
            with open(latest_path) as f:
                assert json.load(f)["date"] == "2026-02-23"


class TestRunPipeline:
    @pytest.mark.asyncio
    @patch("backend.build.write_digest")
    @patch("backend.build.generate_audio_for_story")
    @patch("backend.build.generate_levels")
    @patch("backend.build.fetch_stories")
    @patch("backend.build.AsyncOpenAI")
    @patch("backend.build.OpenAI")
    @patch("backend.build.OUTPUT_DIR")
    async def test_full_pipeline(
        self,
        mock_output_dir,
        mock_openai,
        mock_async_openai,
        mock_fetch,
        mock_levels,
        mock_audio,
        mock_write,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_output_dir.__truediv__ = lambda self, other: Path(tmpdir) / other

            raw = RawStory(
                id="111",
                title="Test",
                link="https://dw.com/a-111",
                full_text="Langer Text.",
                published_date=datetime(2026, 2, 23),
            )
            mock_fetch.return_value = [raw]

            processed = ProcessedStory(
                id="111",
                headline_de="Schlagzeile",
                headline_en="Headline",
                summary_en="Summary",
                source_url="https://dw.com/a-111",
                levels={1: LevelContent(text_de="Einfach", text_en="Simple")},
            )
            mock_levels.return_value = processed
            mock_audio.return_value = processed

            config = {
                "api_key": "test-key",
                "llm_model": "gpt-4o-mini",
                "tts_voice": "nova",
                "max_stories": 5,
            }

            await run_pipeline(config)

            mock_fetch.assert_called_once_with(max_stories=5)
            mock_levels.assert_called_once()
            mock_audio.assert_called_once()
            mock_write.assert_called_once()

            # Verify digest structure
            digest = mock_write.call_args.args[0]
            assert digest["schema_version"] == 1
            assert len(digest["stories"]) == 1

    @pytest.mark.asyncio
    @patch("backend.build.fetch_stories")
    async def test_no_stories_raises(self, mock_fetch):
        mock_fetch.return_value = []
        config = {
            "api_key": "test-key",
            "llm_model": "gpt-4o-mini",
            "tts_voice": "nova",
            "max_stories": 5,
        }
        with pytest.raises(RuntimeError, match="No stories fetched"):
            await run_pipeline(config)
