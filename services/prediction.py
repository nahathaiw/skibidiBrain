"""5-day-forward signal — a transparent heuristic, not a black-box model.

Implements the edge reverse-engineered in prediction/REVERSE_ENGINEERING_FINDINGS.md:
a MEAN-REVERSION pattern strongest in high-momentum names, combining

  * ADX(14)        -> regime: Trending (>=25) vs Ranging (<25)
  * recent 5d move -> direction the name just ran
  * RSI(14)        -> overbought / oversold confirmation
  * multi-timeframe trend alignment (fast-daily / daily / weekly)

The empirical fwd-5d table (measured in-sample on a 40-day, 2022 window):

  regime  recent  fwd-5d
  T       up      -1.83%   (extended, gives it back)   <- most bearish
  T       down    +0.69%
  R       down    +2.00%   (beaten down, bounces)      <- most bullish
  R       up      +0.04%

IMPORTANT: this was a single choppy regime and is NOT validated out-of-sample.
The UI surfaces this caveat. Educational only — not financial advice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

# Empirical base expectations (% fwd-5d) from the findings' correction #2.
_BASE = {
    ("Trending", "up"): -1.83,
    ("Trending", "down"): 0.69,
    ("Ranging", "down"): 2.00,
    ("Ranging", "up"): 0.04,
}


# --- indicator math (Wilder-smoothed, pure pandas) ------------------------

def _wilder(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1 / n, adjust=False).mean()


def _adx(df: pd.DataFrame, n: int = 14) -> float:
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = _wilder(tr, n)
    plus_di = 100 * _wilder(pd.Series(plus_dm, index=df.index), n) / atr
    minus_di = 100 * _wilder(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder(dx.fillna(0), n)
    return float(adx.iloc[-1])


def _rsi(close: pd.Series, n: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return float((100 - 100 / (1 + rs)).iloc[-1])


def _trend_dir(close: pd.Series, fast: int = 20, slow: int = 50) -> str:
    """Up / down / flat from an EMA stack on a close series."""
    if len(close) < slow:
        return "flat"
    ef = close.ewm(span=fast, adjust=False).mean().iloc[-1]
    es = close.ewm(span=slow, adjust=False).mean().iloc[-1]
    last = close.iloc[-1]
    if last > ef and ef >= es:
        return "up"
    if last < ef and ef <= es:
        return "down"
    return "flat"


# --- main entry -----------------------------------------------------------

def get_prediction(symbol: str) -> dict:
    """Compute the 5-day-forward signal for a ticker from live daily OHLCV."""
    sym = symbol.upper()
    try:
        df = yf.Ticker(sym).history(period="1y")
    except Exception as e:  # noqa: BLE001
        return {"symbol": sym, "error": f"Could not fetch data: {e}"}
    if df is None or df.empty or len(df) < 60:
        return {"symbol": sym, "error": "Not enough price history to predict."}

    close = df["Close"]
    last_price = float(close.iloc[-1])
    asof = df.index[-1].date().isoformat()

    # Regime + recent direction (the two table axes).
    adx = _adx(df)
    regime = "Trending" if adx >= 25 else "Ranging"
    move_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 6 else 0.0
    recent = "up" if move_5d >= 0 else "down"

    base = _BASE[(regime, recent)]

    # RSI confirmation nudge (mean-reversion: OB -> down, OS -> up).
    rsi = _rsi(close)
    if rsi >= 70:
        rsi_state, rsi_nudge = "overbought", -0.5
    elif rsi <= 30:
        rsi_state, rsi_nudge = "oversold", +0.5
    else:
        rsi_state, rsi_nudge = "neutral", 0.0

    # Multi-timeframe trend (fast-daily / daily / weekly).
    weekly = close.resample("W").last().dropna()
    mtf = {
        "fast_daily": _trend_dir(close, 9, 20),
        "daily": _trend_dir(close, 20, 50),
        "weekly": _trend_dir(weekly, 10, 20),
    }
    dirs = [d for d in mtf.values() if d != "flat"]
    aligned = len(dirs) >= 2 and len(set(dirs)) == 1
    mtf_dir = dirs[0] if aligned else "mixed"

    expected = round(base + rsi_nudge, 2)
    if expected > 0.3:
        signal = "Bullish"
    elif expected < -0.3:
        signal = "Bearish"
    else:
        signal = "Neutral"

    # Confidence: magnitude + how many factors agree with the call.
    agree = 0
    if rsi_state == "overbought" and signal == "Bearish":
        agree += 1
    if rsi_state == "oversold" and signal == "Bullish":
        agree += 1
    if aligned and ((mtf_dir == "up" and signal == "Bearish")  # extended uptrend, MR down
                    or (mtf_dir == "down" and signal == "Bullish")):
        agree += 1
    strength = int(min(100, round(abs(expected) * 30 + agree * 12 + 10)))

    factors = [
        ("ADX(14)", f"{adx:.1f} → {regime.lower()} regime"),
        ("Recent 5d move", f"{move_5d:+.2f}% → ran {recent}"),
        ("Mean-reversion base", f"{base:+.2f}% (from {regime}/{recent})"),
        ("RSI(14)", f"{rsi:.0f} → {rsi_state}"),
        ("Multi-timeframe", f"{mtf['fast_daily']}/{mtf['daily']}/{mtf['weekly']} "
                            + ("(aligned)" if aligned else "(mixed)")),
    ]

    return {
        "symbol": sym,
        "asof": asof,
        "last_price": round(last_price, 2),
        "adx": round(adx, 1),
        "regime": regime,
        "move_5d_pct": round(move_5d, 2),
        "recent": recent,
        "rsi": round(rsi, 1),
        "rsi_state": rsi_state,
        "mtf": mtf,
        "mtf_aligned": aligned,
        "expected_5d_pct": expected,
        "signal": signal,
        "strength": strength,
        "factors": factors,
    }
