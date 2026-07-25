import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "research.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    created_at TEXT NOT NULL,
    claim_count INTEGER NOT NULL,
    flagged_count INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    percent_of_portfolio REAL NOT NULL,
    equity REAL NOT NULL
);

-- Small generic key/value store for cross-run state that doesn't warrant
-- its own table, e.g. "have we already sent the credit-exhaustion alert
-- so we don't repeat it every scheduler tick."
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def save_report(report: dict, db_path: str = DB_PATH) -> int:
    """Persists a report. `_retrieved_chunks` is intentionally dropped
    before storage -- it's large (a 10-K alone can be 100+ chunks) and
    reproducible from Chroma, unlike the claims/citations/critic verdicts,
    which are the actual record of what the agent said and why."""
    storable = {k: v for k, v in report.items() if k != "_retrieved_chunks"}

    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO reports (ticker, created_at, claim_count, flagged_count, report_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                report["ticker"],
                _now(),
                len(report.get("claims", [])),
                len(report.get("flagged_claims", [])),
                json.dumps(storable),
            ),
        )
        return cursor.lastrowid


def get_reports(db_path: str = DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ticker, created_at, claim_count, flagged_count "
            "FROM reports ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_report(report_id: int, db_path: str = DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, ticker, created_at, report_json FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()

    if row is None:
        return None

    report = json.loads(row["report_json"])
    report["id"] = row["id"]
    report["created_at"] = row["created_at"]
    return report


def add_to_watchlist(ticker: str, db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, added_at) VALUES (?, ?)",
            (ticker.upper(), _now()),
        )


def remove_from_watchlist(ticker: str, db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))


def get_watchlist(db_path: str = DB_PATH) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY added_at").fetchall()
        return [row["ticker"] for row in rows]


def get_latest_portfolio_snapshot(ticker: str, db_path: str = DB_PATH) -> dict | None:
    """Most recent snapshot for a ticker, taken BEFORE any new snapshot for
    this run is saved -- i.e. this is "what did we last observe", used to
    detect a change against what we're about to observe now."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT ticker, percent_of_portfolio, equity, created_at "
            "FROM portfolio_snapshots WHERE ticker = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (ticker.upper(),),
        ).fetchone()
        return dict(row) if row else None


def save_portfolio_snapshot(
    ticker: str, percent_of_portfolio: float, equity: float, db_path: str = DB_PATH
) -> int:
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO portfolio_snapshots (created_at, ticker, percent_of_portfolio, equity) "
            "VALUES (?, ?, ?, ?)",
            (_now(), ticker.upper(), percent_of_portfolio, equity),
        )
        return cursor.lastrowid


def get_state_flag(key: str, db_path: str = DB_PATH) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
        return bool(row and row["value"])


def set_state_flag(key: str, value: bool, db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO system_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, int(value)),
        )
