"""Prediction page: transparent 5-day-forward signal with full factor breakdown."""
from __future__ import annotations

import streamlit as st

from services import prediction

_COLOR = {"Bullish": "🟢", "Bearish": "🔴", "Neutral": "⚪"}


@st.cache_data(ttl=900, show_spinner=False)
def _predict(symbol: str) -> dict:
    return prediction.get_prediction(symbol)


def render(default_symbol: str = "AAPL"):
    st.warning(
        "🧪 **Experimental.** This 5-day signal is a transparent heuristic reverse-"
        "engineered from one 2022 market window — it is **not validated out-of-sample "
        "and not financial advice.** Treat it as one input, not a crystal ball.",
        icon="⚠️",
    )

    symbol = st.text_input("Ticker", value=default_symbol,
                           key="pred_symbol").strip().upper()
    if not symbol:
        return

    with st.spinner(f"Analyzing {symbol}…"):
        p = _predict(symbol)

    if p.get("error"):
        st.error(p["error"])
        return

    # Verdict banner
    icon = _COLOR.get(p["signal"], "⚪")
    st.markdown(f"## {icon} {p['symbol']}: **{p['signal']}** (next ~5 trading days)")
    st.caption(f"As of {p['asof']} · last {p['last_price']:,.2f}")

    c = st.columns(4)
    c[0].metric("Expected 5d move", f"{p['expected_5d_pct']:+.2f}%")
    c[1].metric("Signal strength", f"{p['strength']}/100")
    c[2].metric(f"ADX(14) · {p['regime']}", f"{p['adx']:.1f}")
    c[3].metric(f"RSI(14) · {p['rsi_state']}", f"{p['rsi']:.0f}")

    st.progress(p["strength"] / 100, text=f"Confidence {p['strength']}%")

    # Factor breakdown
    st.markdown("##### Why")
    for label, detail in p["factors"]:
        st.markdown(f"- **{label}:** {detail}")

    # Plain-English read
    if p["regime"] == "Trending" and p["recent"] == "up":
        note = ("Extended in a trending regime after running up — the edge expects a "
                "**pullback** (mean reversion).")
    elif p["regime"] == "Ranging" and p["recent"] == "down":
        note = ("Beaten down in a ranging regime — the edge expects a **bounce** "
                "(mean reversion).")
    else:
        note = "A mixed setup — the historical edge here is weak; treat as near-neutral."
    st.info(note)

    st.caption("Method: ADX regime × recent direction (mean-reversion table), nudged by "
               "RSI extremes and multi-timeframe trend alignment. "
               "See `prediction/REVERSE_ENGINEERING_FINDINGS.md`. Not financial advice.")
