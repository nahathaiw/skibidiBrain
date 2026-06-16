"""Persistent watchlist of tickers, stored as JSON on disk.

Streamlit's session_state resets on restart, so the watchlist is saved to
watchlist.json in the project root to survive across sessions.
"""
from __future__ import annotations

import json
import os

_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "watchlist.json")
DEFAULT = ["AAPL", "MSFT", "NVDA"]


def load() -> list[str]:
    """Return the saved watchlist (or the default if none/corrupt)."""
    try:
        with open(_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return [str(s).upper() for s in data]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return list(DEFAULT)


def save(tickers: list[str]) -> None:
    # De-dupe while preserving order, uppercase.
    seen: set[str] = set()
    clean = [t.upper() for t in tickers if t and (t.upper() not in seen and not seen.add(t.upper()))]
    try:
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
    except OSError:
        pass


def add(ticker: str) -> list[str]:
    wl = load()
    t = ticker.strip().upper()
    if t and t not in wl:
        wl.append(t)
        save(wl)
    return wl


def remove(ticker: str) -> list[str]:
    wl = [t for t in load() if t != ticker.strip().upper()]
    save(wl)
    return wl
