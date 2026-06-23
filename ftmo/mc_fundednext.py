"""
FundedNext Futures Flex $50k optimizer.
Rules: start $50k, target +$2,500 (5%), $1,500 TRAILING EOD drawdown (floor ratchets up on
each higher END-OF-DAY balance, caps/locks at the $50k start), NO daily loss limit, NO min
days, consistency = best day <= 40% of total profit (dilutable: exceeding raises the bar).

Instrument: NQ/MNQ. 80pt stop. 1 micro (MNQ) over 80pt = $2*80 = $160 risk = 0.32% of $50k.
So risk steps in micros: 1=0.32%, 2=0.64%, 3=0.96%, 4=1.28%, 5=1.60%, 6=1.92%, 7=2.24%.
(Contract cap 3 minis/30 micros = $60/pt = $4,800 = 9.6%, never binding here.)

Sweeps risk x direction. Reports pass<=1mo, eventual pass (<=1yr, before blowing the $1,500),
blow-up rate, and median days-to-pass.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=50000.; TGTP=2500.; TARGET=START+TGTP; ML=1500.; LOCK=START; CONS=0.40
MO=21; HORIZON=252

def build(side, tp_R=3.0):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,tp_R=tp_R,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

def coh(si,dm,r,horizon):
    eq=START; floor=START-ML; td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq
            if low<=floor: return "F",td+1
            eq=eq+r*R*eq
            if eq<=floor: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        floor=max(floor, min(LOCK, eq-ML))           # trailing EOD drawdown, locks at start
        if eq>=TARGET:                                # no min days, no daily limit
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td   # best day <= 40% of total profit
    return "T",td

def metrics(dm,r):
    st=range(len(ALLDAYS)-MO); N=len(st)
    mo=[coh(si,dm,r,MO) for si in st]
    ev=[coh(si,dm,r,HORIZON) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    pe=[d for x,d in ev if x=='P']
    return p(mo,'P'), p(ev,'P'), p(ev,'F'), (np.median(pe) if pe else float('nan'))

MICROS=[(1,0.0032),(2,0.0064),(3,0.0096),(4,0.0128),(5,0.0160),(6,0.0192),(7,0.0224)]
for side in ("long","both"):
    print(f"\n{'='*72}\n  {side.upper()}  (3R TP, 15h+16h)  FundedNext Flex $50k / +$2,500 / $1,500 EOD trail\n{'='*72}")
    print(f"  {'risk':<16}{'pass1mo':>9}{'eventual':>10}{'blow':>8}{'med days':>10}")
    print("  "+"-"*52)
    dm=build(side)
    for nc,r in MICROS:
        m=metrics(dm,r)
        print(f"  {str(nc)+' MNQ ('+format(r*100,'.2f')+'%)':<16}{m[0]:>8.1f}%{m[1]:>9.1f}%{m[2]:>7.1f}%{m[3]:>9.0f}td")
print("\n(eventual = pass before blowing the $1,500 trailing DD, within ~1yr)")
