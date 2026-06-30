"""
ftmo/v4/challenge_conditional.py — CONDITIONAL pass odds for the LIVE 4R EA given
where your account is RIGHT NOW. FTMO's +10% target ($16,500) and 10% floor ($13,500)
are ABSOLUTE, so being up means you are both closer to the target and further from the
floor — both lift your odds. We start the Monte-Carlo at a given current equity E0 and
run forward to completion under the full rules (3% daily, 50% consistency, min 4 days).

Sweeps E0 from -2% to +7% so you can read off wherever you are. 100k paths each.
Consistency is tracked FRESH from now (see note in main). Writes challenge_conditional.png.
Run: python3 challenge_conditional.py
"""
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import data, strategies as S
import challenge_mc as C

ACCT=15000.0; TARGET=1.10; FLOOR=0.90; DAILY=0.03; MIN_DAYS=4
N=100_000; CAP=252; BLOCK=5; RISK=0.01


def mc_from(dR, dmin, traded, E0, risk=RISK, N=N, cap=CAP, block=BLOCK, seed=1):
    """E0 in account-units (1.0 = $15,000). Target/floor absolute (1.10 / 0.90)."""
    rng=np.random.default_rng(seed); nD=len(dR); nb=int(np.ceil(cap/block))
    idx=((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    R_=dR[idx]; Rmin=dmin[idx]; Tr=traded[idx]
    E=np.full(N,E0); passed=np.zeros(N,bool); blown=np.zeros(N,bool); bdaily=np.zeros(N,bool)
    tpass=np.full(N,-1); dtr=np.zeros(N,int); sg=np.zeros(N); mg=np.zeros(N)
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
    return passed, blown, bdaily, tpass


def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    dR,dmin,tr=C.combo_days(df,ad)
    print("="*84)
    print("CONDITIONAL PASS ODDS — live 4R EA (ORB 50 + VWpull 40, 1% risk), run-to-completion")
    print("FTMO target $16,500 (+10%) / floor $13,500 (-10%, static) — both ABSOLUTE")
    print("="*84)
    print(f"  {'equity now':>16} | {'PASS%':>6} {'BLOW%':>6} {'still-run%':>10} | {'median days':>11}  {'Δ vs BE':>8}")
    print("-"*84)
    levels=[-0.02,-0.01,0.0,0.005,0.01,0.02,0.029,0.04,0.05,0.07]
    rows=[]; base=None
    for e in levels:
        E0=1.0+e
        p,b,bd,tp=mc_from(dR,dmin,tr,E0,seed=7)
        td=tp[p]+1; md=np.median(td) if p.any() else np.nan
        run=(~p&~b).mean()
        rows.append((e,p.mean(),b.mean(),run,md))
        if abs(e)<1e-9: base=p.mean()
    for e,p,b,run,md in rows:
        dollars=ACCT*(1.0+e)
        dlt=f"{(p-base)*100:+.1f}pt" if base is not None else ""
        star=" <= up ~here?" if abs(e-0.029)<1e-9 else ""
        print(f"  {e*100:+5.1f}%  ${dollars:7,.0f} | {p*100:5.1f}% {b*100:5.1f}% {run*100:9.1f}% | "
              f"{md:9.0f}d  {dlt:>8}{star}")
    print("-"*84)
    print("NOTE: consistency (50% best-day) is tracked fresh from now. If your gain so far came")
    print("from ONE big day, you'll need a few more green days to dilute it below 50% before the")
    print("pass counts — so treat the 'up' rows as a small optimistic nudge on that axis only.")

    # ---------------- figure ----------------
    es=np.array([r[0] for r in rows])*100
    ps=np.array([r[1] for r in rows])*100; bs=np.array([r[2] for r in rows])*100
    mds=np.array([r[4] for r in rows])
    fig,ax=plt.subplots(figsize=(11,6.5))
    ax.plot(es,ps,"o-",color="#55a868",lw=2,label="PASS %")
    ax.plot(es,bs,"o-",color="#c44e52",lw=2,label="BLOW %")
    ax.axvline(0,color="black",ls=":",alpha=0.5); ax.annotate("breakeven $15k",(0,5),fontsize=8,rotation=90,va="bottom")
    ax.axvline(2.9,color="#1f77b4",ls="--",alpha=0.7); ax.annotate("today +2.9%",(2.9,ps.max()),fontsize=9,color="#1f77b4")
    for x,y in zip(es,ps): ax.annotate(f"{y:.0f}%",(x,y+1.2),ha="center",fontsize=8,color="#2d6a3e")
    ax.set_xlabel("your equity RIGHT NOW (% from the $15k start)"); ax.set_ylabel("% of attempts")
    ax.set_title("Conditional pass / blow odds vs current equity — live 4R EA (100k paths, run-to-completion)")
    ax.grid(alpha=0.25); ax.legend(loc="center left")
    a2=ax.twinx(); a2.plot(es,mds,"s--",color="#8172b3",alpha=0.8,label="median days to pass")
    a2.set_ylabel("median trading days to pass",color="#8172b3"); a2.legend(loc="upper right")
    fig.tight_layout(); fig.savefig("challenge_conditional.png",dpi=120)
    print("\nchart -> challenge_conditional.png")


if __name__=="__main__":
    main()
