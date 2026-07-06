"""
Loop 2: risk-vs-time frontier. Daily P&L scales linearly with qty (engine
multiplies contracts), so backtest ONCE at qty=1, then scale the daily series
to sweep contract size cheaply. This isolates the single biggest pass% lever:
lower per-trade risk traded against (unlimited) time.

Reports TRAIN + TEST pass%/blow%/median-days across the qty frontier, for a
couple of horizons, plus the per-day edge bootstrap CI (does it exclude 0?).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import DATA, split_train_test, bootstrap_edge_ci
from simulator import ComboConfig, mc_contiguous, summarize
from backtest import run_backtest, ExecConfig
import strategies as S

df = pd.read_parquet(DATA)
train, test, cut = split_train_test(df)
exec_cfg = ExecConfig(contract="MNQ")
combo = ComboConfig()
rng = np.random.default_rng(777)

def series(daily, qty):
    return daily["pnl_close"].values * qty, daily["day_min_offset"].values * qty

def frontier(tag, daily, horizons=(250, 500)):
    ci = bootstrap_edge_ci(daily, rng)
    m = daily["pnl_close"].mean()
    print(f"\n[{tag}] n={len(daily)} mean/day@q1=${m:.2f} edge95CI=({ci[0]:.2f},{ci[1]:.2f}) "
          f"{'EXCLUDES 0' if ci[0]>0 or ci[1]<0 else 'includes 0'}")
    print(f"  {'qty':>3} {'$risk/day':>9} | " +
          " | ".join(f"H={h}:pass%/blow%/med" for h in horizons))
    for qty in (1, 2, 3, 4, 5, 6, 8):
        pc, dm = series(daily, qty)
        risk = -np.percentile(dm[dm < 0], 5) if (dm < 0).any() else 0  # ~worst 5% day
        cells = []
        for h in horizons:
            s = summarize(mc_contiguous(pc, dm, combo, 8000, h, rng))
            cells.append(f"{s['pass_pct']:4.1f}/{s['blowup_pct']:4.1f}/"
                         f"{s['median_days_to_pass']:.0f}")
        print(f"  {qty:>3} {risk:>9.0f} | " + " | ".join(cells))

for mode, stop in [("both", 40), ("both", 25)]:
    reg = S.build_regime(df, sma_n=50, mode=mode)
    strat = S.TrendSession(reg, stop_pts=stop, target_pts=None, qty=1)
    dtr = run_backtest(train, strat, exec_cfg)
    dte = run_backtest(test, strat, exec_cfg)
    print("\n" + "=" * 70 + f"\nTrendSession both sma50 stop{stop} hold-to-close")
    frontier(f"TRAIN stop{stop}", dtr)
    frontier(f"TEST  stop{stop}", dte)
