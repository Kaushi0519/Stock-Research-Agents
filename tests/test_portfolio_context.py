from unittest.mock import patch

from src.portfolio.context import get_portfolio_context_for_ticker


@patch("src.portfolio.context.get_portfolio_summary")
def test_returns_none_when_ticker_not_held(mock_summary):
    mock_summary.return_value = {
        "total_equity": 1000.0,
        "positions": [{"ticker": "MSFT", "quantity": 5.0, "equity": 1000.0, "percent_of_portfolio": 100.0}],
    }

    assert get_portfolio_context_for_ticker("AAPL") is None


@patch("src.portfolio.context.get_portfolio_summary")
def test_returns_none_on_summary_error(mock_summary):
    mock_summary.return_value = {"error": "not logged in"}

    assert get_portfolio_context_for_ticker("AAPL") is None


@patch("src.portfolio.context.get_portfolio_summary")
def test_returns_none_when_summary_raises(mock_summary):
    mock_summary.side_effect = Exception("Robinhood is down")

    assert get_portfolio_context_for_ticker("AAPL") is None


@patch("src.portfolio.context.get_portfolio_summary")
def test_describes_held_position_below_threshold(mock_summary):
    mock_summary.return_value = {
        "total_equity": 4000.0,
        "positions": [
            {"ticker": "AAPL", "quantity": 10.0, "equity": 1200.0, "percent_of_portfolio": 15.0},
        ],
    }

    note = get_portfolio_context_for_ticker("AAPL", threshold_pct=20.0)

    assert "10 shares of AAPL" in note
    assert "$1,200.00" in note
    assert "15.0% of their portfolio" in note
    assert "overweight" not in note


@patch("src.portfolio.context.get_portfolio_summary")
def test_flags_overweight_position(mock_summary):
    mock_summary.return_value = {
        "total_equity": 4000.0,
        "positions": [
            {"ticker": "AAPL", "quantity": 10.0, "equity": 3000.0, "percent_of_portfolio": 75.0},
        ],
    }

    note = get_portfolio_context_for_ticker("AAPL", threshold_pct=20.0)

    assert "overweight position" in note
    assert "75.0%" in note


@patch("src.portfolio.context.get_portfolio_summary")
def test_ticker_lookup_is_case_insensitive(mock_summary):
    mock_summary.return_value = {
        "total_equity": 1000.0,
        "positions": [{"ticker": "AAPL", "quantity": 1.0, "equity": 100.0, "percent_of_portfolio": 10.0}],
    }

    note = get_portfolio_context_for_ticker("aapl", threshold_pct=20.0)

    assert note is not None
