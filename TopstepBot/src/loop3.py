"""
Loop 3: (A) zero-edge CONTROL — what pass% does a mean-ZERO daily process get
under these exact rules? Establishes the no-skill ceiling so we can tell a
strong-edge pass from a low-ruin coincidence. (B) final principled long-only
strong-trend attempt with a defined target (variance control). (C) per-year
edge CIs to check sub-period robustness.
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
rng = np.random.default_rng(2024)

# ---------- (A) zero-edge control ----------
print("=" * 70)
print("(A) ZERO-EDGE CONTROL: mean-0 daily P&L, gaussian, no skill")
print("    pass% here is pure geometry of 3000-target vs 2000-trailing-stop")
for daily_vol in (150, 250, 400):   # $ std of daily pnl
    print(f"  daily_vol=${daily_vol}:")
    for qty_scale in (1,):
        # simulate a long synthetic series then contiguous-sample it
        n = 4000
        pnl = rng.normal(0, daily_vol, n)
        # intraday min offset ~ pnl minus a half-day extra adverse swing
        dm = np.minimum(0, pnl) - np.abs(rng.normal(0, daily_vol * 0.6, n))
        for h in (250, 500):
            s = summarize(mc_contiguous(pnl, dm, combo, 8000, h, rng))
            print(f"      H={h}: pass={s['pass_pct']:.1f}% blow={s['blowup_pct']:.1f}% "
                  f"med-days={s['median_days_to_pass']:.0f}")

# ---------- (C) per-year edge CI for the trend family ----------
print("\n" + "=" * 70)
print("(C) Per-year per-day edge 95% CI (qty=1), TrendSession both sma50 stop40")
reg = S.build_regime(df, sma_n=50, mode="both")
strat = S.TrendSession(reg, stop_pts=40, target_pts=None, qty=1)
dall = run_backtest(df, strat, exec_cfg)
for y, g in dall.groupby(dall.index.year):
    ci = bootstrap_edge_ci(g, rng)
    tag = "EXCL 0" if (ci[0] > 0 or ci[1] < 0) else "incl 0"
    print(f"  {y}: n={len(g):3d} mean=${g['pnl_close'].mean():7.2f} "
          f"CI=({ci[0]:7.2f},{ci[1]:7.2f}) {tag}")

# ---------- (B) final long-only strong-trend, defined target ----------
print("\n" + "=" * 70)
print("(B) Long-only strong-trend (sma100), defined target to cut variance")
for stop, tgt in [(30, 30), (25, 40), (40, 20)]:
    reg = S.build_regime(df, sma_n=100, mode="long_flat")
    strat = S.TrendSession(reg, stop_pts=stop, target_pts=tgt, qty=1)
    dtr = run_backtest(train, strat, exec_cfg)
    dte = run_backtest(test, strat, exec_cfg)
    for tag, d in [("TRAIN", dtr), ("TEST ", dte)]:
        ci = bootstrap_edge_ci(d, rng)
        best = summarize(mc_contiguous(d["pnl_close"].values*3, d["day_min_offset"].values*3,
                                       combo, 8000, 250, rng))
        exok = "EXCL0" if (ci[0] > 0 or ci[1] < 0) else "incl0"
        print(f"  stop{stop}/tgt{tgt} [{tag}] mean/day@q1=${d['pnl_close'].mean():6.2f} "
              f"CI=({ci[0]:.1f},{ci[1]:.1f}){exok} | qty3 pass={best['pass_pct']:.1f}% "
              f"blow={best['blowup_pct']:.1f}%")
