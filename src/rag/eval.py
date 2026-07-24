"""Retrieval quality eval for the RAG layer.

Ingests real data for a ticker, then runs a set of queries with
known-relevant keywords and checks whether a chunk containing that keyword
appears in the top-k results. This is a real, if small, measurement of
retrieval quality rather than eyeballing a few outputs.

Note: the news-based queries are grounded in Finnhub's rolling recent-news
window at the time this eval was written and may need updating as the
underlying articles roll out of that window. The filing-based queries are
more stable since SEC filings are permanent documents.
"""

from src.rag.ingest import ingest_ticker
from src.rag.store import get_collection, query

EVAL_QUERIES = [
    {
        "query": "What happened with Qualcomm and Samsung's chip partnership?",
        "ticker": "AAPL",
        "source_type": "news",
        "expected_keywords": ["Qualcomm", "Samsung"],
    },
    {
        "query": "How much market value did Magnificent Seven stocks lose in one day?",
        "ticker": "AAPL",
        "source_type": "news",
        "expected_keywords": ["Magnificent Seven", "797 billion"],
    },
    {
        "query": "What was Apple's most recent closing stock price?",
        "ticker": "AAPL",
        "source_type": "news",
        "expected_keywords": ["321.66"],
    },
    {
        "query": "What risks does the company face from manufacturing and suppliers in Asia?",
        "ticker": "AAPL",
        "source_type": "filing",
        "expected_keywords": ["outsourcing", "manufactur"],
    },
    {
        "query": "How is hardware revenue recognized?",
        "ticker": "AAPL",
        "source_type": "filing",
        "expected_keywords": ["revenue", "recogni"],
    },
]


def run_eval(k_values=(1, 3)):
    collection = get_collection()
    results_by_k = {k: [] for k in k_values}

    for case in EVAL_QUERIES:
        max_k = max(k_values)
        hits = query(
            collection,
            case["query"],
            n_results=max_k,
            ticker=case["ticker"],
            source_type=case["source_type"],
        )

        for k in k_values:
            top_k_text = " ".join(h["text"].lower() for h in hits[:k])
            matched = any(kw.lower() in top_k_text for kw in case["expected_keywords"])
            results_by_k[k].append(matched)

    print(f"{'Query':<70} " + " ".join(f"hit@{k:<5}" for k in k_values))
    for i, case in enumerate(EVAL_QUERIES):
        row = f"{case['query'][:68]:<70} "
        row += " ".join(f"{'YES' if results_by_k[k][i] else 'NO':<8}" for k in k_values)
        print(row)

    print()
    for k in k_values:
        hit_count = sum(results_by_k[k])
        recall = hit_count / len(EVAL_QUERIES)
        print(f"recall@{k}: {recall:.0%} ({hit_count}/{len(EVAL_QUERIES)})")

    return results_by_k


if __name__ == "__main__":
    print("Ingesting AAPL data...")
    ingest_ticker("AAPL", filing_types=["10-K"], filings_limit=1)
    print("Running retrieval eval...\n")
    run_eval()
