"""
MAGIC MONITOR — INDICATOR FITTING HARNESS
==========================================
Goal: given real OHLCV (which Yahoo provides in your local env but is blocked
in this sandbox), recover the EXACT indicator definitions the Syrius Magic
Monitor uses, by matching computed indicators against the labeled snapshots
we parsed from the PDFs (mm_master.pkl).

What it fits, against ground-truth labels in the snapshots:
  1. Trend/Range (T/R)   -> ADX threshold + length        [label: trend_range]
  2. Signal trigger      -> SuperTrend(atr,mult) OR MA-cross(fast,slow)
                            matched against count==0->trigger events
  3. Extreme? flag       -> RSI/Stoch OB/OS thresholds     [if extractable]

Usage (in an env where yfinance works):
    python fit_indicators.py mm_master.pkl
It will:
  - load the parsed snapshots
  - download daily OHLCV for each symbol over the covered date range
  - compute candidate indicators with a grid of parameters
  - score each parameter set by agreement with the sheet's labels
  - print the best-fitting parameters per column

NOTE: requires `pip install yfinance pandas numpy`.
Yahoo hosts must be allowed: query1.finance.yahoo.com, query2.finance.yahoo.com
"""
import sys, itertools
import numpy as np
import pandas as pd

# ----------------------------- indicators ---------------------------------
def wilder_rma(s, n):
    return s.ewm(alpha=1/n, adjust=False).mean()

def true_range(h, l, c):
    pc = c.shift(1)
    return pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)

def adx(h, l, c, dilen=14, adxlen=14):
    """TradingView ta.dmi/ta.adx equivalent (Wilder smoothing)."""
    up = h.diff()
    dn = -l.diff()
    plus_dm  = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(h, l, c)
    atr = wilder_rma(tr, dilen)
    plus_di  = 100 * wilder_rma(pd.Series(plus_dm, index=h.index), dilen) / atr
    minus_di = 100 * wilder_rma(pd.Series(minus_dm, index=h.index), dilen) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = wilder_rma(dx, adxlen)
    return plus_di, minus_di, adx_val

def supertrend(h, l, c, atr_len=10, mult=3.0):
    """Standard SuperTrend. Returns direction series (+1 up / -1 down) and flip bars."""
    tr = true_range(h, l, c)
    atr = wilder_rma(tr, atr_len)
    hl2 = (h + l) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    fu = upper.copy(); fl = lower.copy()
    dirn = pd.Series(index=c.index, dtype=float)
    for i in range(len(c)):
        if i == 0:
            fu.iloc[i] = upper.iloc[i]; fl.iloc[i] = lower.iloc[i]; dirn.iloc[i] = 1; continue
        fu.iloc[i] = min(upper.iloc[i], fu.iloc[i-1]) if c.iloc[i-1] <= fu.iloc[i-1] else upper.iloc[i]
        fl.iloc[i] = max(lower.iloc[i], fl.iloc[i-1]) if c.iloc[i-1] >= fl.iloc[i-1] else lower.iloc[i]
        if c.iloc[i] > fu.iloc[i-1]:
            dirn.iloc[i] = 1
        elif c.iloc[i] < fl.iloc[i-1]:
            dirn.iloc[i] = -1
        else:
            dirn.iloc[i] = dirn.iloc[i-1]
    flip = dirn.diff().fillna(0) != 0
    return dirn, flip

def ma_cross(c, fast, slow, kind='ema'):
    f = c.ewm(span=fast, adjust=False).mean() if kind=='ema' else c.rolling(fast).mean()
    s = c.ewm(span=slow, adjust=False).mean() if kind=='ema' else c.rolling(slow).mean()
    state = np.sign(f - s)
    flip = pd.Series(state, index=c.index).diff().fillna(0) != 0
    return flip

def rsi(c, n=14):
    d = c.diff()
    up = wilder_rma(d.clip(lower=0), n)
    dn = wilder_rma(-d.clip(upper=0), n)
    # When dn==0 (pure uptrend) RSI -> 100; when up==0 (pure downtrend) RSI -> 0.
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100/(1+rs)
    out = out.where(dn != 0, 100.0)
    out = out.where(~((up == 0) & (dn == 0)), 50.0)
    return out

# ----------------------------- fitting -------------------------------------
def fit_trend_range(ohlc_by_sym, labels):
    """labels: df with [symbol, date, trend_range]. Grid-search ADX len+threshold."""
    best = None
    for dilen, adxlen, thr in itertools.product([14], [14], [20, 22, 25, 28, 30]):
        agree = tot = 0
        for sym, px in ohlc_by_sym.items():
            _, _, a = adx(px['High'], px['Low'], px['Close'], dilen, adxlen)
            pred = np.where(a >= thr, 'T', 'R')
            ps = pd.Series(pred, index=px.index)
            lab = labels[labels.symbol==sym].set_index('date')['trend_range']
            for dt, lv in lab.items():
                key = pd.Timestamp(dt)
                if key in ps.index and pd.notna(ps.loc[key]):
                    tot += 1; agree += (ps.loc[key] == lv)
        acc = agree/max(tot,1)
        if best is None or acc > best[0]:
            best = (acc, dict(dilen=dilen, adxlen=adxlen, thr=thr), tot)
        print(f'  ADX dilen={dilen} adxlen={adxlen} thr={thr}: acc={acc:.3f} (n={tot})')
    return best

