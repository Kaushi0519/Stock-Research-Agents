from src.rag.chunking import chunk_text
from src.rag.filing_text import fetch_filing_text
from src.rag.store import add_filing_chunks, add_news_articles, get_collection
from src.tools.filings import get_sec_filings
from src.tools.news import get_news


def ingest_ticker(ticker: str, filing_types: list[str] = None, filings_limit: int = 2) -> dict:
    """Fetch news + SEC filings for a ticker and index them into Chroma.

    Returns a summary of what was indexed, including per-filing status so
    callers can see which filings failed to fetch/index without the whole
    ingestion run failing.
    """
    collection = get_collection()

    news_result = get_news(ticker)
    news_chunks_added = 0
    if "error" not in news_result:
        news_chunks_added = add_news_articles(collection, ticker, news_result["articles"])

    filing_types = filing_types or ["10-K", "10-Q"]
    filing_chunks_added = 0
    filings_indexed = []

    for filing_type in filing_types:
        filings_result = get_sec_filings(ticker, filing_type=filing_type, limit=filings_limit)
        if "error" in filings_result:
            continue

        for filing in filings_result["filings"]:
            try:
                text = fetch_filing_text(filing["document_url"])
            except Exception as e:
                filings_indexed.append({**filing, "status": f"failed: {e}"})
                continue

            chunks = chunk_text(text)
            added = add_filing_chunks(collection, ticker, filing, chunks)
            filing_chunks_added += added
            filings_indexed.append({**filing, "status": f"indexed {added} chunks"})

    return {
        "ticker": ticker,
        "news_chunks_indexed": news_chunks_added,
        "filing_chunks_indexed": filing_chunks_added,
        "filings": filings_indexed,
    }
