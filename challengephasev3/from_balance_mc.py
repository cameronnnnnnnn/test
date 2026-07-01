"""
challengephasev3/from_balance_mc.py — 100k MC of passing FROM the user's ACTUAL current
state, not from scratch. Live 4R EA (ORB 50 + VWpull 40, 1% risk, no breaker).

Seeded with the real account:
  balance $15,577.83  (E0 = +3.85%)   |  3 trading days done (min 4)
  green days so far: +$440.21, +$443.44  -> consistency tracker seeded with these
  (so the 50% best-day rule reflects reality, not a fresh reset)

Reports: eventual (run-to-completion) pass%, blow% by cause, and — the main ask —
how long FROM HERE to hit +10% (mean/median/percentiles), plus pass within N more days.
Writes from_balance_mc.png. Run: python3 from_balance_mc.py
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine
import search as SR

ACCT=15000.0; TARGET=1.10; FLOOR=0.90; DAILY=0.03; MIN_DAYS=4; N=100_000; CAP=252; BLOCK=5

# ---- real account state ----
BAL=15577.83; E0=BAL/ACCT
DAYS_DONE=3
GREEN_DAYS=[440.21, 443.44]                    # $ net of each winning day so far
SG0=sum(GREEN_DAYS)/ACCT                        # summed green (start-units)
MG0=max(GREEN_DAYS)/ACCT                        # biggest green day (start-units)


def live_days(df, ad):
    o=(S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, trail_R=0.0, vol_filter=True)
       + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0))
    d=SR.build_days(engine.simulate(df, o, cost_pts=2.0), ad, 0.0)
    return np.asarray(d["day_R"],float), np.asarray(d["day_min_R"],float), (np.asarray(d["n"])>0).astype(int)


def mc(dR, dmin, traded, risk, e0=E0, sg0=SG0, mg0=MG0, dd0=DAYS_DONE, N=N, cap=CAP, seed=1, block=BLOCK):
    rng=np.random.default_rng(seed); nD=len(dR); nb=int(np.ceil(cap/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    R_=dR[idx]; Rmin=dmin[idx]; Tr=traded[idx]
    E=np.full(N,e0); passed=np.zeros(N,bool); blown=np.zeros(N,bool); bdaily=np.zeros(N,bool)
    tpass=np.full(N,-1); dtr=np.full(N,dd0,int); sg=np.full(N,sg0); mg=np.full(N,mg0)
    for t in range(cap):
        live=~passed&~blown
        rt=R_[:,t]; rmin=Rmin[:,t]
        d_br=(rmin*risk)<=-DAILY; f_br=E*(1+rmin*risk)<=FLOOR
        bn=live&(d_br|f_br); blown|=bn; bdaily|=(bn&d_br&~f_br)
        live=~passed&~blown
        prof=E*rt*risk; E=np.where(live,E*(1+rt*risk),E)
        gp=np.where(live&(prof>0),prof,0.0); sg+=gp; mg=np.maximum(mg,gp)
        dtr+=np.where(live,Tr[:,t],0)
        cons=mg<=0.5*sg+1e-12
        pn=live&(E>=TARGET)&(dtr>=MIN_DAYS)&cons
        passed|=pn; tpass=np.where(pn&(tpass<0),t,tpass)
    return dict(passed=passed,blown=blown,bdaily=bdaily,tpass=tpass)


def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin,tr=live_days(df,ad)
    m=mc(dR,dmin,tr,risk=0.01)
    p,b,bd,tp=m["passed"],m["blown"],m["bdaily"],m["tpass"]
    to=~p&~b; td=tp[p]+1     # trading days FROM NOW to pass
    print("="*76)
    print(f"PASS FROM YOUR CURRENT BALANCE — 100k MC (live 4R EA, 1% risk)")
    print(f"start ${BAL:,.2f} (+{(E0-1)*100:.2f}%) · {DAYS_DONE} days done · greens ${GREEN_DAYS} seeded")
    print(f"need +{(TARGET-E0)*100:.2f}% more to hit +10% ($16,500); floor ${ACCT*FLOOR:,.0f} is {(E0-FLOOR)/E0*100:.1f}% below")
    print("="*76)
    print(f"  EVENTUAL PASS (run-to-completion) : {p.mean()*100:5.1f}%")
    print(f"  BLOW                              : {b.mean()*100:5.1f}%   (floor {((b&~bd).sum()/N)*100:.1f}% · daily {(bd.sum()/N)*100:.1f}%)")
    print("-"*76)
    print(f"  TIME FROM HERE TO PASS (+10%), trading days:")
    print(f"     mean   {td.mean():4.1f}d  (~{td.mean()/5*7:.0f} calendar days)")
    print(f"     median {np.median(td):4.0f}d  (~{np.median(td)/5*7:.0f} calendar days)")
    print(f"     25th {np.percentile(td,25):.0f}d · 75th {np.percentile(td,75):.0f}d · 90th {np.percentile(td,90):.0f}d")
    print("-"*76)
    print(f"  PASS WITHIN N MORE TRADING DAYS (from now):")
    for D in (3,5,10,15,17,20):
        lab="  (rest of 1st month)" if D==17 else ""
        print(f"     {D:2d} more days: {(p&(tp<D)).mean()*100:5.1f}%{lab}")
    print("-"*76)
    # what if you throttle to 0.5% for the run-in
    m2=mc(dR,dmin,tr,risk=0.005,seed=7); p2,b2=m2["passed"],m2["blown"]; td2=m2["tpass"][p2]+1
    print(f"  IF YOU DROP TO 0.5% RISK FROM HERE (safer, slower):")
    print(f"     eventual pass {p2.mean()*100:.1f}%  ·  blow {b2.mean()*100:.1f}%  ·  median {np.median(td2):.0f}d to pass")
    print("="*76)

    # ---- chart ----
    fig,ax=plt.subplots(1,2,figsize=(13,4.8))
    a=ax[0]; a.hist(np.clip(td,0,60),bins=60,color="#55a868",alpha=0.85)
    a.axvline(np.median(td),color="darkgreen",ls="--",label=f"median {np.median(td):.0f}d")
    a.axvline(td.mean(),color="blue",ls="-",label=f"mean {td.mean():.0f}d")
    a.set_title("Trading days FROM NOW to hit +10% (passers)"); a.set_xlabel("trading days"); a.legend(); a.grid(alpha=.2)
    a=ax[1]; Ds=np.arange(1,40)
    a.plot(Ds,[(p&(tp<D)).mean()*100 for D in Ds],color="#1f3b73",lw=2)
    a.axhline(p.mean()*100,color="grey",ls=":",label=f"eventual {p.mean()*100:.0f}%")
    for D in (5,10,17):
        y=(p&(tp<D)).mean()*100; a.axvline(D,color="grey",ls=":",alpha=.5); a.annotate(f"{D}d: {y:.0f}%",(D,y),fontsize=9)
    a.set_title("Cumulative pass% by extra trading days"); a.set_xlabel("more trading days"); a.set_ylabel("pass%"); a.legend(fontsize=8); a.grid(alpha=.2)
    fig.suptitle(f"Pass from ${BAL:,.0f} (+{(E0-1)*100:.1f}%) — 100k MC, live 4R EA @1% risk",fontsize=12)
    fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig("from_balance_mc.png",dpi=120)
    print("\nchart -> from_balance_mc.png")


if __name__=="__main__":
    main()
