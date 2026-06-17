"""Sector / theme classification for tickers.

yfinance only gives broad GICS sectors ("Technology" lumps AI, Cloud, and Semis
together). For a more useful grouping we first consult a curated THEME map
(AI / Cloud / Biotech / Semiconductors / EV / ETF …), then fall back to
yfinance's sector or ETF detection, then "Other".
"""
from __future__ import annotations

import functools

import yfinance as yf

# Curated thematic overrides for well-known tickers (highest priority).
THEMES: dict[str, str] = {
    # AI
    "NVDA": "AI", "PLTR": "AI", "AI": "AI", "SMCI": "AI", "ARM": "AI",
    "PATH": "AI", "BBAI": "AI", "SOUN": "AI",
    # Cloud / Software
    "MSFT": "Cloud", "AMZN": "Cloud", "GOOGL": "Cloud", "GOOG": "Cloud",
    "CRM": "Cloud", "SNOW": "Cloud", "NET": "Cloud", "DDOG": "Cloud",
    "ORCL": "Cloud", "NOW": "Cloud", "MDB": "Cloud", "ZS": "Cloud", "PANW": "Cloud",
    # Semiconductors
    "AMD": "Semiconductors", "INTC": "Semiconductors", "MU": "Semiconductors",
    "QCOM": "Semiconductors", "AVGO": "Semiconductors", "ASML": "Semiconductors",
    "TSM": "Semiconductors", "TXN": "Semiconductors", "LRCX": "Semiconductors",
    # Biotech / Pharma
    "MRNA": "Biotech", "BNTX": "Biotech", "CRSP": "Biotech", "REGN": "Biotech",
    "VRTX": "Biotech", "GILD": "Biotech", "AMGN": "Biotech", "BIIB": "Biotech",
    "NVAX": "Biotech",
    # EV / Auto
    "TSLA": "EV", "RIVN": "EV", "LCID": "EV", "NIO": "EV", "XPEV": "EV", "LI": "EV",
}

# Display order for sector groups; anything else sorts after, alphabetically.
PREFERRED_ORDER = [
    "ETF", "AI", "Cloud", "Semiconductors", "Biotech", "EV",
    "Technology", "Healthcare", "Financial Services", "Communication Services",
    "Consumer Cyclical", "Consumer Defensive", "Industrials", "Energy",
    "Utilities", "Real Estate", "Basic Materials", "Other",
]


@functools.lru_cache(maxsize=1024)
def get_sector(symbol: str) -> str:
    """Best-effort category for a ticker (cached)."""
    s = symbol.upper()
    if s in THEMES:
        return THEMES[s]
    try:
        info = yf.Ticker(s).info or {}
        qtype = (info.get("quoteType") or "").upper()
        if qtype == "ETF":
            return "ETF"
        sector = info.get("sector")
        if sector:
            return sector
        if qtype:
            return qtype.title()
    except Exception:  # noqa: BLE001
        pass
    return "Other"


def order_key(sector: str) -> tuple[int, str]:
    """Sort key so PREFERRED_ORDER leads, then alphabetical."""
    try:
        return (PREFERRED_ORDER.index(sector), "")
    except ValueError:
        return (len(PREFERRED_ORDER), sector)
