"""
newstrat/sweep_all.py — iteration 5 (last untested angle): the sweep-reclaim-on-trend-open edge
was the best OOS find on NAS100 (+0.24). Does it exist on the forex pairs too? If it does, that's
fresh decorrelated frequency from a different mechanism (liquidity, not momentum) — the honest
path to higher frequency + higher pass. Generalized sweep (prior-day H/L + pre-session H/L, sweep
then reclaim -> reversal), gated to trend-opens (first-hour choppiness low, cutoff tuned on TRAIN),
ATR-scaled stops, real cost. Reports /day + WR + expR train/test per instrument. Run: python3 sweep_all.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
RS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regimeswitch"))
for p in (V4, RS):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine                        # noqa: E402
from engine import ExitSpec                            # noqa: E402
import allinstr, indic                                 # noqa: E402

SESS = {"NAS100": 16*60+30, "EURUSD": 10*60, "GBPUSD": 10*60, "AUDUSD": 10*60, "USDJPY": 10*60}
SESS_END = 22*60+55


def sweep_gen(df, open_min, sm, atr_med, hold=8, react_by=4*60, trail_R=2.5, be_R=1.0):
    """Sweep prior-day or pre-session H/L then reclaim -> reversal. ATR-scaled stop, one per level/day."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    groups = list(df.groupby("date").indices.items())
    dayHL = {d: (h[gi].max(), l[gi].min()) for d, gi in groups}
    poke = 0.02 * atr_med
    orders = []
    for k in range(1, len(groups)):
        day, gi = groups[k]; t = tod[gi]
        pdh, pdl = dayHL[groups[k-1][0]]
        pre = gi[(t >= 0) & (t < open_min)]
        sess = gi[(t >= open_min) & (t <= SESS_END)]
        stp = sm.get(day, np.nan)
        if len(pre) < 20 or len(sess) < 30 or not (stp == stp) or stp <= 0:
            continue
        preH, preL = h[pre].max(), l[pre].min()
        eod = sess[-1]
        spec = ExitSpec(tp_R=0.0, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for nm, hi, lo in [("pd", pdh, pdl), ("pre", preH, preL)]:
            swept = 0; swb = -1
            for j, b in enumerate(sess):
                if tod[b] > open_min + react_by:
                    break
                if swept == 0:
                    if h[b] >= hi + poke: swept, swb = 1, j
                    elif l[b] <= lo - poke: swept, swb = -1, j
                    continue
                if j - swb > hold:
                    swept = 0; continue
                if swept == 1 and c[b] < hi:
                    orders.append(dict(entry_bar=b, dir=-1, stop_pts=stp, spec=spec, eod_bar=eod, day=day, tag="sw")); break
                if swept == -1 and c[b] > lo:
                    orders.append(dict(entry_bar=b, dir=1, stop_pts=stp, spec=spec, eod_bar=eod, day=day, tag="sw")); break
    return orders


def main():
    D = allinstr.load_all(verbose=False)
    print("SWEEP-RECLAIM across all instruments (trend-open gated) — does the NAS edge generalise?")
    print(f"  {'instr':8} {'/day':>5} {'WR':>6} {'expR_tr':>8} {'expR_te':>8} {'n':>5}  {'note':>10}")
    for x in allinstr.ALL:
        info = D[x]; df = info["df"]; sm = allinstr.stopmap(info, 0.20)
        ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
        dtr, dte = set(ad[ad <= cut]), set(ad[ad > cut])
        ic = indic.intraday_chop(df, start_min=SESS[x], win_min=60)
        cutoff = pd.Series({d: ic.get(d, np.nan) for d in sorted(dtr)}).dropna().quantile(0.40)
        trend_open = set(d for d in ad if ic.get(d, np.nan) is not None and ic.get(d, np.nan) < cutoff)
        tr = engine.simulate(df, sweep_gen(df, SESS[x], sm, info["atr_med"]), cost_pts=info["cost"])
        tr = tr[tr["day"].isin(trend_open)] if len(tr) else tr
        if not len(tr):
            print(f"  {x:8} no trades"); continue
        e = engine.edge_stats(tr)
        etr = engine.edge_stats(tr[tr["day"].isin(dtr)])["expR"] if len(tr[tr["day"].isin(dtr)]) else float("nan")
        ete = engine.edge_stats(tr[tr["day"].isin(dte)])["expR"] if len(tr[tr["day"].isin(dte)]) else float("nan")
        note = "  <-- holds" if (etr > 0.03 and ete > 0.03) else ""
        print(f"  {x:8} {e['n']/len(ad):5.2f} {e['wr']*100:5.1f}% {etr:+8.3f} {ete:+8.3f} {e['n']:>5}{note}")
    print("-"*70)
    print("Holds on an instrument only if BOTH expR halves are +. NAS100 should confirm the +0.24;")
    print("any forex pair that also holds = a genuinely new decorrelated leg to add frequency.")


if __name__ == "__main__":
    main()
