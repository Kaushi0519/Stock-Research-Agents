import logging

import anthropic

from src.notifications.notifier import Notifier
from src.storage.db import get_state_flag, set_state_flag

logger = logging.getLogger(__name__)

CREDIT_ALERT_STATE_KEY = "anthropic_credit_alert_sent"


def is_insufficient_credit_error(exc: Exception) -> bool:
    """True if `exc` looks like Anthropic API billing exhaustion (a 400
    response with a "credit balance" message), as opposed to a different
    kind of API failure -- rate limiting, a server error, a malformed
    request -- which should be handled/logged differently, not reported to
    the user as "you're out of money" when that isn't actually what happened.
    """
    if not isinstance(exc, anthropic.APIStatusError):
        return False

    message = str(getattr(exc, "message", None) or str(exc)).lower()
    return "credit balance" in message


def alert_credit_exhausted(notifier: Notifier | None) -> None:
    """Sends the "out of API credit" alert at most once per outage -- an
    unattended process stuck failing repeatedly would otherwise re-send
    this every time, which is exactly the false-alarm spam this project's
    notification design has avoided everywhere else. Automatically re-arms
    the next time `clear_credit_alert()` is called after a successful
    analysis, so a later, separate outage still gets its own alert.
    """
    if get_state_flag(CREDIT_ALERT_STATE_KEY):
        return

    logger.error("Anthropic API credit balance is too low")
    if notifier:
        notifier.send(
            "Anthropic API credit balance too low",
            "Analysis is paused until you add credits at console.anthropic.com.",
            priority="urgent",
        )
    set_state_flag(CREDIT_ALERT_STATE_KEY, True)


def clear_credit_alert() -> None:
    """Re-arms the alert after a successful analysis, so a future outage
    (e.g. after topping up and later running out again) sends its own
    fresh notification instead of staying silently suppressed forever."""
    if get_state_flag(CREDIT_ALERT_STATE_KEY):
        set_state_flag(CREDIT_ALERT_STATE_KEY, False)
