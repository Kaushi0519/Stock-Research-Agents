import requests
from bs4 import BeautifulSoup

from src.tools.filings import SEC_HEADERS


def fetch_filing_text(document_url: str) -> str:
    """Fetch a SEC filing document and return its cleaned, visible text.

    Raises requests.RequestException / requests.HTTPError on network or
    HTTP failures — callers should catch and decide how to handle a failed
    fetch (e.g. skip that filing during ingestion).
    """
    response = requests.get(document_url, headers=SEC_HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return " ".join(text.split())
