"""skibidiBrain — Streamlit stock-research app (entry point).

Hybrid design:
  * Live numbers (price, financials, performance) -> OpenAI tool-calling -> yfinance
  * News / analysis / sentiment -> RAG over embedded Yahoo + Finnhub news

Layout (see README for the full tree):
  app.py            this file — config, sidebar, tab dispatch
  views/            one module per page (chart, fundamentals, chat)
  rag/              retrieval + news sources (retriever, news_finnhub)
  services/         data + logic (finance_tools, fundamentals, charting, chat_engine)

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from rag import news_finnhub, retriever
from services import watchlist
from views import (
    chart_view,
    chat_view,
    fundamentals_view,
    prediction_view,
    watchlist_view,
)

load_dotenv()

st.set_page_config(page_title="skibidiBrain", page_icon="🧠", layout="centered")


@st.cache_resource
def get_client() -> OpenAI:
    return OpenAI()


@st.cache_resource(show_spinner="Indexing news…")
def get_news_index(symbols_key: str):
    return retriever.build_index(get_client(), symbols_key.split(","))


# --- Header + sidebar -----------------------------------------------------

st.title("🧠 skibidiBrain")
st.caption("Live data via yfinance + news retrieval (RAG). Not financial advice.")

with st.sidebar:
    st.header("Settings")
    if not os.getenv("OPENAI_API_KEY"):
        key = st.text_input("OpenAI API key", type="password")
        if key:
            os.environ["OPENAI_API_KEY"] = key

    # Optional Finnhub key for historical news fallback.
    fh_key = st.text_input("Finnhub API key (optional)", type="password", value="",
                           help="Enables ~1yr of historical news. Free key at finnhub.io/register")
    if fh_key:
        os.environ["FINNHUB_API_KEY"] = fh_key
    if news_finnhub.has_key():
        st.caption("📰 News: Yahoo (recent) + Finnhub (historical) ✅")
    else:
        st.caption("📰 News: Yahoo only (recent ~1-2 wks). Add Finnhub for history.")

    tickers_raw = st.text_input("Tickers to index for news",
                                value=", ".join(watchlist.load()))
    if st.button("Build / refresh news index"):
        get_news_index.clear()
    st.markdown("---")
    st.markdown("**Examples**")
    st.markdown(
        "- What's NVDA trading at?\n"
        "- Compare AAPL and MSFT P/E\n"
        "- Why was AAPL bearish on June 8?\n"
        "- How did MSFT perform this year?"
    )

if not os.getenv("OPENAI_API_KEY"):
    st.info("Add your OpenAI API key in the sidebar to start.")
    st.stop()

# --- Shared state ---------------------------------------------------------

client = get_client()
symbols = [s.strip().upper() for s in tickers_raw.split(",") if s.strip()]
index = get_news_index(",".join(symbols))
default_symbol = symbols[0] if symbols else "AAPL"

if index.is_empty():
    st.warning("No news indexed yet for these tickers (Yahoo may be rate-limiting).")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Pages (tabs) ---------------------------------------------------------

watchlist_tab, chart_tab, fundamentals_tab, predict_tab, chat_tab = st.tabs(
    ["⭐ Watchlist", "📊 Chart", "🏦 Fundamentals", "🔮 Predict", "💬 Chat"]
)

with watchlist_tab:
    watchlist_view.render()

with chart_tab:
    chart_view.render(default_symbol)

with fundamentals_tab:
    fundamentals_view.render(default_symbol)

with predict_tab:
    prediction_view.render(default_symbol)

with chat_tab:
    chat_view.render(client, index)
