import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

allt = pd.read_pickle("ftmo/m1/mp_daily_trades.pkl")
START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_STOP=0.45; CONS_PASS=0.50; MIN_DAYS=3

# day blocks: list per active date of [(R, MAE_R), ...]
blocks=[list(zip(g["R"].values,g["MAE_R"].values)) for _,g in allt.groupby("date",sort=True)]

def run(r, deadline, rng, max_concurrent=4):
    eq=START; total=0.0; dp=[]; nd=0
    while nd<deadline:
        day=blocks[rng.integers(len(blocks))]
        # cap concurrent positions so worst-case daily loss respects 2.8%
        day=day[:max_concurrent]
        peak=eq; today=0.0
        # worst intraday floating loss from all positions held that day (MAE)
        intraday_loss=sum(r*mae*eq for (_,mae) in day)
        if (intraday_loss)/peak >= DAILY_BUF:
            # daily-loss line touched -> realize -2.8% for the day, halt day
            loss=-DAILY_BUF*peak; eq+=loss; today=loss; total+=loss
            nd+=1; dp.append(today)
            if eq<=GLOBAL: return "FAIL"
            continue
        for (R,mae) in day:
            if eq<=GLOBAL: return "FAIL"
            if total>0 and today>=CONS_STOP*total: break
            pnl=r*R*eq; eq+=pnl; today+=pnl; total+=pnl
            if eq>peak: peak=eq
        nd+=1; dp.append(today)
        if eq<=GLOBAL: return "FAIL"
        if eq>=TARGET and nd>=MIN_DAYS:
            w=[p for p in dp if p>0]
            if not w or max(w)<=CONS_PASS*total: return "PASS"
    return "TIMEOUT"

def mc(r,deadline,n=4000,maxc=4):
    rng=np.random.default_rng(9)
    res=[run(r,deadline,rng,maxc) for _ in range(n)]
    res=pd.Series(res)
    return (res=="PASS").mean(),(res=="FAIL").mean(),(res=="TIMEOUT").mean()

print("Multi-pair DAILY, deadline-constrained pass rate (<=3% daily enforced)")
print("Each 'day' caps concurrent risk to respect the 2.8% daily halt.\n")
for dl,label in [(10,"2 weeks"),(15,"3 weeks"),(40,"~8 weeks"),(80,"~16 weeks"),(250,"unlimited")]:
    row=f"{label:11s} "
    for r in (0.005,0.0075,0.01):
        p,f,t=mc(r,dl)
        row+=f" | r={r*100:.2f}%: PASS={p*100:4.1f}% blow={f*100:4.1f}%"
    print(row)
