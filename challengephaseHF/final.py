"""
challengephaseHF/final.py — the honest wrap-up:
  1. per-strategy edge (WR, RR, /day, expR) with train/test split
  2. correlation matrix of daily returns (is the MR core actually diversified?)
  3. portfolio 20-day pass Monte-Carlo (does stacking them pass?)
  4. head-to-head vs a normal HIGHER-RR baseline (live 4R combo) on monthly pass
Run: python3 final.py
"""
import os, sys
import numpy as np, pandas as pd
import hf_strats as HF
from hf_strats import prep_ind
import data, strategies as S, engine, ftmo
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
if V3 not in sys.path: sys.path.insert(0, V3)
from search import build_days      # noqa: E402
import warnings; warnings.filterwarnings("ignore")

df = S.prep(data.load()); IND = prep_ind(df); ad = np.array(sorted(df["date"].unique()))
NAMES = ["mr_z", "revN", "rsi2", "bbfade", "mim", "gaprev", "orfade"]
MR = {"mr_z", "revN", "rsi2", "bbfade"}
COST = 2.0


def orders_of(nm):
    fn = HF.REGISTRY[nm]
    return fn(df, IND) if nm in MR else fn(df)


def split(a, frac=0.70):
    cut = a[int(len(a)*frac)]; return a[a <= cut], a[a > cut]


def mc_pass(trades, ad_uni, deadline=20, risks=(0.0025, 0.005, 0.0075, 0.01), n=30000):
    best = (-1, None, None)
    for r in risks:
        d = build_days(trades[trades["day"].isin(set(ad_uni))] if len(trades) else trades, ad_uni, 0.0)
        m = ftmo.run_mc(d, r, deadline, n_paths=n, seed=11, block=5)
        if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
    return best


trades = {nm: engine.simulate(df, orders_of(nm), cost_pts=COST) for nm in NAMES}

print("=" * 84)
print("PER-STRATEGY EDGE (all data)   [target profile = high WR, RR<1, high freq]")
print("=" * 84)
print(f"  {'strat':8} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5}   verdict")
day_R = {}
for nm in NAMES:
    tr = trades[nm]; es = engine.edge_stats(tr)
    d = build_days(tr, ad, 0.0); day_R[nm] = np.asarray(d["day_R"], float)
    verdict = "POSITIVE edge" if es["expR"] > 0 else "net-negative (unusable)"
    print(f"  {nm:8} {es['n']/df['date'].nunique():5.1f} {es['wr']*100:5.1f}% {es['expR']:+.3f} {es['pf']:5.2f}   {verdict}")

print("\n" + "=" * 84)
print("CORRELATION of daily returns (is the low-RR core actually uncorrelated?)")
print("=" * 84)
DR = pd.DataFrame(day_R, index=ad)
corr = DR.corr()
print("      " + "".join(f"{n[:6]:>7}" for n in NAMES))
for n in NAMES:
    print(f"  {n[:6]:6}" + "".join(f"{corr.loc[n,m]:7.2f}" for m in NAMES))

print("\n" + "=" * 84)
print("PORTFOLIO 20-day PASS — stack the low-RR core (mr_z+revN+rsi2+bbfade) + decorrelators")
print("=" * 84)
tr_d, te_d = split(ad)
port = pd.concat([trades[nm] for nm in NAMES], ignore_index=True)
for lbl, dd in [("all", ad), ("test(OOS)", te_d)]:
    p, r, m = mc_pass(port, dd)
    print(f"  low-RR portfolio [{lbl:9}]: best risk {r*100:.2f}%  MONTHLY pass {p*100:4.1f}%  "
          f"blow {m['blow_rate']*100:4.1f}%  timeout {m['timeout_rate']*100:4.1f}%")

print("\n" + "=" * 84)
print("BASELINE — normal HIGHER-RR combo (live 4R: ORB 50 4R + VWpull 40 4R)")
print("=" * 84)
base = engine.simulate(df, S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, vol_filter=True)
                       + S.vwap_pullback(df, stop_pts=40, tp_R=4.0), cost_pts=COST)
esb = engine.edge_stats(base)
print(f"  edge: WR {esb['wr']*100:.1f}%  RR~4  expR {esb['expR']:+.3f}  PF {esb['pf']:.2f}")
for lbl, dd in [("all", ad), ("test(OOS)", te_d)]:
    p, r, m = mc_pass(base, dd)
    md = m["med_days_to_pass"]
    print(f"  higher-RR baseline [{lbl:9}]: best risk {r*100:.2f}%  MONTHLY pass {p*100:4.1f}%  "
          f"blow {m['blow_rate']*100:4.1f}%  median {md if md==md else 0:.0f}d")

print("\n" + "=" * 84)
print("VERDICT: does low-RR/high-WR/high-freq beat the higher-RR baseline on monthly pass?")
print("=" * 84)
