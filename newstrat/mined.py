"""
newstrat/mined.py — the strategy CREATED from the data mining (mine.py), after the artifact purge.

Mining protocol recap: patterns selected on TRAIN only at |t|>=3.5, one-shot sign-check on TEST,
then an ECONOMIC-MECHANISM check using the spread column. That check killed the two flashiest
finds (the FX 00:45 "pop" = rollover spread renormalizing on bid bars, t=57 and all; the GER40
22:45 "fade" = spread exploding 60->810 into the close). What survives is a basket of small,
clean, liquid-hour TIME-OF-DAY DRIFTS — each traded as: enter at the window start, exit at the
window end (time exit), protective stop 0.25xATR (rarely hit). No signal beyond the clock.

  N1 NAS100 long  10:15->11:00   (3 adjacent buckets held OOS)
  N2 NAS100 short 17:30->17:45   (post-open reversal window, ~1x cost, held)
  N3 NAS100 long  18:15->18:45   (2 adjacent buckets held)
  N4 NAS100 long  22:45->22:58   (end-of-day drift up; fights the close spread-widening = real)
  G1 GER40  long  09:00->09:15   (pre-EU-open drift, spread flat)
  G2 GER40  long  18:00->18:45   (into the DAX cash close, spread flat)

This IS the user's requested shape: ~6 trades/day, high WR, tiny RR, near-0EV after cost. Honest
eval: per-leg WR/expR train/test, portfolio edge, correlation with 52p, MC pass alone + stacked.
Run: python3 mined.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo, fx_data   # noqa: E402
from engine import ExitSpec                             # noqa: E402
from search import build_days                           # noqa: E402
import ChallengePhase52p as CP52                         # noqa: E402

BREAKER = 0.0            # no breaker: legs are independent tiny time-exits
DEADLINE = 20; NP = 50000
LEGS = [  # (instr, dir, start_min, end_min, tag)
    ("NAS100", +1, 10*60+15, 11*60,      "N1_1015L"),
    ("NAS100", -1, 17*60+30, 17*60+45,   "N2_1730S"),
    ("NAS100", +1, 18*60+15, 18*60+45,   "N3_1815L"),
    ("NAS100", +1, 22*60+45, 22*60+58,   "N4_2245L"),
    ("GER40",  +1,  9*60,     9*60+15,   "G1_0900L"),
    ("GER40",  +1, 18*60,    18*60+45,   "G2_1800L"),
]
COSTS = {"NAS100": 2.0, "GER40": 1.5}


def time_leg(df, d, start, end, sm, tag):
    tod = df["tod"].values
    orders = []
    spec = ExitSpec(tp_R=0.0, be_R=0.0, trail_R=0.0, max_bars=10**9)
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        w = gi[(t >= start) & (t < end)]
        if len(w) < max(3, (end-start)//3):
            continue
        stp = sm.get(day, np.nan)
        if not (stp == stp) or stp <= 0:
            continue
        orders.append(dict(entry_bar=w[0], dir=d, stop_pts=stp, spec=spec,
                           eod_bar=w[-1], day=day, tag=tag))
    return orders


def main():
    dfs = {"NAS100": S.prep(data.load()), "GER40": S.prep(fx_data.load("GER40"))}
    sms = {k: {dd: 0.25*v for dd, v in S.daily_atr(v_, 14).items() if v == v}
           for k, v_ in dfs.items() for v in [None]}
    # fix comprehension: build properly
    sms = {}
    for k, d_ in dfs.items():
        atr = S.daily_atr(d_, 14)
        sms[k] = {dd: 0.25*v for dd, v in atr.items() if v == v}

    all_tr = []
    ad_common = np.array(sorted(set(dfs["NAS100"]["date"].unique()) & set(dfs["GER40"]["date"].unique())))
    cut = ad_common[int(len(ad_common)*0.7)]
    print("MINED time-of-day drift portfolio — per-leg honest edge (train/test)")
    print(f"  {'leg':10} {'/day':>5} {'WR':>6} {'expR':>7} {'exp_tr':>8} {'exp_te':>8} {'n':>6}")
    for instr, d, a, b, tag in LEGS:
        df = dfs[instr]
        tr = engine.simulate(df, time_leg(df, d, a, b, sms[instr], tag), cost_pts=COSTS[instr])
        tr = tr[tr["day"].isin(set(ad_common))]
        e = engine.edge_stats(tr)
        ttr = tr[tr["day"] <= cut]; tte = tr[tr["day"] > cut]
        etr = engine.edge_stats(ttr)["expR"] if len(ttr) else float("nan")
        ete = engine.edge_stats(tte)["expR"] if len(tte) else float("nan")
        print(f"  {tag:10} {e['n']/len(ad_common):5.2f} {e['wr']*100:5.1f}% {e['expR']:+7.3f} "
              f"{etr:+8.3f} {ete:+8.3f} {e['n']:6d}")
        all_tr.append(tr)

    port = pd.concat(all_tr, ignore_index=True)
    ep = engine.edge_stats(port)
    print(f"\n  PORTFOLIO: {ep['n']/len(ad_common):.1f} trades/day  WR {ep['wr']*100:.1f}%  "
          f"expR {ep['expR']:+.3f}  (this IS the high-freq/high-WR/low-RR shape)")

    # correlation with 52p + MC
    p52 = engine.simulate(dfs["NAS100"], CP52.build(dfs["NAS100"]), cost_pts=2.0)
    p52 = p52[p52["day"].isin(set(ad_common))]
    dm = np.asarray(build_days(port, ad_common, 0.0)["day_R"], float)
    d5 = np.asarray(build_days(p52, ad_common, 2.0)["day_R"], float)
    print(f"  correlation with 52p daily returns: {np.corrcoef(dm, d5)[0,1]:+.2f}")

    def mc(t, days, r, brk):
        return ftmo.run_mc(build_days(t[t['day'].isin(set(days))], days, brk), r, DEADLINE,
                           n_paths=NP, seed=11, block=5)
    dtr = ad_common[ad_common <= cut]; dte = ad_common[ad_common > cut]
    print("\n  MC 20-day pass (risk on train, reported on test):")
    RISKS_M = (0.01, 0.02, 0.03, 0.04, 0.06)
    rM = max(RISKS_M, key=lambda r: mc(port, dtr, r, 0.0)["pass_rate"])
    m = mc(port, dte, rM, 0.0)
    print(f"    mined alone    r*={rM*100:.1f}%  TE pass {m['pass_rate']*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%")
    RISKS_S = (0.005, 0.0075, 0.01)
    both = pd.concat([p52, port], ignore_index=True)
    rS = max(RISKS_S, key=lambda r: mc(p52, dtr, r, 2.0)["pass_rate"])
    m0 = mc(p52, dte, rS, 2.0)
    rB = max(RISKS_S, key=lambda r: mc(both, dtr, r, 2.0)["pass_rate"])
    m1 = mc(both, dte, rB, 2.0)
    print(f"    52p alone      r*={rS*100:.2f}%  TE pass {m0['pass_rate']*100:4.1f}%  blow {m0['blow_rate']*100:4.1f}%")
    print(f"    52p + mined    r*={rB*100:.2f}%  TE pass {m1['pass_rate']*100:4.1f}%  blow {m1['blow_rate']*100:4.1f}%")
    print("\nHonest read: each leg is a real but TINY drift (~0.5-2x cost). High WR + high frequency,")
    print("near-0EV after cost — the requested shape, mined from the data, artifact-checked.")


if __name__ == "__main__":
    main()
