"""Fundamentals page: valuation, profitability, health metrics + statements."""
from __future__ import annotations

import streamlit as st

from services import fundamentals


@st.cache_data(ttl=3600, show_spinner=False)
def _get_fundamentals(symbol: str):
    """Cached snapshot + statements (1 hour; these change slowly)."""
    return fundamentals.get_info(symbol), fundamentals.get_statements(symbol)


def render(default_symbol: str = "AAPL"):
    symbol = st.text_input("Ticker", value=default_symbol,
                           key="fund_symbol").strip().upper()
    if not symbol:
        return

    with st.spinner(f"Loading {symbol} fundamentals…"):
        info, statements = _get_fundamentals(symbol)

    if not info or not info.get("symbol"):
        st.warning(f"No fundamentals found for {symbol}. Check the ticker.")
        return

    # Company profile header
    st.subheader(info.get("longName", symbol))
    meta = " · ".join(str(info[k]) for k in ("sector", "industry", "country") if info.get(k))
    if meta:
        st.caption(meta)
    if info.get("website"):
        st.markdown(f"[{info['website']}]({info['website']})")

    # Metric groups as st.metric cards, 4 per row
    for group, metrics in fundamentals.GROUPS.items():
        st.markdown(f"##### {group}")
        cols = st.columns(4)
        for i, (key, label, code) in enumerate(metrics):
            with cols[i % 4]:
                st.metric(label, fundamentals.fmt(info.get(key), code))

    # Revenue & Net Income trend
    trend = fundamentals.revenue_income_trend(statements.get("Income Statement"))
    if not trend.empty:
        st.markdown("##### Revenue & Net Income by Year")
        st.bar_chart(trend)

    # Full statements in expanders
    st.markdown("##### Financial Statements")
    for name, df in statements.items():
        with st.expander(name):
            fdf = fundamentals.format_statement(df)
            if fdf.empty:
                st.write("Not available.")
            else:
                st.dataframe(fdf, width="stretch")

    # Business summary
    if info.get("longBusinessSummary"):
        with st.expander("About the company"):
            st.write(info["longBusinessSummary"])
