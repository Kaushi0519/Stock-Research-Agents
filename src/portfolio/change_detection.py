from src.notifications.notifier import Notifier
from src.portfolio.robinhood import DEFAULT_OVERWEIGHT_THRESHOLD_PCT, get_portfolio_summary
from src.storage.db import get_latest_portfolio_snapshot, save_portfolio_snapshot


def check_and_record_portfolio_changes(
    notifier: Notifier | None = None, threshold_pct: float = DEFAULT_OVERWEIGHT_THRESHOLD_PCT
) -> list[str]:
    """Compares the current portfolio against the last recorded snapshot of
    each position, notifies on any position that just crossed INTO
    overweight territory (wasn't overweight last time, is now), and records
    a new snapshot either way so the next run has something to compare
    against.

    This is the "newly relevant" portfolio-change trigger from the original
    brief -- distinct from `is_position_overweight`'s stateless check, this
    one only fires on a *transition*, not on every run where a position
    happens to still be overweight (which would just be repeat noise).

    Returns the list of tickers that newly crossed the threshold.
    """
    summary = get_portfolio_summary()
    if "error" in summary:
        return []

    newly_overweight = []

    for position in summary["positions"]:
        ticker = position["ticker"]
        previous = get_latest_portfolio_snapshot(ticker)

        was_overweight = previous is not None and previous["percent_of_portfolio"] >= threshold_pct
        is_overweight = position["percent_of_portfolio"] >= threshold_pct

        if is_overweight and not was_overweight:
            newly_overweight.append(ticker)

        save_portfolio_snapshot(ticker, position["percent_of_portfolio"], position["equity"])

    if newly_overweight and notifier:
        tickers_str = ", ".join(newly_overweight)
        notifier.send(
            "Portfolio concentration changed",
            f"Newly overweight (>= {threshold_pct}% of portfolio): {tickers_str}",
            priority="high",
        )

    return newly_overweight
