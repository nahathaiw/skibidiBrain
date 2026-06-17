"""Recreate the Syrius Magic Monitor — a multi-timeframe trend/momentum table.

Faithful to prediction/REVERSE_ENGINEERING_FINDINGS.md: three timeframe blocks
(3h / Daily / Weekly), each with a signal direction, a bar-count since the last
trigger, and the % change since that trigger; plus a shared ADX regime (T/R),
trailing returns, and an RSI extreme flag.

The indicator *families* match the original (ADX(14) regime, EMA(9/21) crossover
trigger ~9-10 day cadence, RSI(14) OB/OS). Exact thresholds were not fit against
the source PDFs (see the findings' caveats), so values are our transparent
reconstruction, not the original sheet's exact numbers.
"""
from __future__ import annotations

import pandas as pd

from . import charting, sectors
from .prediction import _adx, _rsi

# Timeframe label -> charting key (charting handles the resampling).
_TFS = {"3h": "3h", "D": "1D", "W": "1W"}


def _signal(df: pd.DataFrame) -> dict:
    """EMA(9/21) crossover trigger: direction, bars since, price_when, chg_since%."""
    close = df["Close"]
    if len(close) < 25:
        return {"dir": "flat", "count": 0, "price_when": float(close.iloc[-1]),
                "chg_since": 0.0}
    e9 = close.ewm(span=9, adjust=False).mean()
    e21 = close.ewm(span=21, adjust=False).mean()
    up = e9 > e21
    changed = up.ne(up.shift())
    changed.iloc[0] = False
    trigs = [i for i, c in enumerate(changed.tolist()) if c]
    last_trig = trigs[-1] if trigs else 0
    price_when = float(close.iloc[last_trig])
    last = float(close.iloc[-1])
    return {
        "dir": "up" if bool(up.iloc[-1]) else "down",
        "count": len(close) - 1 - last_trig,
        "price_when": price_when,
        "chg_since": (last - price_when) / price_when * 100 if price_when else 0.0,
    }


def _ret(close: pd.Series, n: int, fallback: bool = False) -> float | None:
    if len(close) > n:
        return float((close.iloc[-1] / close.iloc[-1 - n] - 1) * 100)
    # For long lookbacks (1Y) a 1y fetch may be ~251 bars; use the window's start.
    if fallback and len(close) > 1:
        return float((close.iloc[-1] / close.iloc[0] - 1) * 100)
    return None


def _ytd(close: pd.Series) -> float | None:
    year = close.index[-1].year
    same = close[close.index.year == year]
    if len(same) < 2:
        return None
    return float((close.iloc[-1] / same.iloc[0] - 1) * 100)


def compute_row(symbol: str) -> dict:
    """One Magic-Monitor row for a ticker (all timeframes + shared columns)."""
    sym = symbol.upper()
    daily = charting.get_ohlc(sym, "1D")
    if daily is None or daily.empty:
        return {"Symbol": sym, "error": True}

    close = daily["Close"]
    last = float(close.iloc[-1])
    row: dict = {"Sector": sectors.get_sector(sym), "Symbol": sym, "Last": round(last, 2)}

    # Per-timeframe signal blocks.
    for label, key in _TFS.items():
        df = daily if key == "1D" else charting.get_ohlc(sym, key)
        if df is None or df.empty:
            row[f"{label} Sig"], row[f"{label} Bars"], row[f"{label} Δ%"] = "·", None, None
            continue
        s = _signal(df)
        arrow = "▲" if s["dir"] == "up" else "▼" if s["dir"] == "down" else "·"
        row[f"{label} Sig"] = arrow
        row[f"{label} Bars"] = s["count"]
        row[f"{label} Δ%"] = round(s["chg_since"], 2)

    # Shared columns.
    adx = _adx(daily)
    row["Regime"] = "T" if adx >= 25 else "R"
    row["ADX"] = round(adx, 1)
    rsi = _rsi(close)
    row["RSI"] = round(rsi, 0)
    row["Ext"] = "OB" if rsi >= 70 else "OS" if rsi <= 30 else ""
    row["1D%"] = round(_ret(close, 1), 2) if _ret(close, 1) is not None else None
    row["5D%"] = round(_ret(close, 5), 2) if _ret(close, 5) is not None else None
    row["30D%"] = round(_ret(close, 21), 2) if _ret(close, 21) is not None else None
    ytd = _ytd(close)
    row["YTD%"] = round(ytd, 2) if ytd is not None else None
    y1 = _ret(close, 252, fallback=True)
    row["1Y%"] = round(y1, 2) if y1 is not None else None
    return row


def build_table(symbols: list[str]) -> pd.DataFrame:
    """Magic-Monitor DataFrame for a list of tickers (skips failures)."""
    rows = [r for r in (compute_row(s) for s in symbols) if not r.get("error")]
    if not rows:
        return pd.DataFrame()
    cols = [
        "Sector", "Symbol", "Last",
        "3h Sig", "3h Bars", "3h Δ%",
        "D Sig", "D Bars", "D Δ%",
        "W Sig", "W Bars", "W Δ%",
        "Regime", "ADX", "RSI", "Ext",
        "1D%", "5D%", "30D%", "YTD%", "1Y%",
    ]
    return pd.DataFrame(rows).reindex(columns=cols)
