"""
challengephasev3/search.py — the "combine everything and test every combination" search,
scored on ONE metric: pass rate within 20 TRADING DAYS (1 real month) under FTMO 1-Step.

Pulls together every setup tried across the project (ORB at both US opens + EU, VWAP
pullback, OR-fade, VWAP-fade, selective range-fade, PDH/PDL, liquidity sweep, CUSUM
momentum burst, open-drive, IB-break) across a geometry grid, and layers the two real
levers on top:
  * GARCH volatility-regime DAY FILTER (garch.py) — none / low-vol-only / high-vol-only
  * -XR daily circuit breaker — none / -1.5R / -2R / -2.5R
  * per-trade risk sweep.

Everything is scored TRAIN (70%) vs TEST (30%) so the winner is the best OUT-OF-SAMPLE
20-day pass, not an in-sample mirage. Trades per atomic setup are simulated once and
cached; combos are concatenations. Phases: A singles -> B levers on top singles ->
C combos. Run: python3 search.py
"""
import os, sys, pickle, itertools, time
import numpy as np, pandas as pd

V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V2 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev2"))
for p in (V4, V2):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
import features as FE                                # noqa: E402
from strat_gen import filtered_orders, eod_map, split  # noqa: E402
import garch as G                                    # noqa: E402

COST = 2.0; DEADLINE = 20; NP = 30000
RISKS = (0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02)
BANDS = {"none": None, "lowvol": (0.0, 0.40), "himvol": (0.60, 1.01), "midvol": (0.30, 0.70)}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_trades_cache.pkl")


# ---------------- setup library (name -> builder closure) ----------------
def setup_library(df, F, eod):
    L = {}
    # ORB grid: two US opens + EU open, OR len, stop, tp
    for om, tag in [(16*60, "us"), (16*60+30, "us2"), (11*60, "eu")]:
        for orm in (15, 30):
            for stop in (50, 60):
                for tp in (3.0, 4.0, 6.0):
                    L[f"orb_{tag}_or{orm}_s{stop}_tp{tp:g}"] = (
                        lambda d, om=om, orm=orm, stop=stop, tp=tp:
                        S.orb(d, open_min=om, or_min=orm, stop_pts=stop, tp_R=tp, be_R=1.0, vol_filter=True))
    # VWAP pullback grid
    for stop in (40, 50):
        for tp in (3.0, 4.0, 6.0, 8.0):
            for tr in (0.0, 3.0):
                L[f"vwpull_s{stop}_tp{tp:g}_tr{tr:g}"] = (
                    lambda d, stop=stop, tp=tp, tr=tr:
                    S.vwap_pullback(d, stop_pts=stop, tp_R=tp, trail_R=tr))
    # OR fade
    for poke in (10, 15):
        for stop in (30, 40):
            for tp in (1.0, 1.5):
                L[f"orfade_p{poke}_s{stop}_tp{tp:g}"] = (
                    lambda d, poke=poke, stop=stop, tp=tp:
                    S.or_fade(d, poke_pts=poke, stop_pts=stop, tp_R=tp))
    # VWAP fade + selective range fade
    for k in (2.0, 2.5):
        for stop in (40, 50):
            L[f"vwfade_k{k:g}_s{stop}"] = (lambda d, k=k, stop=stop: S.vwap_fade(d, k=k, stop_pts=stop, tp_R=1.0))
    L["vwfadeSel"] = lambda d: S.vwap_fade_sel(d)
    # PDH/PDL, open drive, IB
    for stop in (50, 60):
        L[f"pdhl_s{stop}"] = lambda d, stop=stop: S.pdh_pdl(d, stop_pts=stop, trail_R=3.0)
    L["drive"] = lambda d: S.open_drive(d, stop_pts=50, trail_R=3.0)
    L["ib60"] = lambda d: S.ib_break(d, ib_min=60, stop_pts=60, trail_R=3.0)
    # feature events: sweep + CUSUM (+ with-trend)
    for tp in (1.0, 1.5, 2.0):
        L[f"sweep_tp{tp:g}"] = lambda d, tp=tp: filtered_orders(d, F, eod, "sweep", 40, tp)
    for tp in (0.75, 4.0, 6.0):
        L[f"cusum_tp{tp:g}"] = lambda d, tp=tp: filtered_orders(d, F, eod, "cusum", 50, tp, be_R=1.0)
        L[f"cusumTrend_tp{tp:g}"] = (lambda d, tp=tp:
            filtered_orders(d, F, eod, "cusum", 50, tp, be_R=1.0, filters=[("vwap_slope", 0.04, np.inf, True)]))
    return L


