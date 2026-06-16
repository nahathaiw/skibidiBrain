"""Chart page: TradingView-style candlesticks (single or 2x2 grid)."""
from __future__ import annotations

import streamlit as st

from services import charting

INDICATOR_LABELS = {
    "SMA20": "SMA 20", "SMA50": "SMA 50", "EMA20": "EMA 20",
    "BBANDS": "Bollinger", "Volume": "Volume", "RSI": "RSI", "MACD": "MACD",
}


@st.cache_data(ttl=300, show_spinner=False)
def _get_chart_data(symbol: str, timeframe: str):
    """Cached OHLCV (5 min, respects Yahoo limits)."""
    return charting.get_ohlc(symbol, timeframe)


def _render_one(symbol: str, timeframe: str, indicators: set[str], height: int | None = None):
    df = _get_chart_data(symbol, timeframe)
    if df is None or df.empty:
        st.warning(f"No data for {symbol} at {timeframe}. "
                   "Intraday history is limited by Yahoo (try 1D/1W).")
        return
    fig = charting.build_figure(df, symbol, timeframe, indicators, height=height)
    st.plotly_chart(fig, width="stretch", key=f"chart_{symbol}_{timeframe}")
    last, first = df["Close"].iloc[-1], df["Close"].iloc[0]
    chg = (last - first) / first * 100
    st.caption(f"{symbol} · {timeframe} · last {last:,.2f} · "
               f"{chg:+.2f}% over window · {len(df)} candles")


def render(default_symbol: str = "AAPL"):
    c1, c2 = st.columns([2, 3])
    with c1:
        symbol = st.text_input("Ticker", value=default_symbol,
                               key="chart_symbol").strip().upper()
    with c2:
        view_mode = st.radio("View", ["Single", "Grid (all 4 timeframes)"],
                             horizontal=True, key="view_mode")

    single_mode = view_mode == "Single"
    if single_mode:
        timeframe = st.radio("Timeframe", list(charting.TIMEFRAMES.keys()),
                             index=2, horizontal=True, key="timeframe")

    picked = st.multiselect(
        "Indicators",
        options=list(INDICATOR_LABELS.keys()),
        default=["SMA20", "SMA50", "Volume"],
        format_func=lambda k: INDICATOR_LABELS[k],
        key="indicators",
    )
    indicators = set(picked)

    if not symbol:
        return

    if single_mode:
        with st.spinner(f"Loading {symbol} {timeframe}…"):
            _render_one(symbol, timeframe, indicators)
    else:
        # 2x2 grid: TL=1W, TR=1D, BL=3h, BR=45M
        with st.spinner(f"Loading {symbol} (all timeframes)…"):
            top_l, top_r = st.columns(2)
            bot_l, bot_r = st.columns(2)
            cells = [(top_l, "1W"), (top_r, "1D"), (bot_l, "3h"), (bot_r, "45M")]
            for col, tf in cells:
                with col:
                    _render_one(symbol, tf, indicators, height=420)
