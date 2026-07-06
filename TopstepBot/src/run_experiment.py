"""
Experiment harness: backtest a strategy -> daily outcomes -> Monte-Carlo the
Topstep Combine, on TRAIN and TEST, with walk-forward sub-periods. Logs each
iteration to results/iterations.jsonl.

Anti-overfitting posture:
- TRAIN = older 70% of trading days; TEST = most-recent 30% (untouched).
- MC preserves regime clustering (contiguous-calendar + block bootstrap).
- Only OOS (TEST + walk-forward) numbers count toward any claim.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulator import ComboConfig, mc_contiguous, mc_block_bootstrap, summarize
from backtest import run_backtest, ExecConfig, Costs
import strategies as S

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "clean_m1_ct.parquet"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
LOG = RESULTS / "iterations.jsonl"

TRAIN_FRAC = 0.70
MC_PATHS = 10_000
MC_MAX_LEN = 250          # ~1 year of trading days cap per challenge attempt
SEED = 12345


def split_train_test(df):
    dates = np.sort(df["date"].unique())
    cut = dates[int(len(dates) * TRAIN_FRAC)]
    train = df[df["date"] < cut]
    test = df[df["date"] >= cut]
    return train, test, cut


def daily_stats(daily):
    pnl = daily["pnl_close"].values
    return dict(
        n_days=len(daily),
        traded_days=int((pnl != 0).sum()),
        mean_pnl=float(pnl.mean()),
        median_pnl=float(np.median(pnl)),
        std_pnl=float(pnl.std()),
        win_day_pct=float(100 * (pnl > 0).mean()),
        total_pnl=float(pnl.sum()),
        best_day=float(pnl.max()),
        worst_day=float(pnl.min()),
    )


def bootstrap_edge_ci(daily, rng, n=2000):
    """Bootstrap 95% CI of mean daily P&L (only traded days). Edge excludes 0?"""
    pnl = daily["pnl_close"].values
    pnl = pnl[pnl != 0]
    if len(pnl) < 20:
        return (float("nan"), float("nan"))
    means = [rng.choice(pnl, len(pnl), replace=True).mean() for _ in range(n)]
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def run_mc(daily, cfg, rng):
    pc = daily["pnl_close"].values
    dm = daily["day_min_offset"].values
    cont = summarize(mc_contiguous(pc, dm, cfg, MC_PATHS, MC_MAX_LEN, rng))
    blk = summarize(mc_block_bootstrap(pc, dm, cfg, MC_PATHS, MC_MAX_LEN, rng))
    return {"contiguous": cont, "block_boot": blk}


def walk_forward(daily, cfg, rng, k=4):
    """Split the series into k contiguous sub-periods; MC each; report worst."""
    idx = np.array_split(np.arange(len(daily)), k)
    periods = []
    for j, ids in enumerate(idx):
        sub = daily.iloc[ids]
        if len(sub) < 30:
            continue
        s = summarize(mc_contiguous(sub["pnl_close"].values,
                                    sub["day_min_offset"].values,
                                    cfg, 3000, MC_MAX_LEN, rng))
        periods.append(dict(period=j, start=str(sub.index.min().date()),
                            end=str(sub.index.max().date()),
                            pass_pct=s["pass_pct"], blowup_pct=s["blowup_pct"]))
    worst = min((p["pass_pct"] for p in periods), default=float("nan"))
    return {"periods": periods, "worst_pass_pct": worst}


def evaluate(name, strategy, exec_cfg, combo_cfg, note=""):
    df = pd.read_parquet(DATA)
    train, test, cut = split_train_test(df)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    dtr = run_backtest(train, strategy, exec_cfg)
    dte = run_backtest(test, strategy, exec_cfg)

    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "name": name, "note": note,
        "split_date": str(pd.Timestamp(cut).date()),
        "exec": {"contract": exec_cfg.contract, "flat_by": exec_cfg.flat_by},
        "params": {k: v for k, v in strategy.__dict__.items()
                   if isinstance(v, (int, float, str, bool, type(None)))},
        "train_daily": daily_stats(dtr),
        "test_daily": daily_stats(dte),
        "train_edge_ci95": bootstrap_edge_ci(dtr, rng),
        "test_edge_ci95": bootstrap_edge_ci(dte, rng),
        "train_mc": run_mc(dtr, combo_cfg, rng),
        "test_mc": run_mc(dte, combo_cfg, rng),
        "train_walkforward": walk_forward(dtr, combo_cfg, rng),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _print(rec):
    print(f"\n=== {rec['name']}  ({rec['note']}) ===")
    print(f"split at {rec['split_date']} | runtime {rec['runtime_s']}s")
    for tag in ("train", "test"):
        d = rec[f"{tag}_daily"]; mc = rec[f"{tag}_mc"]
        ci = rec[f"{tag}_edge_ci95"]
        print(f"[{tag.upper()}] days={d['n_days']} traded={d['traded_days']} "
              f"mean/day=${d['mean_pnl']:.2f} win-day={d['win_day_pct']:.1f}% "
              f"total=${d['total_pnl']:.0f}")
        print(f"        edge95%CI=({ci[0]:.2f},{ci[1]:.2f})  "
              f"MC-contig pass={mc['contiguous']['pass_pct']:.1f}% "
              f"blow={mc['contiguous']['blowup_pct']:.1f}% "
              f"med-days={mc['contiguous']['median_days_to_pass']:.0f} | "
              f"block pass={mc['block_boot']['pass_pct']:.1f}%")
    wf = rec["train_walkforward"]
    print(f"[WALK-FWD train] worst-period pass={wf['worst_pass_pct']:.1f}%  "
          + " ".join(f"{p['start']}:{p['pass_pct']:.0f}%" for p in wf["periods"]))


if __name__ == "__main__":
    exec_cfg = ExecConfig(contract="MNQ")
    combo_cfg = ComboConfig()
    strat = S.OpeningRangeBreakout(or_min=15, stop_pts=25, target_R=1.0, qty=5)
    rec = evaluate("ORB_baseline", strat, exec_cfg, combo_cfg,
                   note="or15 stop25 1R qty5 both RTH")
    _print(rec)