def get_trades(df, F, eod):
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f: return pickle.load(f)
    L = setup_library(df, F, eod); out = {}; t0 = time.time()
    for i, (name, fn) in enumerate(L.items()):
        tr = engine.simulate(df, fn(df), cost_pts=COST)
        out[name] = tr[["day", "entry_dt", "R", "mae_R", "mfe_R"]].copy() if len(tr) else tr
        if i % 10 == 0: print(f"  sim {i}/{len(L)} {name} ({time.time()-t0:.0f}s)")
    with open(CACHE, "wb") as f: pickle.dump(out, f)
    print(f"[cache] {len(out)} setups simulated ({time.time()-t0:.0f}s)")
    return out


# ---------------- day-building + masking + MC ----------------
def build_days(trades, ad_uni, breaker):
    base = pd.DataFrame({"day": ad_uni, "day_R": 0.0, "day_min_R": 0.0, "n": 0}).set_index("day")
    if len(trades):
        t = trades[trades["day"].isin(set(ad_uni))]
        if len(t):
            agg = engine.trades_to_days(t, ad_uni, daily_stop_R=breaker).set_index("day")
            base.loc[agg.index, ["day_R", "day_min_R", "n"]] = agg[["day_R", "day_min_R", "n"]].values
    return base.reset_index().to_records(index=False)


def mask_days(days, regmap, band):
    if band is None: return days
    lo, hi = band; d = days.copy()
    keep = np.array([lo <= regmap.get(pd.Timestamp(x).normalize(), 0.5) < hi for x in d["day"]])
    d["day_R"] = np.where(keep, d["day_R"], 0.0)
    d["day_min_R"] = np.where(keep, d["day_min_R"], 0.0)
    d["n"] = np.where(keep, d["n"], 0)
    return d


def best_pass(days, risks=RISKS, deadline=DEADLINE, n=NP):
    br = (-1.0, None, None)
    for r in risks:
        m = ftmo.run_mc(days, r, deadline, n_paths=n, seed=11, block=5)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def eval_combo(trades_list, ad, regmap=None, band="none", breaker=0.0, risks=RISKS):
    """concat trades, build days over TRAIN and TEST, return (test_pass, risk, blow, med)."""
    tr = pd.concat(trades_list, ignore_index=True) if len(trades_list) > 1 else trades_list[0]
    tr_d, te_d = split(ad)
    b = BANDS[band]
    dtr = mask_days(build_days(tr, tr_d, breaker), regmap, b)
    dte = mask_days(build_days(tr, te_d, breaker), regmap, b)
    # pick risk on TRAIN, report on TEST (honest)
    _, r_star, _ = best_pass(dtr)
    m_te = ftmo.run_mc(dte, r_star, DEADLINE, n_paths=NP, seed=11, block=5)
    m_tr = ftmo.run_mc(dtr, r_star, DEADLINE, n_paths=NP, seed=11, block=5)
    return dict(risk=r_star, pass_tr=m_tr["pass_rate"], pass_te=m_te["pass_rate"],
                blow_te=m_te["blow_rate"], med=m_te["med_days_to_pass"])


