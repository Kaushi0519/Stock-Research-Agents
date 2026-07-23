from datetime import datetime, timedelta

import requests

from src.config import FINNHUB_API_KEY

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


def get_news(ticker: str, days_back: int = 7, max_articles: int = 10) -> dict:
    today = datetime.now().date()
    start_date = today - timedelta(days=days_back)

    params = {
        "symbol": ticker,
        "from": start_date.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    try:
        response = requests.get(FINNHUB_NEWS_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch news for {ticker}: {e}"}

    articles = response.json()

    if not articles:
        return {"ticker": ticker, "days_back": days_back, "articles": []}

    trimmed = []
    for article in articles[:max_articles]:
        trimmed.append({
            "headline": article.get("headline", ""),
            "summary": article.get("summary", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "published": datetime.fromtimestamp(article.get("datetime", 0)).isoformat(),
        })

    return {
        "ticker": ticker,
        "days_back": days_back,
        "articles": trimmed,
    }
