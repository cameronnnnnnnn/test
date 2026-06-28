"""
ftmo/v4/funded_pipeline.py — buy 100 challenges -> funded V2 -> withdraw after 1 month.
Full EV with the 50% consistency rule applied (it bites hard with 6R/8R over one month:
a single big day can exceed 50% of the month's winning-day profit -> payout BLOCKED).

Run: python3 funded_pipeline.py
"""
import numpy as np
import data, strategies as S, engine
from run import build_days

ACCT=15000.0; FLOOR=13500.0; DAILY=0.03; RISK=0.0067; SPLIT=0.90
FEE=135.0; PASS=0.408; NBUY=100; MED_PASS_DAYS=8
O, EU = 16*60, 11*60
N, H = 100000, 21   # 1 funded month

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
    bal=np.full(N,ACCT); alive=np.ones(N,bool); sg=np.zeros(N); mg=np.zeros(N)
    for t in range(H):
        rmin=Rm[:,t]; rt=Rd[:,t]
        low=bal*(1.0+RISK*rmin)
        dead=alive & ((rmin*RISK<=-DAILY)|(low<=FLOOR))
        alive&=~dead
        pnl=np.where(alive, bal*RISK*rt, 0.0)        # the day's $ P&L (compounding)
        bal=bal+pnl
        gp=np.where(alive & (pnl>0), pnl, 0.0); sg+=gp; mg=np.maximum(mg,gp)
    return bal, ~alive, sg, mg

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    bal,blown,sg,mg=mc(*v2_days(df,ad))
    alive=~blown; profit=np.maximum(bal-ACCT,0.0)
    consistent = mg <= 0.5*sg + 1e-9
    in_profit = alive & (profit>0)
    can_wd = in_profit & consistent                                   # payout allowed after 1mo
    take_all  = np.where(in_profit, profit, 0.0)*SPLIT                # if consistency ignored
    take_cons = np.where(can_wd,    profit, 0.0)*SPLIT                # consistency-gated (real)

    nfund=PASS*NBUY
    print("="*78)
    print(f"BUY {NBUY} CHALLENGES @ ${FEE:.0f}  ->  FUNDED V2 (6R/8R)  ->  WITHDRAW after 1 month")
    print("="*78)
    print(f"STAGE 1 — challenge: {PASS*100:.1f}% pass (median {MED_PASS_DAYS}d)  ->  ~{nfund:.0f} funded accounts")
    print(f"  spend: {NBUY} x ${FEE:.0f} = ${NBUY*FEE:,.0f}")
    print("-"*78)
    print(f"STAGE 2 — 1 funded month, per funded account:")
    print(f"  blown in month 1            : {blown.mean()*100:.0f}%   -> ~{blown.mean()*nfund:.0f} accts die")
    print(f"  ALIVE after the month       : {alive.mean()*100:.0f}%   -> ~{alive.mean()*nfund:.0f} accts left")
    print(f"  alive & in profit           : {in_profit.mean()*100:.0f}%   -> ~{in_profit.mean()*nfund:.0f} accts")
    print(f"  ...of those, payout ALLOWED : {can_wd.mean()*100:.0f}%   -> ~{can_wd.mean()*nfund:.0f} accts (50% rule lets them)")
    print(f"  ...payout BLOCKED by 50% rule: {(in_profit&~consistent).mean()*100:.0f}%  (one big day > 50% of month profit; withdraw next month)")
    print("-"*78)
    for tag,take,mask in [("IF you could withdraw all (no consistency)",take_all,in_profit),
                          ("REAL month-1 (50% rule applied)",take_cons,can_wd)]:
        per=take.mean(); tot=per*nfund; nacc=mask.mean()*nfund
        avg_each=take[mask].mean() if mask.any() else 0
        net=tot-NBUY*FEE
        print(f"  [{tag}]")
        print(f"     withdrawn from ~{nacc:.0f} accounts, avg ${avg_each:,.0f} each (your 90%)")
        print(f"     TOTAL withdrawn: ${tot:,.0f}   -  spend ${NBUY*FEE:,.0f}  =  NET EV ${net:,.0f}")
    print("-"*78)
    # residual value: blocked + underwater survivors still hold the account & its profit
    resid_profit=(np.where(alive & ~can_wd, profit,0.0)*SPLIT).mean()*nfund
    print(f"  (residual: ~{(alive&~can_wd).mean()*nfund:.0f} surviving accts still hold ~${resid_profit:,.0f} of your-90% profit,")
    print(f"   withdrawable next cadence after diluting the big day / or keep compounding)")
    print("-"*78)
    tdays=MED_PASS_DAYS+H
    print(f"TIMELINE to the withdrawal day (median path, excl. payout processing):")
    print(f"  challenge pass ~{MED_PASS_DAYS} trading days + funded month {H} = ~{tdays} trading days")
    print(f"  ~= {tdays/5*7:.0f} calendar days  (~{tdays/5:.1f} weeks)")

if __name__=="__main__":
    main()
