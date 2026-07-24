import yfinance as yf

from src.tools.news import get_news

DEFAULT_PRICE_MOVE_THRESHOLD_PCT = 5.0
DEFAULT_NEWS_VOLUME_THRESHOLD = 3
DEFAULT_NEWS_VOLUME_WINDOW_DAYS = 1


def get_latest_daily_change_pct(ticker: str) -> float | None:
    """Most recent single trading day's % price change (latest close vs the
    prior close). Distinct from price_data.py's `get_price_history`, which
    reports a period-over-period summary, not the latest single-day move.
    Returns None if there isn't enough recent history to compute this.
    """
    try:
        hist = yf.Ticker(ticker).history(period="5d")
    except Exception:
        return None

    if hist.empty or len(hist) < 2:
        return None

    closes = hist["Close"]
    latest = float(closes.iloc[-1])
    previous = float(closes.iloc[-2])

    return (latest - previous) / previous * 100


def is_significant_price_move(
    ticker: str, threshold_pct: float = DEFAULT_PRICE_MOVE_THRESHOLD_PCT
) -> bool:
    """A move counts as significant if it's at least `threshold_pct` percent
    in EITHER direction -- a big drop matters as much as a big gain."""
    change_pct = get_latest_daily_change_pct(ticker)
    if change_pct is None:
        return False
    return abs(change_pct) >= threshold_pct


def is_significant_news_volume(
    ticker: str,
    count_threshold: int = DEFAULT_NEWS_VOLUME_THRESHOLD,
    days_back: int = DEFAULT_NEWS_VOLUME_WINDOW_DAYS,
) -> bool:
    """Treat a burst of new coverage (>= count_threshold articles in the
    last `days_back` days) as a proxy signal that something notable is
    happening, rather than trying to semantically judge a single headline's
    importance -- which would need either a hand-tuned keyword list (brittle)
    or an extra LLM call per headline (slow and costs money for every poll).
    A volume spike is a coarser but concrete, real, testable threshold.
    """
    result = get_news(ticker, days_back=days_back, max_articles=count_threshold + 5)
    if "error" in result:
        return False
    return len(result["articles"]) >= count_threshold
