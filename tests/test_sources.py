import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.models import RawStory
from backend.sources import fetch_article_text, fetch_stories, parse_rss_entry


class TestParseRssEntry:
    def test_basic_entry(self):
        entry = {
            "id": "76083226",
            "title": "Mexiko: Welle der Gewalt",
            "link": "https://www.dw.com/de/mexiko/a-76083226?maca=de-rss",
            "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
        }
        result = parse_rss_entry(entry)
        assert result["id"] == "76083226"
        assert result["title"] == "Mexiko: Welle der Gewalt"
        assert result["link"] == "https://www.dw.com/de/mexiko/a-76083226"
        assert result["published_date"].year == 2026

    def test_strips_tracking_params(self):
        entry = {
            "id": "123",
            "title": "Test",
            "link": "https://dw.com/a-123?maca=tracking&foo=bar",
            "published_parsed": None,
        }
        result = parse_rss_entry(entry)
        assert "?" not in result["link"]
        assert result["link"] == "https://dw.com/a-123"

    def test_missing_published_date(self):
        entry = {"id": "123", "title": "Test", "link": "https://dw.com/a-123"}
        result = parse_rss_entry(entry)
        assert isinstance(result["published_date"], datetime)


class TestFetchArticleText:
    @patch("backend.sources.httpx.Client")
    def test_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "Full article text about politics.",
            "name": "Test Article",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        text = fetch_article_text("76083226")
        assert text == "Full article text about politics."
        mock_client.get.assert_called_once_with(
            "https://api.dw.com/api/detail/article/76083226"
        )

    @patch("backend.sources.httpx.Client")
    def test_empty_text_raises(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": ""}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="No text found"):
            fetch_article_text("99999")


class TestFetchStories:
    @patch("backend.sources.fetch_article_text")
    @patch("backend.sources.fetch_rss_entries")
    def test_returns_raw_stories(self, mock_rss, mock_api):
        mock_rss.return_value = [
            {
                "id": "111",
                "title": "Story One",
                "link": "https://dw.com/a-111",
                "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
            },
            {
                "id": "222",
                "title": "Story Two",
                "link": "https://dw.com/a-222",
                "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
            },
        ]
        mock_api.side_effect = ["Text for story one.", "Text for story two."]

        stories = fetch_stories(max_stories=5)
        assert len(stories) == 2
        assert all(isinstance(s, RawStory) for s in stories)
        assert stories[0].id == "111"
        assert stories[0].full_text == "Text for story one."
        assert stories[1].id == "222"

    @patch("backend.sources.fetch_article_text")
    @patch("backend.sources.fetch_rss_entries")
    def test_skips_failed_articles(self, mock_rss, mock_api):
        mock_rss.return_value = [
            {
                "id": "111",
                "title": "Story One",
                "link": "https://dw.com/a-111",
                "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
            },
            {
                "id": "222",
                "title": "Story Two",
                "link": "https://dw.com/a-222",
                "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
            },
        ]
        mock_api.side_effect = [Exception("API error"), "Text for story two."]

        stories = fetch_stories(max_stories=5)
        assert len(stories) == 1
        assert stories[0].id == "222"

    @patch("backend.sources.fetch_article_text")
    @patch("backend.sources.fetch_rss_entries")
    def test_respects_max_stories(self, mock_rss, mock_api):
        mock_rss.return_value = [
            {
                "id": str(i),
                "title": f"Story {i}",
                "link": f"https://dw.com/a-{i}",
                "published_parsed": time.strptime("2026-02-23", "%Y-%m-%d"),
            }
            for i in range(10)
        ]
        mock_api.return_value = "Article text."

        stories = fetch_stories(max_stories=3)
        assert len(stories) == 3
