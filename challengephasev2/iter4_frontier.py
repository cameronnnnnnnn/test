"""
iter4_frontier.py — "pass% over speed". FTMO 1-Step has no hard time limit, so we
run challenges to completion (cap 180 trading days) and find the config that MAXIMISES
pass rate (= minimises lifetime blow), accepting more time. Pass% rises as per-trade
risk falls (less daily-cap/floor blow) and as the -2R daily circuit breaker caps bad
days; the cost is a longer median time-to-pass. We print the whole frontier so you can
choose, then recommend a spot. TEST (out-of-sample) days only. Run: python3 iter4_frontier.py
"""
import numpy as np, pandas as pd
import features as FE, data, strategies as S, engine, ftmo
from strat_gen import eod_map, filtered_orders, split
from iter3_probe import days_with_stop
import warnings; warnings.filterwarnings("ignore")

CAP = 180   # trading days ~ 9 months; enough to resolve almost every path


def combo(df, F, eod, tpR):
    return (filtered_orders(df, F, eod, "cusum", 50, tpR, be_R=1.0,
                            filters=[("vwap_slope", 0.04, np.inf, True)])
            + filtered_orders(df, F, eod, "orb", 50, tpR, be_R=1.0,
                              filters=[("min_since_open", 24, np.inf, False)])
            + S.vwap_pullback(df, stop_pts=40, tp_R=tpR, trail_R=0.0))


def frontier(df, F, eod, te_d, tpR, breaker):
    orders = combo(df, F, eod, tpR)
    tr = engine.simulate(df, orders, cost_pts=2.0)
    tr = tr[tr["day"].isin(set(te_d))]
    days = days_with_stop(tr, te_d, daily_stop_R=breaker)
    rows = []
    for r in (0.0025, 0.00375, 0.005, 0.00625, 0.0075, 0.01):
        m = ftmo.run_mc(days, r, CAP, n_paths=40000, seed=11, block=5)
        rows.append((r, m["pass_rate"], m["blow_rate"], m["timeout_rate"],
                     m["med_days_to_pass"]))
    return rows


def main():
    df = S.prep(data.load()); F = FE.compute(df)
    ad = np.array(sorted(df["date"].unique())); eod = eod_map(df)
    _, te_d = split(ad)
    print("=" * 92)
    print(f"PASS-OVER-SPEED FRONTIER — run-to-completion (cap {CAP}d), OOS test days, -2R daily breaker")
    print("=" * 92)
    for tpR in (4.0, 6.0):
        print(f"\n  ── runner combo @ {tpR:.0f}R ──")
        print(f"  {'risk':>6} | {'PASS%':>6} {'BLOW%':>6} {'still-running%':>14} | {'med days':>9}")
        print("  " + "-" * 56)
        for r, p, b, to, md in frontier(df, F, eod, te_d, tpR, breaker=2.0):
            md = md if md == md else float("nan")
            print(f"  {r*100:5.2f}% | {p*100:5.1f}% {b*100:5.1f}% {to*100:13.1f}% | {md:7.0f}d")
    print("\n" + "=" * 92)
    print("Lower risk -> higher pass (less blow) but longer median time. 'still-running' would")
    print("eventually resolve mostly to PASS (positive EV), so true pass is pass% + most of it.")
    print("Recommend the knee: highest pass where median time-to-pass stays tolerable.")


if __name__ == "__main__":
    main()
