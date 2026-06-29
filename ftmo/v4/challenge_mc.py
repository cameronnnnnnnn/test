"""
ftmo/v4/challenge_mc.py — Monte-Carlo of the LIVE challenge strategy (NAS100_v4 EA:
ORB 16:00 15m 50pt + VWAP pullback 40pt, both hard 4R, US session, 1% risk).
Run-to-completion under FTMO 1-Step rules: +10% target, 10% STATIC floor ($13.5k),
3% intraday daily loss, 50% best-day consistency, min 4 trading days.

Reports: % pass (+10%), % blow (which limit), % timeout, and the time-to-pass
distribution (mean / median / percentiles). Run: python3 challenge_mc.py
"""
import numpy as np
import data, strategies as S, engine
from run import build_days

ACCT=15000.0; TARGET=1.10; FLOOR=0.90; DAILY=0.03; MIN_DAYS=4; COST=2.0; RISK=0.01

def combo_days(df, ad):
    o=(S.orb(df,open_min=16*60,or_min=15,stop_pts=50,tp_R=4.0,be_R=0.0,trail_R=0.0,vol_filter=True)
      +S.vwap_pullback(df,stop_pts=40,tp_R=4.0,trail_R=0.0))
    d=build_days(engine.simulate(df,o,cost_pts=COST),ad)
    return np.asarray(d["day_R"],float),np.asarray(d["day_min_R"],float),(np.asarray(d["n"])>0).astype(int)

def mc(dR,dmin,traded,risk=RISK,N=120000,cap=252,seed=1,block=5):
    rng=np.random.default_rng(seed); nD=len(dR); nb=int(np.ceil(cap/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    R_=dR[idx]; Rmin=dmin[idx]; Tr=traded[idx]
    E=np.ones(N); passed=np.zeros(N,bool); blown=np.zeros(N,bool); bdaily=np.zeros(N,bool)
    tpass=np.full(N,-1); tblow=np.full(N,-1); dtr=np.zeros(N,int); sg=np.zeros(N); mg=np.zeros(N)
    for t in range(cap):
        live=~passed&~blown
        rt=R_[:,t]; rmin=Rmin[:,t]
        d_br=(rmin*risk)<=-DAILY; f_br=E*(1+rmin*risk)<=FLOOR
        bn=live&(d_br|f_br); blown|=bn; bdaily|=(bn&d_br&~f_br)
        tblow=np.where(bn&(tblow<0),t,tblow)
        live=~passed&~blown
        prof=E*rt*risk; E=np.where(live,E*(1+rt*risk),E)
        gp=np.where(live&(prof>0),prof,0.0); sg+=gp; mg=np.maximum(mg,gp)
        dtr+=np.where(live,Tr[:,t],0)
        cons=mg<=0.5*sg+1e-12
        pn=live&(E>=TARGET)&(dtr>=MIN_DAYS)&cons
        passed|=pn; tpass=np.where(pn&(tpass<0),t,tpass)
    return dict(passed=passed,blown=blown,bdaily=bdaily,tpass=tpass,tblow=tblow,E=E)

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin,tr=combo_days(df,ad)
    es=engine.edge_stats(engine.simulate(df,(S.orb(df,open_min=16*60,or_min=15,stop_pts=50,tp_R=4.0,vol_filter=True)
                                             +S.vwap_pullback(df,stop_pts=40,tp_R=4.0,trail_R=0.0)),cost_pts=COST))
    m=mc(dR,dmin,tr)
    p,b,bd,tp,tb=m["passed"],m["blown"],m["bdaily"],m["tpass"],m["tblow"]
    N=len(p); to=(~p&~b)
    print("="*72)
    print("CHALLENGE MC — your live strat (ORB 50pt + VWpull 40pt, 4R, 1% risk)")
    print(f"$15k, +10% target, 10% static floor, 3% daily, 50% consistency, min 4d")
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  ~{es['n']/(len(ad)/5):.1f} trades/wk   ({N:,} runs, run-to-completion)")
    print("="*72)
    print(f"  HIT +10% (PASS)          : {p.mean()*100:5.1f}%")
    print(f"  HIT -10% MAX DD (BLOW)   : {b.mean()*100:5.1f}%")
    print(f"     - via overall floor   : {((b&~bd).sum()/N)*100:5.1f}%  ({(b&~bd).sum()/max(b.sum(),1)*100:.0f}% of blows)")
    print(f"     - via 3% daily limit  : {(bd.sum()/N)*100:5.1f}%  ({bd.sum()/max(b.sum(),1)*100:.0f}% of blows)")
    print(f"  still running at 1yr     : {to.mean()*100:5.1f}%")
    print("-"*72)
    td=(tp[p]+1)
    print(f"  TIME TO PASS (+10%), trading days:")
    print(f"     average : {td.mean():4.1f} days  (~{td.mean()/5:.1f} weeks)")
    print(f"     median  : {np.median(td):4.0f} days  (~{np.median(td)/5:.1f} weeks)")
    print(f"     fastest 25% within {np.percentile(td,25):.0f}d · 75% within {np.percentile(td,75):.0f}d · 90% within {np.percentile(td,90):.0f}d")
    print(f"     min {td.min():.0f}d (=min 4 trading days)")
    print("-"*72)
    print(f"  PASS RATE BY DEADLINE (if you only had limited time):")
    for lbl,D in [("1 week",5),("2 weeks",10),("3 weeks",15),("4 weeks",20),("8 weeks",40)]:
        pw=(p&(tp<D)).mean(); bw=(b&(tb<D)).mean()
        print(f"     {lbl:8}: pass {pw*100:4.1f}%   blow {bw*100:4.1f}%")

if __name__=="__main__":
    main()
