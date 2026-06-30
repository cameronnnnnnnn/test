"""
iter3_probe.py — the two remaining honest levers for challenge pass rate:
  (1) a DAILY CIRCUIT BREAKER: stop trading for the day after -X R, so a bad day
      can't reach the -3% daily cliff (the #1 cause of blow). Does capping daily
      downside raise pass?
  (2) DEADLINE sensitivity: how much does pass rise if we allow 30/40/60 days
      instead of 20? (the live runner combo).
Run: python3 iter3_probe.py
"""
import numpy as np, pandas as pd
import features as FE, data, strategies as S, engine, ftmo
from strat_gen import eod_map, filtered_orders, split
import warnings; warnings.filterwarnings("ignore")


def days_with_stop(trades, ad, daily_stop_R=0.0):
    base = pd.DataFrame({"day": ad, "day_R": 0.0, "day_min_R": 0.0, "n": 0}).set_index("day")
    if len(trades):
        agg = engine.trades_to_days(trades, ad, daily_stop_R=daily_stop_R).set_index("day")
        base.loc[agg.index, ["day_R", "day_min_R", "n"]] = agg[["day_R", "day_min_R", "n"]].values
    return base.reset_index().to_records(index=False)


def runner_combo(df, F, eod):
    return (filtered_orders(df, F, eod, "cusum", 50, 6.0, be_R=1.0,
                            filters=[("vwap_slope", 0.04, np.inf, True)])
            + filtered_orders(df, F, eod, "orb", 50, 6.0, be_R=1.0,
                              filters=[("min_since_open", 24, np.inf, False)])
            + S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0))


def main():
    df = S.prep(data.load()); F = FE.compute(df)
    ad = np.array(sorted(df["date"].unique())); eod = eod_map(df)
    tr_d, te_d = split(ad)
    orders = runner_combo(df, F, eod)
    trades = engine.simulate(df, orders, cost_pts=2.0)
    te_trades = trades[trades["day"].isin(set(te_d))]

    print("=" * 92)
    print("(1) DAILY CIRCUIT BREAKER sweep — runner combo, TEST days, 20-day deadline")
    print("=" * 92)
    print(f"  {'dailyStop':>10} {'risk*':>6} {'PASS%':>6} {'BLOW%':>6} {'dailyBlow':>10} {'timeout%':>9} {'med_d':>6}")
    for ds in [0.0, 2.5, 2.0, 1.5, 1.0]:
        days = days_with_stop(te_trades, te_d, daily_stop_R=ds)
        best = None
        for r in (0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02):
            m = ftmo.run_mc(days, r, 20, n_paths=40000, seed=11, block=5)
            if best is None or m["pass_rate"] > best[1]["pass_rate"]: best = (r, m)
        r, m = best
        lbl = "none" if ds == 0 else f"{ds:.1f}R"
        md = m["med_days_to_pass"]
        print(f"  {lbl:>10} {r*100:5.2f}% {m['pass_rate']*100:5.1f}% {m['blow_rate']*100:5.1f}% "
              f"{m['blow_daily_share']*100:8.0f}%* {m['timeout_rate']*100:8.1f}% {md if md==md else 0:5.0f}")
    print("  *dailyBlow = share of blows via the 3% daily cap (rest = the 10% floor)")

    print("\n" + "=" * 92)
    print("(2) DEADLINE sensitivity — runner combo, TEST days, best daily-stop=2.0R, risk swept")
    print("=" * 92)
    days = days_with_stop(te_trades, te_d, daily_stop_R=2.0)
    print(f"  {'deadline':>9} {'risk*':>6} {'PASS%':>6} {'BLOW%':>6} {'timeout%':>9} {'med_d':>6}")
    for dl in [20, 30, 40, 60, 90]:
        best = None
        for r in (0.005, 0.0075, 0.01, 0.0125, 0.015):
            m = ftmo.run_mc(days, r, dl, n_paths=40000, seed=11, block=5)
            if best is None or m["pass_rate"] > best[1]["pass_rate"]: best = (r, m)
        r, m = best; md = m["med_days_to_pass"]
        print(f"  {dl:>7}d {r*100:5.2f}% {m['pass_rate']*100:5.1f}% {m['blow_rate']*100:5.1f}% "
              f"{m['timeout_rate']*100:8.1f}% {md if md==md else 0:5.0f}")
    print("\nIf neither lever pushes TEST pass anywhere near 80%, the conclusion is structural:")
    print("80%/20d is not attainable on NAS100 under FTMO's 3% daily cap with honest edges.")


if __name__ == "__main__":
    main()
