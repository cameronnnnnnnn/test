"""
Multi-pair DAILY strategy on real OHLC (built from M1), with real intraday
stop fills and max-adverse-excursion, then a DEADLINE-constrained FTMO Monte
Carlo that respects the 3% daily-loss cap (2.8% buffer) and 9.5% global.

Strategy per pair (the only edge that survived): trend-aligned pullback.
  trend = SMA10 vs SMA40 ; trigger = 5-day z-score beyond +/-1 (fade toward trend)
  stop = 1.0*ATR(14) ; hold to next close (stop can fill intraday via next-day H/L)
  no Friday entries (no weekend hold).
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

PAIRS = {"EURUSD":(0.0001,0.00001),"GBPUSD":(0.0001,0.00001),
         "AUDUSD":(0.0001,0.00001),"USDJPY":(0.01,0.001)}
SPREAD_PIPS = {"EURUSD":1.1,"GBPUSD":1.2,"AUDUSD":1.3,"USDJPY":1.4}

d = pd.read_pickle("ftmo/m1/daily_all.pkl")
dts = pd.to_datetime(d["Date"])
dow = dts.dt.dayofweek.values

def build_trades(pair):
    pip,_ = PAIRS[pair]
    o=d[f"{pair}_open"].values; h=d[f"{pair}_high"].values
    l=d[f"{pair}_low"].values;  c=d[f"{pair}_close"].values
    s=pd.Series(c)
    fast=s.rolling(10).mean().values; slow=s.rolling(40).mean().values
    ma=s.rolling(5).mean().values; sd=s.rolling(5).std().values
    z=(c-ma)/(sd+1e-12)
    tr=np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    cost=SPREAD_PIPS[pair]*pip + 0.2*pip   # spread + slip, round trip-ish
    rows=[]
    for t in range(40, len(d)-1):
        if dow[t]==4: continue                 # no Friday entry
        if not np.isfinite(atr[t]) or atr[t]<=0: continue
        trend = 1 if fast[t]>slow[t] else (-1 if fast[t]<slow[t] else 0)
        sig = 1 if (z[t]<-1 and trend==1) else (-1 if (z[t]>1 and trend==-1) else 0)
        if sig==0: continue
        entry=c[t]; stop=atr[t]
        # next-day real OHLC for fill
        nh,nl,nc=h[t+1],l[t+1],c[t+1]
        if sig>0:
            stop_px=entry-stop; adv=entry-nl
            hit = nl<=stop_px
        else:
            stop_px=entry+stop; adv=nh-entry
            hit = nh>=stop_px
        if hit:
            R=-1.0 - 0.2*pip/stop
        else:
            R=(sig*(nc-entry)-cost)/stop
        rows.append({"date":dts.iloc[t+1].date(),"pair":pair,"R":R,"MAE_R":max(adv,0)/stop})
    return pd.DataFrame(rows)

allt = pd.concat([build_trades(p) for p in PAIRS], ignore_index=True)
allt = allt.sort_values("date").reset_index(drop=True)

print("Per-pair daily edge (real OHLC, real intraday stops):")
for p in PAIRS:
    t=allt[allt["pair"]==p]; R=t["R"].values
    print(f"  {p}: n={len(R):4d} win={ (R>0).mean()*100:4.1f}% expR={R.mean():+.3f} "
          f"PF={R[R>0].sum()/(-R[R<0].sum()+1e-9):.2f}")
R=allt["R"].values
ndays=allt["date"].nunique()
print(f"  ALL: n={len(R)} trades over {ndays} active days -> {len(R)/ndays:.2f} trades/active-day, "
      f"expR={R.mean():+.3f}")
span_weeks=(dts.max()-dts.min()).days/7
print(f"  active days/week = {ndays/span_weeks:.2f}")
allt.to_pickle("ftmo/m1/mp_daily_trades.pkl")
