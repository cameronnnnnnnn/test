"""
HARD TAKE-PROFIT test: does adding a fixed TP (3R/4R/5R) beat trail-only exit?

Why this could help (and why it's different from the trail sweep):
  Trail-only lets winners run unbounded -> fat tail -> 60% of profit from top 10% of
  trades -> the FTMO 50% CONSISTENCY rule bites hard (one monster day > 50% of profit).
  A hard TP TRUNCATES that tail: every win caps at e.g. 4R, so days are more uniform
  (helps consistency) AND trades that ran to 4R then trailed back to BE now bank a clean
  win (raises WR). The cost is giving up the occasional 10R+ runner (lowers raw expR).
  Net effect on 1-MONTH PASS + WR is exactly what this measures.

Three tests, all FTMO sprint ($15k, +10%, 10% trail, 3% daily, r=1.25%, 15h+16h):
  (1) Edge table         : WR / expR / PF / avg win / avg loss / maxR  per config
  (2) Consistency MC     : forward-CALENDAR walk w/ 50% rule -> pass<=1mo, pass<=4mo, fail
  (3) Regime-switching MC: regime-aware day bootstrap vs i.i.d. -> blow-up + 1mo pass
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]

START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

# ---------- build a config's day->trades map and its flat trade arrays ----------
def build(side, tp_R):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,tp_R=tp_R)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True).sort_values("date").reset_index(drop=True)
    dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    df["atrpct"]=df["date"].dt.normalize().map(lambda d: ctx.get(pd.Timestamp(d),{}).get("atrpct",np.nan))
    return dm,df

# ---------- (2) forward-calendar consistency-rule walk ----------
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

def consistency_row(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    no=[coh(si,dm,False,MO) for si in st]
    ye=[coh(si,dm,True ,MO) for si in st]
    ev=[coh(si,dm,True ,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    pe=[d for x,d in ev if x=='P']
    return dict(no1=p(no,'P'), rule1=p(ye,'P'), rule4=p(ev,'P'),
                fail4=p(ev,'F'), med=np.median(pe) if pe else float('nan'))

# ---------- (3) regime-switching MC (consistency-aware) ----------
def regime_mc(df, N=15000, seed=7):
    d2=df.dropna(subset=["atrpct"]).copy()
    days=[]
    for d,g in d2.groupby(d2["date"].dt.normalize()):
        days.append(dict(trades=list(zip(g["R"].values,g["MAE"].values)),
                         atrpct=float(g["atrpct"].iloc[0])))
    if len(days)<10: return None
    ap=np.array([x["atrpct"] for x in days]); cut=np.median(ap)
    for x in days: x["reg"]=1 if x["atrpct"]>cut else 0
    ND=len(days)
    T=np.zeros((2,2))
    for i in range(ND-1): T[days[i]["reg"]][days[i+1]["reg"]]+=1
    T=T/np.clip(T.sum(axis=1,keepdims=True),1,None)
    w,v=np.linalg.eig(T.T); pi=np.real(v[:,np.argmin(abs(w-1))]); pi=pi/pi.sum()
    pools={g:[x["trades"] for x in days if x["reg"]==g] for g in (0,1)}

    def apply_day(dt,eq,peak,floor):
        ds=eq; dl=eq
        for (R,MAE) in dt:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: return eq,peak,floor,"blow",ds
            eq=eq+r*R*eq
            if eq>peak: peak=eq; floor=peak*(1-TR)
            if eq<=floor: return eq,peak,floor,"blow",ds
        if (ds-dl)/ds>=DD: return eq,peak,floor,"blow",ds
        return eq,peak,floor,None,ds

    def sim(mode,rng,maxd=84):
        eq=START; peak=START; floor=START*(1-TR); td=0; dp=[]
        cur=rng.choice(2,p=pi) if mode=="regime" else None
        while td<maxd:
            dt=pools[cur][rng.integers(len(pools[cur]))] if mode=="regime" else days[rng.integers(ND)]["trades"]
            eq,peak,floor,oc,ds=apply_day(dt,eq,peak,floor); td+=1; dp.append(eq-ds)
            if oc=="blow": return "B",td
            if eq>=TARGET and td>=MIN:
                tot=eq-START
                if tot>0 and max(dp)<=CONS*tot: return "P",td
            if mode=="regime": cur=rng.choice(2,p=T[cur])
        return "T",td
    out={}
    for mode in ("iid","regime"):
        rng=np.random.default_rng(seed)
        res=[sim(mode,rng) for _ in range(N)]
        oc=np.array([x[0] for x in res]); dy=np.array([x[1] for x in res])
        out[mode]=dict(p1=100*((oc=='P')&(dy<=MO)).mean(),
                       p4=100*(oc=='P').mean(), blow=100*(oc=='B').mean())
    return out

# ---------- edge stats ----------
def edge(df):
    R=df["R"].values; w=R[R>0]; l=R[R<=0]; n=len(R)
    return dict(n=n, wr=100*len(w)/n, expR=R.mean(),
                pf=(w.sum()/-l.sum()) if l.sum()<0 else float('inf'),
                avgw=w.mean() if len(w) else 0, avgl=l.mean() if len(l) else 0,
                maxR=R.max())

# ==================================================================================
CONFIGS=[("trail-only",None),("TP 4R",4.0),("TP 3R",3.0),("TP 2.5R",2.5),
         ("TP 2R",2.0),("TP 1.5R",1.5)]   # 2R is the validated optimum (fine grid: 2.0 beats 1.75/2.25)
for side,label in [("long","LONG-ONLY"),("both","BOTH-SIDES")]:
    print(f"\n{'='*82}\n  {label}   ($15k, +10%, 10% trail, 3% daily, r=1.25%, 15h+16h, BE@1R, trail 5R)\n{'='*82}")
    # (1) edge
    print(f"\n(1) EDGE per exit style")
    print(f"  {'exit':<11}{'n':>5}{'WR':>7}{'expR':>8}{'PF':>6}{'avgW':>7}{'avgL':>7}{'maxR':>7}")
    print("  "+"-"*48)
    built={}
    for nm,tp in CONFIGS:
        dm,df=build(side,tp); built[nm]=(dm,df); e=edge(df)
        print(f"  {nm:<11}{e['n']:>5}{e['wr']:>6.1f}%{e['expR']:>+8.3f}{e['pf']:>6.2f}"
              f"{e['avgw']:>+7.2f}{e['avgl']:>+7.2f}{e['maxR']:>+7.1f}")
    # (2) consistency MC
    print(f"\n(2) CONSISTENCY-RULE forward-calendar MC (the realistic FTMO number)")
    print(f"  {'exit':<11}{'no-rule 1mo':>12}{'rule 1mo':>10}{'rule 4mo':>10}{'fail 4mo':>10}{'medDays':>9}")
    print("  "+"-"*60)
    for nm,tp in CONFIGS:
        c=consistency_row(built[nm][0])
        print(f"  {nm:<11}{c['no1']:>11.1f}%{c['rule1']:>9.1f}%{c['rule4']:>9.1f}%{c['fail4']:>9.1f}%{c['med']:>8.0f}td")
    # (3) regime switching
    print(f"\n(3) REGIME-SWITCHING MC vs i.i.d. (consistency-aware, N=15k)")
    print(f"  {'exit':<11}{'method':>9}{'pass 1mo':>10}{'pass 4mo':>10}{'BLOW':>8}")
    print("  "+"-"*48)
    for nm,tp in CONFIGS:
        rm=regime_mc(built[nm][1])
        if rm is None: continue
        for mode in ("iid","regime"):
            x=rm[mode]
            print(f"  {nm if mode=='iid' else '':<11}{('i.i.d.' if mode=='iid' else 'regime'):>9}"
                  f"{x['p1']:>9.1f}%{x['p4']:>9.1f}%{x['blow']:>7.1f}%")
        print("  "+"-"*48)

print("\nRead: hard TP wins only if it RAISES 'rule 1mo'/'rule 4mo' (or WR) without")
print("blowing up 'fail 4mo'. Capping the tail trades raw expR for consistency compliance.")
