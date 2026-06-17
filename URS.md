# User Requirements Specification (URS)

**Project:** 🧠 skibidiBrain — AI-Powered Stock Research Dashboard
**Document type:** User Requirements Specification
**Version:** 1.0
**Date:** 2026-06-17
**Author:** Nahathai Wonganawat

---

## 1. Purpose

This document states **what users need** from skibidiBrain, in business/user terms
(not implementation detail). It is the basis for the Software Requirements
Specification ([SRS.md](SRS.md)), which defines how these needs are met.

## 2. Background

Retail investors and students researching stocks must juggle several tools: a
price chart, a fundamentals page, a news reader, and a notebook of tickers they
follow. Existing AI stock chatbots tend to either invent figures or only skim
headlines. skibidiBrain unifies these into one dashboard where **numbers are
always fetched live** and **news is retrieved and cited**, plus an experimental
signal derived from a reverse-engineered trading dashboard.

## 3. Intended users

| User | Description | Key goals |
|------|-------------|-----------|
| **Retail investor** | Follows a handful of stocks, wants quick context | Track watchlist, read charts, understand news-driven moves |
| **Student / learner** | Studying markets & indicators | See transparent indicator logic, ask questions in plain English |
| **Power user / tinkerer** | Comfortable with technical analysis | Multi-timeframe screener, prediction signal, custom ticker lists |

## 4. User requirements

> Priority: **M** = Must-have, **S** = Should-have, **C** = Could-have.

### 4.1 Watchlist & ticker management
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-01 | keep a personal list of tickers that survives app restarts | M |
| UR-02 | see live price, change, % change and day range for each | M |
| UR-03 | add and remove tickers easily | M |
| UR-04 | switch between multiple named lists (e.g. my own vs a preset) | S |
| UR-05 | have a preset list built from the Magic Monitor reference | S |

### 4.2 Charting
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-06 | view candlestick charts for any ticker | M |
| UR-07 | choose the timeframe (45M, 3h, 1D, 1W) | M |
| UR-08 | see several timeframes side-by-side at once | S |
| UR-09 | toggle technical indicators (SMA, EMA, Bollinger, Volume, RSI, MACD) | S |

### 4.3 Fundamentals
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-10 | see a company's valuation, profitability and health metrics | M |
| UR-11 | view income, balance-sheet and cash-flow statements | S |
| UR-12 | see a revenue & net-income trend at a glance | C |

### 4.4 Multi-timeframe monitor (screener)
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-13 | scan a list of tickers across 3h / Daily / Weekly in one table | S |
| UR-14 | see trend direction, regime (trending/ranging), RSI and returns | S |
| UR-15 | have the table grouped by sector/theme with headers | S |

### 4.5 Prediction
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-16 | get a 5-day-forward signal (bullish/bearish/neutral) for a ticker | S |
| UR-17 | understand WHY the signal was produced (transparent factors) | M |
| UR-18 | be clearly warned it is experimental and not financial advice | M |

### 4.6 Conversational research (chat)
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-19 | ask questions about stocks in plain English | M |
| UR-20 | get live numbers without the bot inventing them | M |
| UR-21 | ask why a stock moved on a specific past date and get a grounded answer | S |
| UR-22 | see the news sources behind an answer (citations) | S |
| UR-23 | ask for a forecast / outlook and get the prediction signal | C |

### 4.7 Cross-cutting
| ID | As a user, I want to… | Priority |
|----|------------------------|----------|
| UR-24 | provide my own API keys (and not have them committed/leaked) | M |
| UR-25 | use the app even without optional keys (graceful degradation) | S |
| UR-26 | have responses feel fast (no needless re-fetching) | S |
| UR-27 | always see a "not financial advice" disclaimer where relevant | M |

## 5. Assumptions & constraints (user view)

- Users have an **OpenAI API key**; a Finnhub key is optional (historical news).
- Market data is **delayed** (free Yahoo Finance), not real-time/tick data.
- The app is for **education/research**, **not** trade execution or advice.
- Free data sources have **rate limits**; very large ticker lists are capped.

## 6. Out of scope

Order execution / brokerage integration; real-time streaming quotes; portfolio
accounting (P&L, tax lots); user accounts/authentication; mobile-native apps;
guaranteed-accurate price predictions.

## 7. Success criteria

- A user can go from "open app" to "understand a stock" (price, fundamentals,
  recent news, a view on direction) **without leaving the app**.
- The chatbot never fabricates a price/metric — numbers trace to a live fetch.
- Secrets never appear in the repository.
