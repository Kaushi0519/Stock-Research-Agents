"""Read-only Robinhood portfolio integration.

Uses the unofficial `robin_stocks` library -- Robinhood has no public,
supported API. This integration can break without warning if Robinhood
changes their (reverse-engineered) endpoints; treat it as fragile.

`guard.enforce_read_only()` is called at import time, before anything else
in this module touches `robin_stocks`, so every function in this file is
backed by a library where write/order operations are already neutered.
"""

from src.portfolio.guard import enforce_read_only

enforce_read_only()

import robin_stocks.robinhood as rh  # noqa: E402  (must follow enforce_read_only())

from src.config import ROBINHOOD_PASSWORD, ROBINHOOD_USERNAME  # noqa: E402

DEFAULT_OVERWEIGHT_THRESHOLD_PCT = 20.0

_logged_in = False


def login() -> None:
    """Logs in to Robinhood if not already logged in this process.

    Note: if the account has MFA/2FA enabled, robin_stocks will prompt
    interactively for a code on first login and can't run unattended in
    that case -- a real limitation of the unofficial API, not something
    this project's code can work around. robin_stocks caches the resulting
    session locally after a successful login, so subsequent runs typically
    don't need MFA again until the session expires.
    """
    global _logged_in
    if _logged_in:
        return

    if not ROBINHOOD_USERNAME or not ROBINHOOD_PASSWORD:
        raise RuntimeError(
            "ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD must be set in .env "
            "to use the portfolio integration."
        )

    rh.login(username=ROBINHOOD_USERNAME, password=ROBINHOOD_PASSWORD)
    _logged_in = True


def get_portfolio_summary() -> dict:
    """Returns total equity and per-position holdings, sorted by portfolio
    weight (largest position first)."""
    login()

    try:
        holdings = rh.build_holdings()
    except Exception as e:
        return {"error": f"Failed to fetch Robinhood holdings: {e}"}

    if not holdings:
        return {"total_equity": 0.0, "positions": []}

    total_equity = sum(float(info["equity"]) for info in holdings.values())

    positions = []
    for ticker, info in holdings.items():
        equity = float(info["equity"])
        percent_of_portfolio = (equity / total_equity * 100) if total_equity else 0.0
        positions.append({
            "ticker": ticker,
            "quantity": float(info["quantity"]),
            "equity": round(equity, 2),
            "percent_of_portfolio": round(percent_of_portfolio, 2),
        })

    positions.sort(key=lambda p: p["percent_of_portfolio"], reverse=True)

    return {"total_equity": round(total_equity, 2), "positions": positions}


def is_position_overweight(
    position: dict, threshold_pct: float = DEFAULT_OVERWEIGHT_THRESHOLD_PCT
) -> bool:
    """A single position's concentration check against a fixed threshold.

    This is a stateless, single-snapshot check ("is this currently
    overweight"), not the "newly became overweight" change-detection the
    brief also asks for -- that needs a persisted prior snapshot to compare
    against, which lives with Phase 7's SQLite storage.
    """
    return position["percent_of_portfolio"] >= threshold_pct
