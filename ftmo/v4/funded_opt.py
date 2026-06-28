"""
ftmo/v4/funded_opt.py — optimize the FTMO FUNDED-phase strategy + WITHDRAWAL POLICY for
EXPECTED REAL BANKED $/MONTH, net of amortized account re-acquisition.

Convex-EV principle: your 90% withdrawals are permanent; the account's whole downside is
capped at what it cost to acquire. So we optimize BANKED DOLLARS (not survival/win-rate)
and front-load withdrawals. A high-blow, fast-extracting config can win.

FTMO 15k funded rules (CONFIRMED by user):
  $15,000 ; 90/10 ; STATIC 10% floor $13,500 (does NOT trail) ; 3% ($450) intraday daily
  loss on floating equity ; no profit target ; payout cadence MONTHLY ; min withdraw $20 ;
  no max. So we withdraw once per ~21 trading days; the only policy choice is how much to
  leave above breakeven (buffer) and the per-trade risk.

PRIMARY metric: net_$/mo = (avg_banked - ACQ) / (avg_life_months + REACQ_MO).
Reproduce: python3 funded_opt.py
"""
import numpy as np, pandas as pd
import data, strategies as S, engine
from run import build_days

ACCT=15000.0; FLOOR=13500.0; DAILY=450.0; SPLIT=0.90; MONTH=21
PAYDAY=21                       # monthly payout cadence (trading days)
COST=2.0                        # NAS100 CFD round-turn points (FTMO); sweep later
FEE=92.0; CHAL_PASS=0.47        # ~$135 AUD eval; eventual challenge pass rate
ACQ=FEE/CHAL_PASS               # ~$196 to (re)acquire one funded account
REACQ_MO=1.5                    # ~months of downtime to re-pass after a blow

