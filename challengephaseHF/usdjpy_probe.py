"""
challengephaseHF/usdjpy_probe.py — the Asian-range breakout flagged a STABLE positive
out-of-sample edge on USDJPY (Tokyo-session range, 00:00-08:00 server, break after 08:00).
That is the first forex setup in the project with real OOS edge, and it makes sense: 00-08
server = 22:00-06:00 GMT is the actual Tokyo session, JPY's home hours. Before trusting it
enough to stack on NAS100, stress it on four axes so an overfit knife-edge is exposed:

  1. window robustness   — is the edge a broad plateau or one lucky (range_start,break_start)?
  2. geometry robustness — stop fraction x TP/trail grid (edge should survive most cells)
  3. per-YEAR stability  — positive expR in most individual years, not one lucky year
  4. cost / direction    — survives 1x..2.5x spread, and is it long-only (carry) or both sides?

Run: python3 usdjpy_probe.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import strategies as S, engine, fx_data          # noqa: E402
from asian_break import asian_break, fx_cost      # noqa: E402


def dir_split(tr):
    lo = tr[tr["dir"] > 0]; sh = tr[tr["dir"] < 0]
    el = engine.edge_stats(lo) if len(lo) else dict(n=0, expR=0, wr=0)
    es = engine.edge_stats(sh) if len(sh) else dict(n=0, expR=0, wr=0)
    return el, es


def main():
    df = S.prep(fx_data.load("USDJPY"))
    base_cost = fx_cost(df)
    atr = S.daily_atr(df, n=14)
    ndays = df["date"].nunique()
    print(f"USDJPY  {ndays} days  base round-turn cost {base_cost:.4f} ({base_cost/0.01:.1f} pips)\n")

    # ---- 1) window robustness (range_start x break_start), hard 3R, 0.30 ATR stop ----
    sm = {d: 0.30 * v for d, v in atr.items() if v == v}
    print("1) WINDOW ROBUSTNESS  (expR, hard 3R, 0.30-ATR stop) — edge should be a plateau")
    print("     break->  " + "".join(f"{bs//60:>8d}h" for bs in (7*60, 8*60, 9*60, 10*60)))
    for rs in (0, 1*60, 2*60, 22*60):   # 22:00 = start Asian from prior-evening rollover
        row = f"  rs {rs//60:02d}h "
        for bs in (7*60, 8*60, 9*60, 10*60):
            if rs >= bs and rs < 12*60:
                row += f"{'—':>9}"; continue
            tr = engine.simulate(df, asian_break(df, rs % (24*60), bs, sm, tp_R=3.0), cost_pts=base_cost)
            e = engine.edge_stats(tr)["expR"] if len(tr) else float("nan")
            row += f"{e:+9.3f}"
        print(row)

    # ---- 2) geometry robustness: stop fraction x exit ----
    print("\n2) GEOMETRY ROBUSTNESS  (range 00-08, expR) — edge should survive most cells")
    print(f"     {'exit':12}" + "".join(f"{f:>9.2f}A" for f in (0.20, 0.30, 0.40, 0.50)))
    for name, kw in [("hard 2R", dict(tp_R=2.0)), ("hard 3R", dict(tp_R=3.0)),
                     ("hard 4R", dict(tp_R=4.0)), ("trail 3R", dict(tp_R=0.0, trail_R=3.0, be_R=1.0))]:
        row = f"     {name:12}"
        for frac in (0.20, 0.30, 0.40, 0.50):
            smf = {d: frac * v for d, v in atr.items() if v == v}
            tr = engine.simulate(df, asian_break(df, 0, 8*60, smf, **kw), cost_pts=base_cost)
            e = engine.edge_stats(tr)["expR"] if len(tr) else float("nan")
            row += f"{e:+10.3f}"
        print(row)

    # ---- 3) per-year stability (range 00-08, hard 3R, 0.30 ATR) ----
    print("\n3) PER-YEAR STABILITY  (range 00-08, hard 3R, 0.30-ATR stop)")
    tr = engine.simulate(df, asian_break(df, 0, 8*60, sm, tp_R=3.0), cost_pts=base_cost)
    tr["yr"] = pd.to_datetime(tr["day"]).dt.year
    print(f"     {'year':6}{'n':>5}{'/day?':>7}{'WR':>7}{'expR':>8}{'PF':>6}")
    for yr, g in tr.groupby("yr"):
        e = engine.edge_stats(g)
        ndy = df[df["date"].dt.year == yr]["date"].nunique()
        print(f"     {yr:<6}{e['n']:>5}{e['n']/max(ndy,1):>7.2f}{e['wr']*100:>6.1f}%{e['expR']:>+8.3f}{e['pf']:>6.2f}")

    # ---- 4) cost sensitivity + direction breakdown ----
    print("\n4) COST SENSITIVITY  (range 00-08, hard 3R, 0.30-ATR stop)")
    print(f"     {'costx':7}{'cost':>9}{'expR':>9}{'PF':>7}")
    for cx in (1.0, 1.5, 2.0, 2.5):
        tr = engine.simulate(df, asian_break(df, 0, 8*60, sm, tp_R=3.0), cost_pts=base_cost * cx)
        e = engine.edge_stats(tr)
        print(f"     {cx:<7.1f}{base_cost*cx:>9.4f}{e['expR']:>+9.3f}{e['pf']:>7.2f}")
    tr = engine.simulate(df, asian_break(df, 0, 8*60, sm, tp_R=3.0), cost_pts=base_cost)
    el, es = dir_split(tr)
    print(f"\n   DIRECTION:  long  n={el['n']:4d} WR {el['wr']*100:4.1f}% expR {el['expR']:+.3f}")
    print(f"               short n={es['n']:4d} WR {es['wr']*100:4.1f}% expR {es['expR']:+.3f}")
    print("\n(If the edge is a plateau across windows/geometry, positive in most years, survives")
    print(" ~2x cost, and is present both directions, it is a real Tokyo-session momentum edge.)")


if __name__ == "__main__":
    main()
