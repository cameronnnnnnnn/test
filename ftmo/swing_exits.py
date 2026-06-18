"""
Daily SWING engine: trend-aligned pullback entry, then test exit management ---
trailing stops at different aggression + hard profit caps + breakeven moves.
Multi-day holds allowed (swing), but flat before weekend (no Friday->Mon hold).
Real daily OHLC -> intraday stop fills via each held day's High/Low.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

PAIRS = {"EURUSD":0.0001,"GBPUSD":0.0001,"AUDUSD":0.0001,"USDJPY":0.01}
SPREAD_PIPS = {"EURUSD":1.1,"GBPUSD":1.2,"AUDUSD":1.3,"USDJPY":1.4}
d = pd.read_pickle("ftmo/m1/daily_all.pkl")
dts = pd.to_datetime(d["Date"]); dow = dts.dt.dayofweek.values

def swing_trades(pair, init_atr=1.0, trail_atr=None, be_at=None, hard_R=None, max_hold=10):
    pip=PAIRS[pair]
    o=d[f"{pair}_open"].values;h=d[f"{pair}_high"].values
    l=d[f"{pair}_low"].values;c=d[f"{pair}_close"].values
    s=pd.Series(c)
    fast=s.rolling(10).mean().values; slow=s.rolling(40).mean().values
    ma=s.rolling(5).mean().values; sd=s.rolling(5).std().values
    z=(c-ma)/(sd+1e-12)
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    cost=SPREAD_PIPS[pair]*pip+0.2*pip
    rows=[]
    for t in range(40,len(d)-1):
        if dow[t]==4: continue
        if not np.isfinite(atr[t]) or atr[t]<=0: continue
        trend=1 if fast[t]>slow[t] else (-1 if fast[t]<slow[t] else 0)
        sig=1 if (z[t]<-1 and trend==1) else (-1 if (z[t]>1 and trend==-1) else 0)
        if sig==0: continue
        entry=c[t]; A=atr[t]; stop0=A*init_atr
        if sig>0: stop_px=entry-stop0
        else:     stop_px=entry+stop0
        ext=entry  # best extreme reached
        exitR=None; mae=0.0
        for k in range(1,max_hold+1):
            ti=t+k
            if ti>=len(d): break
            hi,lo,cl=h[ti],l[ti],c[ti]
            adv=(entry-lo) if sig>0 else (hi-entry); mae=max(mae,adv)
            # stop check (intraday)
            if (sig>0 and lo<=stop_px) or (sig<0 and hi>=stop_px):
                exitR=(sig*(stop_px-entry)-cost)/stop0; break
            # update extreme + trailing
            ext = max(ext,hi) if sig>0 else min(ext,lo)
            curR=(sig*(cl-entry))/stop0
            if be_at is not None and curR>=be_at:
                stop_px = max(stop_px, entry) if sig>0 else min(stop_px, entry)
            if trail_atr is not None:
                ts = ext - sig*trail_atr*A
                stop_px = max(stop_px,ts) if sig>0 else min(stop_px,ts)
            # hard target on close
            if hard_R is not None and curR>=hard_R:
                exitR=(sig*(cl-entry)-cost)/stop0; break
            # weekend / max hold -> close at this close
            if dow[ti]==4 or k==max_hold:
                exitR=(sig*(cl-entry)-cost)/stop0; break
        if exitR is None: exitR=(sig*(c[min(t+max_hold,len(d)-1)]-entry)-cost)/stop0
        rows.append({"date":dts.iloc[t+1].date(),"pair":pair,"R":exitR,"MAE_R":max(mae,0)/stop0})
    return pd.DataFrame(rows)

def agg(cfgname, **cfg):
    allt=pd.concat([swing_trades(p,**cfg) for p in PAIRS],ignore_index=True)
    R=allt["R"].values
    win=(R>0).mean(); exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9)
    avgW=R[R>0].mean() if (R>0).any() else 0; avgL=R[R<0].mean() if (R<0).any() else 0
    print(f"{cfgname:34s} n={len(R):4d} win={win*100:4.1f}% expR={exp:+.3f} PF={pf:.2f} "
          f"avgW={avgW:+.2f} avgL={avgL:+.2f} maxR={R.max():.1f}")
    return allt

print("EXIT-MANAGEMENT SWEEP on daily trend-aligned pullback (4 pairs, real OHLC)\n")
print("baseline / hard caps:")
agg("next-close (1-day, baseline)", max_hold=1)
agg("hard cap 2R", hard_R=2.0)
agg("hard cap 3R", hard_R=3.0)
agg("hard cap 5R", hard_R=5.0)
print("\nlet runners run (trailing, various aggression):")
agg("trail 1.0ATR (tight)", trail_atr=1.0)
agg("trail 1.5ATR", trail_atr=1.5)
agg("trail 2.0ATR", trail_atr=2.0)
agg("trail 3.0ATR (loose)", trail_atr=3.0)
print("\nbreakeven + trail combos:")
agg("BE@1R + trail 2ATR", be_at=1.0, trail_atr=2.0)
agg("BE@1R + trail 3ATR", be_at=1.0, trail_atr=3.0)
agg("BE@1R + trail2 + cap5R", be_at=1.0, trail_atr=2.0, hard_R=5.0)
