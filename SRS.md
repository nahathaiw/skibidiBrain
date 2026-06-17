# Software Requirements Specification (SRS)

**Project:** 🧠 skibidiBrain — AI-Powered Stock Research Dashboard
**Document type:** Software Requirements Specification (IEEE-830 style)
**Version:** 1.0
**Date:** 2026-06-17
**Author:** Nahathai Wonganawat

Traces to [URS.md](URS.md). For design detail see
[systemarchitecture.md](systemarchitecture.md) and [systemflow.md](systemflow.md).

---

## 1. Introduction

### 1.1 Purpose
Specify the functional and non-functional requirements of skibidiBrain, a
Streamlit web application that combines live market data, technical charts,
company fundamentals, a multi-timeframe screener, an experimental prediction
signal, and a retrieval-augmented (RAG) chatbot.

### 1.2 Scope
skibidiBrain runs as a single-page, tab-based Streamlit app. It reads market data
and news from external APIs (Yahoo Finance via `yfinance`, Finnhub) and uses
OpenAI for chat, embeddings, and reranking. It does **not** execute trades, hold
user funds, or provide financial advice.

### 1.3 Definitions
| Term | Meaning |
|------|---------|
| RAG | Retrieval-Augmented Generation — retrieve relevant text, feed to the LLM |
| MTF | Multi-timeframe (3h / Daily / Weekly) |
| OHLCV | Open/High/Low/Close/Volume bars |
| ADX | Average Directional Index — trend strength (regime) |
| RSI | Relative Strength Index — momentum / overbought-oversold |
| Tool-calling | LLM invoking a defined function to fetch live data |
| BM25 | Lexical ranking function for keyword search |
| RRF | Reciprocal Rank Fusion — merge ranked lists |

### 1.4 References
IEEE 830; URS.md; systemarchitecture.md; systemflow.md; OpenAI API; yfinance;
Finnhub API; prediction/REVERSE_ENGINEERING_FINDINGS.md.

## 2. Overall description

### 2.1 Product perspective
A self-contained client app. Three internal layers — `views/` (UI), `services/`
(logic/data), `rag/` (retrieval) — with dependencies pointing downward only.
External services: yfinance (Yahoo), OpenAI, Finnhub.

### 2.2 Product functions (summary)
Watchlist management · candlestick charting · fundamentals · MTF screener ·
5-day prediction · RAG + tool-calling chatbot.

### 2.3 User classes
Retail investor, student/learner, power user (see URS §3).

### 2.4 Operating environment
Python 3.12; Streamlit ≥1.40; modern web browser; internet access to
`*.finance.yahoo.com`, `api.openai.com`, `finnhub.io`.

### 2.5 Design & implementation constraints
- Python, Streamlit, Plotly, pandas, numpy; OpenAI & yfinance SDKs.
- In-memory NumPy vector store (no external vector DB).
- BM25 implemented in-house (no extra dependency).
- Secrets via environment/`.env` or runtime sidebar input; never committed.

### 2.6 Assumptions & dependencies
Valid OpenAI key required; Finnhub key optional; free data sources are
rate-limited and delayed; yfinance reflects Yahoo's (unofficial) availability.

## 3. External interface requirements

### 3.1 User interfaces
Single Streamlit page, title "🧠 skibidiBrain", with a sidebar (API keys,
news-index tickers, examples) and six tabs: **Watchlist, Monitor, Chart,
Fundamentals, Predict, Chat**.

### 3.2 Software interfaces
| Interface | Use | Auth |
|-----------|-----|------|
| OpenAI Chat Completions | chatbot + reranking (`gpt-4o-mini`) | `OPENAI_API_KEY` |
| OpenAI Embeddings | news vectors (`text-embedding-3-small`) | `OPENAI_API_KEY` |
| yfinance (Yahoo) | quotes, OHLCV, fundamentals, recent news | none |
| Finnhub `company-news` | historical news | `FINNHUB_API_KEY` (optional) |

