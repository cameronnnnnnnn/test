"""
NAS100 daily strategy search on REAL daily OHLC (built from clean M1).
Tests entry signals x exit managements with realistic cost + intraday stop fills
+ MAE tracking. R-multiple framework (instrument-agnostic).

Honesty guards:
  - long and short edges reported SEPARATELY (period is one big bull run).
  - cost stressed; real intraday H/L used for stop fills.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

d = pd.read_pickle("ftmo/m1_nas/nas_daily.pkl").reset_index(drop=True)
o=d["open"].values; h=d["high"].values; l=d["low"].values; c=d["close"].values
dow=d["date"].dt.dayofweek.values
N=len(d)

s=pd.Series(c)
fast=s.rolling(10).mean().values; slow=s.rolling(40).mean().values
ma5=s.rolling(5).mean().values; sd5=s.rolling(5).std().values
z5=(c-ma5)/(sd5+1e-12)
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
atr=pd.Series(tr).rolling(14).mean().values
hh20=pd.Series(h).rolling(20).max().shift(1).values
ll20=pd.Series(l).rolling(20).min().shift(1).values
mom=(c-np.roll(c,10))  # 10-day momentum

COST=2.0   # base spread+slip in index points (FTMO NAS100 ~1-1.8pt); stress later

def simulate(signal_fn, init_atr=1.0, trail_atr=None, be_at=None,
             hard_R=None, max_hold=1, cost=COST):
    """signal_fn(t)->(+1 long / -1 short / 0 none). Enter next bar open."""
    rows=[]
    for t in range(40, N-1):
        if dow[t]==4: continue                 # no Friday entry (weekend flat)
        if not np.isfinite(atr[t]) or atr[t]<=0: continue
        sig=signal_fn(t)
        if sig==0: continue
        entry=o[t+1]                           # realistic: next-bar open
        stop0=atr[t]*init_atr
        stop_px= entry-stop0 if sig>0 else entry+stop0
        ext=entry; exitR=None; mae=0.0
        for k in range(1,max_hold+1):
            ti=t+k
            if ti>=N: break
            hi,lo,cl=h[ti],l[ti],c[ti]
            adv=(entry-lo) if sig>0 else (hi-entry); mae=max(mae,adv)
            if (sig>0 and lo<=stop_px) or (sig<0 and hi>=stop_px):
                exitR=(sig*(stop_px-entry)-cost)/stop0; break
            ext = max(ext,hi) if sig>0 else min(ext,lo)
            curR=(sig*(cl-entry))/stop0
            if be_at is not None and curR>=be_at:
                stop_px = max(stop_px,entry) if sig>0 else min(stop_px,entry)
            if trail_atr is not None:
                ts=ext - sig*trail_atr*atr[t]
                stop_px = max(stop_px,ts) if sig>0 else min(stop_px,ts)
            if hard_R is not None and curR>=hard_R:
                exitR=(sig*(cl-entry)-cost)/stop0; break
            if dow[ti]==4 or k==max_hold:
                exitR=(sig*(cl-entry)-cost)/stop0; break
        if exitR is None:
            exitR=(sig*(c[min(t+max_hold,N-1)]-entry)-cost)/stop0
        rows.append({"date":d["date"].iloc[t+1].date(),"R":exitR,
                     "MAE_R":max(mae,0)/stop0,"dir":sig})
    return pd.DataFrame(rows)

def stats(df,name):
    if len(df)==0: print(f"{name:38s} no trades"); return None
    R=df["R"].values
    win=(R>0).mean(); exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9)
    L=df[df["dir"]>0]["R"].values; S=df[df["dir"]<0]["R"].values
    eL=L.mean() if len(L) else float('nan'); eS=S.mean() if len(S) else float('nan')
    print(f"{name:38s} n={len(R):4d} win={win*100:4.1f}% expR={exp:+.3f} PF={pf:.2f} "
          f"maxR={R.max():4.1f} | long {len(L):3d}:{eL:+.2f}R short {len(S):3d}:{eS:+.2f}R")
    return df

# ---- entry signal definitions ----
def sig_pullback(t):   # fade 1-sigma stretch toward trend
    trend=1 if fast[t]>slow[t] else (-1 if fast[t]<slow[t] else 0)
    if z5[t]<-1 and trend==1: return 1
    if z5[t]>1  and trend==-1: return -1
    return 0
def sig_breakout(t):   # 20-day breakout in trend dir
    trend=1 if fast[t]>slow[t] else (-1 if fast[t]<slow[t] else 0)
    if c[t]>hh20[t] and trend>=0: return 1
    if c[t]<ll20[t] and trend<=0: return -1
    return 0
def sig_mom(t):        # momentum continuation
    if mom[t]>0 and c[t]>fast[t]: return 1
    if mom[t]<0 and c[t]<fast[t]: return -1
    return 0
def sig_trend_long_only(t):  # buy any dip while in uptrend (long-only beta check)
    trend=1 if fast[t]>slow[t] else 0
    if z5[t]<-0.5 and trend==1: return 1
    return 0

print("NAS100 daily strategy search (real OHLC, cost=2.0pt, R-multiples)\n")
print("--- ENTRIES, baseline exit = next close (1 day) ---")
stats(simulate(sig_pullback),                 "pullback (trend-aligned)")
stats(simulate(sig_breakout),                 "breakout (20d, trend)")
stats(simulate(sig_mom),                      "momentum continuation")
stats(simulate(sig_trend_long_only),          "long-only dip buy")

print("\n--- BEST ENTRY x exit management (let runners run / fat tails) ---")
for nm,fn in [("pullback",sig_pullback),("breakout",sig_breakout),("momentum",sig_mom)]:
    stats(simulate(fn,max_hold=5,trail_atr=2.0,be_at=1.0), f"{nm} +5d swing trail2ATR BE1")
    stats(simulate(fn,max_hold=10,trail_atr=3.0,be_at=1.0),f"{nm} +10d swing trail3ATR BE1")
    stats(simulate(fn,max_hold=10,trail_atr=2.0),          f"{nm} +10d swing trail2ATR")

print("\n--- COST STRESS on best-looking config (breakout +10d trail3) ---")
for cs in (2.0,3.0,4.0,6.0):
    stats(simulate(sig_breakout,max_hold=10,trail_atr=3.0,be_at=1.0,cost=cs),
          f"breakout swing cost={cs}pt")
