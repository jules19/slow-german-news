import logging
from datetime import datetime

import feedparser
import httpx

from backend.models import RawStory

logger = logging.getLogger(__name__)

DW_RSS_URL = "https://rss.dw.com/xml/rss-de-all"
DW_API_URL = "https://api.dw.com/api/detail/article/{article_id}"
HTTP_TIMEOUT = 30.0


def fetch_rss_entries(max_entries: int = 10) -> list[dict]:
    """Fetch and return the most recent RSS entries from DW."""
    feed = feedparser.parse(DW_RSS_URL)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"Failed to parse DW RSS feed: {feed.bozo_exception}")
    entries = feed.entries[:max_entries]
    logger.info("Fetched %d RSS entries from DW", len(entries))
    return entries


def parse_rss_entry(entry: dict) -> dict:
    """Extract article ID, title, link, and published date from an RSS entry."""
    article_id = entry.get("id", "")
    title = entry.get("title", "")
    link = entry.get("link", "")
    # Strip tracking parameters from link
    if "?" in link:
        link = link.split("?")[0]

    published = entry.get("published_parsed")
    if published:
        published_date = datetime(*published[:6])
    else:
        published_date = datetime.now()

    return {
        "id": article_id,
        "title": title,
        "link": link,
        "published_date": published_date,
    }


def fetch_article_text(article_id: str) -> str:
    """Fetch full article text from DW's public JSON API."""
    url = DW_API_URL.format(article_id=article_id)
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("text", "")
        if not text:
            raise ValueError(f"No text found for article {article_id}")
        return text


def fetch_stories(max_stories: int = 5) -> list[RawStory]:
    """Fetch today's stories from DW: RSS discovery + API full text."""
    entries = fetch_rss_entries(max_entries=max_stories * 2)
    stories = []

    for entry in entries:
        if len(stories) >= max_stories:
            break

        parsed = parse_rss_entry(entry)
        try:
            full_text = fetch_article_text(parsed["id"])
        except Exception:
            logger.warning("Failed to fetch article %s, skipping", parsed["id"])
            continue

        stories.append(
            RawStory(
                id=parsed["id"],
                title=parsed["title"],
                link=parsed["link"],
                full_text=full_text,
                published_date=parsed["published_date"],
            )
        )

    logger.info("Fetched %d stories with full text", len(stories))
    return stories
