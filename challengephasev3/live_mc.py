"""
challengephasev3/live_mc.py — the SAME 100k Monte-Carlo settings as
challengephasev2/challenge_v2_mc.py, but run on the strat you are CURRENTLY running:
NAS100_v4 EA = US-open ORB (16:00, 15m, 50pt, 4R, vol-filter) + VWAP pullback (40pt, 4R),
1% risk, NO daily breaker.

Identical MC: 100,000 block-bootstrap paths (block=5), run-to-completion (cap 252d),
FTMO $15k 1-Step rules (+10% target / 10% static floor / 3% daily / 50% consistency /
min 4 days). Same reporting: pass / blow-by-cause / still-running, time-to-pass, pass-by-
deadline, and the risk frontier. Writes live_mc.png. Run: python3 live_mc.py
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine
import search as SR

# ---- identical MC settings/constants to challenge_v2_mc.py ----
ACCT=15000.0; TARGET=1.10; FLOOR=0.90; DAILY=0.03; MIN_DAYS=4; COST=2.0
N=100_000; CAP=252; BLOCK=5


def live_days(df, ad):
    o = (S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, trail_R=0.0, vol_filter=True)
         + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0))
    tr = engine.simulate(df, o, cost_pts=COST)
    d = SR.build_days(tr, ad, 0.0)                      # 0.0 = NO daily breaker (as you run it)
    return (np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float),
            (np.asarray(d["n"]) > 0).astype(int), tr)


def mc(dR, dmin, traded, risk, N=N, cap=CAP, seed=1, block=BLOCK):
    rng=np.random.default_rng(seed); nD=len(dR); nb=int(np.ceil(cap/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    R_=dR[idx]; Rmin=dmin[idx]; Tr=traded[idx]
    E=np.ones(N); passed=np.zeros(N,bool); blown=np.zeros(N,bool); bdaily=np.zeros(N,bool)
    tpass=np.full(N,-1); dtr=np.zeros(N,int); sg=np.zeros(N); mg=np.zeros(N)
    for t in range(cap):
        live=~passed&~blown
        rt=R_[:,t]; rmin=Rmin[:,t]
        d_br=(rmin*risk)<=-DAILY; f_br=E*(1+rmin*risk)<=FLOOR
        bn=live&(d_br|f_br); blown|=bn; bdaily|=(bn&d_br&~f_br)
        tpass=tpass                                      # (no-op, keep parallel to v2)
        live=~passed&~blown
        prof=E*rt*risk; E=np.where(live,E*(1+rt*risk),E)
        gp=np.where(live&(prof>0),prof,0.0); sg+=gp; mg=np.maximum(mg,gp)
        dtr+=np.where(live,Tr[:,t],0)
        cons=mg<=0.5*sg+1e-12
        pn=live&(E>=TARGET)&(dtr>=MIN_DAYS)&cons
        passed|=pn; tpass=np.where(pn&(tpass<0),t,tpass)
    return dict(passed=passed,blown=blown,bdaily=bdaily,tpass=tpass,E=E)


def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin,tr,trades=live_days(df,ad); es=engine.edge_stats(trades)
    m=mc(dR,dmin,tr,risk=0.01)
    p,b,bd,tp=m["passed"],m["blown"],m["bdaily"],m["tpass"]
    to=~p&~b; td=tp[p]+1
    print("="*76)
    print("YOUR CURRENT EA — 100,000-path MC  (ORB 50 4R + VWpull 40 4R, 1% risk, NO breaker)")
    print(f"$15k 1-Step: +10% / 10% static floor / 3% daily / 50% consistency / min 4d")
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  PF {es['pf']:.2f}  "
          f"({es['n']} trades)   run-to-completion (cap {CAP}d)")
    print("="*76)
    print(f"  PASS (+10%)              : {p.mean()*100:5.1f}%")
    print(f"  BLOW (-10% / 3% daily)   : {b.mean()*100:5.1f}%")
    print(f"     - via 10% floor       : {((b&~bd).sum()/N)*100:5.1f}%  ({(b&~bd).sum()/max(b.sum(),1)*100:.0f}% of blows)")
    print(f"     - via 3% daily limit  : {(bd.sum()/N)*100:5.1f}%  ({bd.sum()/max(b.sum(),1)*100:.0f}% of blows)")
    print(f"  still running at {CAP}d    : {to.mean()*100:5.1f}%")
    print("-"*76)
    print(f"  TIME TO PASS (+10%), trading days:")
    print(f"     mean {td.mean():.1f} · median {np.median(td):.0f} · "
          f"25th {np.percentile(td,25):.0f} · 75th {np.percentile(td,75):.0f} · 90th {np.percentile(td,90):.0f}")
    print("-"*76)
    print(f"  PASS BY DEADLINE:")
    for lbl,D in [("1 week",5),("2 weeks",10),("3 weeks",15),("4 weeks (1mo)",20),
                  ("6 weeks",30),("8 weeks",40),("12 weeks",60)]:
        pw=(p&(tp<D)).mean()
        star=" <= 20 trading days" if D==20 else ""
        print(f"     {lbl:14}: pass {pw*100:5.1f}%{star}")
    print("="*76)
    print("  100k FRONTIER across risk (run-to-completion):")
    print(f"     {'risk':>6} {'PASS%':>7} {'BLOW%':>7} {'running%':>9} {'med d':>6} {'20d pass':>9}")
    rows=[]
    for r in (0.0025,0.005,0.0075,0.01,0.0125,0.015):
        mr=mc(dR,dmin,tr,risk=r,seed=7)
        pr,br=mr["passed"],mr["blown"]; tdr=mr["tpass"][pr]+1
        run=(~pr&~br).mean(); md=np.median(tdr) if pr.any() else np.nan
        p20=(pr&(mr["tpass"]<20)).mean()
        rows.append((r,pr.mean(),br.mean(),run,md,p20))
        print(f"     {r*100:5.2f}% {pr.mean()*100:6.1f}% {br.mean()*100:6.1f}% {run*100:8.1f}% {md:5.0f} {p20*100:8.1f}%")
    print("="*76)

    # ---- chart (same style as challenge_v2_mc.py) ----
    fig,ax=plt.subplots(2,2,figsize=(13,8.5))
    a=ax[0,0]
    vals=[p.mean()*100,(b&~bd).sum()/N*100,bd.sum()/N*100,to.mean()*100]
    a.bar(["pass","blow\n(floor)","blow\n(daily)","still\nrunning"],vals,
          color=["#55a868","#c44e52","#e1812c","#8172b3"])
    for i,v in enumerate(vals): a.text(i,v+0.6,f"{v:.1f}%",ha="center",fontsize=10)
    a.set_title("Outcome @ 1.0% risk, run-to-completion (100k)"); a.set_ylabel("% of attempts")
    a.set_ylim(0,max(vals)*1.2); a.grid(alpha=0.2,axis="y")
    a=ax[0,1]; a.hist(np.clip(td,0,120),bins=60,color="#55a868",alpha=0.85)
    a.axvline(np.median(td),color="darkgreen",ls="--",label=f"median {np.median(td):.0f}d")
    a.axvline(td.mean(),color="blue",ls="-",label=f"mean {td.mean():.0f}d")
    a.set_title("Time to pass +10% (passers)"); a.set_xlabel("trading days"); a.legend(); a.grid(alpha=0.2)
    a=ax[1,0]; Ds=np.arange(4,80)
    a.plot(Ds,[(p&(tp<D)).mean()*100 for D in Ds],color="#1f3b73",lw=2)
    for D,lab in [(20,"20d (1mo)"),(40,"40d"),(60,"60d")]:
        y=(p&(tp<D)).mean()*100; a.axvline(D,color="grey",ls=":",alpha=0.6); a.annotate(f"{lab}: {y:.0f}%",(D,y),fontsize=9)
    a.set_title("Cumulative pass% by deadline (1.0% risk)"); a.set_xlabel("trading-day deadline"); a.set_ylabel("pass%"); a.grid(alpha=0.2)
    a=ax[1,1]; rs=[r[0]*100 for r in rows]
    a.plot(rs,[r[1]*100 for r in rows],"o-",color="#55a868",label="pass% (run-to-compl.)")
    a.plot(rs,[r[5]*100 for r in rows],"o--",color="#2d6a3e",label="pass% within 20d")
    a.plot(rs,[r[2]*100 for r in rows],"o-",color="#c44e52",label="blow%")
    a.set_xlabel("risk % per trade"); a.set_ylabel("%"); a.set_title("Frontier: pass / blow vs risk"); a.grid(alpha=0.2)
    a.legend(loc="center right",fontsize=8)
    fig.suptitle("YOUR CURRENT EA (ORB 50 4R + VWpull 40 4R, 1%) — 100,000-path MC, FTMO $15k 1-Step",fontsize=12)
    fig.tight_layout(rect=[0,0,1,0.97]); fig.savefig("live_mc.png",dpi=120)
    print("\nchart -> live_mc.png")


if __name__=="__main__":
    main()