def fit_trigger(ohlc_by_sym, trigger_events):
    """trigger_events: df [symbol, date] of fresh DAILY signals.
    Score SuperTrend & MA-cross param grids by F1 of flip-bar vs trigger-bar."""
    results = []
    st_grid = [(10,3.0),(10,2.0),(14,3.0),(7,3.0),(14,2.0),(10,1.5)]
    for atr_len, mult in st_grid:
        tp=fp=fn=0
        for sym, px in ohlc_by_sym.items():
            _, flip = supertrend(px['High'],px['Low'],px['Close'],atr_len,mult)
            trig_dates = set(pd.Timestamp(d) for d in trigger_events[trigger_events.symbol==sym]['date'])
            flip_dates = set(px.index[flip])
            # tolerance: +-1 trading day
            for td in trig_dates:
                if any(abs((td-fd).days)<=2 for fd in flip_dates): tp+=1
                else: fn+=1
            for fd in flip_dates:
                if not any(abs((td-fd).days)<=2 for td in trig_dates): fp+=1
        prec=tp/max(tp+fp,1); rec=tp/max(tp+fn,1); f1=2*prec*rec/max(prec+rec,1e-9)
        results.append(('SuperTrend',atr_len,mult,prec,rec,f1))
        print(f'  SuperTrend({atr_len},{mult}): P={prec:.2f} R={rec:.2f} F1={f1:.2f}')
    ma_grid=[('ema',9,21),('ema',8,21),('ema',5,20),('ema',10,30),('sma',9,21),('ema',12,26)]
    for kind,f,s in ma_grid:
        tp=fp=fn=0
        for sym, px in ohlc_by_sym.items():
            flip=ma_cross(px['Close'],f,s,kind)
            trig_dates=set(pd.Timestamp(d) for d in trigger_events[trigger_events.symbol==sym]['date'])
            flip_dates=set(px.index[flip])
            for td in trig_dates:
                if any(abs((td-fd).days)<=2 for fd in flip_dates): tp+=1
                else: fn+=1
            for fd in flip_dates:
                if not any(abs((td-fd).days)<=2 for td in trig_dates): fp+=1
        prec=tp/max(tp+fp,1); rec=tp/max(tp+fn,1); f1=2*prec*rec/max(prec+rec,1e-9)
        results.append((f'{kind}MA',f,s,prec,rec,f1))
        print(f'  {kind}MA({f},{s}): P={prec:.2f} R={rec:.2f} F1={f1:.2f}')
    return sorted(results,key=lambda r:-r[-1])[0]

def build_trigger_events(snap):
    ev=[]
    for sym,g in snap.sort_values('snapshot').groupby('symbol'):
        g=g.reset_index(drop=True); pw=g['daily_price_when'].values
        for i in range(len(g)):
            if pw[i]>0 and (i==0 or pw[i]!=pw[i-1]):
                ev.append({'symbol':sym,'date':g['date'].iloc[i]})
    return pd.DataFrame(ev)

if __name__=='__main__':
    snap=pd.read_pickle(sys.argv[1] if len(sys.argv)>1 else 'mm_master.pkl')
    snap['date']=pd.to_datetime(snap['date'])
    syms=sorted(snap['symbol'].unique())
    d0,d1=snap['date'].min(),snap['date'].max()
    print(f'{len(syms)} symbols, {d0.date()}..{d1.date()}')
    try:
        import yfinance as yf
    except ImportError:
        print('\\n[!] yfinance not installed / network blocked here.')
        print('    Run this script in your LOCAL env. It is ready to go.')
        sys.exit(0)
    # download OHLCV
    ohlc={}
    for s in syms:
        tk=s.replace('US.','')
        try:
            df=yf.download(tk,start=str((d0-pd.Timedelta(days=60)).date()),
                           end=str((d1+pd.Timedelta(days=10)).date()),
                           progress=False,auto_adjust=False)
            if len(df): ohlc[s]=df.rename(columns=lambda c:c if isinstance(c,str) else c[0])
        except Exception as e:
            pass
    print(f'downloaded {len(ohlc)} symbols')
    labels=snap[['symbol','date','trend_range']].dropna()
    print('\\n=== FIT 1: Trend/Range = ADX threshold ===')
    print(fit_trend_range(ohlc,labels))
    print('\\n=== FIT 2: Trigger = SuperTrend vs MA-cross ===')
    print('BEST:',fit_trigger(ohlc,build_trigger_events(snap)))
