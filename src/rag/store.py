import chromadb

CHROMA_PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "stock_research_docs"


def get_collection(persist_directory: str = CHROMA_PERSIST_DIR):
    client = chromadb.PersistentClient(path=persist_directory)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def add_news_articles(collection, ticker: str, articles: list[dict]) -> int:
    """Index news articles as one chunk each. Returns number of chunks added."""
    if not articles:
        return 0

    documents, metadatas, ids = [], [], []

    for article in articles:
        text = f"{article['headline']}. {article['summary']}"
        doc_id = f"news:{ticker}:{article['url']}"

        documents.append(text)
        metadatas.append({
            "ticker": ticker,
            "source_type": "news",
            "headline": article["headline"],
            "source": article["source"],
            "url": article["url"],
            "published": article["published"],
        })
        ids.append(doc_id)

    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return len(documents)


def add_filing_chunks(collection, ticker: str, filing: dict, chunks: list[str]) -> int:
    """Index a filing's text chunks. Returns number of chunks added."""
    if not chunks:
        return 0

    documents, metadatas, ids = [], [], []

    for i, chunk in enumerate(chunks):
        doc_id = f"filing:{ticker}:{filing['accession_number']}:{i}"

        documents.append(chunk)
        metadatas.append({
            "ticker": ticker,
            "source_type": "filing",
            "form_type": filing["form_type"],
            "filing_date": filing["filing_date"],
            "accession_number": filing["accession_number"],
            "document_url": filing["document_url"],
            "chunk_index": i,
        })
        ids.append(doc_id)

    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return len(documents)


def _build_where(ticker: str = None, source_type: str = None):
    conditions = []
    if ticker:
        conditions.append({"ticker": ticker})
    if source_type:
        conditions.append({"source_type": source_type})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def query(collection, query_text: str, n_results: int = 5, ticker: str = None, source_type: str = None) -> list[dict]:
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=_build_where(ticker, source_type),
    )

    hits = []
    for doc, meta, dist, doc_id in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    ):
        hits.append({"id": doc_id, "text": doc, "metadata": meta, "distance": dist})

    return hits
