"""
Comprehensive FTMO Monte Carlo — latest strat (BE@1R, trail 5R, range+vol filters).
Correct rules modelled:
  - stop loss: 60pt = 1R; a stopped trade = -1R; intraday MAE bounds floating loss
  - daily loss: one trade/day so worst day = ~1R (< 3% always)
  - overall: 10% END-OF-DAY TRAILING drawdown (ratchets up behind peak balance)
  - target: account balance +10%  (+ min 4 days + consistency: best day <= 50% of profit)
Reports: pass/blow/timeout %, avg & median time to pass, avg & median time to blow,
avg final balance, avg worst drawdown. Risk swept; floor-guard off vs on.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v3 import build_all, orb_v3

DAYS,ctx=build_all()
RR,MAE,DTS=orb_v3(DAYS,ctx,open_hr=16,range_min=30,stop_pts=60,be_at=1.0,trail_k=5.0,
                  cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,with_dates=True)
o=np.argsort([pd.Timestamp(x) for x in DTS]); RR=RR[o]; MAE=MAE[o]; DTS=[pd.Timestamp(DTS[i]) for i in o]
span_weeks=(DTS[-1]-DTS[0]).days/7.0
tpw=len(RR)/span_weeks   # real trades per calendar week
print(f"Strategy: BE@1R, trail5R, filters | {len(RR)} trades, expR={RR.mean():+.3f}, "
      f"win={(RR>0).mean()*100:.1f}%, PF={RR[RR>0].sum()/-RR[RR<0].sum():.2f}")
print(f"Trade frequency: {tpw:.2f} trades/week (used to convert trades -> weeks)\n")

START=15000.0; TARGET=1.10*START; TRAIL=0.10*START; MIN_DAYS=4; CONS=0.50

def simulate(r, guard, max_steps, rng):
    eq=START; peak=START; floor=START-TRAIL; profits=[]; n=0; worst=0.0
    while n<max_steps:
        rr=r
        if guard and (eq-floor)/eq < 0.05: rr=r*0.5     # floor defense
        if guard and (eq-floor) <= 0.01*START: return ("BLOW",n,eq,worst)  # hard stop hugging floor
        i=rng.integers(len(RR)); R=RR[i]; mae=MAE[i]; eb=eq
        if eb - rr*mae*eb <= floor: return ("BLOW",n+1,eb-rr*mae*eb,worst)  # floating breach
        eq=eb + rr*R*eb; n+=1; profits.append(eq-eb)
        dd=(peak-eq)/peak; worst=max(worst,dd)
        if eq<=floor: return ("BLOW",n,eq,worst)
        if eq>peak: peak=eq; floor=peak-TRAIL
        if eq>=TARGET and n>=MIN_DAYS:
            w=[p for p in profits if p>0]
            if w and max(w)<=CONS*sum(w): return ("PASS",n,eq,worst)
    return ("TIMEOUT",n,eq,worst)

def run(r, guard, N=20000, max_steps=300, seed=7):
    rng=np.random.default_rng(seed)
    res=[simulate(r,guard,max_steps,rng) for _ in range(N)]
    out=np.array([x[0] for x in res]); steps=np.array([x[1] for x in res])
    fin=np.array([x[2] for x in res]); worst=np.array([x[3] for x in res])
    P=out=="PASS"; B=out=="BLOW"; T=out=="TIMEOUT"
    def wk(a): return a/tpw
    d={"pass":P.mean()*100,"blow":B.mean()*100,"to":T.mean()*100,
       "pass_steps_mean":steps[P].mean() if P.any() else np.nan,
       "pass_steps_med":np.median(steps[P]) if P.any() else np.nan,
       "blow_steps_mean":steps[B].mean() if B.any() else np.nan,
       "blow_steps_med":np.median(steps[B]) if B.any() else np.nan,
       "fin":fin.mean(),"worstdd":worst.mean()*100}
    return d

def show(title, guard):
    print(f"=== {title} ===")
    print(f"{'risk':>5} | {'PASS':>5} {'BLOW':>5} {'TIME':>5} | "
          f"{'pass: avg wk (med)':>20} | {'blow: avg wk (med)':>20} | {'avg$end':>8} {'avgMaxDD':>8}")
    for r in (0.005,0.0075,0.01,0.011):
        d=run(r,guard)
        pa=f"{d['pass_steps_mean']/tpw:4.1f}wk ({d['pass_steps_med']/tpw:3.1f})" if d['pass']>0 else "  -"
        bl=f"{d['blow_steps_mean']/tpw:4.1f}wk ({d['blow_steps_med']/tpw:3.1f})" if d['blow']>0 else "  -"
        print(f"{r*100:4.2f}% | {d['pass']:4.1f}% {d['blow']:4.1f}% {d['to']:4.1f}% | "
              f"{pa:>20} | {bl:>20} | {d['fin']:8,.0f} {d['worstdd']:6.1f}%")
    print()

show("RAW strategy (no floor guard)  — understanding the stop loss", guard=False)
show("WITH floor guard (what the EA does, recommended)", guard=True)
print("Notes: 'TIME'=timed out (no pass/blow within ~70 weeks). Weeks via "
      f"{tpw:.1f} trades/wk. Target=+10% balance; blow=10% EOD-trailing drawdown.")