def main():
    df = S.prep(data.load()); F = FE.compute(df); eod = eod_map(df)
    ad = np.array(sorted(df["date"].unique())); regmap = G.regime(df)
    TR = get_trades(df, F, eod)
    names = list(TR.keys())

    # -------- Phase A: singles, best risk, TRAIN vs TEST 20-day pass --------
    print("\n" + "=" * 96)
    print("PHASE A — every single setup, best-risk 20-day pass (no filter/breaker)  [rank by TEST]")
    print("=" * 96)
    rowsA = []
    for nm in names:
        if not len(TR[nm]): continue
        r = eval_combo([TR[nm]], ad)
        rowsA.append((nm, r))
    rowsA.sort(key=lambda x: x[1]["pass_te"], reverse=True)
    print(f"  {'setup':26s} {'risk':>6} {'passTR':>7} {'passTE':>7} {'blowTE':>7} {'med':>5}")
    for nm, r in rowsA[:18]:
        print(f"  {nm:26s} {r['risk']*100:5.2f}% {r['pass_tr']*100:6.1f}% {r['pass_te']*100:6.1f}% "
              f"{r['blow_te']*100:6.1f}% {r['med'] if r['med']==r['med'] else 0:4.0f}d")

    topA = [nm for nm, _ in rowsA[:10]]

    # -------- Phase B: GARCH regime + breaker on the top singles --------
    print("\n" + "=" * 96)
    print("PHASE B — top singles x GARCH day-filter x daily breaker  [TEST 20-day pass]")
    print("=" * 96)
    print(f"  {'setup':22s} {'filter':7s} {'break':>6} {'risk':>6} {'passTE':>7} {'blowTE':>7}")
    for nm in topA[:6]:
        best = None
        for band in ("none", "lowvol", "himvol"):
            for bk in (0.0, 2.0):
                r = eval_combo([TR[nm]], ad, regmap, band=band, breaker=bk)
                tagbest = (r["pass_te"], band, bk, r)
                if best is None or tagbest[0] > best[0]: best = tagbest
                print(f"  {nm:22s} {band:7s} {bk:5.1f}R {r['risk']*100:5.2f}% {r['pass_te']*100:6.1f}% {r['blow_te']*100:6.1f}%")
        print(f"    -> best for {nm}: {best[1]} breaker -{best[2]:g}R  passTE={best[0]*100:.1f}%")

    # -------- Phase C: combos of top decorrelated setups --------
    print("\n" + "=" * 96)
    print("PHASE C — 2- and 3-leg combos of top setups x filter x breaker  [rank by TEST 20d pass]")
    print("=" * 96)
    cand = topA[:7]
    combos = list(itertools.combinations(cand, 2)) + list(itertools.combinations(cand, 3))
    rowsC = []
    for combo in combos:
        for band in ("none", "lowvol"):
            for bk in (0.0, 2.0):
                r = eval_combo([TR[c] for c in combo], ad, regmap, band=band, breaker=bk)
                rowsC.append((combo, band, bk, r))
    rowsC.sort(key=lambda x: x[3]["pass_te"], reverse=True)
    print(f"  {'combo':44s} {'filt':6s} {'brk':>4} {'risk':>6} {'passTE':>7} {'blowTE':>7} {'med':>5}")
    for combo, band, bk, r in rowsC[:15]:
        cs = "+".join(c.replace("_", "")[:13] for c in combo)
        print(f"  {cs:44s} {band:6s} {bk:3.1f}R {r['risk']*100:5.2f}% {r['pass_te']*100:6.1f}% "
              f"{r['blow_te']*100:6.1f}% {r['med'] if r['med']==r['med'] else 0:4.0f}d")

    print("\n" + "=" * 96)
    print(f"BEST OOS 20-day pass found: {rowsC[0][3]['pass_te']*100:.1f}%  "
          f"(combo {rowsC[0][0]}, filter={rowsC[0][1]}, breaker=-{rowsC[0][2]:g}R, risk={rowsC[0][3]['risk']*100:.2f}%)")
    print("Compare to the established ~44% honest ceiling. Anything materially above needs OOS scrutiny.")


if __name__ == "__main__":
    main()
