"""
Trail-stop sweep under the FTMO 50% consistency rule.
Tests trail_k in [2, 3, 4, 5] for both-sides and long-only configs.
Tighter trails clip fat-tail winners into smaller per-day gains, potentially
satisfying the consistency rule more often without re-trading past +10%.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]

def build(specs):
    dfs=[]
    for sp in specs:
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=sp["open_hr"],range_min=30,
            stop_pts=80,be_at=1.0,trail_k=sp["trail_k"],cost=2.0,eod_hr=23,
            rng_filter=True,vol_confirm=True,side=sp.get("side","both"))
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()): dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def coh(si,dm,rule,horizon):
    eq=START; pk=START; fl=pk*(1-TR); td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq; dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=fl: return "F",td+1
            eq=eq+r*R*eq
            if eq>pk: pk=eq; fl=pk*(1-TR)
            if eq<=fl: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return "F",td
        if eq>=TARGET and td>=MIN:
            if not rule: return "P",td
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
    return "T",td

TRAILS=[2.0,3.0,4.0,5.0]

print(f"$15k, +10% target, 10% trail, 3% daily, r={r*100:.2f}%, consistency=best day<=50% of profit\n")
print(f"{'trail':>5}  {'side':>10}  {'no-rule 1mo':>12}  {'rule 1mo':>9}  {'rule 4mo':>9}  {'fail 4mo':>9}  {'med days':>8}")
print("-"*72)

for trail in TRAILS:
    for label,side in [("both-sides","both"),("long-only","long")]:
        specs=[{"open_hr":15,"trail_k":trail,"side":side},{"open_hr":16,"trail_k":trail,"side":side}]
        dm=build(specs)
        st=range(len(ALLDAYS)-MO); N=len(st)
        no=[coh(si,dm,False,MO) for si in st]
        ye=[coh(si,dm,True ,MO) for si in st]
        ev=[coh(si,dm,True ,84) for si in st]
        p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
        pe=[d for x,d in ev if x=='P']
        med=np.median(pe) if pe else float('nan')
        print(f"{trail:>5.0f}R  {label:>10}  {p(no,'P'):>11.1f}%  {p(ye,'P'):>8.1f}%  {p(ev,'P'):>8.1f}%  {p(ev,'F'):>8.1f}%  {med:>7.0f}td")
    print()

print()
print("Key: rule 1mo = pass within 1 month WITH consistency rule")
print("     rule 4mo = eventual pass within 4 months WITH consistency rule")
print("     fail 4mo = blown out within 4 months WITH rule")
print("     Tighter trail → smaller per-day max → satisfies consistency more easily")
print("     but also lowers expectancy. Look for sweet spot in rule 4mo × fail tradeoff.")
