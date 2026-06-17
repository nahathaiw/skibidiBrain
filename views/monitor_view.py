"""Magic Monitor page: live multi-timeframe trend/momentum screener table."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import magic_monitor, sectors, watchlist

_PCT_COLS = ["3h Δ%", "D Δ%", "W Δ%", "1D%", "5D%", "30D%", "YTD%", "1Y%"]


@st.cache_data(ttl=300, show_spinner=False)
def _table(symbols_key: str) -> pd.DataFrame:
    return magic_monitor.build_table(symbols_key.split(","))


def _color_pct(v):
    if v is None or (isinstance(v, float) and v != v):
        return "color: #888"
    return "color: #26a69a" if v > 0 else "color: #ef5350" if v < 0 else "color: #888"


def _color_sig(v):
    return "color: #26a69a" if v == "▲" else "color: #ef5350" if v == "▼" else "color: #888"


def _color_regime(v):
    return "background-color: rgba(38,166,154,0.18)" if v == "T" else "background-color: rgba(120,120,120,0.12)"


def _color_ext(v):
    if v == "OB":
        return "background-color: rgba(239,83,80,0.25)"
    if v == "OS":
        return "background-color: rgba(38,166,154,0.25)"
    return ""


def render():
    st.markdown("#### 🪄 Magic Monitor")
    st.caption("Multi-timeframe trend & momentum screener — a live reconstruction of the "
               "Syrius Magic Monitor (3h / Daily / Weekly). **Sig** = EMA(9/21) cross "
               "direction · **Bars** = bars since trigger · **Δ%** = move since trigger · "
               "**Regime** T/R = ADX(14) ≥/< 25 · **Ext** = RSI OB/OS.")

    c0, c1, c2 = st.columns([2, 3, 1])
    with c0:
        lists = watchlist.names()
        chosen = st.selectbox("List", lists, index=0, key="mm_list",
                              label_visibility="collapsed")
    with c1:
        default = ", ".join(watchlist.load(chosen))
        raw = st.text_input("Tickers", value=default, key=f"mm_tickers_{chosen}",
                            label_visibility="collapsed")
    with c2:
        if st.button("↻ Refresh", width="stretch", key="mm_refresh"):
            _table.clear()
            st.rerun()

    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not symbols:
        st.info("Add some tickers above.")
        return

    with st.spinner(f"Scanning {len(symbols)} tickers across 3 timeframes…"):
        df = _table(",".join(symbols))

    if df.empty:
        st.warning("No data (Yahoo may be rate-limiting). Try again shortly.")
        return

    # Group by sector, sectors in preferred order, with a header per group.
    present = sorted(df["Sector"].dropna().unique(), key=sectors.order_key)
    for sector in present:
        group = df[df["Sector"] == sector].drop(columns=["Sector"])
        st.markdown(f"##### {sector}  ·  {len(group)}")
        st.dataframe(_style(group), width="stretch", hide_index=True,
                     height=min(560, 44 + 35 * len(group)))

    st.caption("Grouped by sector/theme (curated, then yfinance). Indicator *families* "
               "match the reverse-engineered original; exact thresholds were not fit to "
               "the source PDFs. Educational — not financial advice.")


def _style(group):
    return (
        group.style
        .map(_color_sig, subset=["3h Sig", "D Sig", "W Sig"])
        .map(_color_pct, subset=[c for c in _PCT_COLS if c in group.columns])
        .map(_color_regime, subset=["Regime"])
        .map(_color_ext, subset=["Ext"])
        .format({c: "{:+.2f}" for c in _PCT_COLS if c in group.columns}, na_rep="—")
        .format({"Last": "{:,.2f}", "ADX": "{:.1f}", "RSI": "{:.0f}"}, na_rep="—")
    )
