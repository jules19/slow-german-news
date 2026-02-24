from datetime import datetime

import pytest

from backend.models import LevelContent, ProcessedStory, RawStory


class TestRawStory:
    def test_construction(self):
        story = RawStory(
            id="12345",
            title="Test Headline",
            link="https://dw.com/a-12345",
            full_text="Full article text here.",
            published_date=datetime(2026, 2, 23, 10, 0, 0),
        )
        assert story.id == "12345"
        assert story.title == "Test Headline"
        assert story.link == "https://dw.com/a-12345"
        assert story.full_text == "Full article text here."
        assert story.published_date == datetime(2026, 2, 23, 10, 0, 0)

    def test_frozen(self):
        story = RawStory(
            id="12345",
            title="Test",
            link="https://dw.com/a-12345",
            full_text="Text",
            published_date=datetime(2026, 2, 23),
        )
        with pytest.raises(AttributeError):
            story.title = "Changed"


class TestLevelContent:
    def test_construction_minimal(self):
        content = LevelContent(text_de="Hallo", text_en="Hello")
        assert content.text_de == "Hallo"
        assert content.text_en == "Hello"
        assert content.audio_url is None
        assert content.audio_duration_seconds is None

    def test_construction_with_audio(self):
        content = LevelContent(
            text_de="Hallo",
            text_en="Hello",
            audio_url="content/2026-02-23/12345/level-1.mp3",
            audio_duration_seconds=15.5,
        )
        assert content.audio_url == "content/2026-02-23/12345/level-1.mp3"
        assert content.audio_duration_seconds == 15.5

    def test_frozen(self):
        content = LevelContent(text_de="Hallo", text_en="Hello")
        with pytest.raises(AttributeError):
            content.text_de = "Tschüss"


class TestProcessedStory:
    def test_construction(self):
        levels = {
            1: LevelContent(text_de="Einfach", text_en="Simple"),
            3: LevelContent(text_de="Komplex", text_en="Complex"),
        }
        story = ProcessedStory(
            id="12345",
            headline_de="Test Schlagzeile",
            headline_en="Test Headline",
            summary_en="A test summary.",
            source_url="https://dw.com/a-12345",
            levels=levels,
        )
        assert story.id == "12345"
        assert story.headline_de == "Test Schlagzeile"
        assert len(story.levels) == 2
        assert story.levels[1].text_de == "Einfach"
        assert story.levels[3].text_en == "Complex"

    def test_all_three_levels(self):
        levels = {
            i: LevelContent(text_de=f"Level {i} DE", text_en=f"Level {i} EN")
            for i in range(1, 4)
        }
        story = ProcessedStory(
            id="99999",
            headline_de="Schlagzeile",
            headline_en="Headline",
            summary_en="Summary",
            source_url="https://dw.com/a-99999",
            levels=levels,
        )
        assert len(story.levels) == 3
        for i in range(1, 4):
            assert i in story.levels
