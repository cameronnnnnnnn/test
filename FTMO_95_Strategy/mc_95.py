"""
Full Monte-Carlo on the committed 95% config. 10k block-bootstrap paths from a fresh $15k
account under the complete FTMO rule set (+10% target, 3% daily, 50% best-day consistency,
min 4 days, static $13,500 floor = real FTMO; trailing peak-10% reported too).
Outputs a text summary + JSON (histograms, percentiles, sample equity curves) for charting.
"""
import sys, os, json
sys.path.insert(0,'/home/user/v4/ftmo/passopt')
import numpy as np
from evalcfg import build_df, _dayseq, START, TARGET, STATIC, DDAY, MIN, CONS, TOTAL_TD

CFG=json.load(open('/home/user/v4/FTMO_95_Strategy/strategy.json'))['engine_config']
df=build_df(CFG); DAYS=_dayseq(df); ND=len(DAYS); r=CFG['risk_pct']/100
CALM=TOTAL_TD/ND/21.0   # trade-days -> calendar months

def run(floor_mode, N=10000, seed=7, keep_curves=70):
    rng=np.random.default_rng(seed)
    out={'P':0,'B':0,'T':0}; ttp=[]; maxdd=[]; finals=[]; curves=[]
    for k in range(N):
        eq=START; peak=START; floor=STATIC if floor_mode=='static' else peak*0.9
        dp=[]; td=0; pib=999; bs=0; res='T'; lowest=eq; hi=eq; curve=[eq]
        for s in range(600):
            if pib>=120: bs=rng.integers(0,ND); pib=0
            _,day=DAYS[(bs+pib)%ND]; pib+=1; ds=eq; dl=eq
            for (R,MAE) in day:
                low=eq-r*MAE*eq; dl=min(dl,low); lowest=min(lowest,low)
                if low<=floor: res='B'; break
                eq=eq+r*R*eq
                if eq>peak: peak=eq
                if floor_mode=='trail' and eq>peak-1e-9: floor=peak*0.9
                if eq<=floor: res='B'; break
            hi=max(hi,eq)
            if res=='B': break
            td+=1; dp.append(eq-ds)
            if k<keep_curves: curve.append(eq)
            if (ds-dl)/ds>=DDAY: res='B'; break
            if eq>=TARGET and td>=MIN:
                pos=[x for x in dp if x>0]
                if pos and max(pos)<=CONS*sum(pos): res='P'; break
        out[res]+=1
        if res=='P': ttp.append(td*CALM); finals.append(eq)
        maxdd.append(100*(hi-lowest)/hi if hi>0 else 0)
        if k<keep_curves: curves.append((res,curve))
    return out,ttp,maxdd,finals,curves

for fl in ['static','trail']:
    o,ttp,mdd,fin,curves=run(fl)
    N=sum(o.values()); P=100*o['P']/N; B=100*o['B']/N; T=100*o['T']/N
    print(f"\n=== {fl.upper()} floor {'(REAL FTMO)' if fl=='static' else '(stress test)'} | 10,000 paths ===")
    print(f"  PASS {P:.1f}%   BLOW {B:.1f}%   still-running-at-cap {T:.1f}%")
    if ttp:
        q=np.percentile(ttp,[10,25,50,75,90])
        print(f"  time-to-pass (months): p10 {q[0]:.1f}  p25 {q[1]:.1f}  median {q[2]:.1f}  p75 {q[3]:.1f}  p90 {q[4]:.1f}")
    q2=np.percentile(mdd,[50,90,99])
    print(f"  max drawdown from peak: median {q2[0]:.1f}%  p90 {q2[1]:.1f}%  p99 {q2[2]:.1f}%  (fail floor = 10%)")
    if fin:
        print(f"  passing final balance : median ${np.median(fin):,.0f}  (target $16,500; overshoot = consistency dilution)")
    if fl=='static':
        # dump data for the chart
        edges=[round(float(x),1) for x in np.arange(0,12.5,0.5)]
        hist=[int(x) for x in np.histogram(ttp,bins=edges)[0]] if ttp else []
        json.dump(dict(N=int(N),pass_pct=round(P,1),blow_pct=round(B,1),to_pct=round(T,1),
            ttp_bins=edges[:-1], ttp_hist=hist,
            ttp_pct={str(p):round(float(np.percentile(ttp,p)),2) for p in [10,25,50,75,90]} if ttp else {},
            mdd_median=round(float(np.median(mdd)),1),
            curves=[dict(o=res,c=[round(x,1) for x in c]) for (res,c) in curves]),
            open('/home/user/v4/FTMO_95_Strategy/mc_95_data.json','w'))
print("\n[chart data -> FTMO_95_Strategy/mc_95_data.json]")
