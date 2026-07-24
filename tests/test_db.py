from src.storage import db


def _fresh_db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(db_path=path)
    return path


def test_save_and_get_report_strips_retrieved_chunks(tmp_path):
    path = _fresh_db_path(tmp_path)
    report = {
        "ticker": "AAPL",
        "claims": [{"section": "price_performance", "text": "x", "source_ids": []}],
        "flagged_claims": [],
        "_retrieved_chunks": {"news:1": {"text": "should not be persisted"}},
    }

    report_id = db.save_report(report, db_path=path)
    fetched = db.get_report(report_id, db_path=path)

    assert fetched["ticker"] == "AAPL"
    assert len(fetched["claims"]) == 1
    assert "_retrieved_chunks" not in fetched
    assert fetched["id"] == report_id
    assert "created_at" in fetched


def test_get_report_returns_none_for_missing_id(tmp_path):
    path = _fresh_db_path(tmp_path)
    assert db.get_report(9999, db_path=path) is None


def test_get_reports_lists_summaries_newest_first(tmp_path):
    path = _fresh_db_path(tmp_path)
    db.save_report({"ticker": "AAPL", "claims": [], "flagged_claims": []}, db_path=path)
    db.save_report(
        {"ticker": "MSFT", "claims": [{"section": "x", "text": "y", "source_ids": []}], "flagged_claims": [{}]},
        db_path=path,
    )

    reports = db.get_reports(db_path=path)

    assert len(reports) == 2
    tickers = {r["ticker"] for r in reports}
    assert tickers == {"AAPL", "MSFT"}
    msft = next(r for r in reports if r["ticker"] == "MSFT")
    assert msft["claim_count"] == 1
    assert msft["flagged_count"] == 1


def test_watchlist_add_remove_and_list(tmp_path):
    path = _fresh_db_path(tmp_path)

    db.add_to_watchlist("aapl", db_path=path)
    db.add_to_watchlist("MSFT", db_path=path)

    assert db.get_watchlist(db_path=path) == ["AAPL", "MSFT"]

    db.remove_from_watchlist("aapl", db_path=path)
    assert db.get_watchlist(db_path=path) == ["MSFT"]


def test_watchlist_add_is_idempotent(tmp_path):
    path = _fresh_db_path(tmp_path)

    db.add_to_watchlist("AAPL", db_path=path)
    db.add_to_watchlist("AAPL", db_path=path)

    assert db.get_watchlist(db_path=path) == ["AAPL"]


def test_portfolio_snapshot_save_and_get_latest(tmp_path):
    path = _fresh_db_path(tmp_path)

    assert db.get_latest_portfolio_snapshot("AAPL", db_path=path) is None

    db.save_portfolio_snapshot("aapl", 10.0, 1000.0, db_path=path)
    latest = db.get_latest_portfolio_snapshot("AAPL", db_path=path)

    assert latest["ticker"] == "AAPL"
    assert latest["percent_of_portfolio"] == 10.0
    assert latest["equity"] == 1000.0

    db.save_portfolio_snapshot("AAPL", 25.0, 2500.0, db_path=path)
    newest = db.get_latest_portfolio_snapshot("AAPL", db_path=path)

    assert newest["percent_of_portfolio"] == 25.0
