"""Watchlist page: persistent ticker list with live quotes + add/remove."""
from __future__ import annotations

import streamlit as st

from services import finance_tools, watchlist


@st.cache_data(ttl=60, show_spinner=False)
def _quote(symbol: str) -> dict:
    """Live price snapshot, cached 60s."""
    return finance_tools.get_stock_price(symbol)


def render():
    # Add-ticker row.
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        new = st.text_input("Add ticker", key="wl_add",
                            label_visibility="collapsed", placeholder="Add ticker, e.g. TSLA")
    with c2:
        if st.button("Add", width="stretch"):
            if new.strip():
                watchlist.add(new)
                st.rerun()
    with c3:
        if st.button("↻ Refresh", width="stretch"):
            _quote.clear()
            st.rerun()

    tickers = watchlist.load()
    if not tickers:
        st.info("Your watchlist is empty. Add a ticker above.")
        return

    # Header row.
    h = st.columns([2, 2, 3, 3, 1])
    for col, label in zip(h, ["Ticker", "Price", "Change", "Day range", ""]):
        col.markdown(f"**{label}**")

    for sym in tickers:
        q = _quote(sym)
        r = st.columns([2, 2, 3, 3, 1])
        r[0].markdown(f"**{sym}**")
        if q.get("error"):
            r[1].markdown("—")
            r[2].markdown("_unavailable_")
            r[3].markdown("—")
        else:
            price = q["last_price"]
            chg, pct = q["change"], q["change_percent"]
            arrow = "🟢▲" if chg > 0 else "🔴▼" if chg < 0 else "⚪"
            cur = q.get("currency", "USD")
            r[1].markdown(f"{price:,.2f} {cur}")
            r[2].markdown(f"{arrow} {chg:+.2f} ({pct:+.2f}%)")
            r[3].markdown(f"{q['day_low']:,.2f} – {q['day_high']:,.2f}")
        if r[4].button("🗑", key=f"rm_{sym}", help=f"Remove {sym}"):
            watchlist.remove(sym)
            st.rerun()

    st.caption("Quotes cached ~60s · prices are delayed. Not financial advice.")
