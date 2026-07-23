import yfinance as yf


def get_price_history(ticker: str, period: str = "6mo") -> dict:
    try:
        hist = yf.Ticker(ticker).history(period=period)
    except Exception as e:
        return {"error": f"Failed to fetch price data for {ticker}: {e}"}

    if hist.empty:
        return {"error": f"No price data found for ticker '{ticker}'. Check the symbol."}

    close = hist["Close"]
    current_price = close.iloc[-1]
    start_price = close.iloc[0]
    pct_change = (current_price - start_price) / start_price * 100

    return {
        "ticker": ticker,
        "period": period,
        "current_price": round(float(current_price), 2),
        "period_change_pct": round(float(pct_change), 2),
        "period_high": round(float(hist["High"].max()), 2),
        "period_low": round(float(hist["Low"].min()), 2),
        "avg_volume": int(hist["Volume"].mean()),
        "trading_days": len(hist),
    }
