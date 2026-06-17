"""Live Yahoo Finance data via yfinance, exposed as OpenAI tool-calling functions.

These tools return *fresh* structured data (prices, financials, company info).
Live numbers should never be answered from the RAG store — always fetch them here.
"""
from __future__ import annotations

import functools
from datetime import datetime, timedelta

import yfinance as yf

from rag import news_finnhub

from . import prediction


# yfinance hits Yahoo's servers, which rate-limit. Cache for a short window so
# repeated questions in a session don't re-fetch. (Streamlit caching lives in
# app.py; this cache helps when tools are called outside Streamlit too.)
@functools.lru_cache(maxsize=128)
def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol.upper())


def get_stock_price(symbol: str) -> dict:
    """Latest price snapshot for a ticker."""
    t = _ticker(symbol)
    info = t.fast_info
    try:
        last = float(info.last_price)
        prev = float(info.previous_close)
        change = last - prev
        pct = (change / prev * 100) if prev else 0.0
        return {
            "symbol": symbol.upper(),
            "last_price": round(last, 2),
            "previous_close": round(prev, 2),
            "change": round(change, 2),
            "change_percent": round(pct, 2),
            "currency": getattr(info, "currency", "USD"),
            "day_high": round(float(info.day_high), 2),
            "day_low": round(float(info.day_low), 2),
        }
    except Exception as e:  # noqa: BLE001 - surface a clean message to the LLM
        return {"symbol": symbol.upper(), "error": f"Could not fetch price: {e}"}


def get_company_info(symbol: str) -> dict:
    """Profile + key valuation metrics for a company."""
    t = _ticker(symbol)
    try:
        info = t.info
        keys = [
            "longName", "sector", "industry", "country", "website",
            "marketCap", "trailingPE", "forwardPE", "dividendYield",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "beta",
            "longBusinessSummary",
        ]
        return {"symbol": symbol.upper(), **{k: info.get(k) for k in keys}}
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol.upper(), "error": f"Could not fetch info: {e}"}


def get_financials(symbol: str) -> dict:
    """Recent income-statement highlights (most recent reported period)."""
    t = _ticker(symbol)
    try:
        fin = t.financials
        if fin is None or fin.empty:
            return {"symbol": symbol.upper(), "error": "No financials available."}
        latest = fin.iloc[:, 0]  # most recent period column
        rows = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]
        out = {}
        for r in rows:
            if r in latest.index:
                val = latest[r]
                out[r] = None if val != val else float(val)  # NaN check
        return {
            "symbol": symbol.upper(),
            "period": str(fin.columns[0].date()),
            "currency": "USD",
            **out,
        }
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol.upper(), "error": f"Could not fetch financials: {e}"}


def get_historical_performance(symbol: str, period: str = "1mo") -> dict:
    """Price performance over a period. period: 1d,5d,1mo,3mo,6mo,1y,5y,max."""
    t = _ticker(symbol)
    try:
        hist = t.history(period=period)
        if hist.empty:
            return {"symbol": symbol.upper(), "error": "No history available."}
        start = float(hist["Close"].iloc[0])
        end = float(hist["Close"].iloc[-1])
        return {
            "symbol": symbol.upper(),
            "period": period,
            "start_price": round(start, 2),
            "end_price": round(end, 2),
            "return_percent": round((end - start) / start * 100, 2),
            "high": round(float(hist["High"].max()), 2),
            "low": round(float(hist["Low"].min()), 2),
        }
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol.upper(), "error": f"Could not fetch history: {e}"}


