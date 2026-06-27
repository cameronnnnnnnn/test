"""
v4/hundred_accounts.py — full-pipeline EV + optimiser for the ONE-SHOT funded play.

Idea (your call): don't try to keep a funded account alive for many small payouts
(the floor jumps to $15k after the first payout, so the account is fragile). Instead,
on each funded account climb to a target +T%, WITHDRAW THE WHOLE PROFIT in one payout
(0.90 x T x $15,000 to you), and walk away — then buy a fresh challenge and repeat.

So each funded account is a clean first-passage race:
    reach equity 1+T  -> WIN: bank 0.90*T*$15,000, account done
    hit  the -10% floor (0.90) first -> BLOW: $0
3% daily loss enforced. Floor-jump-to-$15k is irrelevant (you stop after the payout).

We optimise (risk r, target T) to maximise AVG MONTHLY INCOME, steady-state, by the
renewal-reward theorem (each cycle = time to re-fund a challenge + funded race time):
    net_monthly = (P_win*0.90*T*15000 - cost_to_fund) / ((days_to_fund + race_days)/21)

NOTE (conservative): the -10% floor is checked on the INTRADAY low (day_min_R), but the
+T target is only checked at the DAILY CLOSE (we have no intraday high). So P_win is a
slight UNDER-estimate (a day that touches +T then closes lower isn't counted as a win).
"""
import numpy as np, strategies as S, engine, data
from run import build_days

ACCT = 15000.0; FEE = 135.0; SPLIT = 0.90
R_CHAL = 0.01                               # challenge risk (fixed strategy_v4)
FLOOR0 = 0.90                               # funded -10% floor (pre-payout)
DAILY = 0.03; MONTH = 21

def combo_days():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    o = S.orb(df, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
              tp_R=4.0, be_R=0.0, trail_R=0.0) + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)
    d = build_days(engine.simulate(df, o, cost_pts=2.0), ad)
    return np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float), (np.asarray(d["n"])>0).astype(int)

