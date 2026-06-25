"""
mc_chart.py — 10,000-run Monte-Carlo of the recommended 3-setup combo on the
FTMO $15k 1-Step. Plots account-balance paths (averaged in groups of 100), the
+10% pass barrier and -10% fail floor, a vertical 4-week marker, and prints a
pass/blow summary split by within / outside the 1-month goal.

Run: python3 mc_chart.py   ->  writes mc_chart.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import strategies as S, engine, data
from run import build_days
import recommended

START   = 15000.0
TARGET  = 16500.0    # +10%
FLOOR   = 13500.0    # -10%
RISK    = 0.01       # 1.0% per trade
N       = 12000      # >10k runs
HORIZON = 40         # trading days simulated (~8 weeks)
FOURWK  = 20         # trading days in 4 weeks
COST    = 3.0
GROUP   = 100        # average this many paths per plotted line
SEED    = 12

def mc_paths(days):
    rng = np.random.default_rng(SEED)
    dR   = np.asarray(days["day_R"], float)
    dmin = np.asarray(days["day_min_R"], float)
    traded = (np.asarray(days["n"]) > 0).astype(int)
    nD = len(dR)
    samp = rng.integers(0, nD, size=(N, HORIZON))
    R_, Rmin, Tr = dR[samp], dmin[samp], traded[samp]

    E = np.ones(N)
    bal_path = np.empty((N, HORIZON))
    alive = np.ones(N, bool); passed = np.zeros(N, bool)
    days_traded = np.zeros(N, int)
    sum_g = np.zeros(N); max_g = np.zeros(N)
    t_pass = np.full(N, -1); t_blow = np.full(N, -1)

    for t in range(HORIZON):
        live = alive & ~passed
        rmin = Rmin[:, t]; rt = R_[:, t]
        daily_breach = (rmin * RISK) <= -0.03
        E_low = E * (1 + rmin * RISK)
        overall_breach = E_low <= 0.90
        blow_now = live & (daily_breach | overall_breach)
        # freeze blown equity at the breach level for display
        E = np.where(blow_now, np.minimum(E_low, E), E)
        t_blow = np.where(blow_now & (t_blow < 0), t, t_blow)
        alive = alive & ~blow_now

        live = alive & ~passed
        profit = E * rt * RISK
        E = np.where(live, E * (1 + rt * RISK), E)
        gp = np.where(live & (profit > 0), profit, 0.0)
        sum_g += gp; max_g = np.maximum(max_g, gp)
        days_traded += np.where(live, Tr[:, t], 0)
        consistent = max_g <= 0.5 * sum_g + 1e-12
        pass_now = live & (E >= 1.10) & (days_traded >= 4) & consistent
        t_pass = np.where(pass_now & (t_pass < 0), t, t_pass)
        passed = passed | pass_now

        bal_path[:, t] = E * START
    return bal_path, t_pass, t_blow

def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, recommended.orders(df), cost_pts=COST)
    days = build_days(tr, ad)

    bal, t_pass, t_blow = mc_paths(days)
    passed = t_pass >= 0
    blew   = t_blow >= 0
    timeout = ~passed & ~blew

    # ---- plot: sort by terminal balance, average in groups of GROUP ----
    order = np.argsort(bal[:, -1])
    bal_s = bal[order]
    ngrp = N // GROUP
    x = np.arange(1, HORIZON + 1)
    fig, ax = plt.subplots(figsize=(13, 7.5))
    cmap = plt.get_cmap("RdYlGn")
    for g in range(ngrp):
        line = bal_s[g*GROUP:(g+1)*GROUP].mean(axis=0)
        c = cmap(np.clip((line[-1] - FLOOR) / (TARGET - FLOOR), 0, 1))
        ax.plot(x, line, color=c, lw=0.7, alpha=0.55)

    ax.axhline(TARGET, color="green", lw=2, ls="--", label="PASS  +10%  ($16,500)")
    ax.axhline(FLOOR,  color="red",   lw=2, ls="--", label="FAIL  -10%  ($13,500)")
    ax.axhline(START,  color="black", lw=1, ls=":",  alpha=0.6, label="Start  ($15,000)")
    ax.axvline(FOURWK, color="navy",  lw=1.8, ls="-.", label="4 weeks (20 trading days)")

    ax.set_xlim(1, HORIZON); ax.set_ylim(FLOOR-300, TARGET+1200)
    ax.set_xlabel("Trading days into the challenge")
    ax.set_ylabel("Account balance ($)")
    ax.set_title(f"FTMO $15k 1-Step — NAS100 3-setup scale-out combo\n"
                 f"{N:,} Monte-Carlo runs @ {RISK*100:.1f}%/trade "
                 f"({ngrp} lines, each avg of {GROUP} runs)")
    ax.legend(loc="upper left", fontsize=9); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig("mc_chart.png", dpi=120)

    # ---- summary ----
    p_in  = int((passed & (t_pass < FOURWK)).sum())
    p_out = int((passed & (t_pass >= FOURWK)).sum())
    b_in  = int((blew   & (t_blow < FOURWK)).sum())
    b_out = int((blew   & (t_blow >= FOURWK)).sum())
    to    = int(timeout.sum())
    pct = lambda k: f"{k} ({k/N*100:.1f}%)"
    print("="*64)
    print(f"MONTE-CARLO SUMMARY  —  {N:,} runs, {RISK*100:.1f}%/trade, {HORIZON}-day horizon")
    print("="*64)
    print(f"  PASSED total : {pct(p_in+p_out)}")
    print(f"     within 4 weeks (<=20 td) : {pct(p_in)}")
    print(f"     after  4 weeks           : {pct(p_out)}")
    print(f"  BLEW UP total: {pct(b_in+b_out)}")
    print(f"     within 4 weeks           : {pct(b_in)}")
    print(f"     after  4 weeks           : {pct(b_out)}")
    print(f"  still going at day {HORIZON} : {pct(to)}")
    print("-"*64)
    # state exactly at the 4-week line
    passed_by20 = int((passed & (t_pass < FOURWK)).sum())
    blew_by20   = int((blew & (t_blow < FOURWK)).sum())
    print(f"  AT THE 4-WEEK MARK: passed {pct(passed_by20)} | "
          f"blew {pct(blew_by20)} | still trading {pct(N-passed_by20-blew_by20)}")
    print(f"\n  chart -> mc_chart.png")

if __name__ == "__main__":
    main()
