import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import intraday_engine as E

m1 = E.load_m1()

def ema(x,n): return pd.Series(x).ewm(span=n,adjust=False).mean().values
def sma(x,n): return pd.Series(x).rolling(n).mean().values
def rstd(x,n): return pd.Series(x).rolling(n).std().values

# --- signals (fire only on the event bar) ---
def sig_ema_cross(bars, f=12, s=48):
    c=bars["close"].values; ef=ema(c,f); es=ema(c,s)
    up=(ef>es)&(np.roll(ef<=es,1)); dn=(ef<es)&(np.roll(ef>=es,1))
    out=np.zeros(len(c)); out[up]=1; out[dn]=-1; out[:s]=0; return out

def sig_breakout(bars, n=20):
    c=bars["close"].values
    hi=pd.Series(c).rolling(n).max().shift(1).values
    lo=pd.Series(c).rolling(n).min().shift(1).values
    out=np.zeros(len(c)); out[c>hi]=1; out[c<lo]=-1; out[:n+1]=0; return out

def sig_bb_revert(bars, n=20, k=2.0):
    c=bars["close"].values; m=sma(c,n); sd=rstd(c,n)
    out=np.zeros(len(c)); out[c < m-k*sd]=1; out[c > m+k*sd]=-1; out[:n]=0; return out

def sig_rsi_revert(bars, n=14, lo=30, hi=70):
    c=pd.Series(bars["close"].values); d=c.diff()
    up=d.clip(lower=0).rolling(n).mean(); dn=(-d.clip(upper=0)).rolling(n).mean()
    rsi=100-100/(1+up/(dn+1e-12))
    out=np.zeros(len(c)); out[rsi<lo]=1; out[rsi>hi]=-1; out[:n]=0; return out

CFG=dict(session=(7,20), flat_hour=20, slip_pips=0.2)

def show(name, bars, fn, stop, tR, **kw):
    tr=E.backtest(bars, fn, stop, tR, **{**CFG,**kw})
    st=E.trade_stats(tr)
    if st is None: print(f"{name:34s} no trades"); return None
    print(f"{name:34s} n={st['n']:5d} t/day={st['tpd']:4.2f} win={st['win']*100:4.1f}% "
          f"expR={st['expR']:+.3f} PF={st['pf']:.2f} sumR={st['sumR']:6.0f}")
    return tr

for tf in ("15min","30min"):
    bars=E.resample(m1, tf)
    print(f"\n===== timeframe {tf}  ({len(bars)} bars) =====")
    for stop in (8,12,18):
        print(f"-- stop={stop}p --")
        show(f"ema12/48 tgt2R s{stop}", bars, sig_ema_cross, stop, 2.0)
        show(f"breakout20 tgt2R s{stop}", bars, sig_breakout, stop, 2.0)
        show(f"bb20/2 tgt1R s{stop}", bars, sig_bb_revert, stop, 1.0)
        show(f"rsi14 tgt1R s{stop}", bars, sig_rsi_revert, stop, 1.0)
