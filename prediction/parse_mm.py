"""
Syrius Magic Monitor PDF parser (v2 - structural).

Each data row (identified by a US.XXXX symbol) contains, left-to-right:
  symbol,
  [3h]    count_or_pos, price_when, chg_since%,
  [daily] count_or_pos, price_when, chg_since%,
  [weekly]count_or_pos, price_when, chg_since%,
  last_price, trend_range(T/R),
  chg_1d%, chg_5d%, chg_30d%, chg_ytd%, chg_1y%

When a block has no active signal the price_when/chg are 0/0.0% but STILL
present as tokens, so token count per row is stable. Returns (trailing 5 %)
and the T/R flag anchor the right side; we parse inward from both ends.
"""
import re
import pdfplumber
import pandas as pd
from pathlib import Path

SYMBOL_RE = re.compile(r'^US\.[A-Z0-9.]+$')
PCT_RE = re.compile(r'^-?\d+\.?\d*%$')
NUM_RE = re.compile(r'^-?\d+\.?\d*$')
TR_RE = re.compile(r'^[TR]$')

def _rows_by_y(words):
    rows = {}
    for w in words:
        rows.setdefault(round(w['top']), []).append(w)
    return rows

def parse_row(toks):
    syms = [w for w in toks if SYMBOL_RE.match(w['text'])]
    if not syms:
        return None
    sym = syms[0]['text']
    sx = syms[0]['x0']
    right = sorted([w for w in toks if w['x0'] > sx + 1], key=lambda w: w['x0'])
    vals = [w['text'] for w in right]
    if len(vals) < 6:
        return None

    # ---- right side: trailing 5 percentages = returns ----
    returns = []
    j = len(vals) - 1
    while j >= 0 and len(returns) < 5 and PCT_RE.match(vals[j]):
        returns.insert(0, vals[j]); j -= 1
    if len(returns) != 5:
        return None
    # remaining vals[0..j] hold: blocks + last_price + T/R
    mid = vals[:j+1]

    # ---- find T/R flag (rightmost single T or R) ----
    tr_idx = None
    for k in range(len(mid)-1, -1, -1):
        if TR_RE.match(mid[k]):
            tr_idx = k; break
    if tr_idx is None:
        return None
    trend_range = mid[tr_idx]
    last_price = mid[tr_idx-1] if tr_idx-1 >= 0 else None
    block_tokens = mid[:tr_idx-1]   # everything before last_price

    # ---- block_tokens should be 9 tokens: 3 blocks x (num, price_when, chg%) ----
    # Some rows have stray leading pos digits; we right-align into groups of 3.
    rec = {'symbol': sym, 'last_price': last_price, 'trend_range': trend_range,
           'chg_1d': returns[0], 'chg_5d': returns[1], 'chg_30d': returns[2],
           'chg_ytd': returns[3], 'chg_1y': returns[4]}
    block_names = ['3h', 'daily', 'weekly']
    # Expect 9 tokens. If more/fewer, parse defensively by pattern num,num,pct.
    # Walk left-to-right collecting (count, price_when, chg) triples.
    triples = []
    i = 0
    bt = block_tokens
    while i + 2 < len(bt) + 1 and len(triples) < 3:
        # need at least: count(num) price(num) chg(pct)
        if i+2 <= len(bt)-1 and NUM_RE.match(bt[i]) and NUM_RE.match(bt[i+1]) and PCT_RE.match(bt[i+2]):
            triples.append((bt[i], bt[i+1], bt[i+2])); i += 3
        else:
            i += 1
    # pad
    while len(triples) < 3:
        triples.append((None, None, None))
    for name, (cnt, pw, ch) in zip(block_names, triples):
        rec[f'{name}_count'] = cnt
        rec[f'{name}_price_when'] = pw
        rec[f'{name}_chg_since'] = ch
    return rec

def parse_pdf(path):
    path = Path(path)
    m = re.search(r'(\d{8})\s*-\s*(\d{4})\.pdf$', path.name)
    dt = pd.to_datetime(m.group(1)+m.group(2), format='%Y%m%d%H%M') if m else None
    records = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for _, toks in _rows_by_y(page.extract_words()).items():
                r = parse_row(toks)
                if r:
                    r['snapshot'] = dt
                    r['source_file'] = path.name
                    records.append(r)
    df = pd.DataFrame(records)
    # de-dup symbols that appear in multiple theme sections: keep first
    if len(df):
        df = df.drop_duplicates(subset=['snapshot','symbol'], keep='first').reset_index(drop=True)
    return df

if __name__ == '__main__':
    import sys
    df = parse_pdf(sys.argv[1])
    cols = ['symbol','3h_count','3h_price_when','3h_chg_since',
            'daily_count','daily_price_when','daily_chg_since',
            'weekly_count','weekly_price_when','weekly_chg_since',
            'last_price','trend_range','chg_1d','chg_5d']
    print('rows:', len(df), '| symbols:', df['symbol'].nunique())
    print(df[df['symbol'].isin(['US.SPXL','US.EDZ','US.QQQ','US.TQQQ'])][cols].to_string())
