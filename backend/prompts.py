"""CEFR-aligned prompt templates for progressive difficulty generation.

Generation order: top-down sequential (C1 → B1 → A1).
3 levels: 1 (A1 Einfach), 2 (B1 Mittel), 3 (C1 Original).
"""

SYSTEM_PROMPT = """\
You are a German language teaching expert specializing in CEFR-aligned text \
simplification. You transform German news articles into precisely graded \
difficulty levels for language learners. Always respond in valid JSON."""

LEVEL_5_C1_PROMPT = """\
Take this German news article and lightly edit it for clarity. Keep the full \
news register, all complex grammar, and domain vocabulary. Only fix obvious \
errors or unclear phrasing. This is Level 5 (C1 — "Original").

ALLOWED GRAMMAR: Everything — Konjunktiv I (indirect speech), extended \
participial constructions, nominalization, complex multi-clause sentences, \
full news register.

CONSTRAINTS:
- Keep it close to the original article
- Lightly edit for clarity only
- Maintain all domain-specific vocabulary
- No sentence length limit

ARTICLE:
{article_text}

Respond with JSON:
{{
  "text_de": "The C1-level German text",
  "headline_de": "A concise German headline for this story",
  "headline_en": "English translation of the headline",
  "summary_en": "1-2 sentence English summary of the story"
}}"""

LEVEL_4_B2_PROMPT = """\
Simplify this German text from C1 to B2 level. Remove the most complex \
features while keeping sophisticated news language.

CURRENT TEXT (C1):
{previous_text}

CHANGES TO MAKE:
- Replace Konjunktiv I (indirect speech) with direct speech or indicative
- Simplify extended participial constructions into relative clauses
- Reduce nominalizations back to verb phrases where possible
- Keep genitive prepositions (trotz, wegen), two-part connectors (sowohl...als auch)
- Keep full Konjunktiv II, domain vocabulary
- Maximum ~25 words per sentence

ALLOWED GRAMMAR: Full Konjunktiv II, genitive prepositions (trotz, wegen), \
two-part connectors (sowohl...als auch, nicht nur...sondern auch), relative \
clauses, Präteritum, passive voice, domain vocabulary.

Respond with JSON:
{{
  "text_de": "The B2-level German text"
}}"""

LEVEL_3_B1_PROMPT = """\
Simplify this German text from C1 to B1 level. This is the middle ground — \
clear news language without advanced grammar.

CURRENT TEXT (C1):
{previous_text}

CHANGES TO MAKE:
- Replace Konjunktiv II with simpler alternatives (würde + infinitive or indicative)
- Remove genitive prepositions (trotz → obwohl, wegen → weil)
- Break two-part connectors into simple connectors
- Replace domain vocabulary with common equivalents
- Keep Präteritum, passive voice (Vorgangspassiv), relative clauses
- Keep common Konjunktiv II (wäre, hätte) only
- Maximum ~18 words per sentence

ALLOWED GRAMMAR: Präteritum, passive voice (Vorgangspassiv), relative \
clauses, common Konjunktiv II (wäre, hätte, könnte), weil/dass/wenn clauses.

Respond with JSON:
{{
  "text_de": "The B1-level German text"
}}"""

LEVEL_2_A2_PROMPT = """\
Simplify this German text from B1 to A2 level. Use only basic past tense \
and simple subordinate clauses.

CURRENT TEXT (B1):
{previous_text}

CHANGES TO MAKE:
- Replace Präteritum with Perfekt (except sein/haben/werden/modal verbs)
- Remove passive voice entirely — use active voice
- Remove relative clauses — use separate sentences instead
- Remove any remaining Konjunktiv
- Use only weil, dass, wenn for subordination
- Use modal verbs (können, müssen, wollen, sollen)
- Use basic, high-frequency vocabulary
- Maximum ~12 words per sentence

ALLOWED GRAMMAR: Perfekt tense, weil/dass/wenn clauses, modal verbs \
(können, müssen, wollen, sollen), separable verbs, basic adjective \
declension. Conjunctions: und, oder, aber, weil, dass, wenn.

Respond with JSON:
{{
  "text_de": "The A2-level German text"
}}"""

LEVEL_1_A1_PROMPT = """\
Simplify this German text from B1 to A1 level. Use only the most basic \
German. This should be understandable by a true beginner.

CURRENT TEXT (B1):
{previous_text}

CHANGES TO MAKE:
- Use present tense ONLY (no Perfekt, no past tense)
- Use only main clauses with SVO word order
- Remove all subordinate clauses (no weil, dass, wenn)
- Only und, oder, aber for connecting ideas
- Use only the most basic vocabulary (top 500 words)
- Write 2-3 short sentences total
- Maximum ~8 words per sentence

ALLOWED GRAMMAR: Present tense only, SVO main clauses only, und/oder/aber, \
basic vocabulary, no subordination.

Respond with JSON:
{{
  "text_de": "The A1-level German text"
}}"""

TRANSLATION_PROMPT = """\
Translate this German text into natural, fluent English. Keep the same level \
of complexity and register as the German original.

GERMAN TEXT:
{text_de}

Respond with JSON:
{{
  "text_en": "The English translation"
}}"""

# Map level numbers to their prompts (3 = C1 first, down to 1 = A1)
LEVEL_PROMPTS = {
    3: LEVEL_5_C1_PROMPT,
    2: LEVEL_3_B1_PROMPT,
    1: LEVEL_1_A1_PROMPT,
}
