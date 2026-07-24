import requests

SEC_HEADERS = {"User-Agent": "Stock Research Agents kaushi19rk@gmail.com"}
TICKER_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_cik_cache = None


def _get_cik_map() -> dict:
    global _cik_cache
    if _cik_cache is None:
        resp = requests.get(TICKER_CIK_URL, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _cik_cache = {
            entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
            for entry in data.values()
        }
    return _cik_cache


def get_sec_filings(ticker: str, filing_type: str = None, limit: int = 5) -> dict:
    try:
        cik = _get_cik_map().get(ticker.upper())
    except Exception as e:
        return {"error": f"Failed to look up CIK for {ticker}: {e}"}

    if cik is None:
        return {"error": f"No CIK found for ticker '{ticker}'. Check the symbol."}

    try:
        response = requests.get(SUBMISSIONS_URL.format(cik=cik), headers=SEC_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch filings for {ticker}: {e}"}

    recent = response.json().get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])

    cik_no_zeros = str(int(cik))
    filings = []
    for i in range(len(forms)):
        if filing_type and forms[i] != filing_type:
            continue

        accession_no_dashes = accession_numbers[i].replace("-", "")
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_no_zeros}/{accession_no_dashes}/{primary_documents[i]}"
        )

        filings.append({
            "form_type": forms[i],
            "filing_date": dates[i],
            "accession_number": accession_numbers[i],
            "document_url": doc_url,
        })

        if len(filings) >= limit:
            break

    return {"ticker": ticker, "filing_type": filing_type, "filings": filings}
