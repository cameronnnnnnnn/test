"""
STRICT consistency rule: NO single trading day's profit may exceed $750 (= 50% of the
$1,500 / +10% goal), as a HARD DOLLAR CAP -- not a ratio of realized profit. Under this
reading you cannot 'dilute' a big day by trading more; a day over $750 permanently kills
the pass. So the only defense is to PREVENT big days at the execution level.

Levers tested (long-only, r=1.25%, $15k, 15h+16h unless noted):
  - per-trade hard TP (caps a single win)
  - DAILY PROFIT LOCK: stop opening trades for the day once day P&L >= lock $ (caps the day)
  - single session (max one trade/day -> structurally hard to breach)

A day breaches when both sessions win big (2 x 2R ~ $800 > $750), so 2R TP ALONE is not
enough here. Reports strict 1mo/4mo pass, blow-up, cap-violation rate, and realized max day.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; GOAL=0.10*START; TARGET=START+GOAL; CAP=0.50*GOAL  # $750 hard daily cap
TR=.10; DD=.03; MIN=4; MO=21; r=.0125

def build(side, tp_R, sessions=(15,16)):
    dfs=[]
    for hr in sessions:
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,tp_R=tp_R)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE,"hr":hr,
                                 "ct":pd.to_datetime(DTS)}))
    df=pd.concat(dfs,ignore_index=True)
    dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        # order same-day trades by session hour (15h before 16h) to model the daily lock in time order
        g=g.sort_values("hr")
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

def coh(si,dm,daily_lock,horizon):
    """strict walk. outcomes: P pass, F blow(DD), V reached target but a day>CAP (dead), T timeout."""
    eq=START; pk=START; fl=pk*(1-TR); td=0; maxday=0.0
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq; dl=eq; daypl=0.0
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=fl: return "F",td+1
            if daily_lock is not None and daypl>=daily_lock: break   # locked: no more entries today
            g=r*R*eq; eq+=g; daypl+=g
            if eq>pk: pk=eq; fl=pk*(1-TR)
            if eq<=fl: return "F",td+1
        td+=1; maxday=max(maxday,daypl)
        if (ds-dl)/ds>=DD: return "F",td
        if eq>=TARGET and td>=MIN:
            if maxday<=CAP: return "P",td
            else: return "V",td   # hit target but a day breached the hard cap -> cannot pass
    return "T",td

def report(nm, side, tp, lock, sessions=(15,16)):
    dm=build(side,tp,sessions)
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,lock,MO) for si in st]
    ev=[coh(si,dm,lock,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    # realized max-day across all 1mo windows (diagnostic)
    md=[]
    for si in st:
        eq=START; pk=START; fl=pk*(1-TR); mx=0
        for j in range(si,min(si+MO,len(ALLDAYS))):
            daypl=0
            for (R,MAE) in dm.get(ALLDAYS[j],[]):
                if lock is not None and daypl>=lock: break
                g=r*R*eq; eq+=g; daypl+=g
            mx=max(mx,daypl)
        md.append(mx)
    print(f"  {nm:<26}{p(ye,'P'):>7.1f}%{p(ev,'P'):>8.1f}%{p(ye,'F'):>7.1f}%{p(ye,'V'):>8.1f}%  "
          f"${np.median(md):>5.0f} / ${np.max(md):>5.0f}")

print(f"$15k, +10%=$1,500, HARD daily cap=${CAP:.0f} (50% of goal), r=1.25%\n")
print(f"  {'config':<26}{'pass1mo':>7}{'pass4mo':>8}{'blow':>7}{'capkill':>8}  {'medMaxDay/worst':>16}")
print("  "+"-"*78)
print("  -- both sessions (15h+16h) --")
report("2R TP, no lock",          "long",2.0,None)
report("1.75R TP, no lock",       "long",1.75,None)
report("1.6R TP, no lock",        "long",1.6,None)
report("1.5R TP, no lock",        "long",1.5,None)
report("2R TP, lock $340",        "long",2.0,340)
report("1.75R TP, lock $400",     "long",1.75,400)
print("  -- single session (max one trade/day) --")
report("15h only, 2R TP",         "long",2.0,None,sessions=(15,))
report("16h only, 2R TP",         "long",2.0,None,sessions=(16,))
report("15h only, 2.5R TP",       "long",2.5,None,sessions=(15,))
print("\nkey: capkill = reached +10% but a day broke $750 so the pass DOESN'T COUNT.")
print("Best config = highest pass1mo with low capkill AND worst-day under $750.")
