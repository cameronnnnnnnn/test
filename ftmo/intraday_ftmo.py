"""
Intraday FTMO simulator with a DEADLINE, using real per-trade R and MAE
(max adverse excursion) so the 2.8% intraday daily-loss rule is enforced on the
real worst floating drawdown, not just on closes.

Goal under test: pass the FTMO 1-Step (+10%) within `deadline` trading days.
Anything not passed by the deadline counts as a FAIL for the 2-week question.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import intraday_engine as E

START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_STOP=0.45; CONS_PASS=0.50; MIN_DAYS=3

def day_blocks(tr):
    out=[]
    for _,g in tr.groupby("date",sort=True):
        out.append(list(zip(g["R"].values, g["MAE_R"].values)))
    return out

def run(blocks, r, deadline, rng):
    eq=START; total=0.0; dayp=[]; nd=0
    while nd<deadline:
        day=blocks[rng.integers(len(blocks))]
        peak=eq; today=0.0
        for (R,mae) in day:
            if eq<=GLOBAL: return ("FAIL",eq,nd)
            if (peak-eq)/peak>=DAILY_BUF: break
            if total>0 and today>=CONS_STOP*total: break
            # intraday: would MAE breach the daily 2.8% from peak before target/stop?
            float_low = eq - r*mae*eq
            if (peak-float_low)/peak >= DAILY_BUF:
                # forced out at the daily-loss line this bar
                loss = -((DAILY_BUF*peak)-(peak-eq))   # bring equity down to the 2.8% line
                eq += loss; today+=loss; total+=loss
                break
            pnl=r*R*eq
            eq+=pnl; today+=pnl; total+=pnl
            if eq>peak: peak=eq
            if eq<=GLOBAL: return ("FAIL",eq,nd)
        nd+=1; dayp.append(today)
        if eq>=TARGET and nd>=MIN_DAYS:
            w=[p for p in dayp if p>0]
            if not w or max(w)<=CONS_PASS*total: return ("PASS",eq,nd)
    return ("TIMEOUT",eq,nd)   # missed deadline = fail for the 2-week goal

def mc(tr, r, deadline, n=4000, seed=3):
    rng=np.random.default_rng(seed)
    b=day_blocks(tr)
    res=[run(b,r,deadline,rng) for _ in range(n)]
    res=pd.DataFrame(res,columns=["result","eq","days"])
    return ((res["result"]=="PASS").mean(),
            (res["result"]=="FAIL").mean(),
            (res["result"]=="TIMEOUT").mean())

if __name__=="__main__":
    m1=E.load_m1(); b15=E.resample(m1,"15min")
    # least-bad high-frequency intraday strat from the scan (BB mean-revert)
    def bb(bars,n=20,k=2.0):
        c=bars["close"].values; m=pd.Series(c).rolling(n).mean().values
        sd=pd.Series(c).rolling(n).std().values
        out=np.zeros(len(c)); out[c<m-k*sd]=1; out[c>m+k*sd]=-1; out[:n]=0; return out
    tr=E.backtest(b15,bb,18,1.0,session=(7,20),flat_hour=20,slip_pips=0.2)
    st=E.trade_stats(tr)
    print(f"Intraday BB-revert: n={st['n']} t/day={st['tpd']:.2f} expR={st['expR']:+.3f} PF={st['pf']:.2f}\n")
    print("2-WEEK (10 trading-day) DEADLINE — pass rate vs risk:")
    for r in (0.005,0.01,0.02,0.03,0.05):
        p,f,t=mc(tr,r,10,n=4000)
        print(f"  r={r*100:4.1f}%  PASS={p*100:5.1f}%  blowup={f*100:5.1f}%  missed-deadline={t*100:5.1f}%")
    print("\nFor reference, same strat with NO deadline (60 days):")
    for r in (0.005,0.01,0.02):
        p,f,t=mc(tr,r,60,n=4000)
        print(f"  r={r*100:4.1f}%  PASS={p*100:5.1f}%  blowup={f*100:5.1f}%  timeout={t*100:5.1f}%")
