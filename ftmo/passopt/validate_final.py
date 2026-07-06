"""
Full rigor battery on the vol-regime candidate (causal atrpct, both-sides, 3R TP, 80pt).
A) Threshold plateau at 0.50% risk (full data) -- is it broad or a spike?
B) Honest OOS: pick threshold on TRAIN (<2024-10), evaluate untouched on TEST (>=2024-10).
   Report each set's forward-calendar pass + worst-start-half + per-trade edge 90% CI.
C) Risk re-sweep WITH the filter: fastest config still >=95% worst-half. Calendar-time honest.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,CTX=build_all()
order=[d[0] for d in DAYS]
CAUSAL={}; prev=np.nan
for day in order:
    cur=CTX.get(day,{}).get('atrpct',np.nan); cc=dict(CTX.get(day,{})); cc['atrpct']=prev; CAUSAL[day]=cc; prev=cur
SPLIT=pd.Timestamp('2024-10-01')
START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50
TOTAL_TD=len(order)  # all trading days in the data

def trades(reg):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,CAUSAL,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,be_at=1.0,
            trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side='both',atr_regime=reg)
        dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
    return pd.concat(dfs,ignore_index=True).sort_values('date')

def dayseq(df): return [(pd.Timestamp(d),list(zip(g['R'].values,g['MAE'].values))) for d,g in df.groupby(df['date'].dt.normalize())]
def walk(days,i,r,H=300):
    n=len(days); eq=START; floor=STATIC; dp=[]; td=0
    for s in range(H):
        _,day=days[(i+s)%n]; ds=eq; dl=eq
        for (R,MAE) in day:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: return 'B',td+1
            eq=eq+r*R*eq
            if eq<=floor: return 'B',td+1
        td+=1; dp.append(eq-ds)
        if (ds-dl)/ds>=DDAY: return 'B',td
        if eq>=TARGET and td>=MIN:
            pos=[x for x in dp if x>0]
            if pos and max(pos)<=CONS*sum(pos): return 'P',td
    return 'T',td
def ev(days,r):
    res=[(days[i][0],*walk(days,i,r)) for i in range(len(days))]
    P=100*sum(o=='P' for _,o,_ in res)/len(res); B=100*sum(o=='B' for _,o,_ in res)/len(res)
    def hy(t): return f"{t.year}H{1 if t.month<7 else 2}"
    bh={};
    for d,o,_ in res: bh.setdefault(hy(d),[]).append(o)
    worst=min(100*v.count('P')/len(v) for v in bh.values())
    pdays=[t for _,o,t in res if o=='P']
    ntd=len(days); cal=(np.median(pdays)*TOTAL_TD/ntd) if pdays else np.nan  # trade-days -> calendar trading days
    return P,B,worst,cal,bh
def ci(df):
    R=df['R'].values; rng=np.random.default_rng(1); n=len(R)
    m=np.array([R[rng.integers(0,n,n)].mean() for _ in range(4000)])
    return R.mean(),np.percentile(m,5),np.percentile(m,95),n

print("A) THRESHOLD PLATEAU @0.50% risk (full data, causal)")
for lo in [0.35,0.4,0.45,0.5,0.55,0.6]:
    d=dayseq(trades((lo,1.0))); P,B,w,cal,_=ev(d,0.005)
    print(f"   vol {lo:.2f}-1.0 : pass {P:5.1f}%  blow {B:4.1f}%  worst-half {w:5.1f}%  ~{cal/21:.1f}mo")

print("\nB) HONEST OOS: threshold fixed at 0.5 (mid-plateau), TRAIN vs TEST separately")
df=trades((0.5,1.0))
for setn,sub in [('TRAIN',df[df['date']<SPLIT]),('TEST ',df[df['date']>=SPLIT])]:
    d=dayseq(sub); P,B,w,cal,bh=ev(d,0.005); mR,l,h,n=ci(sub)
    sig='EDGE (CI>0)' if l>0 else 'CI incl 0'
    print(f"   {setn}: pass {P:5.1f}%  blow {B:4.1f}%  worst-half {w:5.1f}%  edge {mR:+.3f}[{l:+.3f},{h:+.3f}] {sig}  n={n}")
    print(f"          by half: "+" ".join(f"{k}:{100*v.count('P')/len(v):.0f}%" for k,v in sorted(bh.items())))

print("\nC) RISK RE-SWEEP with vol 0.5-1.0 (find fastest config still >=95% worst-half)")
d=dayseq(trades((0.5,1.0)))
for rp in [0.5,0.75,1.0,1.25,1.5]:
    P,B,w,cal,_=ev(d,rp/100)
    print(f"   risk {rp:.2f}% : pass {P:5.1f}%  blow {B:4.1f}%  worst-half {w:5.1f}%  medPass ~{cal/21:.1f} months")