### 3.3 Data / file interfaces
`watchlist.json` (named lists + active), `.env` (secrets),
`.streamlit/config.toml` (local port), `services/presets.py` (Magic Monitor
tickers extracted from the source PDF).

## 4. Functional requirements

> ID scheme **FR-<area>-<n>**. Each traces to one or more URS items.

### 4.1 Watchlist (traces UR-01..05)
- **FR-WL-1** The system shall persist named ticker lists to disk and reload them on start.
- **FR-WL-2** The system shall display, per ticker, last price, absolute & % change, and day low–high.
- **FR-WL-3** The system shall let the user add a ticker (uppercased, de-duplicated) and remove a ticker.
- **FR-WL-4** The system shall let the user select an active list from all available lists.
- **FR-WL-5** The system shall provide a built-in "Magic Monitor" preset list and a "My Watchlist" default, auto-migrating any legacy single-list file.
- **FR-WL-6** The active list shall seed the default tickers used for the news index.

### 4.2 Charting (traces UR-06..09)
- **FR-CH-1** The system shall render a candlestick chart for a user-entered ticker.
- **FR-CH-2** The system shall support timeframes 45M, 3h, 1D, 1W, resampling 15m→45M and 1h→3h where Yahoo lacks a native interval.
- **FR-CH-3** The system shall offer a 2×2 grid view (1W, 1D, 3h, 45M) of the same ticker.
- **FR-CH-4** The system shall optionally overlay SMA, EMA, Bollinger Bands and add Volume, RSI, MACD panels.

### 4.3 Fundamentals (traces UR-10..12)
- **FR-FN-1** The system shall display valuation, profitability, financial-health, and dividend metrics, formatted scale-aware ($T/B/M, %).
- **FR-FN-2** The system shall display the income statement, balance sheet, and cash-flow statement.
- **FR-FN-3** The system shall plot a revenue & net-income by-year trend when available.

### 4.4 Monitor / MTF screener (traces UR-13..15)
- **FR-MN-1** The system shall compute, per ticker and per timeframe (3h/D/W): trend signal direction, bars since the last trigger, and % change since trigger (EMA(9/21) crossover).
- **FR-MN-2** The system shall compute shared columns: ADX-based regime (T≥25 / R<25), RSI, an OB/OS flag, and trailing returns 1D/5D/30D/YTD/1Y.
- **FR-MN-3** The system shall group rows by sector/theme with a header per group in a defined order.
- **FR-MN-4** The system shall let the user choose which list to scan and refresh on demand.

### 4.5 Prediction (traces UR-16..18)
- **FR-PR-1** The system shall produce a 5-day-forward signal ∈ {Bullish, Bearish, Neutral} with an expected % move and a strength score.
- **FR-PR-2** The signal shall be computed transparently: ADX regime × recent 5-day direction (mean-reversion table), nudged by RSI extremes and MTF trend alignment.
- **FR-PR-3** The system shall display the contributing factors (ADX, recent move, RSI, MTF) for explainability.
- **FR-PR-4** The system shall prominently mark the prediction experimental, in-sample, and not financial advice.

### 4.6 Chatbot (traces UR-19..23)
- **FR-CB-1** The system shall accept free-text questions and stream/return a natural-language answer.
- **FR-CB-2** For numeric questions the system shall call live-data tools and never fabricate figures.
- **FR-CB-3** The system shall expose tools: `get_stock_price`, `get_company_info`, `get_financials`, `get_historical_performance`, `get_price_on_date`, `get_news_on_date`, `get_price_prediction`.
- **FR-CB-4** For date-specific questions the system shall confirm the actual price move via `get_price_on_date` and source news via context or `get_news_on_date`.
- **FR-CB-5** The system shall retrieve news via a hybrid pipeline: BM25 + dense embeddings fused by RRF, ticker-filtered, recency-weighted, de-duplicated, then LLM-reranked.
- **FR-CB-6** The system shall display the news sources used (citations) and resolve relative dates against the current date.
- **FR-CB-7** Buy/sell/hold or forecast answers shall include a "not financial advice" statement.

