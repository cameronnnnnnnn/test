"""
regimeswitch/sweep_refine.py — the one real edge the regime work found is SWEEP-RECLAIM on
directional (low first-hour-chop) opens: +0.21 train / +0.24 test expR, ~2.7x 52p's edge. But
it fires only ~0.33x/day, so stacking it barely moves the pass rate. The only way it matters is
MORE FREQUENCY at the SAME edge. This builds a multi-level sweep (prior-day H/L, pre-open H/L,
opening-range H/L — sweep the level then reclaim -> reversal), gated to trend-opens (cut tuned
on TRAIN), and checks: does frequency go up while the OOS edge holds? Then stacks on 52p.
Run: python3 sweep_refine.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
from engine import ExitSpec                           # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402
import indic                                          # noqa: E402

COST = 2.0; BREAKER = 2.0; DEADLINE = 20; NP = 40000
OPEN = 16 * 60 + 30; SESS_END = 22 * 60 + 55
RISKS = (0.005, 0.0075, 0.01, 0.0125)


def multi_sweep(df, stop_pts=45, trail_R=2.5, be_R=1.0, poke=4, hold=8, react_by=20*60):
    """Sweep + reclaim of several reference levels -> reversal. Levels (all known before the
    session or from completed windows): prior-day H/L, pre-open (00:00-16:30) H/L, first 30-min
    opening-range H/L. One trade per level per day (first reclaim), so more shots than the single
    pre-open sweep. No look-ahead: a level's reclaim is only traded after it forms."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    groups = list(df.groupby("date").indices.items())
    dayHL = {day: (h[gi].max(), l[gi].min()) for day, gi in groups}
    orders = []
    for k in range(1, len(groups)):
        day, gi = groups[k]
        t = tod[gi]
        pdh, pdl = dayHL[groups[k-1][0]]
        pre = gi[(t >= 0) & (t < OPEN)]
        orb = gi[(t >= OPEN) & (t < OPEN + 30)]
        sess = gi[(t >= OPEN) & (t <= SESS_END)]
        if len(pre) < 30 or len(sess) < 40:
            continue
        preH, preL = h[pre].max(), l[pre].min()
        eod = sess[-1]
        levels = [("pdh", pdh, pdl)]                       # (name, hi, lo)
        levels.append(("pre", preH, preL))
        if len(orb) >= 10:
            levels.append(("orb", h[orb].max(), l[orb].min()))
        spec = ExitSpec(tp_R=0.0, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for nm, hi, lo in levels:
            start_bar = orb[-1] if (nm == "orb" and len(orb)) else sess[0]
            swept = 0; swb = -1
            for j, b in enumerate(sess):
                if b < start_bar or tod[b] > react_by:
                    continue
                if swept == 0:
                    if h[b] >= hi + poke: swept, swb = 1, j
                    elif l[b] <= lo - poke: swept, swb = -1, j
                    continue
                if j - swb > hold:
                    swept = 0; continue
                if swept == 1 and c[b] < hi:               # reclaim below swept high -> short
                    orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                       eod_bar=eod, day=day, tag="msweep")); break
                if swept == -1 and c[b] > lo:
                    orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                       eod_bar=eod, day=day, tag="msweep")); break
    return orders


def split(ad, frac=0.7):
    cut = ad[int(len(ad) * frac)]; return ad[ad <= cut], ad[ad > cut]


def mc(ds, r): return ftmo.run_mc(ds, r, DEADLINE, n_paths=NP, seed=11, block=5)
def best_risk(ds): return max(RISKS, key=lambda r: mc(ds, r)["pass_rate"])


def stack_eval(parts, ad, dtr, dte, tag):
    tr = pd.concat(parts, ignore_index=True)
    dtr_s = build_days(tr[tr["day"].isin(set(dtr))], dtr, BREAKER)
    dte_s = build_days(tr[tr["day"].isin(set(dte))], dte, BREAKER)
    r = best_risk(dtr_s)
    folds = np.array_split(ad, 4); fps = []
    for fo in folds:
        tro = np.concatenate([x for x in folds if x[0] != fo[0]])
        rf = best_risk(build_days(tr[tr["day"].isin(set(tro))], tro, BREAKER))
        fps.append(mc(build_days(tr[tr["day"].isin(set(fo))], fo, BREAKER), rf)["pass_rate"])
    print(f"  {tag:34} r*={r*100:4.2f}%  TE {mc(dte_s, r)['pass_rate']*100:4.1f}%  "
          f"blowTE {mc(dte_s, r)['blow_rate']*100:4.1f}%  foldMean {np.mean(fps)*100:4.1f}% "
          f"foldWorst {np.min(fps)*100:4.1f}%")


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    dtr, dte = split(ad)
    ic = indic.intraday_chop(df, start_min=16*60, win_min=60)
    cut = pd.Series({d: ic.get(d, np.nan) for d in dtr}).dropna().quantile(0.40)
    trendopen = [d for d in ad if ic.get(d, np.nan) is not None and ic.get(d, np.nan) < cut]
    print(f"trend-open cut (train): 1h chop < {cut:.1f}   -> {len(trendopen)} trend-open days\n")

    swp = engine.simulate(df, multi_sweep(df), cost_pts=COST)
    swp_g = swp[swp["day"].isin(set(trendopen))]
    momo = engine.simulate(df, CP52.build(df), cost_pts=COST)

    def e(tr, days):
        g = tr[tr["day"].isin(set(days))]; return engine.edge_stats(g) if len(g) else dict(n=0, expR=0, wr=0)
    ndays = len(ad); nte = len(dte); ntr = len(dtr)
    print("multi-level sweep, gated to trend-opens — frequency + OOS edge:")
    for nm, tr in [("all opens (ungated)", swp), ("trend-opens only (gated)", swp_g)]:
        a = e(tr, ad); at, ae = e(tr, dtr), e(tr, dte)
        print(f"  {nm:26} {a['n']/ndays:.2f}/day  expR ALL {a['expR']:+.3f}  "
              f"TRAIN {at['expR']:+.3f}(n{at['n']})  TEST {ae['expR']:+.3f}(n{ae['n']})")

    print("\n" + "=" * 84)
    print("STACKED 20-day FTMO pass with the higher-frequency gated sweep  [risk on train]")
    print("=" * 84)
    stack_eval([momo], ad, dtr, dte, "52p baseline")
    stack_eval([momo, swp_g], ad, dtr, dte, "52p + multi-sweep|trendopen")
    print("-" * 84)
    print("Win only if the richer sweep KEPT its +OOS edge at higher /day AND lifted TE/foldWorst.")


if __name__ == "__main__":
    main()