def get_price_on_date(symbol: str, date: str) -> dict:
    """OHLC + move for a specific date (YYYY-MM-DD). Grounds 'why bearish/bullish'.

    Returns the trading day on or before `date` (handles weekends/holidays),
    its open/high/low/close, volume, and the % change vs the prior close.
    """
    t = _ticker(symbol)
    try:
        target = datetime.fromisoformat(date).date()
    except ValueError:
        return {"symbol": symbol.upper(), "error": f"Bad date '{date}', use YYYY-MM-DD."}

    try:
        # Pull a window so we also have the previous trading day's close.
        hist = t.history(
            start=(target - timedelta(days=10)).isoformat(),
            end=(target + timedelta(days=1)).isoformat(),
        )
        if hist.empty:
            return {"symbol": symbol.upper(), "error": f"No data near {date}."}

        hist = hist.reset_index()
        hist["d"] = hist["Date"].dt.date
        on_or_before = hist[hist["d"] <= target]
        if on_or_before.empty:
            return {"symbol": symbol.upper(), "error": f"No trading day on/before {date}."}

        idx = on_or_before.index[-1]
        row = hist.loc[idx]
        prev_close = float(hist.loc[idx - 1, "Close"]) if idx >= 1 else float(row["Open"])
        close = float(row["Close"])
        change = close - prev_close
        pct = (change / prev_close * 100) if prev_close else 0.0
        return {
            "symbol": symbol.upper(),
            "trading_date": row["d"].isoformat(),
            "requested_date": date,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(close, 2),
            "previous_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_percent": round(pct, 2),
            "direction": "bearish" if change < 0 else "bullish" if change > 0 else "flat",
            "volume": int(row["Volume"]),
        }
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol.upper(), "error": f"Could not fetch date price: {e}"}


def get_news_on_date(symbol: str, date: str, window_days: int = 3) -> dict:
    """Company news around a specific date via Finnhub (fallback for older dates).

    Yahoo's feed only covers the last ~1-2 weeks; this reaches ~1 year back.
    Returns headlines within +/- window_days of `date`. Requires FINNHUB_API_KEY.
    """
    if not news_finnhub.has_key():
        return {
            "symbol": symbol.upper(),
            "configured": False,
            "message": "Finnhub not configured (no FINNHUB_API_KEY); only recent "
                       "Yahoo news is available.",
        }
    try:
        target = datetime.fromisoformat(date).date()
    except ValueError:
        return {"symbol": symbol.upper(), "error": f"Bad date '{date}', use YYYY-MM-DD."}

    frm = (target - timedelta(days=window_days)).isoformat()
    to = (target + timedelta(days=window_days)).isoformat()
    items = news_finnhub.fetch_company_news(symbol, frm, to, limit=15)
    return {
        "symbol": symbol.upper(),
        "configured": True,
        "date_range": f"{frm} to {to}",
        "count": len(items),
        "articles": items,
    }


def get_price_prediction(symbol: str) -> dict:
    """Experimental 5-day-forward signal (mean-reversion heuristic). Not advice."""
    return prediction.get_prediction(symbol)


# --- OpenAI tool schemas --------------------------------------------------

TOOL_FUNCTIONS = {
    "get_stock_price": get_stock_price,
    "get_company_info": get_company_info,
    "get_financials": get_financials,
    "get_historical_performance": get_historical_performance,
    "get_price_on_date": get_price_on_date,
    "get_news_on_date": get_news_on_date,
    "get_price_prediction": get_price_prediction,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the latest live price snapshot for a stock ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Ticker, e.g. AAPL"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get company profile and valuation metrics (P/E, market cap, sector, etc.).",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financials",
            "description": "Get recent income-statement highlights (revenue, net income, etc.).",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_performance",
            "description": "Get price return over a period (1d,5d,1mo,3mo,6mo,1y,5y,max).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "period": {"type": "string", "default": "1mo"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_on_date",
            "description": (
                "Get the OHLC, volume, and % change vs prior close for a stock on a "
                "SPECIFIC date. Use this for any question about what happened on a "
                "particular day (e.g. 'why was AAPL bearish on June 8') to confirm the "
                "actual price move. Handles weekends/holidays by using the prior trading day."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "date": {"type": "string", "description": "Date as YYYY-MM-DD"},
                },
                "required": ["symbol", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_on_date",
            "description": (
                "Get company news headlines around a SPECIFIC date (via Finnhub, ~1 year "
                "of history). Use this for date-specific news questions, ESPECIALLY when "
                "the NEWS CONTEXT (recent Yahoo news) has nothing from that day. Pair with "
                "get_price_on_date to explain why a stock moved on a given day."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "date": {"type": "string", "description": "Date as YYYY-MM-DD"},
                    "window_days": {
                        "type": "integer",
                        "description": "Days before/after the date to include (default 3).",
                    },
                },
                "required": ["symbol", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_prediction",
            "description": (
                "Experimental 5-day-forward signal (Bullish/Bearish/Neutral) from a "
                "transparent mean-reversion heuristic: ADX regime x recent direction, "
                "nudged by RSI and multi-timeframe trend. Use for 'will it go up', "
                "'forecast', 'next week' questions. ALWAYS state it is experimental and "
                "not financial advice."
            ),
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
]
