"""Persistent, multi-list watchlists stored as JSON on disk.

Supports several named lists (e.g. "My Watchlist", "Magic Monitor") with one
marked active. Streamlit's session_state resets on restart, so everything is
saved to watchlist.json to survive across sessions.

On-disk format:
    {"active": "My Watchlist",
     "lists": {"My Watchlist": ["AAPL", ...], "Magic Monitor": ["QQQ", ...]}}

Older single-list files (a bare JSON array) are migrated automatically.
"""
from __future__ import annotations

import json
import os

from .presets import MAGIC_MONITOR

_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "watchlist.json")

DEFAULT_NAME = "My Watchlist"
MAGIC_NAME = "Magic Monitor"
_DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]


def _dedup_upper(tickers: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tickers:
        u = str(t).upper().strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _ensure(data: dict) -> dict:
    """Guarantee the two built-in lists exist and active points at a real list."""
    lists = data.setdefault("lists", {})
    if DEFAULT_NAME not in lists:
        lists[DEFAULT_NAME] = list(_DEFAULT_TICKERS)
    if MAGIC_NAME not in lists:
        lists[MAGIC_NAME] = _dedup_upper(MAGIC_MONITOR)
    if data.get("active") not in lists:
        data["active"] = DEFAULT_NAME
    return data


def _read() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    # Migrate a legacy bare-array file into the new structure.
    if isinstance(data, list):
        data = {"active": DEFAULT_NAME, "lists": {DEFAULT_NAME: _dedup_upper(data)}}
    if not isinstance(data, dict):
        data = {}
    return _ensure(data)


def _write(data: dict) -> None:
    try:
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(_ensure(data), f, indent=2)
    except OSError:
        pass


# --- public API -----------------------------------------------------------

def names() -> list[str]:
    """All list names (active first)."""
    data = _read()
    active = data["active"]
    return [active] + [n for n in data["lists"] if n != active]


def active_name() -> str:
    return _read()["active"]


def set_active(name: str) -> None:
    data = _read()
    if name in data["lists"]:
        data["active"] = name
        _write(data)


def load(name: str | None = None) -> list[str]:
    """Tickers in the given list (or the active list)."""
    data = _read()
    return list(data["lists"].get(name or data["active"], []))


def add(ticker: str, name: str | None = None) -> list[str]:
    data = _read()
    name = name or data["active"]
    lst = data["lists"].setdefault(name, [])
    t = ticker.strip().upper()
    if t and t not in lst:
        lst.append(t)
        _write(data)
    return lst


def remove(ticker: str, name: str | None = None) -> list[str]:
    data = _read()
    name = name or data["active"]
    data["lists"][name] = [t for t in data["lists"].get(name, []) if t != ticker.strip().upper()]
    _write(data)
    return data["lists"][name]
