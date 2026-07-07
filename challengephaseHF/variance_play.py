"""
challengephaseHF/variance_play.py — the honest test of "0EV can pass via variance".

A prop challenge is a first-passage bet: reach +10% before -10% (with a 3% daily cap,
50% consistency, min 4 days, inside 20 trading days). By optional stopping, a driftless
(0EV) account hits +10% before -10% about 50% of the time with NO deadline and NO daily
cap. The question is how much the deadline + the one-sided 3% daily cap + consistency drag
that down, and what VARIANCE STRUCTURE (reward:risk, trades/day, risk %) maximizes the
20-day pass rate for a strategy with exactly zero edge.

Synthetic strategy: each trade wins +rr with prob wr, loses -1, with wr = 1/(1+rr) so
EV = 0 exactly (drift lets us make it slightly +/- to test sensitivity). k trades/day.
We build day_R and the intraday low (day_min) from the k trades, then run the full FTMO
rule set. Sweep the structure, find the best 0EV monthly pass. Run: python3 variance_play.py
"""
import numpy as np
TARGET=1.10; FLOOR=0.90; DAILY=0.03; MIN_DAYS=4; N=60000; D=20


def synth(wr, rr, k, drift, seed):
    rng=np.random.default_rng(seed)
    win = rng.random((N, D, k)) < wr
    tR = np.where(win, rr, -1.0) - drift
    cum = np.cumsum(tR, axis=2)
    return cum[:, :, -1], np.minimum(cum.min(axis=2), 0.0)   # day_R, intraday low (R)


def mc(day_R, day_min, risk, deadline=D):
    E=np.ones(N); passed=np.zeros(N,bool); blown=np.zeros(N,bool); bdaily=np.zeros(N,bool)
    tp=np.full(N,-1); dtr=np.zeros(N,int); sg=np.zeros(N); mg=np.zeros(N)
    for t in range(deadline):
        live=~passed&~blown; rmin=day_min[:,t]; rt=day_R[:,t]
        d_br=(rmin*risk)<=-DAILY; f_br=E*(1+rmin*risk)<=FLOOR
        bn=live&(d_br|f_br); blown|=bn; bdaily|=bn&d_br&~f_br
        live=~passed&~blown
        prof=E*rt*risk; E=np.where(live,E*(1+rt*risk),E)
        gp=np.where(live&(prof>0),prof,0.0); sg+=gp; mg=np.maximum(mg,gp)
        dtr+=np.where(live,1,0)
        cons=mg<=0.5*sg+1e-12
        pn=live&(E>=TARGET)&(dtr>=MIN_DAYS)&cons; passed|=pn; tp=np.where(pn&(tp<0),t,tp)
    td=tp[passed]+1
    return passed.mean(), blown.mean(), bdaily.sum()/max(blown.sum(),1), (np.median(td) if passed.any() else np.nan)


def main():
    print("="*88)
    print("MAX MONTHLY (20-day) PASS FOR A ZERO-EDGE STRATEGY — sweep the variance structure")
    print("EV=0 exactly (wr=1/(1+rr)). FTMO rules: +10% / -10% floor / 3% daily / 50% consist / min 4d")
    print("="*88)
    print(f"  {'RR':>4} {'wr':>5} {'trd/day':>7} {'risk':>6} | {'PASS%':>6} {'blow%':>6} {'dailyblow':>10} {'med d':>6}")
    best=(-1,None)
    for rr in (0.5, 1.0, 2.0, 4.0):
        wr=1.0/(1.0+rr)
        for k in (1, 3, 6):
            dR,dm=synth(wr,rr,k,0.0,seed=7)
            for risk in (0.005,0.01,0.02,0.03,0.05):
                p,b,dbs,md=mc(dR,dm,risk)
                if p>best[0]: best=(p,(rr,wr,k,risk,b,md))
                if risk in (0.01,0.02,0.03) and k in (1,3):
                    print(f"  {rr:4.1f} {wr:5.2f} {k:7d} {risk*100:5.1f}% | {p*100:5.1f}% {b*100:5.1f}% "
                          f"{dbs*100:8.0f}% {md if md==md else 0:5.0f}")
    p,(rr,wr,k,risk,b,md)=best
    print("-"*88)
    print(f"BEST 0EV STRUCTURE: RR={rr} (wr={wr:.0%}), {k} trade/day, risk {risk*100:.1f}% "
          f"-> MONTHLY PASS {p*100:.1f}%  (blow {b*100:.0f}%, median {md:.0f}d)")

    print("\n" + "="*88)
    print("SENSITIVITY: how fast does pass decay as EV goes slightly negative (real cost)?")
    print(f"at the best structure (RR={rr}, {k} trd/day, risk {risk*100:.1f}%)")
    print("="*88)
    print(f"  {'per-trade EV':>13} | {'PASS%':>6} {'blow%':>6}")
    for drift in (0.0, 0.01, 0.02, 0.03, 0.05, -0.02):
        # drift subtracts from each trade R -> per-trade EV = -drift (since base is 0EV)
        dR,dm=synth(wr,rr,k,drift,seed=7); p,b,_,_=mc(dR,dm,risk)
        print(f"  {-drift:+12.3f}R | {p*100:5.1f}% {b*100:5.1f}%")
    print("-"*88)
    print("Takeaway: a true 0EV strategy with the right variance can pass a real fraction of")
    print("the time. But every -0.01R of cost drift knocks the pass rate down fast, and real")
    print("intraday setups sit around -0.03 to -0.06R after costs. So the game is to get as")
    print("close to 0EV as possible (minimise cost drag) AND hit the optimal variance.")


if __name__=="__main__":
    main()
