## News source: Finnhub over NewsAPI.org
Chose Finnhub because it has a ticker-scoped news endpoint (news filtered by
company already) rather than NewsAPI's general keyword search, and its free
tier fits a stock research tool better. NewsAPI's free tier also caps at
100 req/day and only returns snippets, not full article text.

## Chroma default (local) embedding function, not a hosted embeddings API
Chroma ships with a default local embedding function (ONNX MiniLM, downloaded
once, runs on-device) so `chromadb` alone was enough to add to
requirements.txt -- no separate embeddings API key, no per-embedding cost,
and no extra network dependency for indexing. Trade-off: retrieval quality
is capped by a small general-purpose model rather than a larger hosted
embedding model, which may need revisiting if retrieval quality on harder
queries turns out to be a bottleneck later.

## SEC filings tool returns metadata only; RAG layer fetches full text separately
`get_sec_filings` (Phase 1) intentionally returns only filing metadata (form
type, date, URL) -- not full document text -- to keep the agent-facing tool
result small. Full filing text is fetched and chunked separately in
`src/rag/filing_text.py` + `src/rag/ingest.py`, only when actually indexing
into Chroma, since 10-K/10-Q documents are large (100+ pages) and shouldn't
be pulled into an LLM context wholesale.

## Chunking: word-based sliding window (300 words, 50-word overlap)
Chose a simple word-count sliding window over sentence/paragraph-aware
chunking for a first pass -- avoids mid-word cuts (unlike raw character
slicing) without adding a sentence-boundary-detection dependency. 300 words
with a 50-word (~17%) overlap balances chunk count (a 10-K produces roughly
100-150 chunks) against not losing context at chunk boundaries. May revisit
with paragraph-aware chunking if eval quality demands it.

## Analysis Agent: programmatic retrieval + structured output, not a tool-use loop
Unlike the Phase 1 data collection agent (which uses a tool-use loop so Claude
decides what to fetch), the Analysis Agent retrieves context itself with a
fixed set of Chroma queries (news + filing risk/financials) before making one
LLM call. This is the more standard RAG pattern: retrieval is a
retrieval-augmentation step under the app's control, not something the model
decides ad hoc, since the report generation step needs the exact retrieved
chunks already in context to cite them.

## Analysis Agent output: structured JSON claims with per-claim source_ids
The report is generated via `output_config.format` (structured outputs) as a
list of individual claims, each tagged with which retrieved chunk id(s)
support it, or an empty list if the claim is Claude's own synthesis/inference.
This makes grounded-vs-ungrounded explicit at generation time (not just
prose citations Claude might format inconsistently), and gives Phase 4's
Critic Agent a directly checkable structure: for each non-empty source_ids
claim, verify the claim against that exact chunk's text.

## Model choice: Sonnet for the Analysis Agent, Haiku for data collection
The data collection agent (Phase 1) mostly routes between three well-defined
tools -- Haiku is plenty. The Analysis Agent does the actual synthesis and
citation judgment calls (deciding what's grounded vs. inferred) that the
whole "not just plausible-sounding, but actually checkable" premise of this
project depends on, so it uses Sonnet 5 despite the higher per-token cost.

## Retrieval eval: real ingested data + keyword-verified recall@k, not vibes
Built `src/rag/eval.py`: ingests real AAPL news + a real 10-K, runs 5 queries
(3 news, 2 filing) against the actual indexed content, and checks whether an
expected keyword appears in the top-k retrieved chunks -- a real, falsifiable
recall measurement instead of eyeballing a couple of query outputs. Current
result: 100% recall@1 and recall@3 on all 5 queries. Caveat: the news-based
queries are grounded in whatever articles were in Finnhub's rolling 7-day
window when the eval was written, so they may need updating as that window
rolls forward and the underlying articles age out. The filing-based queries
are stable since SEC filings are permanent documents.
