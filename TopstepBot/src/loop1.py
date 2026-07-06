"""
Iteration loop 1: TrendSession (intraday drift capture, trend-filtered).
Sweep the key levers and report TRAIN + TEST + walk-forward. We read OOS and
worst-period numbers, not in-sample peaks.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import evaluate, DATA, _print
from simulator import ComboConfig
from backtest import ExecConfig
import strategies as S

df = pd.read_parquet(DATA)
exec_cfg = ExecConfig(contract="MNQ")
combo = ComboConfig()

configs = []
# (sma_n, mode, stop_pts, qty, target_pts)
for sma_n in (50,):
    for mode in ("long_flat", "both"):
        for stop, qty in [(40, 10), (40, 5), (60, 6), (30, 8)]:
            configs.append((sma_n, mode, stop, qty, None))

for sma_n, mode, stop, qty, tgt in configs:
    reg = S.build_regime(df, sma_n=sma_n, mode=mode)
    strat = S.TrendSession(reg, stop_pts=stop, target_pts=tgt, qty=qty)
    name = f"Trend_sma{sma_n}_{mode}_stop{stop}_qty{qty}"
    rec = evaluate(name, strat, exec_cfg, combo,
                   note=f"sma{sma_n} {mode} stop{stop} qty{qty} holdclose")
    _print(rec)
