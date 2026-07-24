from unittest.mock import MagicMock, patch

from src.notifications.events import (
    notify_flagged_claims,
    notify_report_ready,
    notify_significant_news_volume,
    notify_significant_price_move,
)
from src.notifications.notifier import Notifier


def _fake_notifier() -> MagicMock:
    notifier = MagicMock(spec=Notifier)
    notifier.send.return_value = True
    return notifier


def test_notify_report_ready_always_fires():
    notifier = _fake_notifier()
    report = {"ticker": "AAPL", "claims": [{"text": "x", "source_ids": []}], "flagged_claims": []}

    result = notify_report_ready(notifier, report)

    assert result is True
    notifier.send.assert_called_once()
    title, message = notifier.send.call_args.args[:2]
    assert "AAPL" in title
    assert "1 claims generated" in message
    assert "flagged" not in message


def test_notify_report_ready_mentions_flagged_count():
    notifier = _fake_notifier()
    report = {
        "ticker": "AAPL",
        "claims": [{"text": "x", "source_ids": []}],
        "flagged_claims": [{"claim_index": 0, "claim_text": "x", "explanation": "y"}],
    }

    notify_report_ready(notifier, report)

    _, message = notifier.send.call_args.args[:2]
    assert "1 flagged as unsupported" in message


def test_notify_flagged_claims_does_not_fire_when_nothing_flagged():
    """The core anti-spam case: a clean report should NOT trigger a second
    notification on top of notify_report_ready."""
    notifier = _fake_notifier()
    report = {"ticker": "AAPL", "flagged_claims": []}

    result = notify_flagged_claims(notifier, report)

    assert result is False
    notifier.send.assert_not_called()


def test_notify_flagged_claims_fires_and_truncates_to_three():
    notifier = _fake_notifier()
    report = {
        "ticker": "AAPL",
        "flagged_claims": [
            {"claim_index": i, "claim_text": f"claim {i}", "explanation": "y"} for i in range(5)
        ],
    }

    result = notify_flagged_claims(notifier, report)

    assert result is True
    _, message = notifier.send.call_args.args[:2]
    assert "claim 0" in message
    assert "claim 2" in message
    assert "claim 3" not in message
    assert "and 2 more" in message


@patch("src.notifications.events.is_significant_price_move")
@patch("src.notifications.events.get_latest_daily_change_pct")
def test_notify_significant_price_move_does_not_fire_below_threshold(mock_change, mock_is_sig):
    mock_is_sig.return_value = False
    notifier = _fake_notifier()

    result = notify_significant_price_move(notifier, "AAPL", threshold_pct=5.0)

    assert result is False
    notifier.send.assert_not_called()
    mock_change.assert_not_called()


@patch("src.notifications.events.is_significant_price_move")
@patch("src.notifications.events.get_latest_daily_change_pct")
def test_notify_significant_price_move_fires_above_threshold(mock_change, mock_is_sig):
    mock_is_sig.return_value = True
    mock_change.return_value = -7.5
    notifier = _fake_notifier()

    result = notify_significant_price_move(notifier, "AAPL", threshold_pct=5.0)

    assert result is True
    title, message = notifier.send.call_args.args[:2]
    assert "AAPL" in title
    assert "down 7.5%" in message


@patch("src.notifications.events.is_significant_news_volume")
def test_notify_significant_news_volume_does_not_fire_below_threshold(mock_is_sig):
    mock_is_sig.return_value = False
    notifier = _fake_notifier()

    result = notify_significant_news_volume(notifier, "AAPL", count_threshold=3)

    assert result is False
    notifier.send.assert_not_called()


@patch("src.notifications.events.is_significant_news_volume")
def test_notify_significant_news_volume_fires_above_threshold(mock_is_sig):
    mock_is_sig.return_value = True
    notifier = _fake_notifier()

    result = notify_significant_news_volume(notifier, "AAPL", count_threshold=3)

    assert result is True
    notifier.send.assert_called_once()
