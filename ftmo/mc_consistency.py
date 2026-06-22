"""
CONSISTENCY-RULE-AWARE sprint MC. FTMO-style rule: your single best trading day's profit
must be <= 50% of total profit, or the +10% target doesn't count yet (keep trading to
dilute the big day). This strategy makes ~60% of profit from its top 10% of trades, so
the rule bites hard. Reports pass<=1mo and eventual-pass (any time) WITH the rule, vs the
naive no-rule number, to show whether consistency KILLS passes or just DELAYS them.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]

def build(specs):
    dfs=[]
    for sp in specs:
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=sp["open_hr"],range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=sp.get("side","both"))
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True);dm={}
    for d,g in df.groupby(df["date"].dt.normalize()): dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

START=15000.;TARGET=1.1*START;TR=.10;DD=.03;MIN=4;MO=21;r=.0125;CONS=0.50
def coh(si,dm,rule,horizon):
    """returns (outcome, trading_day_of_outcome). horizon caps the search window."""
    eq=START;pk=START;fl=pk*(1-TR);td=0;daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j];ds=eq;dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq;dl=min(dl,low)
            if low<=fl: return "F",td+1
            eq=eq+r*R*eq
            if eq>pk:pk=eq;fl=pk*(1-TR)
            if eq<=fl: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return "F",td
        if eq>=TARGET and td>=MIN:
            if not rule: return "P",td
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
        # consistency unmet -> keep trading
    return "T",td

def report(nm,specs):
    dm=build(specs); st=range(len(ALLDAYS)-MO); N=len(st)
    # within 1 month
    no=[coh(si,dm,False,MO) for si in st]
    ye=[coh(si,dm,True ,MO) for si in st]
    # eventual (let it run up to ~4 months = 84 td)
    ev=[coh(si,dm,True ,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    print(f"{nm}")
    print(f"  pass<=1mo  no rule           : {p(no,'P'):5.1f}%")
    print(f"  pass<=1mo  WITH 50% rule      : {p(ye,'P'):5.1f}%   (fail {p(ye,'F'):.1f}%, unresolved {p(ye,'T'):.1f}%)")
    pe=[d for x,d in ev if x=='P']
    print(f"  EVENTUAL pass (<=4mo) w/ rule : {p(ev,'P'):5.1f}%   (fail {p(ev,'F'):.1f}%)   "
          f"median time-to-pass {np.median(pe):.0f}td (~{np.median(pe)/MO:.1f} months)")
    print()

print(f"$15k, +10% target, 10% trail, 3% daily, r={r*100:.2f}%, consistency=best day<=50% of total profit\n")
report("both-sides 15+16",[{"open_hr":15},{"open_hr":16}])
report("long-only 15+16",[{"open_hr":15,"side":"long"},{"open_hr":16,"side":"long"}])
print("takeaway: consistency forces you to keep trading past +10% to dilute big days. For")
print("long-only that mostly DELAYS the pass (45% eventual vs 26% in 1mo). For both-sides the")
print("extra time bleeds into the trailing DD (fail rises to 68%), so it ADDS failures. Net:")
print("the rule makes long-only clearly the better play, and turns the sprint into a ~1-2mo grind.")
