import logging

from src.agents.analysis_agent import analyze_ticker
from src.agents.critic_agent import critique_report
from src.agents.errors import alert_credit_exhausted, clear_credit_alert, is_insufficient_credit_error
from src.config import NTFY_TOPIC
from src.notifications.events import (
    notify_flagged_claims,
    notify_report_ready,
    notify_significant_news_volume,
    notify_significant_price_move,
)
from src.notifications.notifier import NtfyNotifier
from src.notifications.significance import (
    DEFAULT_NEWS_VOLUME_THRESHOLD,
    DEFAULT_PRICE_MOVE_THRESHOLD_PCT,
    is_significant_news_volume,
    is_significant_price_move,
)
from src.portfolio.change_detection import check_and_record_portfolio_changes
from src.portfolio.robinhood import DEFAULT_OVERWEIGHT_THRESHOLD_PCT
from src.storage.db import get_watchlist, save_report

logger = logging.getLogger(__name__)


def _get_notifier() -> NtfyNotifier | None:
    if not NTFY_TOPIC:
        return None
    return NtfyNotifier(topic=NTFY_TOPIC)


def run_watchlist_check(
    price_threshold_pct: float = DEFAULT_PRICE_MOVE_THRESHOLD_PCT,
    news_threshold: int = DEFAULT_NEWS_VOLUME_THRESHOLD,
    overweight_threshold_pct: float = DEFAULT_OVERWEIGHT_THRESHOLD_PCT,
) -> dict:
    """One scheduled pass over the watchlist.

    A full analysis (the expensive path -- LLM calls, ingestion) only runs
    for a ticker if it crossed a significance threshold this tick, not on
    every tick regardless -- "monitors a watchlist" in the brief means
    watching for something worth reporting, not re-analyzing everything on
    a timer regardless of whether anything happened.

    One ticker failing for an ordinary reason (network blip, API hiccup) is
    logged and skipped, not allowed to crash the rest of the run. But if the
    Anthropic API is rejecting calls for insufficient credit specifically,
    every remaining ticker this tick would fail identically -- so that case
    alerts once and stops the run early instead of burning through the rest
    of the watchlist on calls that can't succeed.
    """
    notifier = _get_notifier()
    watchlist = get_watchlist()

    analyzed = []
    skipped = []

    for ticker in watchlist:
        price_significant = is_significant_price_move(ticker, price_threshold_pct)
        news_significant = is_significant_news_volume(ticker, news_threshold)

        if price_significant and notifier:
            notify_significant_price_move(notifier, ticker, price_threshold_pct)
        if news_significant and notifier:
            notify_significant_news_volume(notifier, ticker, news_threshold)

        if not (price_significant or news_significant):
            skipped.append(ticker)
            continue

        try:
            report = analyze_ticker(ticker)
            report = critique_report(report)
            report_id = save_report(report)
            if notifier:
                notify_report_ready(notifier, report, report_id)
                notify_flagged_claims(notifier, report, report_id)
            analyzed.append(ticker)
            clear_credit_alert()
        except Exception as e:
            if is_insufficient_credit_error(e):
                alert_credit_exhausted(notifier)
                remaining = watchlist[watchlist.index(ticker):]
                skipped.extend(remaining)
                break

            logger.exception("Failed to analyze %s during scheduled run", ticker)
            skipped.append(ticker)

    newly_overweight = check_and_record_portfolio_changes(notifier, overweight_threshold_pct)

    return {
        "analyzed": analyzed,
        "skipped": skipped,
        "portfolio_newly_overweight": newly_overweight,
    }
