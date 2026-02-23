import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.audio import (
    chunk_text,
    generate_audio_for_story,
    generate_single_audio,
    get_mp3_duration,
    reencode_mp3,
)
from backend.models import LevelContent, ProcessedStory


class TestChunkText:
    def test_short_text_single_chunk(self):
        result = chunk_text("Hallo Welt.", max_chars=100)
        assert result == ["Hallo Welt."]

    def test_splits_at_sentence_boundaries(self):
        text = "Satz eins. Satz zwei. Satz drei."
        result = chunk_text(text, max_chars=25)
        assert len(result) == 2
        assert result[0] == "Satz eins. Satz zwei."
        assert result[1] == "Satz drei."

    def test_handles_long_text(self):
        # 5000 chars should be split into 2 chunks at default limit
        sentences = ["Dies ist ein Testsatz." for _ in range(300)]
        text = " ".join(sentences)
        assert len(text) > 4096
        result = chunk_text(text)
        assert len(result) >= 2
        for c in result:
            assert len(c) <= 4096

    def test_preserves_all_text(self):
        text = "Erster Satz. Zweiter Satz. Dritter Satz."
        result = chunk_text(text, max_chars=20)
        rejoined = " ".join(result)
        assert rejoined == text


class TestReencodeMp3:
    @patch("backend.audio.subprocess.run")
    def test_calls_ffmpeg_correctly(self, mock_run):
        reencode_mp3(Path("/tmp/input.mp3"), Path("/tmp/output.mp3"))
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[0] == "ffmpeg"
        assert "-ac" in args and "1" in args
        assert "-ab" in args and "48k" in args
        assert "-ar" in args and "22050" in args
        assert args[-1] == "/tmp/output.mp3"


class TestGetMp3Duration:
    @patch("backend.audio.MP3")
    def test_returns_duration(self, mock_mp3_cls):
        mock_audio = MagicMock()
        mock_audio.info.length = 15.5
        mock_mp3_cls.return_value = mock_audio

        duration = get_mp3_duration(Path("/tmp/test.mp3"))
        assert duration == 15.5


class TestGenerateSingleAudio:
    @pytest.mark.asyncio
    @patch("backend.audio.get_mp3_duration", return_value=12.3)
    @patch("backend.audio.reencode_mp3")
    async def test_generates_and_reencodes(self, mock_reencode, mock_duration):
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock()
        client.audio.speech.create.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test" / "level-1.mp3"

            path, duration = await generate_single_audio(
                client, "nova", "Hallo Welt", output_path
            )

            client.audio.speech.create.assert_called_once_with(
                model="tts-1",
                voice="nova",
                input="Hallo Welt",
            )
            mock_reencode.assert_called_once()
            assert duration == 12.3


class TestGenerateAudioForStory:
    @pytest.mark.asyncio
    @patch("backend.audio.generate_single_audio")
    async def test_updates_story_with_audio(self, mock_gen):
        story = ProcessedStory(
            id="12345",
            headline_de="Test",
            headline_en="Test",
            summary_en="Test",
            source_url="https://dw.com/a-12345",
            levels={
                1: LevelContent(text_de="Einfach", text_en="Simple"),
                2: LevelContent(text_de="Leicht", text_en="Easy"),
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "content" / "2026"
            output_dir.mkdir(parents=True)

            # Return paths relative to the actual tmpdir
            audio_path = str(output_dir / "12345" / "level-1.mp3")
            mock_gen.return_value = (audio_path, 10.5)

            result = await generate_audio_for_story(
                story,
                client=AsyncMock(),
                voice="nova",
                output_dir=output_dir,
            )

            assert len(result.levels) == 2
            assert mock_gen.call_count == 2
            # Audio URL should include content/ prefix for site serving
            assert result.levels[1].audio_url.startswith("content/")
            assert "12345/level-1.mp3" in result.levels[1].audio_url
            assert result.levels[1].audio_duration_seconds == 10.5

    @pytest.mark.asyncio
    @patch("backend.audio.generate_single_audio")
    async def test_handles_partial_failure(self, mock_gen):
        story = ProcessedStory(
            id="12345",
            headline_de="Test",
            headline_en="Test",
            summary_en="Test",
            source_url="https://dw.com/a-12345",
            levels={
                1: LevelContent(text_de="Einfach", text_en="Simple"),
                2: LevelContent(text_de="Leicht", text_en="Easy"),
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "content" / "2026"
            output_dir.mkdir(parents=True)

            audio_path = str(output_dir / "12345" / "level-1.mp3")
            # Level 1 succeeds, Level 2 fails
            mock_gen.side_effect = [
                (audio_path, 10.5),
                Exception("TTS API error"),
            ]

            result = await generate_audio_for_story(
                story,
                client=AsyncMock(),
                voice="nova",
                output_dir=output_dir,
            )

            # Level 2 should still exist but without audio
            assert result.levels[2].audio_url is None
            assert result.levels[2].audio_duration_seconds is None
