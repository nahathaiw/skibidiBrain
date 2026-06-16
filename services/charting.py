"""TradingView-style candlestick charts with selectable timeframes + indicators.

yfinance has no native 45-minute or 3-hour interval, so those are built by
resampling finer bars (15m -> 45min, 1h -> 3h). 1D and 1W are fetched natively.

Indicators (all computed locally with pandas):
  overlays on price: SMA(20), SMA(50), EMA(20), Bollinger Bands(20, 2)
  lower panels:      Volume, RSI(14), MACD(12,26,9)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from plotly.subplots import make_subplots

# label -> how to fetch it. resample=None means yfinance gives it natively.
# yfinance intraday limits: 15m max ~60d, 1h max ~730d.
TIMEFRAMES: dict[str, dict] = {
    "45M": {"interval": "15m", "period": "1mo", "resample": "45min"},
    "3h": {"interval": "1h", "period": "6mo", "resample": "3h"},
    "1D": {"interval": "1d", "period": "1y", "resample": None},
    "1W": {"interval": "1wk", "period": "5y", "resample": None},
}

_OHLC_AGG = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
}


def get_ohlc(symbol: str, timeframe: str) -> pd.DataFrame:
    """Return an OHLCV DataFrame for a ticker at the requested timeframe."""
    cfg = TIMEFRAMES[timeframe]
    df = yf.Ticker(symbol.upper()).history(
        period=cfg["period"], interval=cfg["interval"]
    )
    if df.empty:
        return df

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if cfg["resample"]:
        df = df.resample(cfg["resample"]).agg(_OHLC_AGG).dropna()
    return df


# --- indicator math -------------------------------------------------------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal


def build_figure(df: pd.DataFrame, symbol: str, timeframe: str, indicators: set[str],
                 height: int | None = None) -> go.Figure:
    """Assemble the candlestick figure with the requested indicators.

    height: override the auto-computed height (used for the compact grid view).
    """
    close = df["Close"]

    # Decide how many lower panels we need.
    lower = [p for p in ("Volume", "RSI", "MACD") if p in indicators]
    n_rows = 1 + len(lower)
    # Price panel gets the lion's share of the height.
    heights = [0.55] + [0.45 / len(lower)] * len(lower) if lower else [1.0]

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=heights,
    )

    # --- price panel (row 1) ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=symbol,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    if "SMA20" in indicators:
        fig.add_trace(go.Scatter(x=df.index, y=close.rolling(20).mean(),
                                 name="SMA 20", line=dict(color="#42a5f5", width=1)), row=1, col=1)
    if "SMA50" in indicators:
        fig.add_trace(go.Scatter(x=df.index, y=close.rolling(50).mean(),
                                 name="SMA 50", line=dict(color="#ffa726", width=1)), row=1, col=1)
    if "EMA20" in indicators:
        fig.add_trace(go.Scatter(x=df.index, y=close.ewm(span=20, adjust=False).mean(),
                                 name="EMA 20", line=dict(color="#ab47bc", width=1)), row=1, col=1)
    if "BBANDS" in indicators:
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        fig.add_trace(go.Scatter(x=df.index, y=mid + 2 * std, name="BB upper",
                                 line=dict(color="#90a4ae", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=mid - 2 * std, name="BB lower",
                                 line=dict(color="#90a4ae", width=1, dash="dot"),
                                 fill="tonexty", fillcolor="rgba(144,164,174,0.08)"), row=1, col=1)

    # --- lower panels ---
    r = 2
    for panel in lower:
        if panel == "Volume":
            colors = ["#26a69a" if c >= o else "#ef5350"
                      for o, c in zip(df["Open"], df["Close"])]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                                 marker_color=colors, showlegend=False), row=r, col=1)
            fig.update_yaxes(title_text="Vol", row=r, col=1)
        elif panel == "RSI":
            rsi = _rsi(close)
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                                     line=dict(color="#7e57c2", width=1)), row=r, col=1)
            fig.add_hline(y=70, line=dict(color="#ef5350", width=1, dash="dash"), row=r, col=1)
            fig.add_hline(y=30, line=dict(color="#26a69a", width=1, dash="dash"), row=r, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=r, col=1)
        elif panel == "MACD":
            macd, signal, hist = _macd(close)
            hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in hist]
            fig.add_trace(go.Bar(x=df.index, y=hist, name="Hist",
                                 marker_color=hist_colors, showlegend=False), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=macd, name="MACD",
                                     line=dict(color="#42a5f5", width=1)), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=signal, name="Signal",
                                     line=dict(color="#ffa726", width=1)), row=r, col=1)
            fig.update_yaxes(title_text="MACD", row=r, col=1)
        r += 1

    fig.update_layout(
        title=f"{symbol.upper()} · {timeframe}",
        template="plotly_dark",
        height=height if height is not None else 300 + 220 * len(lower),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
        hovermode="x unified",
    )
    # Hide weekend/overnight gaps on intraday + daily for a cleaner look.
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig
