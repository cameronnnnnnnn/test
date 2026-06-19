"""
FINAL NAS100 strategy + definitive FTMO deadline x risk Monte Carlo.
Config (locked): US cash session 16h-server opening-range breakout,
  30-min range, 60pt fixed stop, trail at 3R, flat by EOD, no Friday/weekend hold.
Cost 2pt (stress-checked to 6pt earlier). One trade/day => clean 1R daily risk.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from nas_intraday import orb

df=orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=60,trail_R=3.0,eod_hr=23)
df=df.sort_values("date").reset_index(drop=True)
df.to_pickle("ftmo/m1_nas/nas_final_trades.pkl")
RR=df["R"].values; MAE=df["MAE_R"].values

# walk-forward recap
cut=int(len(df)*0.6); ins=df.iloc[:cut]["R"]; oos=df.iloc[cut:]["R"]
print("=== FINAL NAS100 ORB (16h US, range30, stop60, trail3R, EOD) ===")
print(f"trades={len(RR)}  ~5/wk  expR={RR.mean():+.3f}  win={(RR>0).mean()*100:.1f}%  "
      f"PF={RR[RR>0].sum()/-RR[RR<0].sum():.2f}  maxR={RR.max():.1f}")
print(f"walk-forward: in-sample expR={ins.mean():+.3f}  out-of-sample expR={oos.mean():+.3f}")
print(f"long {df[df.dir>0]['R'].mean():+.3f}R  short {df[df.dir<0]['R'].mean():+.3f}R\n")

START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_PASS=0.50; MIN_DAYS=4

def run(r,deadline,rng):
    eq=START; dp=[]; nd=0
    while nd<deadline:
        i=rng.integers(len(RR)); R=RR[i]; mae=MAE[i]; peak=eq
        if r*mae*eq/peak>=DAILY_BUF: pnl=-DAILY_BUF*peak
        else:
            pnl=r*R*eq
            if pnl<-DAILY_BUF*peak: pnl=-DAILY_BUF*peak
        eq+=pnl; nd+=1; dp.append(pnl)
        if eq<=GLOBAL: return "FAIL"
        if eq>=TARGET and nd>=MIN_DAYS:
            w=[p for p in dp if p>0]
            if w and max(w)<=CONS_PASS*sum(w): return "PASS"
    if eq>=TARGET and nd>=MIN_DAYS:
        w=[p for p in dp if p>0]
        if w and max(w)<=CONS_PASS*sum(w): return "PASS"
    return "TIMEOUT"

def mc(r,dl,n=8000):
    rng=np.random.default_rng(5)
    res=pd.Series([run(r,dl,rng) for _ in range(n)])
    return (res=="PASS").mean(),(res=="FAIL").mean(),(res=="TIMEOUT").mean()

print("Definitive FTMO pass rate  (P=pass% B=blowup% T=timeout%), all 5 rules:")
print(f"{'deadline':11s} | " + " | ".join(f"r={r*100:.1f}%" for r in (0.01,0.015,0.02)))
for dl,lab in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),(30,"6 weeks"),
               (40,"8 weeks"),(60,"12 weeks"),(120,"24 weeks"),(400,"unlimited")]:
    cells=[]
    for r in (0.01,0.015,0.02):
        p,f,t=mc(r,dl); cells.append(f"P{p*100:4.1f} B{f*100:4.1f} T{t*100:4.1f}")
    print(f"{lab:11s} | " + " | ".join(cells))
