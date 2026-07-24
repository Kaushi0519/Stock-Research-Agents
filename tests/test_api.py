from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import src.api.main as main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def no_notifier(monkeypatch):
    """None of these tests should attempt a real ntfy.sh call."""
    monkeypatch.setattr(main, "NTFY_TOPIC", None)


def test_dashboard_renders(monkeypatch):
    monkeypatch.setattr(main.db, "get_reports", lambda: [
        {"id": 1, "ticker": "AAPL", "created_at": "2026-07-23T10:00:00+00:00", "claim_count": 5, "flagged_count": 1},
    ])
    monkeypatch.setattr(main.db, "get_watchlist", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(main, "get_portfolio_summary", lambda: {"total_equity": 0.0, "positions": []})

    response = client.get("/")

    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "MSFT" in response.text
    assert "Stock Research Agents" in response.text


def test_report_detail_page_found(monkeypatch):
    fake_report = {
        "id": 1,
        "ticker": "AAPL",
        "created_at": "2026-07-23T10:00:00+00:00",
        "claims": [{"section": "price_performance", "text": "Up 5%", "source_ids": []}],
        "flagged_claims": [],
    }
    monkeypatch.setattr(main.db, "get_report", lambda report_id: fake_report if report_id == 1 else None)

    response = client.get("/reports/1")

    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "Up 5%" in response.text


def test_report_detail_page_not_found(monkeypatch):
    monkeypatch.setattr(main.db, "get_report", lambda report_id: None)

    response = client.get("/reports/999")

    assert response.status_code == 404


def test_analyze_page_redirects_to_report(monkeypatch):
    monkeypatch.setattr(main, "analyze_ticker", lambda ticker: {"ticker": ticker, "claims": [], "flagged_claims": []})
    monkeypatch.setattr(main, "critique_report", lambda report: report)
    monkeypatch.setattr(main.db, "save_report", lambda report: 42)

    response = client.post("/analyze/AAPL", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/reports/42"


def test_api_list_reports(monkeypatch):
    monkeypatch.setattr(main.db, "get_reports", lambda: [{"id": 1, "ticker": "AAPL"}])

    response = client.get("/api/reports")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "ticker": "AAPL"}]


def test_api_get_report_404(monkeypatch):
    monkeypatch.setattr(main.db, "get_report", lambda report_id: None)

    response = client.get("/api/reports/999")

    assert response.status_code == 404


def test_api_create_report_runs_pipeline_and_notifies(monkeypatch):
    fake_report = {"ticker": "AAPL", "claims": [], "flagged_claims": []}
    monkeypatch.setattr(main, "analyze_ticker", lambda ticker: fake_report)
    monkeypatch.setattr(main, "critique_report", lambda report: report)
    monkeypatch.setattr(main.db, "save_report", lambda report: 7)
    monkeypatch.setattr(main.db, "get_report", lambda report_id: {**fake_report, "id": 7})

    mock_notify_ready = MagicMock()
    mock_notify_flagged = MagicMock()
    monkeypatch.setattr(main, "notify_report_ready", mock_notify_ready)
    monkeypatch.setattr(main, "notify_flagged_claims", mock_notify_flagged)
    monkeypatch.setattr(main, "NTFY_TOPIC", "fake-topic")

    response = client.post("/api/reports/aapl")

    assert response.status_code == 200
    assert response.json()["id"] == 7
    mock_notify_ready.assert_called_once()
    mock_notify_flagged.assert_called_once()


def test_api_watchlist_crud(monkeypatch):
    added = []
    removed = []
    monkeypatch.setattr(main.db, "add_to_watchlist", lambda ticker: added.append(ticker))
    monkeypatch.setattr(main.db, "remove_from_watchlist", lambda ticker: removed.append(ticker))
    monkeypatch.setattr(main.db, "get_watchlist", lambda: ["AAPL"])

    assert client.get("/api/watchlist").json() == ["AAPL"]

    add_resp = client.post("/api/watchlist/aapl")
    assert add_resp.status_code == 200
    assert add_resp.json() == {"status": "added", "ticker": "AAPL"}
    assert added == ["aapl"]

    del_resp = client.delete("/api/watchlist/aapl")
    assert del_resp.status_code == 200
    assert removed == ["aapl"]


def test_api_get_portfolio(monkeypatch):
    monkeypatch.setattr(main, "get_portfolio_summary", lambda: {"total_equity": 500.0, "positions": []})

    response = client.get("/api/portfolio")

    assert response.status_code == 200
    assert response.json()["total_equity"] == 500.0


def test_api_check_portfolio(monkeypatch):
    monkeypatch.setattr(main, "check_and_record_portfolio_changes", lambda notifier: ["AAPL"])

    response = client.post("/api/portfolio/check")

    assert response.status_code == 200
    assert response.json() == {"newly_overweight": ["AAPL"]}
