from src.portfolio.robinhood import (
    DEFAULT_OVERWEIGHT_THRESHOLD_PCT,
    get_portfolio_summary,
    is_position_overweight,
)


def get_portfolio_context_for_ticker(
    ticker: str, threshold_pct: float = DEFAULT_OVERWEIGHT_THRESHOLD_PCT
) -> str | None:
    """Returns a short note describing the user's existing position in this
    ticker, for the Analysis Agent to factor into its report -- or None if
    Robinhood isn't configured, the lookup fails, or the ticker isn't held.

    This degrades gracefully on purpose: the portfolio integration is
    optional enrichment, not a hard dependency of the research pipeline --
    analysis should still work for users who haven't set up Robinhood at
    all, or on a run where the (unofficial, fragile) integration happens to
    be down.
    """
    try:
        summary = get_portfolio_summary()
    except Exception:
        return None

    if "error" in summary:
        return None

    position = next(
        (p for p in summary["positions"] if p["ticker"].upper() == ticker.upper()), None
    )
    if position is None:
        return None

    overweight_note = ""
    if is_position_overweight(position, threshold_pct):
        overweight_note = (
            f" This is already an overweight position (>= {threshold_pct}% of "
            f"the portfolio) -- factor existing concentration risk into the analysis."
        )

    return (
        f"The user currently holds {position['quantity']:g} shares of {ticker}, "
        f"worth ${position['equity']:,.2f}, representing "
        f"{position['percent_of_portfolio']:.1f}% of their portfolio."
        f"{overweight_note}"
    )
