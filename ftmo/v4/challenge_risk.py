"""
ftmo/v4/challenge_risk.py — risk sweep of the live challenge strat (ORB 50pt +
VWpull 40pt, 4R, US session) under FTMO 1-Step rules. Shows the speed-vs-safety
tradeoff: pass%, blow% (+ how many via the 3% daily limit), time-to-pass, timeout.
Run-to-completion, cap 1 year. Run: python3 challenge_risk.py
"""
import numpy as np
import data, strategies as S
import challenge_mc as C

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin,tr=C.combo_days(df,ad)
    print("="*92)
    print("CHALLENGE RISK SWEEP — ORB 50pt + VWpull 40pt, 4R  (run-to-completion, 1yr cap)")
    print("="*92)
    print(f"  {'risk':>5} | {'PASS%':>6} {'BLOW%':>6} {'dailyBlow':>10} {'timeout%':>9} | "
          f"{'avg days':>9} {'med days':>9} {'4wk pass':>9}")
    print("-"*92)
    for r in [0.005,0.0075,0.01,0.0125,0.015,0.02]:
        m=C.mc(dR,dmin,tr,risk=r,N=100000)
        p,b,bd,tp,tb=m["passed"],m["blown"],m["bdaily"],m["tpass"],m["tblow"]
        to=(~p&~b).mean(); td=tp[p]+1
        dshare=bd.sum()/max(b.sum(),1)*100
        pass4=(p&(tp<20)).mean()*100
        print(f"  {r*100:4.2f}% | {p.mean()*100:5.1f}% {b.mean()*100:5.1f}% {dshare:8.0f}%* {to*100:8.1f}% | "
              f"{td.mean():7.1f}d {np.median(td):7.0f}d {pass4:7.1f}%")
    print("-"*92)
    print("  *dailyBlow = share of blows caused by the 3% daily limit (rest = the 10% floor)")
    print("  avg/med days = time to hit +10% (passers only); 4wk pass = pass within 20 trading days")

if __name__=="__main__":
    main()