### 4.7 Configuration & secrets (traces UR-24..25)
- **FR-CFG-1** The system shall read `OPENAI_API_KEY` and optional `FINNHUB_API_KEY` from environment/`.env` or sidebar input.
- **FR-CFG-2** The system shall function with only the OpenAI key, degrading news to Yahoo's recent feed when Finnhub is absent.
- **FR-CFG-3** Secret files (`.env`, `watchlist.json`) shall be excluded from version control.

## 5. Non-functional requirements

### 5.1 Performance (traces UR-26)
- **NFR-P-1** Cached live tool data (15 min), quotes (60 s), chart data (5 min), fundamentals (1 h), and the news index (per ticker set) to avoid redundant calls.
- **NFR-P-2** Ticker lists used for quoting/scanning shall be capped (Magic Monitor preset = 25 of ~368) to stay within free-tier rate limits.

### 5.2 Reliability / robustness
- **NFR-R-1** External-call failures (Yahoo/OpenAI/Finnhub) shall be caught and surfaced as a message or empty result, never an app crash.
- **NFR-R-2** Missing data (bad ticker, no news, short history) shall be handled gracefully with user-visible notices.

### 5.3 Security & privacy (traces UR-24)
- **NFR-S-1** API keys shall never be written to tracked files or logs.
- **NFR-S-2** `.gitignore` shall cover `.env`, `.venv/`, caches, and `watchlist.json`.

### 5.4 Usability (traces UR-27)
- **NFR-U-1** A "not financial advice" disclaimer shall appear on the Predict page, in relevant chat answers, and in the app caption.
- **NFR-U-2** Each page shall be reachable in one click via tabs; controls shall have sensible defaults.

### 5.5 Maintainability
- **NFR-M-1** Layered architecture (views/services/rag) with downward-only dependencies.
- **NFR-M-2** New page = one `views/*` module + one tab line; new live tool = one function + schema entry.

### 5.6 Portability
- **NFR-PO-1** Pure-Python dependencies from `requirements.txt`; deployable to Streamlit Community Cloud without code changes (local-only port config excluded).

## 6. Data requirements

| Data | Source | Shape / store |
|------|--------|---------------|
| Quotes / OHLCV | yfinance | pandas DataFrame (cached) |
| Fundamentals | yfinance `.info`, statements | dict + DataFrames |
| News | yfinance, Finnhub | `NewsChunk(text,title,publisher,link,published,ticker)` |
| News index | derived | `NewsIndex(chunks, matrix, bm25, symbols, aliases)` |
| Watchlists | local JSON | `{active, lists:{name:[tickers]}}` |
| Magic Monitor preset | source PDF (one-time parse) | `services/presets.py` list |

## 7. Constraints, risks & mitigations

| Risk | Mitigation |
|------|------------|
| Yahoo rate-limiting / outages | aggressive caching; list-size caps; graceful errors |
| Historical news only ~1–2 wks (Yahoo) | optional Finnhub fallback (~1 yr) |
| Prediction not validated out-of-sample | clearly labeled experimental; factors shown |
| LLM cost on a public deploy | visitors supply their own key; spend limits advised |
| Secret leakage | gitignore + pre-commit scan; keys only in `.env`/sidebar |

## 8. Acceptance criteria (sample)

- AC-1: Adding a ticker in Watchlist persists after an app restart.
- AC-2: Asking "what's NVDA trading at?" returns a fresh price via a tool call.
- AC-3: Asking "why was AAPL bearish on June 8?" reports the real % move and dated news.
- AC-4: Monitor renders tickers grouped under sector headers (e.g. ETF, AI, Cloud).
- AC-5: Predict shows a signal, expected move, strength, factor list, and the disclaimer.
- AC-6: `git ls-files` contains no `.env` or `watchlist.json`.

## 9. Future enhancements (non-binding)

Full-article news scraping; walk-forward backtest of the prediction signal;
streaming chat; news markers on charts; deploy with a live demo link; peer
comparison; recover the original Magic Monitor `Ind 1–5` glyph columns via PDF
color parsing.
