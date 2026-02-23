from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawStory:
    id: str
    title: str
    link: str
    full_text: str
    published_date: datetime


@dataclass(frozen=True, slots=True)
class LevelContent:
    text_de: str
    text_en: str
    audio_url: str | None = None
    audio_duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ProcessedStory:
    id: str
    headline_de: str
    headline_en: str
    summary_en: str
    source_url: str
    levels: dict[int, LevelContent]
