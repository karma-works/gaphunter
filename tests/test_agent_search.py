from __future__ import annotations

from agent.tools.search import clean_search_text


def test_agent_clean_search_text_strips_tags_and_decodes_entities():
    text = "<strong>Review</strong> finance data &amp;amp; controls&amp;hellip;"

    assert clean_search_text(text) == "Review finance data & controls..."
