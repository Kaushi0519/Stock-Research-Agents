from src.config import DASHBOARD_BASE_URL
from src.notifications.notifier import Notifier
from src.notifications.significance import (
    DEFAULT_NEWS_VOLUME_THRESHOLD,
    DEFAULT_PRICE_MOVE_THRESHOLD_PCT,
    get_latest_daily_change_pct,
    is_significant_news_volume,
    is_significant_price_move,
)


def _report_url(report_id: int = None) -> str:
    """Builds a tappable link back to a report, or None if either the
    report id or DASHBOARD_BASE_URL isn't available -- ntfy just omits the
    click action in that case rather than sending a broken link."""
    if not DASHBOARD_BASE_URL or report_id is None:
        return None
    return f"{DASHBOARD_BASE_URL.rstrip('/')}/reports/{report_id}"


def notify_report_ready(notifier: Notifier, report: dict, report_id: int = None) -> bool:
    """Always fires when a new report finishes -- this isn't threshold-gated,
    since "a report you asked for is ready" is inherently something you want
    to know about, not noise to filter."""
    ticker = report["ticker"]
    claim_count = len(report["claims"])
    flagged_count = len(report.get("flagged_claims", []))

    title = f"Research report ready: {ticker}"
    message = f"{claim_count} claims generated."
    if flagged_count:
        message += f" {flagged_count} flagged as unsupported -- review before trusting."

    return notifier.send(title, message, priority="default", click_url=_report_url(report_id))


def notify_flagged_claims(notifier: Notifier, report: dict, report_id: int = None) -> bool:
    """Only fires if the Critic Agent actually flagged something -- a clean
    report (no flags) sends no notification, since a second "everything's
    fine" ping after notify_report_ready would just be noise."""
    flagged = report.get("flagged_claims", [])
    if not flagged:
        return False

    ticker = report["ticker"]
    title = f"Unsupported claims flagged: {ticker}"
    lines = [f"- {f['claim_text']}" for f in flagged[:3]]
    if len(flagged) > 3:
        lines.append(f"...and {len(flagged) - 3} more")
    message = "\n".join(lines)

    return notifier.send(title, message, priority="high", click_url=_report_url(report_id))


def notify_significant_price_move(
    notifier: Notifier, ticker: str, threshold_pct: float = DEFAULT_PRICE_MOVE_THRESHOLD_PCT
) -> bool:
    if not is_significant_price_move(ticker, threshold_pct):
        return False

    change_pct = get_latest_daily_change_pct(ticker)
    direction = "up" if change_pct > 0 else "down"

    title = f"Significant price move: {ticker}"
    message = f"{ticker} is {direction} {abs(change_pct):.1f}% today (threshold: {threshold_pct}%)."

    return notifier.send(title, message, priority="high")


def notify_significant_news_volume(
    notifier: Notifier, ticker: str, count_threshold: int = DEFAULT_NEWS_VOLUME_THRESHOLD
) -> bool:
    if not is_significant_news_volume(ticker, count_threshold):
        return False

    title = f"News activity spike: {ticker}"
    message = f"{count_threshold}+ new articles about {ticker} in the last day."

    return notifier.send(title, message, priority="default")
