import json
from datetime import datetime
from unittest.mock import MagicMock, call, patch

from backend.levels import _call_llm, generate_levels
from backend.models import RawStory


def _make_mock_response(content: dict) -> MagicMock:
    """Create a mock OpenAI chat completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(content)
    return mock_response


SAMPLE_STORY = RawStory(
    id="12345",
    title="Test Schlagzeile",
    link="https://dw.com/a-12345",
    full_text="Ein langer Nachrichtentext über deutsche Politik.",
    published_date=datetime(2026, 2, 23),
)


class TestCallLlm:
    def test_parses_json_response(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_response(
            {"text_de": "Hallo Welt"}
        )

        result = _call_llm(client, "gpt-4o-mini", "Test prompt")
        assert result == {"text_de": "Hallo Welt"}

    def test_passes_system_prompt(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_response(
            {"text_de": "Test"}
        )

        _call_llm(client, "gpt-4o-mini", "User prompt")

        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "CEFR" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"


class TestGenerateLevels:
    def test_generates_all_five_levels(self):
        client = MagicMock()

        # Build response sequence: L5, trans5, L4, trans4, L3, trans3, L2, trans2, L1, trans1
        responses = [
            # Level 5 (C1)
            _make_mock_response({
                "text_de": "Komplexer C1 Text.",
                "headline_de": "C1 Schlagzeile",
                "headline_en": "C1 Headline",
                "summary_en": "A C1 summary.",
            }),
            # Translation for L5
            _make_mock_response({"text_en": "Complex C1 text."}),
            # Level 4 (B2)
            _make_mock_response({"text_de": "Einfacherer B2 Text."}),
            _make_mock_response({"text_en": "Simpler B2 text."}),
            # Level 3 (B1)
            _make_mock_response({"text_de": "Mittlerer B1 Text."}),
            _make_mock_response({"text_en": "Medium B1 text."}),
            # Level 2 (A2)
            _make_mock_response({"text_de": "Leichter A2 Text."}),
            _make_mock_response({"text_en": "Easy A2 text."}),
            # Level 1 (A1)
            _make_mock_response({"text_de": "Einfach A1."}),
            _make_mock_response({"text_en": "Simple A1."}),
        ]
        client.chat.completions.create.side_effect = responses

        result = generate_levels(SAMPLE_STORY, client, "gpt-4o-mini")

        assert result.id == "12345"
        assert result.headline_de == "C1 Schlagzeile"
        assert result.headline_en == "C1 Headline"
        assert result.summary_en == "A C1 summary."
        assert result.source_url == "https://dw.com/a-12345"

        # All 5 levels present
        assert len(result.levels) == 5
        for i in range(1, 6):
            assert i in result.levels
            assert result.levels[i].text_de
            assert result.levels[i].text_en

        # Verify specific content
        assert result.levels[5].text_de == "Komplexer C1 Text."
        assert result.levels[5].text_en == "Complex C1 text."
        assert result.levels[1].text_de == "Einfach A1."
        assert result.levels[1].text_en == "Simple A1."

    def test_makes_ten_llm_calls(self):
        """5 levels + 5 translations = 10 LLM calls."""
        client = MagicMock()

        responses = [
            _make_mock_response({
                "text_de": "Text",
                "headline_de": "H",
                "headline_en": "H",
                "summary_en": "S",
            }),
        ] + [_make_mock_response({"text_de": "T", "text_en": "T"})] * 9

        client.chat.completions.create.side_effect = responses

        generate_levels(SAMPLE_STORY, client, "gpt-4o-mini")
        assert client.chat.completions.create.call_count == 10

    def test_sequential_simplification(self):
        """Each level prompt receives the text from the previous level."""
        client = MagicMock()

        responses = [
            _make_mock_response({
                "text_de": "C1_TEXT",
                "headline_de": "H",
                "headline_en": "H",
                "summary_en": "S",
            }),
            _make_mock_response({"text_en": "trans"}),
            _make_mock_response({"text_de": "B2_TEXT"}),
            _make_mock_response({"text_en": "trans"}),
            _make_mock_response({"text_de": "B1_TEXT"}),
            _make_mock_response({"text_en": "trans"}),
            _make_mock_response({"text_de": "A2_TEXT"}),
            _make_mock_response({"text_en": "trans"}),
            _make_mock_response({"text_de": "A1_TEXT"}),
            _make_mock_response({"text_en": "trans"}),
        ]
        client.chat.completions.create.side_effect = responses

        generate_levels(SAMPLE_STORY, client, "gpt-4o-mini")

        # Check that each level prompt contains the previous level's text
        calls = client.chat.completions.create.call_args_list

        # Call 0: L5 prompt should contain original article text
        l5_prompt = calls[0].kwargs["messages"][1]["content"]
        assert SAMPLE_STORY.full_text in l5_prompt

        # Call 2: L4 prompt should contain C1_TEXT (the L5 output)
        l4_prompt = calls[2].kwargs["messages"][1]["content"]
        assert "C1_TEXT" in l4_prompt

        # Call 4: L3 prompt should contain B2_TEXT
        l3_prompt = calls[4].kwargs["messages"][1]["content"]
        assert "B2_TEXT" in l3_prompt

        # Call 6: L2 prompt should contain B1_TEXT
        l2_prompt = calls[6].kwargs["messages"][1]["content"]
        assert "B1_TEXT" in l2_prompt

        # Call 8: L1 prompt should contain A2_TEXT
        l1_prompt = calls[8].kwargs["messages"][1]["content"]
        assert "A2_TEXT" in l1_prompt
