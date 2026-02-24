import json
import logging

from openai import OpenAI

from backend.models import LevelContent, ProcessedStory, RawStory
from backend.prompts import (
    LEVEL_PROMPTS,
    SYSTEM_PROMPT,
    TRANSLATION_PROMPT,
)

logger = logging.getLogger(__name__)


def _call_llm(client: OpenAI, model: str, prompt: str) -> dict:
    """Call OpenAI with a prompt and return parsed JSON response."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return json.loads(content)


def generate_levels(
    story: RawStory, client: OpenAI, model: str
) -> ProcessedStory:
    """Generate 3 CEFR-aligned difficulty levels for a story.

    Generation order: top-down sequential (C1 → B1 → A1).
    Levels are numbered 1 (A1), 2 (B1), 3 (C1).
    """
    levels: dict[int, LevelContent] = {}
    headline_de = ""
    headline_en = ""
    summary_en = ""

    # Level 3 (C1) — start from original article
    prompt_c1 = LEVEL_PROMPTS[3].format(article_text=story.full_text)
    result_c1 = _call_llm(client, model, prompt_c1)

    headline_de = result_c1.get("headline_de", story.title)
    headline_en = result_c1.get("headline_en", "")
    summary_en = result_c1.get("summary_en", "")
    text_de_c1 = result_c1["text_de"]

    # Translate C1
    trans_prompt = TRANSLATION_PROMPT.format(text_de=text_de_c1)
    trans_result = _call_llm(client, model, trans_prompt)
    text_en_c1 = trans_result["text_en"]

    levels[3] = LevelContent(text_de=text_de_c1, text_en=text_en_c1)
    logger.info("Story %s: Level 3 (C1) generated", story.id)

    # Level 2 (B1) — simplify from C1
    previous_text = text_de_c1
    for level_num in [2, 1]:
        prompt = LEVEL_PROMPTS[level_num].format(previous_text=previous_text)
        result = _call_llm(client, model, prompt)
        text_de = result["text_de"]

        trans_prompt = TRANSLATION_PROMPT.format(text_de=text_de)
        trans_result = _call_llm(client, model, trans_prompt)
        text_en = trans_result["text_en"]

        levels[level_num] = LevelContent(text_de=text_de, text_en=text_en)
        previous_text = text_de
        logger.info("Story %s: Level %d generated", story.id, level_num)

    return ProcessedStory(
        id=story.id,
        headline_de=headline_de,
        headline_en=headline_en,
        summary_en=summary_en,
        source_url=story.link,
        levels=levels,
    )
