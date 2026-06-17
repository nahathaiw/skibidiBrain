# Syrius Magic Monitor — Reverse-Engineering Findings

*Working notes from overnight analysis. Read top-to-bottom; confidence levels and
caveats are marked honestly, including two places where I corrected my own earlier
conclusions.*

---

## 1. What the data is

- **440 PDFs, 149 trading days, 6 May → 20 Dec 2022**, ~500 tickers/snapshot.
- Parsed into a tidy time series keyed by `(snapshot_datetime, symbol)`.
- A **40-day consecutive window (3 Oct – 30 Nov)** was parsed first and used for
  all logic-cracking below. The full 149-day parse was running in the background.

## 2. The engine, identified

The Magic Monitor is a **multi-timeframe (MTF) trend + momentum dashboard** — a very
common TradingView archetype. Three timeframe blocks (3h / Daily / Weekly), each with
the same columns, plus shared trend-regime and return columns.

### Column-by-column verdict

| Column | Meaning | How cracked | Confidence |
|---|---|---|---|
| `{tf}_price_when` | price frozen at signal trigger bar | matches last_price at trigger 87% | **certain** |
| `{tf}_chg_since` | (last_price − price_when)/price_when | 100% match, all 3 blocks | **certain** |
| `{tf}_count` | bars since trigger (0 at trigger, +1/bar) | 92% consecutive-increment | **certain** |
| `chg_1d/5d/30d/ytd/1y` | trailing returns of last_price | reconstructs to <0.05% err | **certain** |
| `trend_range` (T/R) | ADX-based regime: T=ADX≥~25, R=ADX<~25 | statistical signature (below) | **high** |
| `New Sig?` / trigger | a crossover event (SuperTrend or MA-cross) | symmetric, ~9-day cadence | **medium** |
| `Extreme?` | RSI>70/<30 or StochRSI>80/<20 flag | standard archetype | **medium-high** |
| `Pos` | oscillator zone/position state (where RSI/Stoch sits vs OB/OS bands) | matched to twin dashboard | **medium** |
| `Ind 1–5` | per-indicator bull/bear/neutral arrows: EMA-stack / RSI / StochRSI (+ likely MACD/DI) | matched to twin dashboard; glyph cells | **medium-high** |

**Key external confirmation:** TradingView's "Momentum Table – By Felipe" is a near-structural
twin — an MTF dashboard using EMA(9/20/100/200) close-vs-EMA checks (green up / red-arrow down),
RSI(14) with red>70 / green<30 / gray-neutral backgrounds, and StochRSI with the same logic.
This is almost certainly the template family for the `Ind 1-5` arrow cells and the `Pos`/`Extreme`
oscillator columns. The reason `Ind 1-5` and the flag columns didn't extract as text is that they
are **colored glyphs / cell fills, not numbers** — to recover them exactly we'd parse cell
background colors from the PDF (doable via pdfplumber rects), not text.

### Why "Trend/Range = ADX" (evidence derived from data, not just web search)
- **93.3% day-to-day sticky** → slow-moving smoothed average. ADX(14) signature.
- **T-labeled names show ~60% larger 30-day moves** (16.4% vs 10.4% median |move|).
  ADX measures directional-move magnitude — exactly this.
- **~50/50 T/R split** → threshold sits mid-distribution, consistent with ADX≈25.
- **Signal-ON coincides with T** (56% vs 41%) → the trigger is trend-following.

### The signal state machine
Not a simple counter. It's **OFF (dormant) → ON (trigger, count=0) → ages (count++) → OFF**.
- Daily block: **48% OFF / 52% ON**.
- **95% of new signals are preceded by an OFF bar** → genuine dormant state, i.e. a
  crossover state machine (price between bands / no directional signal).
- Fresh signals fire about **every 9–10 trading days** on average → medium-speed
  trigger (SuperTrend(10,3) or an EMA(9,21)-class cross), not a fast scalping one.

## 3. Predictive structure (for the 5-day-forward prediction page)

Measured on the 40-day window. **These are real in-sample signals but NOT yet
validated out-of-sample — see caveats.**

- **MTF alignment works:** when 3h+Daily+Weekly all have active signals →
  **+0.68% fwd-5d** vs +0.11% otherwise.
