"""
HONEST pass-rate: contiguous forward-calendar MC (preserves regime clustering) instead of
i.i.d. day-bootstrap (which mixes periods and overstates robustness). A real challenge runs
over ONE contiguous stretch, so it can land entirely inside a bad regime. For each real start
day we walk the actual day sequence forward (circular wrap for full runway) at a fixed risk %,
under FTMO static-floor rules, until pass/blow/timeout(252d). Reports overall pass/blow AND the
spread by start half-year -- the worst-period number is the real robustness metric.
Also scans a few config variants to see if any lifts the WORST period toward 95%.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from harness import build_trades

START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50

def day_seq(df):
    df=df.sort_values('date')
    days=[(pd.Timestamp(d), list(zip(g['R'].values,g['MAE'].values)))
          for d,g in df.groupby(df['date'].dt.normalize())]
    return days

def walk(days, start, r, horizon=252):
    n=len(days); eq=START; floor=STATIC; daypnl=[]; td=0
    for s in range(horizon):
        _,day=days[(start+s)%n]; ds=eq; dl=eq
        for (R,MAE) in day:
            low=eq-r*MAE*eq
            if low<dl: dl=low
            if low<=floor: return 'B',td+1
            eq=eq+r*R*eq
            if eq<=floor: return 'B',td+1
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DDAY: return 'B',td
        if eq>=TARGET and td>=MIN:
            pos=[x for x in daypnl if x>0]
            if pos and max(pos)<=CONS*sum(pos): return 'P',td
    return 'T',td

def evaluate(days, r):
    starts=range(len(days))
    res=[(days[i][0], *walk(days,i,r)) for i in starts]
    outc=[o for _,o,_ in res]
    P=100*outc.count('P')/len(res); B=100*outc.count('B')/len(res); T=100*outc.count('T')/len(res)
    # by start half-year
    def hy(ts): return f"{ts.year}H{1 if ts.month<7 else 2}"
    byhy={}
    for d,o,_ in res: byhy.setdefault(hy(d),[]).append(o)
    return P,B,T,byhy

CONFIGS={
 'baseline 15+16 both 3RTP 80pt': dict(open_hrs=[15,16],stop_pts=80,tp_R=3.0,side='both'),
 'vol-regime 0.4-1.0':            dict(open_hrs=[15,16],stop_pts=80,tp_R=3.0,side='both',atr_regime=(0.4,1.0)),
 'close-confirm':                 dict(open_hrs=[15,16],stop_pts=80,tp_R=3.0,side='both',close_confirm=True),
 'single sess 16':                dict(open_hrs=[16],stop_pts=80,tp_R=3.0,side='both'),
 'wider 120pt stop':              dict(open_hrs=[15,16],stop_pts=120,tp_R=3.0,side='both'),
}
R=0.005
print(f"HONEST contiguous forward-calendar MC | risk {R*100:.2f}% | static floor | horizon 252d\n")
for name,cfg in CONFIGS.items():
    tr,te,df=build_trades(cfg)
    days=day_seq(df)
    P,B,T,byhy=evaluate(days,R)
    worst=min((100*v.count('P')/len(v)) for v in byhy.values())
    print(f"{name}")
    print(f"  overall: PASS {P:.1f}%  BLOW {B:.1f}%  timeout {T:.1f}%   |   WORST start-half {worst:.1f}%")
    print("  by start half: "+"  ".join(f"{k}:{100*v.count('P')/len(v):.0f}%" for k,v in sorted(byhy.items())))
    print()
print("A robust >=95% requires the WORST start-half to be near 95%. If the worst period is far")
print("below, the strategy fails whenever a challenge lands in that regime -> 95% is not robust.")
