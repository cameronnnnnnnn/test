"""
REGIME-SWITCHING Monte Carlo for the 1-month SPRINT product (15h+16h ORB, stop80,
BE@1R, trail5, filters, no overnight), r=1.25%, $15k FTMO.

Why this exists
---------------
mc_monthly_cohorts.py / mc_multisession.py already do the "reshuffling" MC the video
describes: draw trades i.i.d. with replacement, order-independent. The video's critique
is that real trade returns CLUSTER by market regime, so i.i.d. resampling understates
streaks (and therefore drawdown / blow-up risk). This script implements the regime-
switching method to fix that, and prints it next to the i.i.d. baseline so the effect of
clustering is visible.

Method (faithful to the video, adapted to this strategy)
--------------------------------------------------------
1. Build the REAL combined sprint sequence (15h + 16h), sorted by calendar day. Group
   trades by day -> the resampling unit is a whole trading DAY (preserves the correlation
   between the two same-day sessions and lets us apply FTMO's 3% DAILY loss rule).
2. Tag each day with a volatility REGIME from atrpct (rolling ATR percentile, computed
   from prior bars -> not outcome-derived). 2 regimes via median split: calm vs volatile.
3. Count day-to-day regime transitions in the real sequence -> transition matrix.
4. Regime-switching day-bootstrap: start in a regime (stationary dist), draw a random real
   day from that regime's pool, apply FTMO rules, then hop regimes per the matrix. Repeat.
5. Compare to i.i.d. day-bootstrap (draw days uniformly, ignore regime) under identical
   rules. Same edge, same variance -> the ONLY difference is whether streaks are preserved.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

DAYS,ctx=build_all()

def trades(hr):
    RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
                      be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True)
    return pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE})

df=pd.concat([trades(15),trades(16)],ignore_index=True).sort_values("date").reset_index(drop=True)
# attach the day's volatility-regime proxy (atrpct) to every trade
df["atrpct"]=df["date"].dt.normalize().map(lambda d: ctx.get(pd.Timestamp(d),{}).get("atrpct",np.nan))
df=df.dropna(subset=["atrpct"]).reset_index(drop=True)

# ---- group into trading DAYS (the resampling unit) ----
days=[]   # each: dict(trades=[(R,MAE),...], atrpct=float, date=...)
for d,g in df.groupby(df["date"].dt.normalize()):
    days.append(dict(date=d, trades=list(zip(g["R"].values,g["MAE"].values)),
                     atrpct=float(g["atrpct"].iloc[0])))
days.sort(key=lambda x:x["date"])
NDAY=len(days)
allR=df["R"].values; allM=df["MAE"].values
print(f"data: {days[0]['date'].date()} .. {days[-1]['date'].date()}  "
      f"({NDAY} trading days, {len(df)} trades, {len(df)/NDAY:.2f} trades/day)")

# ===================================================================================
# (A) THE VIDEO'S HEADLINE: is the per-trade edge statistically distinguishable from 0?
# ===================================================================================
def boot_ci(x,N=20000,lo=5,hi=95,seed=1):
    rng=np.random.default_rng(seed); n=len(x)
    means=np.array([x[rng.integers(0,n,n)].mean() for _ in range(N)])
    return means.mean(), np.percentile(means,lo), np.percentile(means,hi)
m,clo,chi=boot_ci(allR)
print(f"\n=== per-trade edge (bootstrap, {len(allR)} trades) ===")
print(f"mean R/trade = {m:+.3f}   90% CI [{clo:+.3f}, {chi:+.3f}]   "
      f"{'EDGE (CI excludes 0)' if clo>0 else 'NOT distinguishable from 0 (CI spans 0)'}")
print(f"WR={(allR>0).mean()*100:.1f}%  PF={allR[allR>0].sum()/-allR[allR<0].sum():.2f}  "
      f"maxR={allR.max():.1f}  minR={allR.min():.1f}")

# ===================================================================================
# (B) REGIMES + per-regime edge + transition matrix
# ===================================================================================
ap=np.array([d["atrpct"] for d in days])
cut=np.median(ap)
for d in days: d["reg"]=1 if d["atrpct"]>cut else 0   # 0=calm(low vol), 1=volatile(high vol)
REG=["calm","volatile"]
print(f"\n=== regimes (split at median atrpct={cut:.2f}) ===")
for g in (0,1):
    rr=np.concatenate([[t[0] for t in d["trades"]] for d in days if d["reg"]==g]) if any(d["reg"]==g for d in days) else np.array([])
    nd=sum(d["reg"]==g for d in days)
    print(f"  {REG[g]:8s}: {nd:3d} days, {len(rr):3d} trades  WR={(rr>0).mean()*100:4.1f}%  "
          f"expR={rr.mean():+.3f}  std={rr.std():.2f}  maxR={rr.max():.1f}")

# day-to-day transition matrix (consecutive real days)
T=np.zeros((2,2))
for i in range(NDAY-1): T[days[i]["reg"]][days[i+1]["reg"]]+=1
cnt=T.copy()
T=T/T.sum(axis=1,keepdims=True)
# stationary distribution (left eigenvector of T for eigenvalue 1)
w,v=np.linalg.eig(T.T); pi=np.real(v[:,np.argmin(abs(w-1))]); pi=pi/pi.sum()
freq=np.array([np.mean([d["reg"]==g for d in days]) for g in (0,1)])
print(f"\ntransition matrix (rows=from, cols=to)   counts: {cnt.astype(int).tolist()}")
print(f"  from calm     -> calm {T[0,0]*100:4.1f}%   volatile {T[0,1]*100:4.1f}%")
print(f"  from volatile -> calm {T[1,0]*100:4.1f}%   volatile {T[1,1]*100:4.1f}%")
print(f"stationary dist: calm {pi[0]*100:.1f}%  volatile {pi[1]*100:.1f}%")
# clustering test: compare P(stay) to what independence would give
p_stay_obs=(cnt[0,0]+cnt[1,1])/cnt.sum()
p_stay_ind=freq[0]**2+freq[1]**2
print(f"clustering check: observed P(same regime next day)={p_stay_obs*100:.1f}%  "
      f"vs independence={p_stay_ind*100:.1f}%  -> {'CLUSTERS (regime matters)' if p_stay_obs>p_stay_ind+0.03 else 'weak/no clustering'}")

# ===================================================================================
# (C) FTMO challenge MC: regime-switching day-bootstrap vs i.i.d. day-bootstrap
# ===================================================================================
START=15000.0; TARGET=1.10*START; TRAILDD=0.10; DAILYDD=0.03; MINTD=4; MONTH=21; r=0.0125
pools={g:[d["trades"] for d in days if d["reg"]==g] for g in (0,1)}

def apply_day(daytrades, eq, peak, floor):
    """advance equity through one day's trades; return (eq,peak,floor,outcome) where
       outcome in {None,'trail','daily','pass-eligible'} (pass handled by caller)."""
    ds=eq; daylow=eq
    for (R,MAE) in daytrades:
        low=eq-r*MAE*eq; daylow=min(daylow,low)
        if low<=floor: return low,peak,floor,"trail"
        eq=eq+r*R*eq
        if eq>peak: peak=eq; floor=peak*(1-TRAILDD)
        if eq<=floor: return eq,peak,floor,"trail"
    if (ds-daylow)/ds>=DAILYDD: return eq,peak,floor,"daily"
    return eq,peak,floor,None

def sim(mode,rng,max_days=252):
    eq=START; peak=START; floor=START*(1-TRAILDD); td=0
    cur=rng.choice(2,p=pi) if mode=="regime" else None
    while td<max_days:
        if mode=="regime":
            dt=pools[cur][rng.integers(len(pools[cur]))]
        else:
            dt=days[rng.integers(NDAY)]["trades"]
        eq,peak,floor,oc=apply_day(dt,eq,peak,floor)
        td+=1
        if oc in ("trail","daily"): return oc,td,eq
        if eq>=TARGET and td>=MINTD: return "pass",td,eq
        if mode=="regime": cur=rng.choice(2,p=T[cur])
    return "timeout",td,eq

def run(mode,N=20000,seed=7):
    rng=np.random.default_rng(seed)
    out=[sim(mode,rng) for _ in range(N)]
    oc=np.array([o[0] for o in out]); dy=np.array([o[1] for o in out]); fe=np.array([o[2] for o in out])
    P=oc=="pass"; B=(oc=="trail")|(oc=="daily")
    p1=(P&(dy<=MONTH)).mean()*100; pl=(P&(dy>MONTH)).mean()*100
    return dict(mode=mode,p1=p1,pl=pl,blow=B.mean()*100,
                trail=(oc=="trail").mean()*100,daily=(oc=="daily").mean()*100,
                to=(oc=="timeout").mean()*100,
                med_pass=np.median(dy[P]) if P.any() else np.nan,
                fe=fe, dy=dy, P=P, B=B)

reg=run("regime"); iid=run("iid")
print(f"\n=== FTMO sprint MC: r={r*100:.2f}%, $15k, +10% target, 10% trailing DD, 3% daily, "
      f"1 month={MONTH}td (N=20000 each) ===")
hdr=f"{'method':<16}{'pass<=1mo':>10}{'pass>1mo':>10}{'BLOW':>8}{'(trail/daily)':>15}{'timeout':>9}{'medPass':>9}"
print(hdr); print("-"*len(hdr))
for x in (iid,reg):
    nm="i.i.d. reshuffle" if x["mode"]=="iid" else "regime-switching"
    print(f"{nm:<16}{x['p1']:>9.1f}%{x['pl']:>9.1f}%{x['blow']:>7.1f}%"
          f"{x['trail']:>7.1f}/{x['daily']:.1f}%{x['to']:>8.1f}%{x['med_pass']:>8.0f}td")

# drawdown / final-equity comparison
print(f"\nfinal-equity percentiles (% of $15k start):")
for x in (iid,reg):
    nm="i.i.d." if x["mode"]=="iid" else "regime"
    pct=lambda q: (np.percentile(x['fe'],q)/START-1)*100
    print(f"  {nm:<7} p5={pct(5):+5.1f}%  p25={pct(25):+5.1f}%  median={pct(50):+5.1f}%  "
          f"p75={pct(75):+5.1f}%  p95={pct(95):+5.1f}%")

dB=reg['blow']-iid['blow']; dP=reg['p1']-iid['p1']
print(f"\n=== verdict ===")
print(f"regime-switching vs i.i.d.:  blow-up {dB:+.1f}pp,  pass<=1mo {dP:+.1f}pp")
if abs(dB)<2 and abs(dP)<2:
    print("-> clustering barely moves the numbers: the i.i.d. sprint MC was already ~honest.")
else:
    print("-> clustering MATTERS: i.i.d. resampling was "
          f"{'UNDER' if dB>0 else 'OVER'}stating real blow-up risk by ~{abs(dB):.0f}pp.")
