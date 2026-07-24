# Stock Research Agents

A multi-agent system that researches stock tickers autonomously: it pulls price data, news, and SEC filings, indexes the qualitative sources into a vector store, has one agent synthesize a citation-backed research report, and has a second agent independently fact-check every citation against the actual source text before you ever see it. It can optionally factor in your real (read-only) Robinhood holdings, and it pushes a notification when something worth your attention happens.

> **This is a research tool, not financial advice.** It never places trades — trade execution is always manual. Every recommendation should be treated as a starting point for your own judgment, not a conclusion. See [Limitations](#limitations) below before trusting anything it tells you.

Built as a portfolio project to explore agent orchestration, retrieval-augmented generation, and — the part I think is most interesting — using a second LLM call to verify the first one's claims against ground truth rather than just trusting the model to be right.

## Why this exists

LLMs are fluent, and fluency is easy to mistake for correctness. The core bet of this project is that a research pipeline is more trustworthy if:

1. Every factual claim is tagged with *exactly which retrieved source* it came from, at generation time — not reconstructed after the fact.
2. A second, independent pass checks each claim against that specific source text and flags anything that isn't actually supported — including claims that are *true in the real world* but not stated by the cited source, and claims that overreach what the evidence actually says.

That second part is the Critic Agent, and it isn't a hypothetical safeguard — during development it caught a real error where the Analysis Agent conflated two different tax-rate comparisons in a live Apple 10-K filing (see [Methodology](#methodology) below).

## Architecture

```
                                    ┌─────────────────────┐
  Data Collection Agent ──────────▶│  Chroma (vector DB)  │
  (price / news / filings,         │  news + filing chunks│
   Claude tool-use loop)           └──────────┬───────────┘
                                               │ retrieval
                                               ▼
                                    ┌─────────────────────┐
                                    │   Analysis Agent     │
                                    │ structured claims,   │
                                    │ each cited to a      │
                                    │ specific chunk id    │
                                    └──────────┬───────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │    Critic Agent      │
                                    │ verifies each cited  │
                                    │ claim against its OWN│
                                    │ evidence text         │
                                    └──────────┬───────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                  SQLite (reports,      Notifier (ntfy.sh)    Portfolio context
                  watchlist, snapshots) report ready /        (read-only Robinhood,
                          │             flagged claims /      code-enforced no-write)
                          ▼             significant moves
                  FastAPI dashboard
```

A **Scheduler** service ties it together for unattended use: it watches a ticker watchlist, and only triggers a full (expensive) analysis when a ticker crosses a real significance threshold — a price move or a news-volume spike — rather than re-analyzing everything on a timer regardless of whether anything happened.

### Components

| Component | What it does |
|---|---|
| **Data Collection Agent** (`src/agents/data_collector.py`) | Claude tool-use loop over three tools (`get_price_history`, `get_news`, `get_sec_filings`) — Claude decides which to call and can call them in parallel |
| **RAG layer** (`src/rag/`) | Chunks news articles and SEC filing text, indexes into Chroma with a local embedding model, retrieves by ticker + source type |
| **Analysis Agent** (`src/agents/analysis_agent.py`) | Retrieves relevant chunks programmatically, generates a structured report via Claude's structured outputs — every claim tagged with the exact source chunk id(s) that support it, or an empty list if it's the model's own synthesis |
| **Critic Agent** (`src/agents/critic_agent.py`) | Re-checks every cited claim against its *own* cited evidence text (not a fresh retrieval) and flags anything unsupported |
| **Notifications** (`src/notifications/`) | Swappable `Notifier` interface; ntfy.sh implementation; real numeric/count-based significance thresholds, not "any move" |
| **Portfolio integration** (`src/portfolio/`) | Read-only Robinhood holdings — the no-write guarantee is enforced in code (every order/cancel function in the library is monkey-patched to raise if called), not just by convention |
| **Storage** (`src/storage/`) | SQLite: reports, watchlist, portfolio snapshots (for detecting *newly* overweight positions, not just currently-overweight ones) |
| **Dashboard** (`src/api/`) | FastAPI app — server-rendered HTML pages plus a JSON API for the same operations |
| **Scheduler** (`src/scheduler/`) | Watches the watchlist on an interval, analyzes only what crossed a significance threshold, runs portfolio change detection |

Full rationale for every non-obvious decision — including several reversed or refined mid-project — is in [`DECISIONS.md`](DECISIONS.md).

## Tech stack

Python 3.11+, Anthropic API (Claude Sonnet 5 for analysis/critic, Haiku 4.5 for data collection), Chroma, yfinance, Finnhub, SEC EDGAR, `robin_stocks`, ntfy.sh, FastAPI + Jinja2, SQLite, pytest, Docker Compose.

## Setup

### 1. Local (no Docker)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys, see below
```

Run the dashboard:

```bash
uvicorn src.api.main:app --reload
```

Visit `http://127.0.0.1:8000`.

Run the scheduler standalone:

```bash
python3 -m src.scheduler.loop
```

### 2. Docker Compose (recommended for anything longer than a quick local test)

```bash
cp .env.example .env   # fill in your keys
docker compose up -d --build
```

This starts three services: `chroma` (vector store, its own container so `backend` and `scheduler` share one index), `backend` (the dashboard, `http://127.0.0.1:8000`), and `scheduler` (the watchlist loop, runs unattended on `SCHEDULER_INTERVAL_SECONDS`, default 3600).

**One-time step if you use the Robinhood integration:** the first login needs a phone approval, and an unattended `scheduler` container has no one there to approve it. Log in once via the `backend` container (or locally) to populate the shared `robinhood_session` volume, and subsequent runs reuse that cached session automatically. See [Limitations](#limitations).

### Required `.env` values

```
ANTHROPIC_API_KEY=      # required
FINNHUB_API_KEY=        # required (news)
NTFY_TOPIC=              # optional -- notifications are skipped if unset. Pick a random,
                          # unguessable string, not something descriptive -- see notifier.py
ROBINHOOD_USERNAME=      # optional -- portfolio context is skipped if unset
ROBINHOOD_PASSWORD=      # optional
```

## Usage

- Add a ticker to your watchlist from the dashboard, or `POST /api/watchlist/{ticker}`.
- Click "Analyze" (or `POST /api/reports/{ticker}`) to run the full pipeline on demand.
- The report page shows the rendered report plus a separate, highlighted section for anything the Critic Agent flagged as unsupported.
- With the scheduler running, tickers on your watchlist get analyzed automatically — but only when something crosses a significance threshold, not on every tick.

## Methodology

**Citations are structural, not stylistic.** The Analysis Agent doesn't write prose and hope it's traceable — it's constrained (via Claude's structured outputs) to emit a list of individual claims, each with a `source_ids` field pointing at specific retrieved chunks, or an explicit empty list marking it as the model's own inference. This makes "is this claim grounded?" a checkable property of the data, not something you have to eyeball in a paragraph.

**The Critic Agent sees exactly what the Analysis Agent saw.** It's handed the same retrieved chunk objects the report was generated from — not a fresh Chroma query — because a fresh retrieval could return different chunks than what actually informed the claim, which would mean checking the claim against the wrong evidence.

**The critic's standard is traceability, not truth.** Its system prompt explicitly separates "is this stated in the cited text" from "is this plausible" — a claim can be real-world-true and still get flagged if its specific citation doesn't say it, and a surprising claim passes if its evidence really does support it. This was verified with a real-model eval (`tests/test_critic_eval.py`) covering directly-supported, contradicted, plausible-but-unstated, and overreach-beyond-evidence cases.

**It isn't just a designed-in safeguard — it caught a real error.** During development, on a live Apple 10-K, the Analysis Agent generated a claim attributing Apple's year-over-year effective tax rate change to a set of factors that the filing actually used to explain a *different* comparison (the gap versus the 21% statutory rate). The Critic Agent caught the misattribution and flagged it, with an explanation pointing at exactly what the evidence did and didn't support.

**Retrieval quality is measured, not assumed.** `src/rag/eval.py` runs real queries against real ingested data (not synthetic fixtures) and checks recall@k against keyword-verified expected answers, rather than treating "it returned something" as success.

## Limitations

Documented honestly, because a tool like this is only useful if you know where to be skeptical of it — both of the underlying data and of the boundaries of what's been verified.

- **The Critic Agent verifies traceability, not real-world accuracy.** If a source is itself wrong, a claim can be "supported" by it and still be false. The critic catches hallucination and misattribution, not bad upstream data.
- **Robinhood's API is unofficial and MFA can block unattended runs.** `robin_stocks` reverse-engineers an API Robinhood doesn't publish, and can break without warning. If your account requires phone-approval MFA, the *first* login needs a human present — confirmed empirically: an unattended scheduler run against a fresh session hung indefinitely waiting for an approval nobody was there to give. The mitigation (priming the session once) works, but it's a real, manual, unavoidable step, not something the code can route around.
- **News relevance is loose.** Finnhub's "company news" endpoint often returns market-wide or competitor news that only tangentially mentions the ticker, alongside genuinely company-specific stories. The Analysis Agent has to judge relevance itself; nothing upstream filters this out.
- **"Significant news" is a volume-spike proxy, not semantic judgment.** A real, important development covered by only one or two articles won't trigger a notification. Real semantic significance detection would need either a hand-tuned keyword list (brittle) or an LLM call per headline (slow, costs money on every poll) — this project chose a coarser but concrete, testable threshold instead.
- **Embeddings are a small local model, not a hosted state-of-the-art one.** Chroma's default embedding function (ONNX MiniLM) keeps the project free of a second API key and cost, at the expense of retrieval quality on harder or more nuanced queries than the ones in the eval set.
- **SQLite is shared across containers via a mounted volume.** This works for this project's actual usage pattern (occasional on-demand writes, periodic scheduled writes) but file-locking-based concurrency is not as robust as a real database server under genuinely concurrent writes.
- **Filing chunking is a simple word-count sliding window**, not sentence- or section-aware. It avoids mid-word cuts but doesn't respect document structure (e.g. it can split a table or a sentence across chunk boundaries).
- **This has been tested against a small number of real tickers** (primarily AAPL) during development, not a broad or adversarial set. Behavior on thinly-covered or highly volatile tickers is less validated.

## Testing

114 tests, `pytest`. Notably:
- The Critic Agent's claim-verification logic is checked with a real-model eval against known right answers (`tests/test_critic_eval.py`), not just mocked wiring tests
- The Robinhood read-only guarantee is checked by asserting every real write function in the installed library actually raises, and every real read function stays callable (`tests/test_portfolio_guard.py`)
- Notification threshold logic is checked at exact boundaries (at/above/below threshold, both directions) specifically to guard against false-alarm spam (`tests/test_significance.py`, `tests/test_events.py`)
- The RAG retrieval eval (`src/rag/eval.py`) runs against real ingested data with keyword-verified recall@k, not synthetic fixtures

```bash
python3 -m pytest -v
```

## Project log

- [`DECISIONS.md`](DECISIONS.md) — every architectural decision, with rationale, in the order they were made across all 8 phases.
