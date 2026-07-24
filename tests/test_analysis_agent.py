from src.agents.analysis_agent import _format_context, render_report


def test_format_context_news_chunk():
    chunks = [{
        "id": "news:AAPL:https://example.com/1",
        "text": "Apple announced a new product.",
        "metadata": {
            "source_type": "news",
            "headline": "Apple announces new product",
            "source": "Yahoo",
            "published": "2026-07-23T10:00:00",
        },
    }]

    formatted = _format_context(chunks)

    assert "[source_id: news:AAPL:https://example.com/1]" in formatted
    assert "NEWS - Apple announces new product (Yahoo, 2026-07-23T10:00:00)" in formatted
    assert "Apple announced a new product." in formatted


def test_format_context_filing_chunk():
    chunks = [{
        "id": "filing:AAPL:0000320193-25-000079:3",
        "text": "The Company faces supply chain risk.",
        "metadata": {
            "source_type": "filing",
            "form_type": "10-K",
            "filing_date": "2025-10-31",
            "chunk_index": 3,
        },
    }]

    formatted = _format_context(chunks)

    assert "[source_id: filing:AAPL:0000320193-25-000079:3]" in formatted
    assert "FILING - 10-K filed 2025-10-31 (chunk 3)" in formatted
    assert "The Company faces supply chain risk." in formatted


def test_render_report_groups_by_section_and_shows_citations():
    report = {
        "ticker": "AAPL",
        "claims": [
            {
                "section": "price_performance",
                "text": "AAPL is up 26% over 6 months.",
                "source_ids": [],
            },
            {
                "section": "recent_news",
                "text": "Tim Cook is stepping down as CEO.",
                "source_ids": ["news:AAPL:https://example.com/1"],
            },
            {
                "section": "risks",
                "text": "The company depends on suppliers in Asia.",
                "source_ids": ["filing:AAPL:acc123:0"],
            },
        ],
    }

    rendered = render_report(report)

    assert "# Research Report: AAPL" in rendered
    assert "## Price Performance" in rendered
    assert "## Recent News & Catalysts" in rendered
    assert "## Key Risks" in rendered
    assert "[unsourced synthesis]" in rendered
    assert "['news:AAPL:https://example.com/1']" in rendered
    # No overall_assessment claims -> that section header should be omitted
    assert "## Overall Assessment" not in rendered


def test_render_report_skips_empty_sections():
    report = {"ticker": "MSFT", "claims": []}

    rendered = render_report(report)

    assert "# Research Report: MSFT" in rendered
    assert "##" not in rendered
