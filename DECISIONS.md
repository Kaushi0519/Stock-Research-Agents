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

## Critic Agent: judge traceability to cited evidence, not plausibility
The Critic Agent's system prompt explicitly instructs it to judge whether a
claim is stated in its cited evidence text, not whether the claim sounds
true or plausible in general. This is the whole point of the critic step --
a claim can be real-world-true and still get flagged if the specific
retrieved chunk it cited doesn't actually say it, and a surprising-sounding
claim should pass if the evidence really does support it. Verified with a
real-model eval (`tests/test_critic_eval.py`) covering directly-supported,
contradicted, plausible-but-unstated, and overreach-beyond-evidence cases --
all 4 judged correctly. In a real run against AAPL, the critic also caught a
genuine subtle error the Analysis Agent made: it conflated two different
comparisons in a 10-K's tax-rate discussion (factors explaining the gap vs.
the 21% statutory rate, misattributed to the year-over-year change instead).

## Critic Agent reuses the Analysis Agent's exact retrieved chunks
`critique_report` reads `report["_retrieved_chunks"]` (the same chunk
objects the Analysis Agent retrieved and cited from) rather than re-querying
Chroma. A fresh retrieval could return different chunks than what the claim
was actually generated from, which would make the critic check against the
wrong evidence -- so the critic must see exactly what the analysis agent saw.

## Notifier abstraction + ntfy.sh, per original plan
`Notifier` is an ABC with a single `send(title, message, priority)` method;
`NtfyNotifier` is the only concrete implementation so far. Swapping in
Pushover or email later means writing one new class, not touching any
calling code, since `events.py` only ever depends on the `Notifier`
interface.

SECURITY NOTE (also documented in the class docstring): ntfy.sh's public
server has no access control by topic -- anyone who knows the topic string
can subscribe and read notifications. `NTFY_TOPIC` must be a random,
unguessable string (not something descriptive like "stock-alerts"), and is
gitignored via `.env` like the other secrets.

## Significance thresholds: numeric price move %, and news volume count
Price: a single-day move >= a configurable percent threshold (default 5%),
checked in EITHER direction via `abs()` -- a big drop is just as significant
as a big gain, and using the signed value instead would silently miss
crashes. Missing/insufficient price data fails closed (not significant, no
notification) rather than failing open, since a false negative (missed
alert) is a much smaller problem than spamming on bad data.

News: rather than judging a single headline's importance semantically
(which would need either a brittle hand-tuned keyword list or an extra LLM
call per headline), "significant" is defined as a volume spike -- N or more
new articles in a time window (default 3 in 24h). This is a coarser signal
than true semantic significance but is a concrete, real, testable threshold,
consistent with the project's "don't want false-alarm spam" requirement.
Documented limitation: a real news event with only 1-2 articles about it
(quieter coverage) won't trigger this -- a future iteration could add an
LLM-based headline classifier as a complementary, not replacement, signal.

## notify_report_ready always fires; notify_flagged_claims only fires if something was flagged
A finished report is inherently something the user asked for and wants to
know about, so it's not threshold-gated. But a *second* notification saying
"nothing was flagged" on top of that would be pure noise for the common
case (most reports probably won't have flagged claims) -- so
notify_flagged_claims is a no-op, not a "nothing wrong" ping, when
flagged_claims is empty.

## Robinhood read-only guarantee: enforced in code, not convention
`src/portfolio/guard.py` monkey-patches every function in
`robin_stocks.robinhood.{orders,options,crypto}` matching an
order/cancel/buy/sell name pattern to raise `ReadOnlyViolation` instead of
calling Robinhood's API, at import time, before any other robin_stocks
usage in this project. Verified empirically against the actually-installed
robin_stocks version (not assumed from memory) -- inspected all 169
functions in the `orders` submodule directly; confirmed every real
write/order function is a name-pattern match, and that no `get_*` read
function collides with the pattern. `options`/`crypto` submodules currently
have zero write functions of their own (everything, including crypto/option
orders, lives in `orders`), but are still swept for robustness against
future robin_stocks versions moving things around.

Deliberately over-broad pattern trade-off: a couple of harmless URL-builder
helpers (e.g. `cancel_url`, which just returns a string) also get neutered
as false positives. Accepted deliberately -- a blocked helper is a loud,
obvious bug to fix; a missed write function is not recoverable after the
fact. Verified with parametrized tests asserting real write functions raise
and real read functions remain unpatched.

## Portfolio integration degrades silently, doesn't hard-fail the pipeline
`get_portfolio_context_for_ticker` catches all failures (missing
credentials, login failure, network error) and returns `None` rather than
raising, and `analyze_ticker` treats portfolio context as optional
enrichment. Robinhood's unofficial API is inherently fragile (no public,
supported endpoint, can break without warning), and MFA-enabled accounts
can't complete a fully unattended login -- the research pipeline (Phases
1-5) should keep working for users who never configure Robinhood at all,
or on a run where this specific integration happens to be down.

## Overweight is a stateless threshold check; "newly overweight" needs Phase 7's storage
`is_position_overweight` checks a single snapshot against a fixed percent
threshold (default 20%). The brief's "portfolio composition changes in a
way the system flags as newly relevant" notification needs a *prior*
snapshot to compare against -- that requires persisted history, which
belongs with Phase 7's SQLite layer. Wiring the actual
notify-on-newly-overweight event happens once that storage exists.

## Dashboard: server-rendered HTML forms, no JS framework
Per the brief's own allowance ("even just clean markdown/PDF reports"), the
dashboard is plain Jinja2-templated HTML with `<form>` POSTs (redirect
afterward) -- no React/JS build step. This is a research/portfolio tool run
locally, not a product with real users, so the extra frontend tooling
wouldn't buy anything. A JSON API (`/api/*`) exists alongside the HTML pages
for the same underlying operations, for programmatic use (e.g. a future
scheduler in Phase 7.5).

## SQLite stores the report minus `_retrieved_chunks`
`db.save_report` strips `_retrieved_chunks` before persisting. A single
10-K alone can produce 100+ chunks; keeping them in every stored report
would bloat the database for data that's reproducible from Chroma on demand,
whereas the claims/citations/critic verdicts are the actual durable record
of what the agent concluded and why.

## Newly-overweight detection: transition-based, not snapshot-based
`check_and_record_portfolio_changes` (the piece deferred from Phase 6)
compares each position's current weight against the last *recorded*
snapshot, and only notifies on positions that just crossed INTO overweight
territory -- a position that was already overweight last run and still is
does not re-fire. Same anti-spam principle as the Phase 5 notification
design: a repeat state is not new information.

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
