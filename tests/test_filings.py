from unittest.mock import MagicMock, patch

import pytest
import requests

import src.tools.filings as filings_module
from src.tools.filings import get_sec_filings


@pytest.fixture(autouse=True)
def reset_cik_cache():
    filings_module._cik_cache = None
    yield
    filings_module._cik_cache = None


def _fake_ticker_map_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    }
    return mock_response


def _fake_submissions_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "10-Q", "8-K"],
                "filingDate": ["2025-10-31", "2025-08-01", "2025-05-01", "2025-04-15"],
                "accessionNumber": [
                    "0000320193-25-000079",
                    "0000320193-25-000060",
                    "0000320193-25-000040",
                    "0000320193-25-000030",
                ],
                "primaryDocument": [
                    "aapl-20250927.htm",
                    "aapl-20250628.htm",
                    "aapl-20250329.htm",
                    "aapl-8k.htm",
                ],
            }
        }
    }
    return mock_response


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_success(mock_get):
    mock_get.side_effect = [_fake_ticker_map_response(), _fake_submissions_response()]

    result = get_sec_filings("AAPL", limit=5)

    assert result["ticker"] == "AAPL"
    assert len(result["filings"]) == 4
    first = result["filings"][0]
    assert first["form_type"] == "10-K"
    assert first["filing_date"] == "2025-10-31"
    assert first["accession_number"] == "0000320193-25-000079"
    assert first["document_url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
    )


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_filters_by_type(mock_get):
    mock_get.side_effect = [_fake_ticker_map_response(), _fake_submissions_response()]

    result = get_sec_filings("AAPL", filing_type="10-Q")

    assert len(result["filings"]) == 2
    assert all(f["form_type"] == "10-Q" for f in result["filings"])


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_respects_limit(mock_get):
    mock_get.side_effect = [_fake_ticker_map_response(), _fake_submissions_response()]

    result = get_sec_filings("AAPL", limit=1)

    assert len(result["filings"]) == 1


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_unknown_ticker(mock_get):
    mock_get.return_value = _fake_ticker_map_response()

    result = get_sec_filings("NOTAREALTICKER")

    assert "error" in result
    assert "NOTAREALTICKER" in result["error"]


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_cik_lookup_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no internet")

    result = get_sec_filings("AAPL")

    assert "error" in result
    assert "no internet" in result["error"]


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_submissions_network_error(mock_get):
    ticker_map_response = _fake_ticker_map_response()
    submissions_error_response = MagicMock()
    submissions_error_response.raise_for_status.side_effect = requests.HTTPError("404")

    mock_get.side_effect = [ticker_map_response, submissions_error_response]

    result = get_sec_filings("AAPL")

    assert "error" in result


@patch("src.tools.filings.requests.get")
def test_get_sec_filings_caches_cik_map_across_calls(mock_get):
    mock_get.side_effect = [
        _fake_ticker_map_response(),
        _fake_submissions_response(),
        _fake_submissions_response(),
    ]

    get_sec_filings("AAPL")
    get_sec_filings("AAPL")

    # Ticker map should only be fetched once (3 calls total: 1 map + 2 submissions)
    assert mock_get.call_count == 3
