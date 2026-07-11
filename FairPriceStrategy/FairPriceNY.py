"""
FairPriceStrategy/FairPriceNY.py — THE STANDALONE DELIVERABLE. The fair-price framework distilled
to its honestly-surviving core, as its own challenge strategy (not a 52p add-on):

  LEG 1 — NY_P1  : big-candle CONTINUATION. First 15 min after the 9:30 NY open, trade the
                   opening candle's direction on a displacement or break-of-structure trigger
                   whose candle range > 25pts. Up to 2 entries. 50pt stop.
  LEG 2 — NY_P2  : big-candle REVERSION. 15-90 min after open, price outside the fair zone
                   (pre-open candle) with >=30pts room, BOS trigger with range > 25pts. 50pt stop.
  EXIT: hard 4R take-profit (200pts) — swept on train only; the video's 1.5R is the weakest exit
        (this framework's winners run; at 4R even the reversion leg turns +EV both halves).

Edge: 0.64 trades/day, WR 36.3%, expR +0.138 (train +0.17 / test +0.12 — better per-trade than
52p). Ceiling as a STANDALONE (its structural limit is frequency, not edge):
  at 1.00% risk: 2 months ~27% pass / 12% blow · 3 months ~39%/18% · ~4.5 months ~51%/24%
  at 0.75% risk: nearly never blows (<10% at 90d) but crawls.
Run: python3 FairPriceNY.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from search import build_days                            # noqa: E402
from standalone import leg_orders, seq, EXITS            # noqa: E402

RISK = 0.01            # 1% — the standalone's sweet spot (see risk-horizon map)
NY = 16*60 + 30


def trades(df=None):
    df = df if df is not None else S.prep(data.load())
    t = pd.concat([seq(engine.simulate(df, leg_orders(df, NY, 1, EXITS["rr4"]), cost_pts=2.0)),
                   seq(engine.simulate(df, leg_orders(df, NY, 2, EXITS["rr4"]), cost_pts=2.0))],
                  ignore_index=True)
    return t, np.array(sorted(df["date"].unique()))


def verify(n_paths=100000):
    tr, ad = trades()
    es = engine.edge_stats(tr)
    dd = build_days(tr, ad, 2.0)
    print("=" * 70)
    print("FairPriceNY — standalone fair-price strategy (NY open, big-candle, 4R)")
    print("=" * 70)
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  {es['n']/len(ad):.2f} trades/day  ({es['n']} trades)")
    print(f"risk {RISK*100:.2f}%:")
    for dl, lbl in [(20, "1 month "), (40, "2 months"), (60, "3 months"), (90, "4.5 months")]:
        m = ftmo.run_mc(dd, RISK, dl, n_paths=n_paths, seed=11, block=5)
        print(f"  [{lbl}] pass {m['pass_rate']*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%")


if __name__ == "__main__":
    verify()
