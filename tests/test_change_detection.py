from unittest.mock import MagicMock, patch

from src.notifications.notifier import Notifier
from src.portfolio.change_detection import check_and_record_portfolio_changes


def _fake_notifier():
    notifier = MagicMock(spec=Notifier)
    notifier.send.return_value = True
    return notifier


@patch("src.portfolio.change_detection.save_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_latest_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_newly_overweight_position_triggers_notification(mock_summary, mock_latest, mock_save):
    mock_summary.return_value = {
        "total_equity": 4000.0,
        "positions": [{"ticker": "AAPL", "quantity": 10, "equity": 3000.0, "percent_of_portfolio": 75.0}],
    }
    # Previously below threshold
    mock_latest.return_value = {"ticker": "AAPL", "percent_of_portfolio": 15.0, "equity": 600.0}
    notifier = _fake_notifier()

    result = check_and_record_portfolio_changes(notifier, threshold_pct=20.0)

    assert result == ["AAPL"]
    notifier.send.assert_called_once()
    title, message = notifier.send.call_args.args[:2]
    assert "AAPL" in message
    mock_save.assert_called_once_with("AAPL", 75.0, 3000.0)


@patch("src.portfolio.change_detection.save_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_latest_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_already_overweight_position_does_not_renotify(mock_summary, mock_latest, mock_save):
    """The core anti-spam case: a position that was ALREADY overweight last
    time should not trigger a fresh notification just for staying that way."""
    mock_summary.return_value = {
        "total_equity": 4000.0,
        "positions": [{"ticker": "AAPL", "quantity": 10, "equity": 3000.0, "percent_of_portfolio": 75.0}],
    }
    mock_latest.return_value = {"ticker": "AAPL", "percent_of_portfolio": 70.0, "equity": 2800.0}
    notifier = _fake_notifier()

    result = check_and_record_portfolio_changes(notifier, threshold_pct=20.0)

    assert result == []
    notifier.send.assert_not_called()


@patch("src.portfolio.change_detection.save_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_latest_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_first_ever_snapshot_above_threshold_counts_as_newly_overweight(mock_summary, mock_latest, mock_save):
    mock_summary.return_value = {
        "total_equity": 1000.0,
        "positions": [{"ticker": "AAPL", "quantity": 10, "equity": 900.0, "percent_of_portfolio": 90.0}],
    }
    mock_latest.return_value = None  # never snapshotted before
    notifier = _fake_notifier()

    result = check_and_record_portfolio_changes(notifier, threshold_pct=20.0)

    assert result == ["AAPL"]
    notifier.send.assert_called_once()


@patch("src.portfolio.change_detection.save_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_latest_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_below_threshold_position_never_notifies(mock_summary, mock_latest, mock_save):
    mock_summary.return_value = {
        "total_equity": 1000.0,
        "positions": [{"ticker": "AAPL", "quantity": 1, "equity": 100.0, "percent_of_portfolio": 10.0}],
    }
    mock_latest.return_value = None
    notifier = _fake_notifier()

    result = check_and_record_portfolio_changes(notifier, threshold_pct=20.0)

    assert result == []
    notifier.send.assert_not_called()


@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_portfolio_error_returns_empty_without_crashing(mock_summary):
    mock_summary.return_value = {"error": "not logged in"}

    result = check_and_record_portfolio_changes(_fake_notifier())

    assert result == []


@patch("src.portfolio.change_detection.save_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_latest_portfolio_snapshot")
@patch("src.portfolio.change_detection.get_portfolio_summary")
def test_works_without_a_notifier(mock_summary, mock_latest, mock_save):
    """No notifier configured (e.g. NTFY_TOPIC unset) shouldn't crash --
    change detection + snapshot recording should still happen."""
    mock_summary.return_value = {
        "total_equity": 1000.0,
        "positions": [{"ticker": "AAPL", "quantity": 10, "equity": 900.0, "percent_of_portfolio": 90.0}],
    }
    mock_latest.return_value = None

    result = check_and_record_portfolio_changes(notifier=None, threshold_pct=20.0)

    assert result == ["AAPL"]
    mock_save.assert_called_once()
