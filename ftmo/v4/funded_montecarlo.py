"""
ftmo/v4/funded_montecarlo.py — forward Monte-Carlo of the V2 funded strategy
(US ORB 6R + EU ORB 6R + VWpull 8R), compounding 0.67%/trade like the MT5 tester,
with the FTMO static $13,500 floor and 3% intraday daily limit ENFORCED (blow = dead).
NO withdrawals — this is the account-equity (trading) view, matching the tester.

100k block-bootstrap paths over 12 months. Outputs a fan-chart + return histograms
(funded_mc_v2.png) and a per-horizon table (avg/median return, % in profit, % blown).

Run: python3 funded_montecarlo.py
"""
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import data, strategies as S, engine
from run import build_days

ACCT=15000.0; FLOOR=13500.0; DAILY=0.03; RISK=0.0067; MONTH=21
O, EU = 16*60, 11*60
N, H = 100000, 252

def v2_days(df, ad):
    o=(S.orb(df,open_min=O,or_min=30,stop_pts=60,tp_R=6.0,be_R=1.0,vol_filter=True)
      +S.orb(df,open_min=EU,or_min=30,stop_pts=60,tp_R=6.0,be_R=1.0,vol_filter=True)
      +S.vwap_pullback(df,stop_pts=40,tp_R=8.0,trail_R=3.0))
    d=build_days(engine.simulate(df,o,cost_pts=2.0),ad)
    return np.asarray(d["day_R"],float), np.asarray(d["day_min_R"],float)

def mc(dR,dmin,seed=1,block=5):
    rng=np.random.default_rng(seed); nD=len(dR); nb=int(np.ceil(H/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:H]
    Rd=dR[idx]; Rm=dmin[idx]
    bal=np.full(N,ACCT); alive=np.ones(N,bool); blow_day=np.full(N,-1)
    traj=np.empty((N,H+1),dtype=np.float32); traj[:,0]=ACCT
    for t in range(H):
        rmin=Rm[:,t]; rt=Rd[:,t]
        low=bal*(1.0+RISK*rmin)                                  # intraday floating low
        dead=alive & ((rmin*RISK<=-DAILY)|(low<=FLOOR))          # 3% daily OR static floor
        blow_day=np.where(dead,t,blow_day)
        bal=np.where(dead, np.maximum(low,FLOOR), bal)           # pin terminal at death level
        alive&=~dead
        bal=np.where(alive, bal*(1.0+RISK*rt), bal)              # survivors compound the close
        traj[:,t+1]=bal
    return traj, blow_day

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin=v2_days(df,ad)
    traj,blow_day=mc(dR,dmin)
    print(f"V2 strategy: WR/edge -> {engine.edge_stats(engine.simulate(df, S.orb(df,open_min=O,or_min=30,stop_pts=60,tp_R=6.0,be_R=1.0,vol_filter=True)+S.orb(df,open_min=EU,or_min=30,stop_pts=60,tp_R=6.0,be_R=1.0,vol_filter=True)+S.vwap_pullback(df,stop_pts=40,tp_R=8.0,trail_R=3.0),cost_pts=2.0))['expR']:+.3f}R/trade")
    print(f"Monte-Carlo: {N:,} paths, compounding {RISK*100:.2f}%/trade, floor $13.5k + 3% daily enforced\n")

    hz=[("1 month",21),("2 months",42),("3 months",63),("6 months",126),("12 months",252)]
    print("="*86)
    print(f"  {'horizon':10} {'avg ret':>9} {'median':>8} {'in profit':>10} {'blown':>7} {'10th pct':>9} {'90th pct':>9}")
    print("="*86)
    rows=[]
    for name,h in hz:
        end=traj[:,h].astype(float); ret=end/ACCT-1.0
        blown=(blow_day>=0)&(blow_day<h)
        inprofit=(~blown)&(end>ACCT)
        avg=ret.mean()*100; med=np.median(ret)*100
        p10=np.percentile(ret,10)*100; p90=np.percentile(ret,90)*100
        rows.append((name,avg,med,inprofit.mean()*100,blown.mean()*100,p10,p90))
        print(f"  {name:10} {avg:+8.1f}% {med:+7.1f}% {inprofit.mean()*100:9.1f}% {blown.mean()*100:6.1f}% {p10:+8.1f}% {p90:+8.1f}%")
    print("="*86)
    m1=rows[0]
    print(f"AVERAGE MONTHLY RETURN (1-mo): {m1[1]:+.1f}% mean / {m1[2]:+.1f}% median   "
          f"|  in profit after 1mo: {m1[3]:.0f}%  ·  after 3mo: {rows[2][3]:.0f}%")
    print("NOTE: account-equity (compounding, no withdrawals) — matches the tester. Your take-home")
    print("      = 90% of what you WITHDRAW; for monthly banked cash see FUNDED_RESULTS.md.")

    # ---------- figure: fan chart + return histograms ----------
    fig=plt.figure(figsize=(14,9)); gs=fig.add_gridspec(2,2,height_ratios=[1.4,1])
    ax=fig.add_subplot(gs[0,:]); x=np.arange(H+1)/MONTH
    pct={p:np.percentile(traj.astype(float),p,axis=0) for p in (5,25,50,75,95)}
    ax.fill_between(x,pct[5],pct[95],color="#4c72b0",alpha=0.15,label="5–95th pct")
    ax.fill_between(x,pct[25],pct[75],color="#4c72b0",alpha=0.30,label="25–75th pct")
    ax.plot(x,pct[50],color="#1f3b73",lw=2,label="median")
    ax.axhline(ACCT,color="black",ls=":",alpha=0.6); ax.axhline(FLOOR,color="red",ls="--",lw=1.5,label="floor $13.5k (blow)")
    ax.set_yscale("log"); ax.set_xlim(0,12); ax.set_xlabel("months"); ax.set_ylabel("account balance ($, log)")
    ax.set_title(f"FTMO funded V2 (6R/8R) — {N:,}-path Monte-Carlo, compounding 0.67%/trade (floor+3% daily enforced)")
    ax.legend(loc="upper left",fontsize=9); ax.grid(alpha=0.25,which="both")
    for nm,h in [("1mo",21),("3mo",63),("12mo",252)]:
        r=traj[:,h].astype(float)/ACCT-1.0
        ax.annotate(f"{nm}: med {np.median(r)*100:+.0f}%", (h/MONTH, pct[50][h]), fontsize=8)
    for k,(nm,h) in enumerate([("1 month",21),("3 months",63)]):
        a=fig.add_subplot(gs[1,k]); r=(traj[:,h].astype(float)/ACCT-1.0)*100
        a.hist(np.clip(r,-15,80),bins=80,color="#55a868",alpha=0.8)
        a.axvline(0,color="black",ls=":"); a.axvline(r.mean(),color="blue",ls="-",label=f"mean {r.mean():+.0f}%")
        a.axvline(np.median(r),color="darkgreen",ls="--",label=f"median {np.median(r):+.0f}%")
        a.set_title(f"return distribution — {nm}"); a.set_xlabel("return %"); a.legend(fontsize=8); a.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig("funded_mc_v2.png",dpi=120)
    print("\nchart -> funded_mc_v2.png")

if __name__=="__main__":
    main()
