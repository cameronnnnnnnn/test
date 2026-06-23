"""
Is the 80pt stop too tight? Tests whether WIDER stops (which survive wicks like the ORB16
trade) actually improve results, or just trade fewer stop-outs for bigger losses + harder TPs.
Stop is in PRICE points; TP/BE are in R so they scale with the stop. RiskPercent is constant
(1.25%), so a -1R loss is always 1.25% regardless of stop width -- a wider stop = smaller lots.
Also reports MAE stats: how often eventual WINNERS dipped close to the 1R stop before running.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, stop_pts=None, atr_stop=None):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,
            stop_pts=(stop_pts if stop_pts else 80.0),atr_stop=atr_stop,
            be_at=1.0,trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm, df

def coh(si,dm,horizon):
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
            pos=[d for d in daypnl if d>0]
            if pos and max(pos)<=CONS*sum(pos): return "P",td
    return "T",td

def metrics(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,MO) for si in st]; ev=[coh(si,dm,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    return p(ye,'P'), p(ev,'P'), p(ev,'F')

print("3R TP, BE@1R, long-only, best-day rule | STOP-SIZE sweep (RiskPercent fixed 1.25%)")
print(f"{'stop':<16}{'WR':>7}{'expR':>8}{'maxR':>7}{'#trades':>8}   {'pass1mo':>8}{'pass4mo':>9}{'blow4mo':>9}")
print("-"*74)
configs=[("60pt",dict(stop_pts=60)),("80pt (current)",dict(stop_pts=80)),
         ("100pt",dict(stop_pts=100)),("120pt",dict(stop_pts=120)),("150pt",dict(stop_pts=150)),
         ("1.0xATR",dict(atr_stop=1.0)),("1.5xATR",dict(atr_stop=1.5))]
for nm,kw in configs:
    dm,df=build("long",**kw); R=df["R"].values; wr=100*(R>0).mean(); m=metrics(dm)
    print(f"{nm:<16}{wr:>6.1f}%{R.mean():>+8.3f}{R.max():>+7.1f}{len(R):>8}   {m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%")

# MAE: of eventual WINNERS, how deep did they dig before running? (at the current 80pt stop)
dm,df=build("long",stop_pts=80)
win=df[df["R"]>0]; los=df[df["R"]<=0]
print(f"\nMAE of WINNERS (how close eventual winners came to the 1R stop), 80pt stop:")
print(f"  median {win['MAE'].median():.2f}R   p75 {win['MAE'].quantile(.75):.2f}R   "
      f"p90 {win['MAE'].quantile(.90):.2f}R   max {win['MAE'].max():.2f}R")
print(f"  winners that dipped past 0.8R before running: {100*(win['MAE']>0.8).mean():.1f}%  "
      f"(these are the ones a slightly wider stop would 'save')")