def funded_mc(days, risk_d, N=60000, cap=504, seed=3, buffer=0.0, cadence=PAYDAY, gate=PAYDAY, block=5):
    """FTMO funded MC. Withdraw (bal-(ACCT+buffer)) every `cadence` trading days, first at
    `gate`. Breach = intraday 3% daily OR static $13,500 floor on floating equity."""
    rng=np.random.default_rng(seed)
    dR=np.asarray(days["day_R"],float); dmin=np.asarray(days["day_min_R"],float); nD=len(dR)
    nb=int(np.ceil(cap/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    Rd=dR[idx]; Rm=dmin[idx]
    bal=np.full(N,ACCT); alive=np.ones(N,bool); cum=np.zeros(N); npay=np.zeros(N,int)
    life=np.full(N,cap); tfirst=np.full(N,-1); since=np.full(N,10**6); target=ACCT+buffer
    sg=np.zeros(N); mg=np.zeros(N)                             # 50% best-day: sum/max winning days
    for t in range(cap):
        rmin=Rm[:,t]*risk_d
        dead=alive & ((rmin<=-DAILY)|(bal+rmin<=FLOOR))        # intraday daily OR static floor
        life=np.where(dead,t,life); alive&=~dead
        prof=Rd[:,t]*risk_d
        bal=np.where(alive,bal+prof,bal)                       # close the day
        gp=np.where(alive&(prof>0),prof,0.0); sg+=gp; mg=np.maximum(mg,gp)
        since+=1
        consistent=mg<=0.5*sg+1e-9                             # 50% rule BLOCKS payout (not a fail)
        elig=alive & (t>=gate) & (since>=cadence) & (bal>target+20.0) & consistent
        w=np.where(elig,bal-target,0.0)
        bal-=w; cum+=w; paid=w>0; npay+=paid
        tfirst=np.where(paid&(tfirst<0),t,tfirst); since=np.where(paid,0,since)
        sg=np.where(paid,0.0,sg); mg=np.where(paid,0.0,mg)     # reset the cycle after a payout
    life=np.where(alive,cap,life)
    return dict(banked=cum*SPLIT, life=life, npay=npay, tfirst=tfirst, blown=~alive)

def score(m):
    b=m["banked"]; life_mo=m["life"]/MONTH; tf=m["tfirst"][m["tfirst"]>=0]
    return dict(avg=b.mean(), med=np.median(b),
                net_mo=(b.mean()-ACQ)/(life_mo.mean()+REACQ_MO),
                blow=m["blown"].mean(), life_mo=life_mo.mean(),
                tfirst=(np.median(tf)+1 if len(tf) else np.nan), npay=m["npay"].mean())

# ---------- bug-check: independent scalar reference ----------
def ref_path(dR, dmin, risk_d, buffer, cadence, gate, cap):
    bal=ACCT; cum=0.0; since=10**6; tfirst=-1; life=cap; target=ACCT+buffer; sg=0.0; mg=0.0
    for t in range(cap):
        rmin=dmin[t]*risk_d
        if (rmin<=-DAILY) or (bal+rmin<=FLOOR): life=t; return cum*SPLIT, life, tfirst
        prof=dR[t]*risk_d; bal+=prof
        if prof>0: sg+=prof; mg=max(mg,prof)
        since+=1
        if t>=gate and since>=cadence and bal>target+20.0 and mg<=0.5*sg+1e-9:
            w=bal-target; bal-=w; cum+=w; since=0; sg=0.0; mg=0.0
            if tfirst<0: tfirst=t
    return cum*SPLIT, life, tfirst

def golden_and_equiv(days):
    print("--- bug-check ---")
    # golden A (consistency-aware): 3x +$500 days, cad1/gate0/buf0. day0 BLOCKED (best=100%>50%);
    #   day1 sg=1000,mg=500 -> 500<=500 OK, withdraw 1000; day2 BLOCKED again. cum=1000 -> banked 900.
    b,_,_=ref_path(np.array([0.5,0.5,0.5]),np.zeros(3),1000,0.0,1,0,3)
    print(f"  golden A banked={b:.0f} (expect 900, 50%-rule blocks days 0&2)  {'PASS' if abs(b-900)<1e-6 else 'FAIL'}")
    # golden B: daily breach -0.5R*1000=-500<=-450 -> blow day0
    _,life,_=ref_path(np.array([-0.5]),np.array([-0.5]),1000,0.0,1,0,1)
    print(f"  golden B life={life} (expect 0)  {'PASS' if life==0 else 'FAIL'}")
    # golden C: static floor on day1 (start 15000, -1.5R intraday = -1500 -> 13500 floor) blow
    _,life,_=ref_path(np.array([0.0,0.0]),np.array([0.0,-1.5]),1000,0.0,1,0,2)
    print(f"  golden C life={life} (expect 1)  {'PASS' if life==1 else 'FAIL'}")
    # golden D: 50% best-day rule BLOCKS payout until diluted. +1000 then +300x4 (risk1000),
    #  cad1 gate0: days0-3 blocked (best>50%); day4 sg=2200,mg=1000<=1100 -> withdraw 2200 ->1980
    b,_,tf=ref_path(np.array([1.0,0.3,0.3,0.3,0.3]),np.zeros(5),1000,0.0,1,0,5)
    print(f"  golden D banked={b:.0f} tfirst={tf} (expect 1980 @ day4)  {'PASS' if abs(b-1980)<1e-6 and tf==4 else 'FAIL'}")
    # equivalence: vectorized vs scalar on identical sampled paths (monthly policy)
    dR=np.asarray(days["day_R"],float); dmin=np.asarray(days["day_min_R"],float); nD=len(dR)
    cap=252; N=3000; seed=9; block=5; nb=int(np.ceil(cap/block))
    m=funded_mc(days,180,N=N,cap=cap,seed=seed,buffer=0.0,cadence=14,gate=14)
    rng=np.random.default_rng(seed)
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    bad=0
    for p in range(N):
        rb,rl,_=ref_path(dR[idx[p]],dmin[idx[p]],180,0.0,14,14,cap)
        if abs(rb-m["banked"][p])>1e-6 or rl!=m["life"][p]: bad+=1
    print(f"  equivalence: {N} paths, {bad} mismatches  {'PASS' if bad==0 else 'FAIL'}")
    return bad==0

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    def days_of(orders): return build_days(engine.simulate(df,orders,cost_pts=COST),ad)
    strategies={
      "combo(ORB15+VWpull4R)": days_of(S.orb(df,open_min=16*60,or_min=15,stop_pts=50,tp_R=4.0,vol_filter=True)
                                       +S.vwap_pullback(df,stop_pts=40,tp_R=4.0)),
      "US ORB30 s60 tp3":      days_of(S.orb(df,open_min=16*60,or_min=30,stop_pts=60,tp_R=3.0,be_R=1.0,vol_filter=True)),
      "EU ORB30 s60 tp3":      days_of(S.orb(df,open_min=11*60,or_min=30,stop_pts=60,tp_R=3.0,be_R=1.0,vol_filter=True)),
      "US+EU ORB30":           days_of(S.orb(df,open_min=16*60,or_min=30,stop_pts=60,tp_R=3.0,be_R=1.0,vol_filter=True)
                                       +S.orb(df,open_min=11*60,or_min=30,stop_pts=60,tp_R=3.0,be_R=1.0,vol_filter=True)),
    }
    print("="*100)
    print("FTMO 15k FUNDED — optimize strategy + monthly withdrawal buffer for NET BANKED $/MONTH")
    print(f"static $13.5k floor, 3% daily, 90/10, MONTHLY payout, COST={COST}pt, ACQ=${ACQ:.0f}, reacq={REACQ_MO}mo")
    print("="*100)
    golden_and_equiv(strategies["EU ORB30 s60 tp3"]); print()

    print(f"  {'strategy':22}{'risk$':>6}{'cad':>4}{'buf$':>6} | {'net$/mo':>8}{'avgBank':>8}{'medBank':>8}{'blow%':>6}{'life(mo)':>8}{'t1st':>6}{'#pay':>5}")
    rows=[]
    for name,days in strategies.items():
        for risk_d in [125,150,175,200,225]:
            for cad in [14,30,60]:                       # payout cadence is choosable
                for buf in [0.0,500.0]:
                    rows.append((name,risk_d,cad,buf,score(funded_mc(days,risk_d,N=40000,buffer=buf,cadence=cad,gate=cad))))
    rows.sort(key=lambda r:r[4]["net_mo"],reverse=True)
    for name,risk_d,cad,buf,s in rows[:14]:
        print(f"  {name:22}{risk_d:6.0f}{cad:4.0f}{buf:6.0f} | {s['net_mo']:8.0f}{s['avg']:8.0f}{s['med']:8.0f}"
              f"{s['blow']*100:5.0f}%{s['life_mo']:8.1f}{s['tfirst']:6.0f}{s['npay']:5.1f}")
    print("-"*100)
    bn,br,bc,bb,bs=rows[0]
    print(f"LEADER: {bn}  risk ${br:.0f}/trade, withdraw every {bc}d down to BE+${bb:.0f}")
    print(f"  NET ${bs['net_mo']:.0f}/mo | avg banked ${bs['avg']:.0f} med ${bs['med']:.0f} | "
          f"blow {bs['blow']*100:.0f}% | life {bs['life_mo']:.1f}mo | 1st payout ~{bs['tfirst']:.0f}d | {bs['npay']:.1f} payouts")

if __name__=="__main__":
    main()
