"""Company fundamentals: valuation, profitability, health, and statements.

Pulls from yfinance .info (snapshot metrics) plus the income / balance /
cash-flow statements. Value scales differ by field, so each metric declares how
to format it (see FMT below). Notably yfinance returns most margins/growth as
decimals (0.27 -> 27%) but dividendYield already as a percent (0.36 -> 0.36%).
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

# metric key -> (label, format code)
#   money  : large currency, humanized ($1.23T)
#   pct    : decimal fraction -> percent (0.27 -> 27.2%)
#   pctraw : already a percent (0.36 -> 0.36%)
#   ratio  : plain multiple (x)
#   price  : per-share currency
#   int    : humanized count
GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Valuation": [
        ("marketCap", "Market Cap", "money"),
        ("enterpriseValue", "Enterprise Value", "money"),
        ("trailingPE", "P/E (TTM)", "ratio"),
        ("forwardPE", "Forward P/E", "ratio"),
        ("priceToBook", "P/B", "ratio"),
        ("priceToSalesTrailing12Months", "P/S", "ratio"),
        ("enterpriseToEbitda", "EV/EBITDA", "ratio"),
        ("beta", "Beta", "ratio"),
    ],
    "Profitability": [
        ("grossMargins", "Gross Margin", "pct"),
        ("operatingMargins", "Operating Margin", "pct"),
        ("profitMargins", "Net Margin", "pct"),
        ("returnOnEquity", "ROE", "pct"),
        ("returnOnAssets", "ROA", "pct"),
        ("revenueGrowth", "Revenue Growth (YoY)", "pct"),
        ("earningsGrowth", "Earnings Growth (YoY)", "pct"),
    ],
    "Financial Health": [
        ("totalRevenue", "Revenue (TTM)", "money"),
        ("freeCashflow", "Free Cash Flow", "money"),
        ("totalCash", "Total Cash", "money"),
        ("totalDebt", "Total Debt", "money"),
        ("debtToEquity", "Debt / Equity", "ratio"),
        ("currentRatio", "Current Ratio", "ratio"),
        ("quickRatio", "Quick Ratio", "ratio"),
    ],
    "Dividends & Per Share": [
        ("dividendYield", "Dividend Yield", "pctraw"),
        ("dividendRate", "Dividend Rate", "price"),
        ("payoutRatio", "Payout Ratio", "pct"),
        ("trailingEps", "EPS (TTM)", "price"),
        ("forwardEps", "Forward EPS", "price"),
        ("bookValue", "Book Value / Share", "price"),
        ("sharesOutstanding", "Shares Outstanding", "int"),
    ],
}

PROFILE_KEYS = ["longName", "symbol", "sector", "industry", "country", "website"]


def _humanize(n: float) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            return f"{sign}{n / div:.2f}{suf}"
    return f"{sign}{n:.0f}"


def fmt(value, code: str) -> str:
    """Format one metric value per its format code; '—' if missing."""
    if value is None or (isinstance(value, float) and value != value):  # None/NaN
        return "—"
    try:
        if code == "money":
            return "$" + _humanize(float(value))
        if code == "pct":
            return f"{float(value) * 100:.2f}%"
        if code == "pctraw":
            return f"{float(value):.2f}%"
        if code == "ratio":
            return f"{float(value):.2f}"
        if code == "price":
            return f"${float(value):.2f}"
        if code == "int":
            return _humanize(float(value))
    except (TypeError, ValueError):
        return str(value)
    return str(value)


def get_info(symbol: str) -> dict:
    """Raw .info dict for a ticker (snapshot fundamentals + profile)."""
    try:
        return yf.Ticker(symbol.upper()).info or {}
    except Exception:  # noqa: BLE001
        return {}


def get_statements(symbol: str) -> dict[str, pd.DataFrame]:
    """Annual income statement, balance sheet, and cash-flow statement."""
    t = yf.Ticker(symbol.upper())
    out: dict[str, pd.DataFrame] = {}
    for name, attr in (("Income Statement", "income_stmt"),
                       ("Balance Sheet", "balance_sheet"),
                       ("Cash Flow", "cashflow")):
        try:
            df = getattr(t, attr)
            out[name] = df if df is not None else pd.DataFrame()
        except Exception:  # noqa: BLE001
            out[name] = pd.DataFrame()
    return out


def revenue_income_trend(income_stmt: pd.DataFrame) -> pd.DataFrame:
    """Tidy Revenue + Net Income by fiscal year for a trend bar chart."""
    if income_stmt is None or income_stmt.empty:
        return pd.DataFrame()
    rows = {"Total Revenue": "Revenue", "Net Income": "Net Income"}
    data = {}
    for src, label in rows.items():
        if src in income_stmt.index:
            data[label] = income_stmt.loc[src]
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df.index = [c.year if hasattr(c, "year") else c for c in df.index]
    return df.dropna(how="all").sort_index()


def format_statement(df: pd.DataFrame) -> pd.DataFrame:
    """Humanize a statement DataFrame for display (columns -> fiscal years)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [c.date().isoformat() if hasattr(c, "date") else str(c) for c in out.columns]
    return out.map(lambda v: _humanize(v) if isinstance(v, (int, float)) and v == v else "—")
