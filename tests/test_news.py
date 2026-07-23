from datetime import datetime
from unittest.mock import MagicMock, patch

import requests

from src.tools.news import get_news


def _fake_response(json_data, status_ok=True):
    mock_response = MagicMock()
    mock_response.json.return_value = json_data
    if not status_ok:
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Client Error")
    return mock_response


@patch("src.tools.news.requests.get")
def test_get_news_success(mock_get):
    fake_articles = [{
        "headline": "Fake headline",
        "summary": "Fake summary",
        "source": "Yahoo",
        "url": "https://example.com/article",
        "datetime": 1721606400,
    }]
    mock_get.return_value = _fake_response(fake_articles)

    result = get_news("AAPL", days_back=7)

    assert result["ticker"] == "AAPL"
    assert result["days_back"] == 7
    assert len(result["articles"]) == 1

    article = result["articles"][0]
    assert article["headline"] == "Fake headline"
    assert article["summary"] == "Fake summary"
    assert article["source"] == "Yahoo"
    assert article["url"] == "https://example.com/article"
    assert article["published"] == datetime.fromtimestamp(1721606400).isoformat()


@patch("src.tools.news.requests.get")
def test_get_news_trims_to_max_articles(mock_get):
    fake_articles = [
        {"headline": f"Headline {i}", "summary": "", "source": "Yahoo", "url": "", "datetime": 1721606400}
        for i in range(15)
    ]
    mock_get.return_value = _fake_response(fake_articles)

    result = get_news("AAPL", max_articles=10)

    assert len(result["articles"]) == 10


@patch("src.tools.news.requests.get")
def test_get_news_empty(mock_get):
    mock_get.return_value = _fake_response([])

    result = get_news("AAPL")

    assert result["articles"] == []


@patch("src.tools.news.requests.get")
def test_get_news_http_error(mock_get):
    mock_get.return_value = _fake_response([], status_ok=False)

    result = get_news("AAPL")

    assert "error" in result


@patch("src.tools.news.requests.get")
def test_get_news_connection_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no internet")

    result = get_news("AAPL")

    assert "error" in result
    assert "no internet" in result["error"]