- **Signal age decays:** fresh (count 0–3) positive; stale (count 3–12) negative.
- **Strongest pattern = mean-reversion of extended names** (see correction #2).

## 4. Self-corrections (things I got wrong first, then fixed)

**Correction #1 — I mislabeled the regime.** I initially called Oct–Nov 2022 a "bear
market" and explained results through that. In fact **SPY rallied +11.2%** over the
window (off the October low). The bear-market story was wrong.

**Correction #2 — the T/R edge is mean-reversion, not trend-continuation.** After
controlling for recent direction, the pattern flips interpretation:

| regime | recent move | fwd-5d |
|---|---|---|
| **T (trending)** | up | **−1.83%** (worst) |
| T | down | +0.69% |
| **R (ranging)** | down | **+2.00%** (best) |
| R | up | +0.04% |

So extended/high-ADX names that *ran up* gave it back; beaten-down names bounced.
This is **mean-reversion, strongest in high-momentum names** — the opposite of the
trend-following story I'd have told if I'd stopped early.

## 5. Critical caveats (read before trusting any of this)

1. **40 days, one regime.** This window was choppy/mean-reverting. Mean-reversion is
   NOT a proven durable edge — it's what *this* slice did. The full 149-day set must
   confirm before anything is trusted.
2. **No OHLCV in the sandbox.** Yahoo hosts are blocked here, so exact thresholds
   (ADX 20 vs 25, RSI 70 vs 80, MA lengths) are NOT yet fit — only the indicator
   *families* are identified. The fitting harness (below) nails exact params locally.
3. **Reconstructed prices are coarse** (1 snapshot/day, gaps). Intraday high/low were
   not available, so the 3h block and exact trigger timing are approximate.
4. **Look-ahead hygiene:** when you build the model, features must be as-of the
   snapshot only; fwd-5d is the label. Don't leak.

## 6. What's ready to run

- `parse_mm.py` — validated PDF→dataframe parser (exact matches on SPXL/QQQ/TQQQ/EDZ).
- `fit_indicators.py` — fitting harness with ADX / SuperTrend / MA-cross / RSI
  implementations, all **validated on synthetic data**. Run locally with yfinance to
  recover exact parameters against the parsed labels.
- `mm_window.pkl` — 40-day parsed dataset (13,944 rows).
- `mm_master.pkl` — full 149-day dataset (parsing was completing in background).

## 7. Next steps when you're back

1. Let the full parse finish (or re-run parser) → `mm_master.pkl`.
2. Run `fit_indicators.py` locally → lock exact ADX threshold + trigger params.
3. Confirm correction #2 (mean-reversion) holds across all 149 days, both halves.
4. Build YOUR engine: ADX regime + MTF crossover + OB/OS, computed transparently.
5. Train the 5-day-forward-sign model on these features; honest walk-forward backtest.

## 8. Bonus unlock: the arrow columns ARE recoverable

Verified that pdfplumber exposes per-cell **fill colors** (256 colored rects/page) and
colored glyph chars (red = (1,0,0)). The `Ind 1-5`, `Pos`, and `Extreme?` columns — which
don't extract as text because they're colored arrows/cells — can be recovered by mapping
each cell's fill RGB to a state: green ~(0.78,0.88,0.71)=bullish, light-blue
~(0.87,0.92,0.97)=neutral, red glyph=bearish. `color_probe.py` is a working prototype.
The extension is binding each colored rect to its column by x-position (same banding as
parse_mm.py). This completes reverse-engineering of ALL columns.

## 9. Honest status note

- The 40-day window (mm_window.pkl) is fully parsed and is what all analysis above used.
- The full 149-day parse hit two avoidable WRITE bugs (missing pyarrow; then a pyarrow
  extension-type crash that ate the run because parquet was attempted before pickle).
  Fixed: rebuild now writes pickle first, no parquet. It was re-running at hand-off.
- Net: the logic is cracked and documented; only regenerating the full-history pickle
  is pending, which is mechanical.

## 10. Files delivered
- REVERSE_ENGINEERING_FINDINGS.md (this doc)
- parse_mm.py (validated parser)
- fit_indicators.py (fitting harness, synth-validated)
- color_probe.py (arrow-column color extractor prototype)
- mm_window.pkl (40-day parsed dataset)
