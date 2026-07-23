import pandas as pd
from unittest.mock import patch

from src.tools.price_data import get_price_history


def _fake_history():
    return pd.DataFrame({
        "Close": [100.0, 105.0, 110.0],
        "High": [101.0, 106.0, 111.0],
        "Low": [99.0, 104.0, 109.0],
        "Volume": [1000, 2000, 3000],
    })


@patch("src.tools.price_data.yf.Ticker")
def test_get_price_history_success(mock_ticker):
    mock_ticker.return_value.history.return_value = _fake_history()

    result = get_price_history("FAKE", period="1mo")

    assert result["ticker"] == "FAKE"
    assert result["period"] == "1mo"
    assert result["current_price"] == 110.0
    assert result["period_change_pct"] == 10.0  # (110 - 100) / 100 * 100
    assert result["period_high"] == 111.0
    assert result["period_low"] == 99.0
    assert result["avg_volume"] == 2000
    assert result["trading_days"] == 3


@patch("src.tools.price_data.yf.Ticker")
def test_get_price_history_empty(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()

    result = get_price_history("BADTICKER")

    assert "error" in result
    assert "BADTICKER" in result["error"]


@patch("src.tools.price_data.yf.Ticker")
def test_get_price_history_exception(mock_ticker):
    mock_ticker.return_value.history.side_effect = Exception("network down")

    result = get_price_history("AAPL")

    assert "error" in result
    assert "network down" in result["error"]