def sample(dR, dmin, traded, N, H, seed, block=5):
    rng = np.random.default_rng(seed); nb = int(np.ceil(H/block))
    idx = ((rng.integers(0,len(dR),size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%len(dR)).reshape(N,-1)[:,:H]
    return dR[idx], dmin[idx], traded[idx]

# ---------- challenge: pass rate + timings (fixed strategy_v4, r=1%) ----------
def challenge(dR, dmin, traded, N=150000, cap=378, seed=1):
    R_, Rmin, Tr = sample(dR, dmin, traded, N, cap, seed)
    E = np.ones(N); alive = np.ones(N, bool); passed = np.zeros(N, bool); blown = np.zeros(N, bool)
    dtr = np.zeros(N, int); sg = np.zeros(N); mg = np.zeros(N)
    tpass = np.full(N,-1); tblow = np.full(N,-1)
    for t in range(cap):
        live = alive & ~passed
        rmin = Rmin[:,t]; rt = R_[:,t]
        dead = live & (((rmin*R_CHAL)<=-DAILY) | (E*(1+rmin*R_CHAL)<=FLOOR0))
        tblow = np.where(dead & (tblow<0), t, tblow); blown |= dead; alive &= ~dead
        live = alive & ~passed
        prof = E*rt*R_CHAL; E = np.where(live, E*(1+rt*R_CHAL), E)
        gp = np.where(live & (prof>0), prof, 0.0); sg += gp; mg = np.maximum(mg, gp)
        dtr += np.where(live, Tr[:,t], 0)
        consistent = mg <= 0.5*sg + 1e-12
        now = live & (E>=1.10) & (dtr>=4) & consistent
        tpass = np.where(now & (tpass<0), t, tpass); passed |= now
    return passed, tpass, blown, tblow

# ---------- funded ONE-SHOT: race +T vs -10%, single full payout ----------
def funded_oneshot(R_, Rmin, rf, T):
    """Returns won (reached +T) and rtime (trading-day index when resolved, or H)."""
    N, H = R_.shape
    E = np.ones(N); active = np.ones(N, bool); won = np.zeros(N, bool); rtime = np.full(N, H)
    tgt = 1.0 + T
    for t in range(H):
        rmin = Rmin[:,t]; rt = R_[:,t]
        dead = active & (((rmin*rf)<=-DAILY) | (E*(1+rmin*rf)<=FLOOR0))   # blow on intraday low
        rtime = np.where(dead, t, rtime); active &= ~dead
        E = np.where(active, E*(1+rt*rf), E)
        hit = active & (E >= tgt)                                          # win on daily close
        rtime = np.where(hit, t, rtime); won |= hit; active &= ~hit
        if not active.any(): break
    return won, rtime

def oneshot_metrics(R_, Rmin, rf, T, cost_fund, dtf_days):
    won, rtime = funded_oneshot(R_, Rmin, rf, T)
    payout = SPLIT*T*ACCT                                  # your $ if you win
    p_win = won.mean()
    income = np.where(won, payout, 0.0)
    E_income = income.mean()                               # = p_win*payout
    race_days = (rtime+1).mean()
    win_days  = (rtime[won]+1).mean() if won.any() else np.nan   # days to actually WIN
    cyc_mo = (dtf_days + race_days)/MONTH
    mo_per_payout = cyc_mo/max(p_win,1e-9)                 # months between real payouts (1 slot)
    net_monthly = (E_income - cost_fund)/cyc_mo
    return dict(rf=rf, T=T, payout=payout, p_win=p_win, E_income=E_income,
                med_income=np.median(income), race_days=race_days, win_days=win_days,
                cyc_mo=cyc_mo, mo_per_payout=mo_per_payout, net_monthly=net_monthly)

def main():
    dR, dmin, traded = combo_days()

    # ---- Stage 1: challenge economics ----
    passed, tpass, blown_c, tblow = challenge(dR, dmin, traded)
    p = passed.mean()
    d_pass = (tpass[passed]+1).mean(); d_blow = (tblow[blown_c]+1).mean()
    cost_fund = FEE/p
    days_to_fund = (1-p)/p*d_blow + d_pass
    med_chal = np.median(tpass[passed])+1

    # ---- Stage 2: optimise (risk, target) for the one-shot ----
    Ng, Hg = 60000, 60*MONTH
    Rg, Rming, _ = sample(dR, dmin, traded, Ng, Hg, seed=2)     # shared paired paths
    risks = [0.006, 0.0075, 0.009, 0.010, 0.011, 0.0125]
    targs = [0.03, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70]
    rows = [oneshot_metrics(Rg, Rming, rf, T, cost_fund, days_to_fund) for rf in risks for T in targs]
    rows.sort(key=lambda m: m["net_monthly"], reverse=True)
    best = rows[0]

    print("="*88)
    print("ONE-SHOT FUNDED PLAY — climb to +T%, withdraw the WHOLE profit, walk away, re-fund")
    print("Goal: FREQUENT payouts (every ~1-2 months), NOT a multi-month moonshot. FTMO $15k 90/10")
    print("="*88)
    print("STAGE 1 — CHALLENGE (strategy_v4, r=1.0%, run to completion):")
    print(f"  pass {p*100:.1f}%   median {med_chal:.0f}d   cost-to-fund $135/{p:.3f}=${cost_fund:,.0f}   "
          f"re-fund time {days_to_fund:.0f}d ({days_to_fund/MONTH:.1f}mo)")
    print("-"*88)

    rbest = best["rf"]                                  # income-best risk (also fine for cadence)
    at_rb = sorted([r for r in rows if abs(r['rf']-rbest)<1e-9], key=lambda x: x['T'])
    print(f"CADENCE SWEEP at r={rbest*100:.2f}% — LOWER target = faster, more frequent payouts:")
    print(f"  {'target':>7} {'$/payout':>9} {'P(win)':>7} {'win in':>8} {'mo/payout':>10} {'median$':>8} {'$/mo':>7}")
    for m in at_rb:
        print(f"  {m['T']*100:6.1f}% {m['payout']:9.0f} {m['p_win']*100:6.0f}% {m['win_days']:6.0f}d "
              f"{m['mo_per_payout']:9.1f} {m['med_income']:8.0f} {m['net_monthly']:7.0f}")
    print("  win in   = avg TRADING DAYS a WINNING account needs to hit +T (then you cash out)")
    print("  mo/payout= realistic months between payouts on ONE slot (incl. the share that blow")
    print("             & must re-fund). Run 2-3 slots in parallel for a payout ~EVERY month.")
    print("-"*88)
    print("Max $/mo wants +50-70% targets = 3+ month holds, ~22% win — REJECTED (you want cadence).")
    print("Fast-cadence sweet spot = +5% to +10%:")
    print("="*88)

    def report(tag, T, rf=rbest):
        Nb, Hb = 200000, 60*MONTH
        Rb, Rminb, _ = sample(dR, dmin, traded, Nb, Hb, seed=7)
        won, rtime = funded_oneshot(Rb, Rminb, rf, T)
        payout = SPLIT*T*ACCT; p_win = won.mean()
        win_days = (rtime[won]+1).mean(); race = (rtime+1).mean()
        cyc = (days_to_fund+race)/MONTH; netmo = (p_win*payout-cost_fund)/cyc
        mo_pp = cyc/max(p_win,1e-9); med = np.median(np.where(won, payout, 0.0))
        n_pass = p*100; net100 = p_win*payout*n_pass - 100*FEE
        print(f"{tag}: r={rf*100:.2f}%, target +{T*100:.0f}%  ->  ${payout:,.0f} per win (your 90%)")
        print(f"    win rate {p_win*100:.0f}% (median ${med:,.0f})   a WIN cashes out in ~{win_days:.0f} trading days")
        print(f"    ~{mo_pp:.1f} months between payouts per slot   income ${netmo:,.0f}/mo per slot")
        print(f"    buy 100 challenges -> ~{n_pass:.0f} funded -> NET ${net100:,.0f}")

    report(">> +5%   (fastest cadence, smaller cheques)", 0.05)
    print()
    report(">> +10%  (your instinct: take the whole 10% — best balance)", 0.10)
    print("="*88)

if __name__ == "__main__":
    main()
