from unittest.mock import MagicMock, patch

from src.scheduler.run import run_watchlist_check


@patch("src.scheduler.run.clear_credit_alert")
@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.save_report")
@patch("src.scheduler.run.critique_report")
@patch("src.scheduler.run.analyze_ticker")
@patch("src.scheduler.run.is_significant_news_volume")
@patch("src.scheduler.run.is_significant_price_move")
@patch("src.scheduler.run.get_watchlist")
def test_only_significant_tickers_get_analyzed(
    mock_watchlist, mock_price_sig, mock_news_sig, mock_analyze, mock_critique, mock_save, mock_portfolio, mock_clear
):
    mock_watchlist.return_value = ["AAPL", "MSFT", "GOOGL"]
    # AAPL: price move significant. MSFT: news volume significant. GOOGL: neither.
    mock_price_sig.side_effect = lambda ticker, threshold: ticker == "AAPL"
    mock_news_sig.side_effect = lambda ticker, threshold: ticker == "MSFT"
    mock_analyze.side_effect = lambda ticker: {"ticker": ticker, "claims": [], "flagged_claims": []}
    mock_critique.side_effect = lambda report: report
    mock_portfolio.return_value = []

    result = run_watchlist_check()

    assert set(result["analyzed"]) == {"AAPL", "MSFT"}
    assert result["skipped"] == ["GOOGL"]
    assert mock_analyze.call_count == 2


@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.save_report")
@patch("src.scheduler.run.critique_report")
@patch("src.scheduler.run.analyze_ticker")
@patch("src.scheduler.run.is_significant_news_volume")
@patch("src.scheduler.run.is_significant_price_move")
@patch("src.scheduler.run.get_watchlist")
def test_no_significant_tickers_analyzes_nothing(
    mock_watchlist, mock_price_sig, mock_news_sig, mock_analyze, mock_critique, mock_save, mock_portfolio
):
    mock_watchlist.return_value = ["AAPL", "MSFT"]
    mock_price_sig.return_value = False
    mock_news_sig.return_value = False
    mock_portfolio.return_value = []

    result = run_watchlist_check()

    assert result["analyzed"] == []
    assert result["skipped"] == ["AAPL", "MSFT"]
    mock_analyze.assert_not_called()


@patch("src.scheduler.run.clear_credit_alert")
@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.save_report")
@patch("src.scheduler.run.critique_report")
@patch("src.scheduler.run.analyze_ticker")
@patch("src.scheduler.run.is_significant_news_volume")
@patch("src.scheduler.run.is_significant_price_move")
@patch("src.scheduler.run.get_watchlist")
def test_one_ticker_failing_does_not_crash_the_run(
    mock_watchlist, mock_price_sig, mock_news_sig, mock_analyze, mock_critique, mock_save, mock_portfolio, mock_clear
):
    """Resilience for an unattended process: a single ticker erroring out
    (network blip, API hiccup) must not stop the rest of the watchlist from
    being checked."""
    mock_watchlist.return_value = ["AAPL", "MSFT"]
    mock_price_sig.return_value = True
    mock_news_sig.return_value = False
    mock_analyze.side_effect = [Exception("boom"), {"ticker": "MSFT", "claims": [], "flagged_claims": []}]
    mock_critique.side_effect = lambda report: report
    mock_portfolio.return_value = []

    result = run_watchlist_check()

    assert result["analyzed"] == ["MSFT"]
    assert result["skipped"] == ["AAPL"]


@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.get_watchlist")
def test_portfolio_change_detection_always_runs(mock_watchlist, mock_portfolio):
    mock_watchlist.return_value = []
    mock_portfolio.return_value = ["AAPL"]

    result = run_watchlist_check()

    assert result["portfolio_newly_overweight"] == ["AAPL"]
    mock_portfolio.assert_called_once()


@patch("src.scheduler.run.NtfyNotifier")
@patch("src.scheduler.run.NTFY_TOPIC", None)
@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.get_watchlist")
def test_works_without_ntfy_configured(mock_watchlist, mock_portfolio, mock_notifier_cls):
    mock_watchlist.return_value = []
    mock_portfolio.return_value = []

    run_watchlist_check()

    mock_notifier_cls.assert_not_called()


@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.alert_credit_exhausted")
@patch("src.scheduler.run.is_insufficient_credit_error")
@patch("src.scheduler.run.analyze_ticker")
@patch("src.scheduler.run.is_significant_news_volume")
@patch("src.scheduler.run.is_significant_price_move")
@patch("src.scheduler.run.get_watchlist")
def test_credit_exhaustion_alerts_once_and_skips_remaining_tickers(
    mock_watchlist, mock_price_sig, mock_news_sig, mock_analyze, mock_is_credit_error, mock_alert, mock_portfolio
):
    """A credit-exhaustion failure on the first significant ticker must not
    burn through the rest of the watchlist attempting calls that would fail
    identically -- and must alert exactly once, not once per ticker."""
    mock_watchlist.return_value = ["AAPL", "MSFT", "GOOGL"]
    mock_price_sig.return_value = True
    mock_news_sig.return_value = False
    mock_analyze.side_effect = Exception("credit balance too low")
    mock_is_credit_error.return_value = True
    mock_portfolio.return_value = []

    result = run_watchlist_check()

    assert result["analyzed"] == []
    assert set(result["skipped"]) == {"AAPL", "MSFT", "GOOGL"}
    mock_alert.assert_called_once()
    # Only the first ticker's analyze_ticker should actually have been tried
    assert mock_analyze.call_count == 1


@patch("src.scheduler.run.clear_credit_alert")
@patch("src.scheduler.run.check_and_record_portfolio_changes")
@patch("src.scheduler.run.save_report")
@patch("src.scheduler.run.critique_report")
@patch("src.scheduler.run.analyze_ticker")
@patch("src.scheduler.run.is_significant_news_volume")
@patch("src.scheduler.run.is_significant_price_move")
@patch("src.scheduler.run.get_watchlist")
def test_successful_analysis_clears_credit_alert(
    mock_watchlist, mock_price_sig, mock_news_sig, mock_analyze, mock_critique, mock_save, mock_portfolio, mock_clear
):
    mock_watchlist.return_value = ["AAPL"]
    mock_price_sig.return_value = True
    mock_news_sig.return_value = False
    mock_analyze.return_value = {"ticker": "AAPL", "claims": [], "flagged_claims": []}
    mock_critique.side_effect = lambda report: report
    mock_portfolio.return_value = []

    run_watchlist_check()

    mock_clear.assert_called_once()
