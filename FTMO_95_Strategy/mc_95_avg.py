"""
100,000-path Monte-Carlo on the 95% config, static (real FTMO) floor.
Groups the 100k runs into 100 groups of 1,000 and averages each group's equity curve
(runs padded past resolution by holding their terminal value: pass=final balance, fail=$13,500).
Outputs pass/fail% and the 100 averaged curves for the chart.
"""
import sys, os, json
sys.path.insert(0,'/home/user/v4/ftmo/passopt')
import numpy as np
from evalcfg import build_df, _dayseq, START, TARGET, STATIC, DDAY, MIN, CONS, TOTAL_TD

CFG=json.load(open('/home/user/v4/FTMO_95_Strategy/strategy.json'))['engine_config']
df=build_df(CFG); DAYS=_dayseq(df); ND=len(DAYS); r=CFG['risk_pct']/100
CALM=TOTAL_TD/ND/21.0
N=100000; GROUP=1000; NG=N//GROUP; L=100   # curve length in trade-days

rng=np.random.default_rng(7)
npass=nfail=0; ttp=[]
gsum=np.zeros(L); gcount=0; avg_curves=[]
for k in range(N):
    eq=START; floor=STATIC; dp=[]; td=0; pib=999; bs=0; res='T'
    curve=[eq]
    for s in range(600):
        if pib>=120: bs=rng.integers(0,ND); pib=0
        _,day=DAYS[(bs+pib)%ND]; pib+=1; ds=eq; dl=eq
        blown=False
        for (R,MAE) in day:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: res='B'; blown=True; break
            eq=eq+r*R*eq
            if eq<=floor: res='B'; blown=True; break
        if blown: break
        td+=1; dp.append(eq-ds); curve.append(eq)
        if (ds-dl)/ds>=DDAY: res='B'; break
        if eq>=TARGET and td>=MIN:
            pos=[x for x in dp if x>0]
            if pos and max(pos)<=CONS*sum(pos): res='P'; break
    term = eq if res=='P' else STATIC
    if res=='P': npass+=1; ttp.append(td*CALM)
    elif res=='B': nfail+=1
    # pad to L holding terminal
    arr=np.full(L, term)
    m=min(len(curve),L); arr[:m]=curve[:m]
    gsum+=arr; gcount+=1
    if gcount==GROUP:
        avg_curves.append([round(float(v),1) for v in (gsum/GROUP)]); gsum=np.zeros(L); gcount=0

P=100*npass/N; B=100*nfail/N
print(f"100,000 paths | static floor | PASS {P:.2f}%  FAIL {B:.2f}%")
print(f"median time-to-pass ~{np.median(ttp):.1f} months")
edges=[round(float(x),1) for x in np.arange(0,12.5,0.5)]
hist=[int(x) for x in np.histogram(ttp,bins=edges)[0]]
json.dump(dict(N=N, pass_pct=round(P,1), fail_pct=round(B,1),
    months_per_step=round(CALM,4), avg_curves=avg_curves,
    ttp_bins=edges[:-1], ttp_hist=hist,
    ttp_median=round(float(np.median(ttp)),2)),
    open('/home/user/v4/FTMO_95_Strategy/mc_95_avg_data.json','w'))
print("[data -> FTMO_95_Strategy/mc_95_avg_data.json]  (100 averaged curves)")
