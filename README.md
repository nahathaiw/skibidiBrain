<div align="center">

# 🧠 skibidiBrain

### Your AI-powered stock research command center

*Live market data · candlestick charts · company fundamentals · a smart watchlist ·
and a RAG chatbot that actually knows **why** a stock moved on a given day.*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?logo=openai&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)
![yfinance](https://img.shields.io/badge/yfinance-Yahoo!-6001D2)
![Finnhub](https://img.shields.io/badge/Finnhub-news-1DB954)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Not Financial Advice](https://img.shields.io/badge/⚠️-Not%20Financial%20Advice-red)

</div>

---

## ✨ Why skibidiBrain?

Most stock chatbots either make up numbers or only read headlines. skibidiBrain
splits the problem in two:

> 🔢 **Numbers are fetched live** (never hallucinated) via tool-calling.
> 📰 **News is retrieved** with a hybrid search engine and cited.

Ask *"why was AAPL bearish on June 8?"* and it confirms the **real −1.89% move**,
then pulls the **actual news from that day** to explain it.

---

## 🚀 Features

| | Tab | What it does |
|---|-----|--------------|
| ⭐ | **Watchlist** | Multiple named lists (your own + a *Magic Monitor* preset) with live quotes (price · change · day range). Survives restarts and seeds the news index. |
| 🪄 | **Monitor** | Multi-timeframe screener (**3h / Daily / Weekly**) — trend signal, regime (ADX T/R), RSI, returns — **grouped by sector/theme** (ETF · AI · Cloud · Semiconductors · Biotech · …). |
| 📊 | **Chart** | TradingView-style candlesticks. Timeframes **45M · 3h · 1D · 1W**, single or **2×2 grid**. Indicators: SMA, EMA, Bollinger, Volume, RSI, MACD. |
| 🏦 | **Fundamentals** | Valuation, profitability, financial health & dividends · revenue/income trend · full income / balance / cash-flow statements. |
| 🔮 | **Predict** | Experimental 5-day-forward signal (Bullish/Bearish/Neutral) from a transparent mean-reversion heuristic — ADX regime × recent move, nudged by RSI + multi-timeframe trend. |
| 💬 | **Chat** | Hybrid **RAG + tool-calling** chatbot. Handles live numbers, news/sentiment, **date-specific**, and **forecast** questions — with citations. |

---

## 📸 Screenshots

> _Add your own captures to `assets/` (filenames below) and they'll appear here.
> On macOS: **Cmd+Shift+4**, select the area, then move the PNG into `assets/`._

| ⭐ Watchlist | 📊 Chart |
|:---:|:---:|
| ![Watchlist](assets/watchlist.png) | ![Chart](assets/chart.png) |
| 🏦 **Fundamentals** | 💬 **Chat** |
| ![Fundamentals](assets/fundamentals.png) | ![Chat](assets/chat.png) |

---

## 🧩 How the brain works

```
            ┌──────────────────────── You ────────────────────────┐
            │   "Why was AAPL bearish on June 8?"                   │
            └───────────────────────┬──────────────────────────────┘
                                    ▼
        ┌─────────────── Hybrid News RAG ───────────────┐
        │  BM25 (keywords) + embeddings (meaning)        │
        │  → ticker filter → recency → dedup → rerank    │
        └───────────────────────┬───────────────────────┘
                                ▼  cited context
        ┌──────────────── OpenAI (tool-calling) ─────────┐
        │  get_price_on_date   → real % move that day    │
        │  get_news_on_date    → historical news (Finnhub)│
        │  get_price_prediction → 5-day signal           │
        │  get_stock_price / company_info / financials … │
        └───────────────────────┬───────────────────────┘
                                ▼
                  💬 grounded, cited answer
```

📖 Docs: **[systemflow.md](systemflow.md)** (request flows) ·
**[systemarchitecture.md](systemarchitecture.md)** (component design) ·
**[RAG.md](RAG.md)** (retrieval deep dive) ·
**[SRS.md](SRS.md)** / **[URS.md](URS.md)** (requirements)

---

## ⚡ Quickstart

```bash
git clone <your-repo-url> skibidiBrain && cd skibidiBrain
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your OPENAI_API_KEY (Finnhub optional)
streamlit run app.py          # → http://localhost:8600
```

### 🔑 API keys

| Key | Required | Purpose | Free key |
|-----|:--------:|---------|----------|
| `OPENAI_API_KEY` | ✅ | Chat model + embeddings | [platform.openai.com](https://platform.openai.com/api-keys) |
| `FINNHUB_API_KEY` | ➖ | ~1 year of historical news | [finnhub.io/register](https://finnhub.io/register) |

Set them in `.env` **or** paste them into the sidebar at runtime.

---

## 🗂️ Project structure

```
skibidiBrain/
├── app.py                      # entry point: config · sidebar · shared state · tabs
├── views/                      # 🖼️ UI — one module per page
│   ├── watchlist_view.py       #   ⭐ multi-list watchlist + live quotes
│   ├── monitor_view.py         #   🪄 multi-timeframe screener, sector-grouped
│   ├── chart_view.py
│   ├── fundamentals_view.py
│   ├── prediction_view.py
│   └── chat_view.py
├── rag/                        # 🔍 retrieval
│   ├── retriever.py            #   hybrid pipeline: BM25 + cosine + rerank
│   ├── bm25.py                 #   dependency-free lexical search
│   └── news_finnhub.py         #   Finnhub historical-news fallback
└── services/                   # ⚙️ logic + data
    ├── finance_tools.py        #   yfinance tools + OpenAI tool schemas
    ├── fundamentals.py
    ├── charting.py             #   OHLC fetch/resample + Plotly figures
    ├── chat_engine.py          #   system prompt + tool-calling loop
    ├── prediction.py           #   5-day-forward mean-reversion signal
    ├── magic_monitor.py        #   multi-timeframe screener engine
    ├── sectors.py              #   sector / theme classification
    ├── presets.py              #   Magic Monitor preset tickers (from the PDF)
    └── watchlist.py            #   persistent multi-list watchlist
```

**Design rule:** `views/` (UI) → `services/` & `rag/` (logic) → external APIs.
Dependencies only ever point downward.

---

## 🛠️ Tech stack

| Layer | Tech |
|-------|------|
| UI | Streamlit · Plotly |
| LLM | OpenAI (`gpt-4o-mini` chat · `text-embedding-3-small`) |
| Market data | yfinance (Yahoo Finance) |
| News | Yahoo + Finnhub |
| Retrieval | In-memory NumPy vectors · custom BM25 · RRF fusion · LLM rerank |

---

## 🧠 RAG, in one breath

Hybrid **BM25 + dense embeddings**, fused with Reciprocal Rank Fusion, then
**ticker-filtered**, **recency-weighted**, **de-duplicated**, and **LLM-reranked** —
no external vector database required.

---

## 🗺️ Roadmap ideas

- [ ] Full-article scraping + chunking for deeper news answers
- [ ] News markers on the candlestick chart
- [ ] "Open in Chart" jump from the watchlist
- [ ] Streaming chat responses
- [ ] Peer comparison view

---

## 📄 License

Released under the [MIT License](LICENSE) © 2026 Nahathai Wonganawat.

---

<div align="center">

⚠️ **Disclaimer:** skibidiBrain is an educational project. It is **not financial advice.**

Made with 🧠 + ☕ · Powered by OpenAI, yfinance & Finnhub

</div>
