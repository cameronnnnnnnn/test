"""
news/reopen_opt.py — optimize SL/TP geometry for the 6pm-reopen REVERSAL trade (cand_rev:
trade against the 01:00 reopen candle's close direction, enter 01:01, flat by 09:55).

User context: 50k futures prop accounts (NQ), cap 6 minis = 60 micros (MNQ $2/pt).
Futures cost is lower than the CFD 2pt: assume ~1.5pt effective (spread+commission+slip),
with 1.0/2.0pt sensitivity on the winner. 0EV is acceptable (variance play), so the pick is
max train expR but the WHOLE grid is shown, plus test column, fold stability, and the
contracts-per-risk table incl. where the 60-micro cap binds.
Run: python3 reopen_opt.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402

COST = 1.5                                                   # NQ effective cost in index points
SLS   = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0)
TPRS  = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
USD_PT_MICRO = 2.0                                           # MNQ $/pt
CAP_MICROS = 60


def run(nas, F, stop, tp_r, cost):
    spec = ExitSpec(tp_R=tp_r, be_R=0.0, trail_R=0.0, max_bars=600)
    orders = [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=stop, spec=spec,
                   eod_bar=int(r.eod), day=r.day, tag="rev")
              for _, r in F.iterrows() if r.cdir != 0]
    return engine.simulate(nas, orders, cost_pts=cost)


def main():
    nas = S.prep(data.load())
    F = build_days(nas)
    ad = np.array(sorted(F["day"].unique())); cut = ad[int(len(ad)*0.7)]
    print(f"cand_rev geometry sweep — {len(F)} nights, cost {COST}pt (NQ), eod 09:55\n")

    print("TRAIN expR grid (rows=SL pts, cols=TP as R multiple):")
    print("        " + "".join(f"{t:>8.1f}R" for t in TPRS))
    best = (-9, None)
    cache = {}
    for s in SLS:
        row = f"  SL{s:3.0f} "
        for t in TPRS:
            tr = run(nas, F, s, t, COST); cache[(s, t)] = tr
            g = tr[tr["day"] <= cut]
            e = g["R"].mean()
            row += f"{e:+8.3f} "
            if e > best[0]: best = (e, (s, t))
        print(row)
    (s, t) = best[1]
    tr = cache[(s, t)]
    g = tr[tr["day"] <= cut]; gte = tr[tr["day"] > cut]
    etr = engine.edge_stats(g); ete = engine.edge_stats(gte)
    print(f"\nTRAIN-BEST: SL {s:.0f}pt / TP {s*t:.1f}pt ({t}R)")
    print(f"  train: n={etr['n']} WR {etr['wr']*100:.1f}% expR {etr['expR']:+.3f}")
    print(f"  TEST : n={ete['n']} WR {ete['wr']*100:.1f}% expR {ete['expR']:+.3f}")
    # user's baseline for reference
    trb = cache[(25.0, 1.5)]
    gb = trb[trb["day"] <= cut]; gbe = trb[trb["day"] > cut]
    print(f"  (baseline 25/1.5R: train {gb['R'].mean():+.3f} | test {gbe['R'].mean():+.3f})")

    # fold stability of the winner
    trs = tr.sort_values("entry_dt").reset_index(drop=True); q = len(trs)//4
    print("  folds:", "  ".join(
        f"{trs.iloc[i*q:(i+1)*q if i<3 else len(trs)]['R'].mean():+.3f}" for i in range(4)))
    # cost sensitivity of the winner
    for cc in (1.0, 2.0):
        tc = run(nas, F, s, t, cc)
        print(f"  at {cc:.0f}pt cost: pooled expR {tc['R'].mean():+.3f}  WR {(tc['R']>0).mean()*100:.1f}%")

    # ---- contracts on a 50k (MNQ $2/pt, cap 60 micros) ----
    print(f"\nCONTRACTS on 50k (MNQ $2/pt, cap {CAP_MICROS} micros = 6 minis) at SL {s:.0f}pt:")
    print(f"  {'risk $':>8} {'risk %':>7} {'micros':>7} {'capped?':>8}")
    for usd in (100, 150, 250, 375, 500, 750):
        mic = usd / (s * USD_PT_MICRO)
        capped = mic > CAP_MICROS
        print(f"  {usd:>8} {usd/50000*100:6.2f}% {min(mic, CAP_MICROS):7.1f} {'YES' if capped else 'no':>8}")
    smin = 500 / (CAP_MICROS * USD_PT_MICRO)
    print(f"  (cap math: at {CAP_MICROS} micros, SL pts x $2 x 60 = max risk ${CAP_MICROS*USD_PT_MICRO*s:.0f}; "
          f"cap binds for $500 risk only when SL < {smin:.1f}pt)")


if __name__ == "__main__":
    main()
