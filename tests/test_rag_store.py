import chromadb

from src.rag.store import add_filing_chunks, add_news_articles, query


def _fresh_collection():
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection(name="test_collection")


def test_add_news_articles_and_query():
    collection = _fresh_collection()
    articles = [
        {
            "headline": "Tim Cook steps down as CEO",
            "summary": "John Ternus will take over as CEO in September.",
            "source": "Yahoo",
            "url": "https://example.com/1",
            "published": "2026-07-23T10:00:00",
        },
        {
            "headline": "Apple tests new AI shopping chatbot",
            "summary": "The chatbot helps customers pick devices and complete purchases.",
            "source": "Yahoo",
            "url": "https://example.com/2",
            "published": "2026-07-23T09:00:00",
        },
    ]

    added = add_news_articles(collection, "AAPL", articles)
    assert added == 2

    results = query(collection, "Who is the new CEO of Apple?", n_results=1, ticker="AAPL")
    assert len(results) == 1
    assert "Ternus" in results[0]["text"]
    assert results[0]["metadata"]["source_type"] == "news"


def test_add_news_articles_empty_list_is_noop():
    collection = _fresh_collection()
    assert add_news_articles(collection, "AAPL", []) == 0


def test_add_filing_chunks_and_query():
    collection = _fresh_collection()
    filing = {
        "form_type": "10-K",
        "filing_date": "2025-10-31",
        "accession_number": "0000320193-25-000079",
        "document_url": "https://example.com/10k.htm",
    }
    chunks = [
        "This section discusses supply chain risk and dependency on manufacturing partners in Asia.",
        "This section discusses revenue recognition policies for hardware and services.",
    ]

    added = add_filing_chunks(collection, "AAPL", filing, chunks)
    assert added == 2

    results = query(
        collection,
        "What does the filing say about supply chain risk?",
        n_results=1,
        ticker="AAPL",
        source_type="filing",
    )
    assert len(results) == 1
    assert "supply chain" in results[0]["text"]
    assert results[0]["metadata"]["form_type"] == "10-K"


def test_query_filters_by_ticker():
    collection = _fresh_collection()
    add_news_articles(collection, "AAPL", [{
        "headline": "AAPL news", "summary": "About Apple.", "source": "Yahoo",
        "url": "https://example.com/aapl", "published": "2026-07-23T00:00:00",
    }])
    add_news_articles(collection, "MSFT", [{
        "headline": "MSFT news", "summary": "About Microsoft.", "source": "Yahoo",
        "url": "https://example.com/msft", "published": "2026-07-23T00:00:00",
    }])

    results = query(collection, "company news", n_results=5, ticker="AAPL")
    assert all(r["metadata"]["ticker"] == "AAPL" for r in results)
