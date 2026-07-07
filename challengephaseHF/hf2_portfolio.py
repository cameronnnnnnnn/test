"""
challengephaseHF/hf2_portfolio.py — the corrected direction. The variance-play showed the
winning structure is HIGH-RR / LOW-frequency, and the way to raise pass rate is to stack
UNCORRELATED such setups (each ~1 trade/day) so added frequency does not concentrate
daily-cap risk. Build a battery across different sessions + mechanisms, measure daily-return
correlation, greedily pick a low-correlation set, and Monte-Carlo the 20-day pass vs the
v3 3-leg winner. Run: python3 hf2_portfolio.py
"""
import os, sys
import numpy as np, pandas as pd
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import hf_strats as HF                               # noqa: E402
import warnings; warnings.filterwarnings("ignore")

df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique())); COST = 2.0
def split(a, f=0.70): c = a[int(len(a)*f)]; return a[a <= c], a[a > c]

# battery: high-RR, ~1/day, spread across sessions + mechanisms
SET = {
 "US_ORB1630":  S.orb(df, open_min=16*60+30, or_min=30, stop_pts=60, tp_R=4.0, be_R=1.0, vol_filter=True),
 "US_ORB1600":  S.orb(df, open_min=16*60,    or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True),
 "EU_ORB1100":  S.orb(df, open_min=11*60,    or_min=30, stop_pts=50, tp_R=4.0, be_R=1.0, vol_filter=True),
 "ASIA_ORB0300":S.orb(df, open_min=3*60,     or_min=30, stop_pts=40, tp_R=4.0, be_R=1.0, vol_filter=True),
 "VWPULL6R":    S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0),
 "PDHL":        S.pdh_pdl(df, stop_pts=60, trail_R=3.0),
 "IB60":        S.ib_break(df, ib_min=60, stop_pts=60, trail_R=3.0),
 "DRIVE":       S.open_drive(df, stop_pts=50, trail_R=3.0),
 "GAPREV3R":    HF.gaprev(df, gap_pts=15, stop_pts=50, tp_R=3.0),
 "MIM2R":       HF.mim(df, stop_pts=50, tp_R=2.0, thresh_pts=8.0),
}

trades = {}; dayR = {}
print("="*78); print("HIGH-RR / LOW-FREQ BATTERY — edge per setup"); print("="*78)
print(f"  {'setup':13} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5}")
for nm, o in SET.items():
    tr = engine.simulate(df, o, COST); trades[nm] = tr
    d = build_days(tr, ad, 0.0); dayR[nm] = np.asarray(d["day_R"], float)
    es = engine.edge_stats(tr) if len(tr) else dict(n=0, wr=0, expR=0, pf=0)
    print(f"  {nm:13} {es['n']/df['date'].nunique():5.2f} {es['wr']*100:5.1f}% {es['expR']:+.3f} {es.get('pf',0):5.2f}")

DR = pd.DataFrame(dayR, index=ad); names = list(SET)
print("\n" + "="*78); print("DAILY-RETURN CORRELATION (lower = better diversification)"); print("="*78)
corr = DR.corr()
print("        " + "".join(f"{n[:6]:>7}" for n in names))
for n in names:
    print(f"  {n[:7]:7}" + "".join(f"{corr.loc[n,m]:7.2f}" for m in names))

def mc(trade_list, ad_uni, breaker=2.0, deadline=20, risks=(0.005,0.0075,0.01,0.0125,0.015)):
    tr = pd.concat(trade_list, ignore_index=True) if len(trade_list) > 1 else trade_list[0]
    best = (-1, None, None)
    for r in risks:
        d = build_days(tr[tr["day"].isin(set(ad_uni))] if len(tr) else tr, ad_uni, breaker)
        m = ftmo.run_mc(d, r, deadline, n_paths=30000, seed=11, block=5)
        if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
    return best

tr_d, te_d = split(ad)
def report(tag, combo):
    tl = [trades[c] for c in combo]
    _, r, _ = mc(tl, tr_d)                     # pick risk on train
    d = build_days(pd.concat(tl, ignore_index=True), te_d, 2.0)
    mte = ftmo.run_mc(d, r, 20, n_paths=30000, seed=11, block=5)
    md = mte["med_days_to_pass"]
    print(f"  {tag:44} r*={r*100:.2f}% TESTpass={mte['pass_rate']*100:4.1f}% "
          f"blow={mte['blow_rate']*100:4.1f}% med={md if md==md else 0:.0f}d")

print("\n" + "="*78)
print("PORTFOLIO 20-day pass (TEST/OOS, -2R breaker, risk picked on train)")
print("="*78)
report("v3 winner (EU+US1630+VWPULL)", ["EU_ORB1100","US_ORB1630","VWPULL6R"])
report("+ PDHL (4 legs)", ["EU_ORB1100","US_ORB1630","VWPULL6R","PDHL"])
report("+ PDHL + GAPREV (5 legs)", ["EU_ORB1100","US_ORB1630","VWPULL6R","PDHL","GAPREV3R"])
report("6 legs +ASIA", ["EU_ORB1100","US_ORB1630","VWPULL6R","PDHL","GAPREV3R","ASIA_ORB0300"])
report("7 legs +IB60", ["EU_ORB1100","US_ORB1630","VWPULL6R","PDHL","GAPREV3R","ASIA_ORB0300","IB60"])
print("-"*78)
print("0EV-optimal single-setup ceiling was ~38.6%; v3 3-leg ~47%. Does adding uncorrelated")
print("high-RR legs push higher, or does it plateau / hurt (extra daily-cap exposure)?")
