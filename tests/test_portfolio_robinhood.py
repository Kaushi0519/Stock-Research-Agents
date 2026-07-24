from unittest.mock import MagicMock

import pytest

import src.portfolio.robinhood as robinhood_module
from src.portfolio.robinhood import is_position_overweight


@pytest.fixture(autouse=True)
def reset_login_state():
    robinhood_module._logged_in = False
    yield
    robinhood_module._logged_in = False


def _fake_holdings():
    return {
        "AAPL": {"quantity": "10.0", "equity": "3000.00"},
        "MSFT": {"quantity": "5.0", "equity": "1000.00"},
    }


def test_get_portfolio_summary_computes_percentages(monkeypatch):
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_USERNAME", "fake_user")
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_PASSWORD", "fake_pass")
    monkeypatch.setattr(robinhood_module.rh, "login", MagicMock())
    monkeypatch.setattr(
        robinhood_module.rh, "build_holdings", MagicMock(return_value=_fake_holdings())
    )

    summary = robinhood_module.get_portfolio_summary()

    assert summary["total_equity"] == 4000.00
    assert len(summary["positions"]) == 2
    # Sorted by weight descending: AAPL (75%) before MSFT (25%)
    assert summary["positions"][0]["ticker"] == "AAPL"
    assert summary["positions"][0]["percent_of_portfolio"] == 75.0
    assert summary["positions"][1]["ticker"] == "MSFT"
    assert summary["positions"][1]["percent_of_portfolio"] == 25.0


def test_get_portfolio_summary_empty_holdings(monkeypatch):
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_USERNAME", "fake_user")
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_PASSWORD", "fake_pass")
    monkeypatch.setattr(robinhood_module.rh, "login", MagicMock())
    monkeypatch.setattr(robinhood_module.rh, "build_holdings", MagicMock(return_value={}))

    summary = robinhood_module.get_portfolio_summary()

    assert summary == {"total_equity": 0.0, "positions": []}


def test_get_portfolio_summary_handles_api_error(monkeypatch):
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_USERNAME", "fake_user")
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_PASSWORD", "fake_pass")
    monkeypatch.setattr(robinhood_module.rh, "login", MagicMock())
    monkeypatch.setattr(
        robinhood_module.rh,
        "build_holdings",
        MagicMock(side_effect=Exception("Robinhood API changed again")),
    )

    summary = robinhood_module.get_portfolio_summary()

    assert "error" in summary


def test_login_raises_clear_error_without_credentials(monkeypatch):
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_USERNAME", None)
    monkeypatch.setattr(robinhood_module, "ROBINHOOD_PASSWORD", None)

    with pytest.raises(RuntimeError, match="ROBINHOOD_USERNAME"):
        robinhood_module.login()


def test_is_position_overweight_threshold():
    assert is_position_overweight({"percent_of_portfolio": 25.0}, threshold_pct=20.0) is True
    assert is_position_overweight({"percent_of_portfolio": 20.0}, threshold_pct=20.0) is True
    assert is_position_overweight({"percent_of_portfolio": 15.0}, threshold_pct=20.0) is False
