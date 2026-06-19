"""
FTMO deadline Monte Carlo on the NAS100 ORB candidate (one trade/day).
All 5 rules enforced:
  - 3% trailing daily loss  -> halt day at 2.8% buffer (MAE-aware on floating P&L)
  - 10% overall loss        -> FAIL at 9.5% buffer
  - 10% profit target       -> need eq >= 1.10*start
  - consistency             -> biggest single winning day <= 50% of total profit
  - min trading days        -> >=4 active days (FTMO style)
Day-block resampling: each block = one real trade-day (R, MAE_R).
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

t = pd.read_pickle("ftmo/m1_nas/nas_orb_trades.pkl")
RR = t["R"].values; MAE = t["MAE_R"].values
START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_PASS=0.50; MIN_DAYS=4

def run(r, deadline, rng):
    eq=START; total=0.0; day_profits=[]; nd=0
    while nd<deadline:
        i=rng.integers(len(RR))
        R=RR[i]; mae=MAE[i]; peak=eq
        # intraday floating loss from this one position
        floatloss = r*mae*eq
        if floatloss/peak >= DAILY_BUF:
            # daily loss line touched -> realize -2.8% day, halt
            pnl=-DAILY_BUF*peak
        else:
            pnl=r*R*eq
            # cap realized daily loss at 2.8% (stop can't lose more than 1R<2.8% anyway)
            if pnl < -DAILY_BUF*peak: pnl=-DAILY_BUF*peak
        eq+=pnl; total=eq-START; nd+=1
        day_profits.append(pnl)
        if eq<=GLOBAL: return "FAIL"
        if eq>=TARGET and nd>=MIN_DAYS:
            wins=[p for p in day_profits if p>0]
            if wins and max(wins) <= CONS_PASS*sum(wins):
                return "PASS"
            # else: consistency not met yet -> keep trading to dilute the big day
    # deadline reached: final check
    if eq>=TARGET and nd>=MIN_DAYS:
        wins=[p for p in day_profits if p>0]
        if wins and max(wins)<=CONS_PASS*sum(wins): return "PASS"
    return "TIMEOUT"

def mc(r,deadline,n=6000):
    rng=np.random.default_rng(7)
    res=pd.Series([run(r,deadline,rng) for _ in range(n)])
    return (res=="PASS").mean(),(res=="FAIL").mean(),(res=="TIMEOUT").mean()

print(f"NAS100 ORB candidate: n={len(RR)} trades, expR={RR.mean():+.3f}, "
      f"win={ (RR>0).mean()*100:.1f}%, maxR={RR.max():.1f}, ~5 trades/week\n")
print("Deadline-constrained FTMO pass rate (1 trade/day, all 5 rules):")
print(f"{'deadline':12s}", *[f"r={r*100:.2f}%        " for r in (0.01,0.015,0.02,0.025)])
for dl,label in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),
                 (40,"8 weeks"),(80,"16 weeks"),(250,"unlimited")]:
    row=f"{label:12s}"
    for r in (0.01,0.015,0.02,0.025):
        p,f,to=mc(r,dl)
        row+=f" P={p*100:4.1f} B={f*100:4.1f}  "
    print(row)
print("\n(P = pass %, B = blow-up %; remainder = timed out short of target)")
