"""Finnhub company-news fallback source.

Yahoo's news feed only returns the last ~1-2 weeks. Finnhub's free tier exposes
company news by date range (~1 year back), which fills that gap. All functions
no-op gracefully when FINNHUB_API_KEY is unset, so the app works without it.

Get a free key at https://finnhub.io/register and put it in .env:
    FINNHUB_API_KEY=...
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

_URL = "https://finnhub.io/api/v1/company-news"


def has_key() -> bool:
    return bool(os.getenv("FINNHUB_API_KEY"))


def fetch_company_news(symbol: str, from_date: str, to_date: str, limit: int = 50) -> list[dict]:
    """Company news for a ticker between two YYYY-MM-DD dates (inclusive).

    Returns a list of {date, headline, summary, source, url} dicts, newest first.
    Empty list on any error or missing key.
    """
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            _URL,
            params={"symbol": symbol.upper(), "from": from_date, "to": to_date, "token": key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):  # error payloads come back as dicts
            return []
    except (requests.RequestException, ValueError):
        return []

    items: list[dict] = []
    for it in data[:limit]:
        ts = it.get("datetime")
        date = (
            datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            if isinstance(ts, (int, float)) and ts > 0
            else ""
        )
        headline = (it.get("headline") or "").strip()
        if not headline:
            continue
        items.append({
            "date": date,
            "headline": headline,
            "summary": (it.get("summary") or "").strip(),
            "source": it.get("source") or "Finnhub",
            "url": it.get("url") or "",
        })
    return items
