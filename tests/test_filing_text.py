from unittest.mock import MagicMock, patch

import pytest
import requests

from src.rag.filing_text import fetch_filing_text


@patch("src.rag.filing_text.requests.get")
def test_fetch_filing_text_strips_html_and_scripts(mock_get):
    fake_html = """
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <script>console.log('tracking');</script>
        <p>Item 1A. Risk Factors.</p>
        <p>The Company depends on suppliers in Asia.</p>
      </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.text = fake_html
    mock_get.return_value = mock_response

    text = fetch_filing_text("https://example.com/filing.htm")

    assert "Item 1A. Risk Factors." in text
    assert "depends on suppliers in Asia" in text
    assert "console.log" not in text
    assert "color: red" not in text


@patch("src.rag.filing_text.requests.get")
def test_fetch_filing_text_raises_on_http_error(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")
    mock_get.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        fetch_filing_text("https://example.com/missing.htm")
