"""
v4/funded_ev.py — funded-phase EV (challenge fee $135 AUD) + monthly EV after
break-even + a 10,000-run Monte-Carlo of one funded month.

Phase-2 grind = the only +EV config: 4R combo at r=0.40% (low risk = the 'safe'
part; 28% WR is fine because the edge is the fat tail). Start each month at the
account size; 3% daily + 10% overall enforced.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import strategies as S, engine, data
from run import build_days

ACCT   = 15000.0
FLOORP = 0.10          # 10% overall max loss
DAILY  = 0.03
FEE    = 135.0         # challenge fee, AUD
SPLIT  = 0.90          # trader keeps 90%
PASS   = 0.41          # challenge 4-week pass rate (strategy_v4)
RISK   = 0.004         # phase-2 grind risk
MONTH  = 21
N      = 10000
GROUP  = 100

def combo_days():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    o = S.orb(df, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
              tp_R=4.0, be_R=0.0, trail_R=0.0) + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)
    d = build_days(engine.simulate(df, o, cost_pts=2.0), ad)
    return np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float)

def mc_month(dR, dmin, seed=7):
    rng = np.random.default_rng(seed); nD = len(dR); block = 5
    nb = int(np.ceil(MONTH/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:MONTH]
    R_, Rmin = dR[idx], dmin[idx]
    bal = np.full((N, MONTH+1), ACCT); E = np.ones(N); alive = np.ones(N, bool)
    for t in range(MONTH):
        rmin = Rmin[:,t]; rt = R_[:,t]
        dead = alive & (((rmin*RISK) <= -DAILY) | (E*(1+rmin*RISK) <= 1-FLOORP))
        E = np.where(dead, E*(1+rmin*RISK), E); alive &= ~dead
        E = np.where(alive, E*(1+rt*RISK), E)
        bal[:, t+1] = E*ACCT
    return bal, ~alive

def main():
    dR, dmin = combo_days()
    bal, blow = mc_month(dR, dmin)
    end = bal[:,-1]; ret = end/ACCT - 1.0
    mean_gain = ret.mean()                     # avg monthly gain (fraction)
    avg_end = end.mean()

    # ---- EV chain (AUD) ----
    cost_fund = FEE / PASS                      # avg fee spend to get one funded account
    be_pct = cost_fund / (SPLIT*ACCT)           # extraction needed to break even
    monthly_ev_gross = mean_gain * ACCT * SPLIT             # your 90% of the avg month
    p_blow = blow.mean()
    monthly_ev_net = monthly_ev_gross - p_blow*cost_fund    # amortise re-funding after a blow

    # ---- chart: 100 lines (avg of 100), sorted by ending balance ----
    order = np.argsort(end); bs = bal[order]
    fig, ax = plt.subplots(figsize=(13,7.5)); x = np.arange(MONTH+1)
    cmap = plt.get_cmap("RdYlGn")
    lo, hi = ACCT*(1-FLOORP), avg_end
    for g in range(N//GROUP):
        line = bs[g*GROUP:(g+1)*GROUP].mean(axis=0)
        ax.plot(x, line, color=cmap(np.clip((line[-1]-lo)/(ACCT*1.04-lo),0,1)), lw=0.7, alpha=0.55)
    ax.axhline(ACCT*(1-FLOORP), color="red",   lw=2, ls="--", label=f"Max DD  -10%  (${ACCT*0.9:,.0f})")
    ax.axhline(ACCT*1.025,      color="orange",lw=2, ls="--", label=f"+2.5% break-even  (${ACCT*1.025:,.0f})")
    ax.axhline(avg_end,         color="blue",  lw=2, ls="-.", label=f"Avg monthly gain  (${avg_end:,.0f}, {mean_gain*100:+.2f}%)")
    ax.axhline(ACCT, color="black", lw=1, ls=":", alpha=0.5)
    ax.set_xlim(0,MONTH); ax.set_xlabel("Trading days (one funded month)"); ax.set_ylabel("Account balance ($)")
    ax.set_title(f"Funded month — {N:,} Monte-Carlo runs @ {RISK*100:.1f}%/trade (100 lines, each avg of {GROUP})")
    ax.legend(loc="upper left", fontsize=9); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig("funded_mc.png", dpi=120)

    # ---- summary ----
    print("="*64); print("FUNDED-PHASE EV  (challenge fee $135 AUD, FTMO 90/10, $15k acct)"); print("="*64)
    print(f"  challenge pass rate         : {PASS*100:.0f}%  -> {1/PASS:.2f} tries/funded")
    print(f"  cost to get funded          : ${cost_fund:,.0f} AUD")
    print(f"  break-even extraction       : {be_pct*100:.2f}%  (= ${cost_fund:,.0f} at 90% split)")
    print(f"  phase-2 grind               : 4R combo @ r={RISK*100:.2f}% (low-risk safe grind)")
    print("-"*64)
    print(f"  AVG MONTHLY GAIN            : {mean_gain*100:+.2f}%  (= ${mean_gain*ACCT:,.0f} on the account)")
    print(f"  YOUR MONTHLY EV (after BE)  : ${monthly_ev_gross:,.0f}/mo gross (90% share)")
    print(f"  monthly blow probability    : {p_blow*100:.1f}%")
    print(f"  net monthly EV (amortised)  : ${monthly_ev_net:,.0f}/mo  (gross - blow*re-fund)")
    print("="*64)
    print("MONTE-CARLO SUMMARY (one funded month, 10,000 runs):")
    print(f"  ended GREEN (>$15,000)      : {(ret>0).mean()*100:.1f}%")
    print(f"  ended >= +2.5%              : {(ret>=0.025).mean()*100:.1f}%")
    print(f"  blew the account (-10%)     : {p_blow*100:.1f}%")
    print(f"  avg ending balance          : ${avg_end:,.0f}  ({mean_gain*100:+.2f}%)")
    print(f"  median ending balance       : ${np.median(end):,.0f}")
    print(f"  best / worst 100-avg line   : ${bs[-GROUP:].mean(0)[-1]:,.0f} / ${bs[:GROUP].mean(0)[-1]:,.0f}")
    print("  chart -> funded_mc.png")

if __name__ == "__main__":
    main()
