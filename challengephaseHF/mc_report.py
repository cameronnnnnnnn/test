"""
challengephaseHF/mc_report.py — Monte-Carlo report for running ChallengePhase52p AS-IS at
its default EA settings (1% risk, -2R daily breaker, NAS100). 100k+ bootstrapped challenge
attempts under the FTMO 15k 1-Step rules. Reports pass rate, blow (fail) rate, timeout rate,
and mean+median days-to-pass. Also traces the cumulative pass curve across deadlines, because
the FTMO Challenge has NO hard time limit — a "timeout" at 20 days is not a loss, you keep
trading, so the eventual pass rate is higher than the 20-day number.

Run: python3 mc_report.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402

RISK = CP52.RISK            # 1% — the EA default (RiskPercent=1.0)
BREAKER = CP52.BREAKER      # -2R daily breaker (EA default DailyBreakerR=2.0)
NP = 120_000               # >100k paths


def mc(days, deadline, risk=RISK, n=NP):
    return ftmo.run_mc(days, risk, deadline, n_paths=n, seed=11, block=5)


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    es = engine.edge_stats(tr)
    cut = ad[int(len(ad) * 0.7)]; te = ad[ad > cut]
    d_all = build_days(tr[tr["day"].isin(set(ad))], ad, BREAKER)
    d_oos = build_days(tr[tr["day"].isin(set(te))], te, BREAKER)

    print("=" * 78)
    print(f"ChallengePhase52p — {NP:,}-path Monte Carlo, DEFAULT EA settings")
    print(f"NAS100 | risk {RISK*100:.0f}% | -{BREAKER:g}R daily breaker | FTMO 15k 1-Step")
    print("=" * 78)
    print(f"underlying edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  PF {es['pf']:.2f}  "
          f"{es['n']/df['date'].nunique():.1f} trades/day  ({es['n']} trades over {len(ad)} days)\n")

    for lbl, dd in [("ALL DATA (2022-10 .. 2025-10)", d_all), ("OUT-OF-SAMPLE (last 30%)", d_oos)]:
        m = mc(dd, 20)
        print(f"--- {lbl} ---   [target: reach +10% within 20 trading days]")
        print(f"    PASS rate      : {m['pass_rate']*100:5.1f}%   (reached +10% target)")
        print(f"    FAIL/blow rate : {m['blow_rate']*100:5.1f}%   (hit 3% daily or 10% overall floor)")
        print(f"    timeout rate   : {m['timeout_rate']*100:5.1f}%   (neither in 20d — NOT a loss, keep trading)")
        print(f"    of the blows   : {m['blow_daily_share']*100:4.0f}% were the 3% DAILY cap, "
              f"{(1-m['blow_daily_share'])*100:2.0f}% the 10% overall")
        print(f"    days to pass   : mean {m['mean_days_to_pass']:.1f}   median {m['med_days_to_pass']:.0f}   "
              f"(among the {m['pass_rate']*100:.0f}% that passed)\n")

    print("CUMULATIVE PASS RATE vs how long you're willing to run (ALL DATA, no hard FTMO deadline):")
    print(f"    {'by day':>8}" + "".join(f"{d:>7}" for d in (5, 10, 15, 20, 30, 40, 60)))
    row = "    pass %  "
    prev = 0.0
    for d in (5, 10, 15, 20, 30, 40, 60):
        p = mc(d_all, d)["pass_rate"]; row += f"{p*100:6.1f}"
    print(row)
    m60 = mc(d_all, 60)
    print(f"\n    Eventual (60-day) pass {m60['pass_rate']*100:.1f}%  vs  blow {m60['blow_rate']*100:.1f}%  "
          f"-> with no time limit, the real question is PASS vs BLOW, and it is ~"
          f"{m60['pass_rate']/(m60['pass_rate']+m60['blow_rate'])*100:.0f}/"
          f"{m60['blow_rate']/(m60['pass_rate']+m60['blow_rate'])*100:.0f} in your favour.")

    RISKS = (0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02)
    print("\nRISK sensitivity — the 1% EA default WORKS but is not optimal; lower risk is safer:")
    print(f"    {'risk':>7}" + "".join(f"{r*100:>7.2f}%" for r in RISKS))
    def line(tag, dd, deadline, key):
        row = f"    {tag:7}"
        for r in RISKS:
            row += f"{mc(dd, deadline, risk=r)[key]*100:7.1f}"
        print(row)
    line("pass20 ", d_all, 20, "pass_rate")     # 20-day (monthly sprint) pass
    line("blow   ", d_all, 20, "blow_rate")      # fail rate (same at 20 or 60 day)
    line("pass60 ", d_all, 60, "pass_rate")      # eventual pass (no hard FTMO deadline)
    line("passOOS", d_oos, 20, "pass_rate")      # out-of-sample 20-day pass
    print("    (pass20 = reach +10% in 20 days; pass60 = eventual with no time limit; blow = fail)")
    print("    Best 20-day sprint: ~0.75%.  Safest (lowest blow, pass eventually): 0.50-0.75%.")


if __name__ == "__main__":
    main()
