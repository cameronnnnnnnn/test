"""
challengephaseHF/tom_probe.py — the turn-of-month long showed a strong, train/test-stable
edge on NAS100 (+0.21 expR, PF 1.47). Turn-of-month drift is a documented equity anomaly
(month-end pension/index inflows), so it is a priori credible — but it is LONG-ONLY, so the
number could just be NAS100's uptrend beta. Stress it so beta is separated from seasonal:

  1 per-YEAR — must be positive even in 2022 (NAS bear year). If tom is +EV in a down year,
               it is a real calendar effect, not beta.
  2 vs BASELINE — compare tom-day expR to a naive "long every day open->close" over the same
               period. tom must clearly beat the all-days long, or it is just being long.
  3 window robustness — last_n x first_n grid (edge should be a plateau, peak near the turn).

Run: python3 tom_probe.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine               # noqa: E402
from engine import ExitSpec                          # noqa: E402
from creative import tom_long                         # noqa: E402

OPEN = 16 * 60 + 30; SESS_END = 22 * 60 + 55


def daily_long(df, stop_pts=60, trail_R=3.0, be_R=1.0):
    """Baseline: go long at the US open EVERY trading day, same exit as tom_long."""
    h = df["high"].values; tod = df["tod"].values
    orders = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]; sess = gi[(t >= 16*60) & (t <= SESS_END)]
        if len(sess) < 10:
            continue
        spec = ExitSpec(tp_R=0.0, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        orders.append(dict(entry_bar=sess[0], dir=1, stop_pts=stop_pts, spec=spec,
                           eod_bar=sess[-1], day=day, tag="dlong"))
    return orders


def main():
    df = S.prep(data.load()); ndays = df["date"].nunique()
    print(f"NAS100 turn-of-month long — {ndays} days\n")

    # 1) per year, tom vs all-days-long
    tr = engine.simulate(df, tom_long(df), cost_pts=2.0)
    bl = engine.simulate(df, daily_long(df), cost_pts=2.0)
    tr["yr"] = pd.to_datetime(tr["day"]).dt.year
    bl["yr"] = pd.to_datetime(bl["day"]).dt.year
    print("1) PER-YEAR  (tom = turn-of-month long;  base = long every day, same exit)")
    print(f"   {'year':6}{'tom_n':>6}{'tom_WR':>8}{'tom_expR':>10}{'tom_PF':>8}   | {'base_expR':>10}{'edge Δ':>9}")
    for yr in sorted(tr["yr"].unique()):
        g = tr[tr["yr"] == yr]; b = bl[bl["yr"] == yr]
        et = engine.edge_stats(g); eb = engine.edge_stats(b)
        print(f"   {yr:<6}{et['n']:>6}{et['wr']*100:>7.1f}%{et['expR']:>+10.3f}{et['pf']:>8.2f}   | "
              f"{eb['expR']:>+10.3f}{et['expR']-eb['expR']:>+9.3f}")
    ET = engine.edge_stats(tr); EB = engine.edge_stats(bl)
    print(f"   {'ALL':<6}{ET['n']:>6}{ET['wr']*100:>7.1f}%{ET['expR']:>+10.3f}{ET['pf']:>8.2f}   | "
          f"{EB['expR']:>+10.3f}{ET['expR']-EB['expR']:>+9.3f}")
    print(f"   -> tom beats all-days-long by {ET['expR']-EB['expR']:+.3f} expR "
          f"({'REAL seasonal, not beta' if ET['expR']-EB['expR'] > 0.03 else 'mostly just beta'})")

    # 3) window robustness
    print("\n3) WINDOW ROBUSTNESS  (expR by last_n x first_n; edge should peak near the turn)")
    print("      first_n->" + "".join(f"{fn:>9d}" for fn in (1, 2, 3, 4)))
    for ln in (0, 1, 2):
        row = f"   last {ln} "
        for fn in (1, 2, 3, 4):
            if ln == 0 and fn == 0:
                row += f"{'—':>9}"; continue
            t = engine.simulate(df, tom_long(df, last_n=ln, first_n=fn), cost_pts=2.0)
            e = engine.edge_stats(t)["expR"] if len(t) else float("nan")
            row += f"{e:>+9.3f}"
        print(row)
    print("\n(If tom is +EV in 2022's bear tape and clearly beats all-days-long, the turn-of-month")
    print(" drift is a real seasonal worth stacking. If it collapses in 2022, it is just NAS beta.)")


if __name__ == "__main__":
    main()
