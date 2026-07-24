from unittest.mock import patch

import pandas as pd
import pytest

from src.notifications.significance import (
    get_latest_daily_change_pct,
    is_significant_news_volume,
    is_significant_price_move,
)


def _fake_history(closes: list[float]):
    return pd.DataFrame({"Close": closes})


@patch("src.notifications.significance.yf.Ticker")
def test_get_latest_daily_change_pct_computes_last_two_closes(mock_ticker):
    mock_ticker.return_value.history.return_value = _fake_history([100.0, 105.0, 110.0])

    change = get_latest_daily_change_pct("FAKE")

    assert change == pytest.approx((110.0 - 105.0) / 105.0 * 100)


@patch("src.notifications.significance.yf.Ticker")
def test_get_latest_daily_change_pct_insufficient_history_returns_none(mock_ticker):
    mock_ticker.return_value.history.return_value = _fake_history([100.0])

    assert get_latest_daily_change_pct("FAKE") is None


@patch("src.notifications.significance.yf.Ticker")
def test_get_latest_daily_change_pct_empty_history_returns_none(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()

    assert get_latest_daily_change_pct("FAKE") is None


@patch("src.notifications.significance.yf.Ticker")
def test_get_latest_daily_change_pct_network_error_returns_none(mock_ticker):
    mock_ticker.side_effect = Exception("network down")

    assert get_latest_daily_change_pct("FAKE") is None


# --- is_significant_price_move: the "no false-alarm spam" boundary tests ---

@patch("src.notifications.significance.get_latest_daily_change_pct")
def test_is_significant_price_move_below_threshold_is_not_significant(mock_change):
    mock_change.return_value = 2.0
    assert is_significant_price_move("FAKE", threshold_pct=5.0) is False


@patch("src.notifications.significance.get_latest_daily_change_pct")
def test_is_significant_price_move_exactly_at_threshold_is_significant(mock_change):
    mock_change.return_value = 5.0
    assert is_significant_price_move("FAKE", threshold_pct=5.0) is True


@patch("src.notifications.significance.get_latest_daily_change_pct")
def test_is_significant_price_move_above_threshold_is_significant(mock_change):
    mock_change.return_value = 7.3
    assert is_significant_price_move("FAKE", threshold_pct=5.0) is True


@patch("src.notifications.significance.get_latest_daily_change_pct")
def test_is_significant_price_move_big_drop_counts_as_significant(mock_change):
    """A large negative move must trigger just as much as a gain -- using
    the raw signed change instead of abs() would silently miss crashes."""
    mock_change.return_value = -8.0
    assert is_significant_price_move("FAKE", threshold_pct=5.0) is True


@patch("src.notifications.significance.get_latest_daily_change_pct")
def test_is_significant_price_move_no_data_is_not_significant(mock_change):
    """Missing data must fail closed (no notification), not fail open."""
    mock_change.return_value = None
    assert is_significant_price_move("FAKE", threshold_pct=5.0) is False


# --- is_significant_news_volume: same "no false-alarm spam" boundary tests ---

def _fake_news_result(article_count: int) -> dict:
    return {
        "ticker": "FAKE",
        "days_back": 1,
        "articles": [{"headline": f"Article {i}"} for i in range(article_count)],
    }


@patch("src.notifications.significance.get_news")
def test_is_significant_news_volume_below_threshold(mock_get_news):
    mock_get_news.return_value = _fake_news_result(2)
    assert is_significant_news_volume("FAKE", count_threshold=3) is False


@patch("src.notifications.significance.get_news")
def test_is_significant_news_volume_at_threshold(mock_get_news):
    mock_get_news.return_value = _fake_news_result(3)
    assert is_significant_news_volume("FAKE", count_threshold=3) is True


@patch("src.notifications.significance.get_news")
def test_is_significant_news_volume_above_threshold(mock_get_news):
    mock_get_news.return_value = _fake_news_result(10)
    assert is_significant_news_volume("FAKE", count_threshold=3) is True


@patch("src.notifications.significance.get_news")
def test_is_significant_news_volume_error_result_fails_closed(mock_get_news):
    mock_get_news.return_value = {"error": "Finnhub is down"}
    assert is_significant_news_volume("FAKE", count_threshold=3) is False
