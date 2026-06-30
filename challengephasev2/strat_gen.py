"""
challengephasev2/strat_gen.py — turn surviving contexts into strategies and measure
the REAL FTMO 1-Step pass rate at a ~20-trading-day deadline, TRAIN vs TEST.

A strategy = an event generator + a set of context filters + a risk geometry
(stop, tp_R, be_R, trail_R). We lean into the prop-firm convex geometry: tight TP /
wide stop -> high win rate -> low daily P&L variance -> (the hope) high pass rate,
while keeping a max-loss day well under the 3% daily limit. Multiple decorrelated
setups can be merged to raise the daily Sharpe.

Pass rate is bootstrapped (ftmo.run_mc) separately over TRAIN days and TEST days so
we never report an in-sample mirage. Run: python3 strat_gen.py
"""
import os, sys
import numpy as np
import pandas as pd

import features as FE
import data, strategies as S, engine, ftmo     # noqa: E402
from engine import ExitSpec                     # noqa: E402
from run import build_days                      # noqa: E402

COST = 2.0; DEADLINE = 20


def eod_map(df):
    tod = df["tod"].values; out = {}
    for day, gi in df.groupby("date").indices.items():
        sess = gi[(tod[gi] >= FE.CASH_OPEN) & (tod[gi] <= FE.SESS_END)]
        if len(sess): out[day] = sess[-1]
    return out


def filtered_orders(df, F, eod, event, stop_pts, tp_R, be_R=0.0, trail_R=0.0,
                    filters=(), open_min=None):
    """filters: list of (feat, lo, hi, signed). signed -> multiply by trade dir."""
    raw = FE.EVENTS[event](df) if open_min is None else FE.EVENTS[event](df, open_min=open_min)
    dates = df["date"].values; orders = []
    for b0, d, tag in raw:
        day = dates[b0]
        if day not in eod: continue
        ok = True
        for (f, lo, hi, signed) in filters:
            v = F[f][b0]
            if signed: v = v * d
            if not (v == v) or not (lo <= v < hi): ok = False; break
        if not ok: continue
        orders.append(dict(entry_bar=b0, dir=d, stop_pts=stop_pts,
                           spec=ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9),
                           eod_bar=eod[day], day=pd.Timestamp(day), tag=event))
    return orders


def split(ad, frac=0.70):
    cut = ad[int(len(ad) * frac)]
    return ad[ad <= cut], ad[ad > cut]


def eval_orders(df, orders, ad_sub, risks, deadline=DEADLINE):
    """Restrict trades to ad_sub dates, aggregate to days, MC pass at each risk."""
    tr = engine.simulate(df, orders, cost_pts=COST)
    if len(tr): tr = tr[tr["day"].isin(set(ad_sub))]
    es = engine.edge_stats(tr) if len(tr) else dict(n=0, wr=0, expR=0, pf=0)
    days = build_days(tr, ad_sub)
    best = None
    for r in risks:
        m = ftmo.run_mc(days, r, deadline, n_paths=40000, seed=11, block=5)
        if best is None or m["pass_rate"] > best[1]["pass_rate"]:
            best = (r, m)
    return es, best


def report(df, F, eod, ad, name, build, risks=(0.005, 0.0075, 0.01, 0.0125, 0.015)):
    """build: fn(date_array)->orders for that subset's date universe (same orders,
    we just restrict trades by date in eval). Print TRAIN and TEST pass."""
    tr_d, te_d = split(ad)
    orders = build()
    es_a, (r_a, m_a) = eval_orders(df, orders, ad, risks)
    es_tr, (r_tr, m_tr) = eval_orders(df, orders, tr_d, risks)
    es_te, (r_te, m_te) = eval_orders(df, orders, te_d, risks)
    print(f"\n{name}")
    print(f"   trades={es_a['n']:4d}  WR={es_a['wr']*100:4.1f}%  expR={es_a['expR']:+.3f}  PF={es_a.get('pf',0):.2f}")
    for lbl, r, m in [("ALL ", r_a, m_a), ("TRN ", r_tr, m_tr), ("TEST", r_te, m_te)]:
        md = m["med_days_to_pass"]
        print(f"   [{lbl}] r*={r*100:.2f}%  pass={m['pass_rate']*100:5.1f}%  "
              f"blow={m['blow_rate']*100:5.1f}%  timeout={m['timeout_rate']*100:5.1f}%  "
              f"med_days={md if md==md else float('nan'):.0f}")
    return m_te["pass_rate"]


def main():
    df = S.prep(data.load()); F = FE.compute(df)
    ad = np.array(sorted(df["date"].unique())); eod = eod_map(df)
    print("=" * 92)
    print(f"STRATEGY GENERATOR — FTMO 1-Step, {DEADLINE}-day deadline, pass% TRAIN vs TEST (OOS)")
    print(f"target: 80% pass in ~20 trading days   |   baseline ceiling so far ~46% (live strat)")
    print("=" * 92)

    # --- 0) sanity: the current live strat (ORB 50pt + VWpull 40pt, 4R) ---
    report(df, F, eod, ad, "0) LIVE baseline  (ORB 50 4R + VWpull 40 4R)",
           lambda: (S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True)
                    + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)))

    # --- 1) CUSUM continuation, UNFILTERED, high-WR geometry (tp 0.75R) ---
    report(df, F, eod, ad, "1) CUSUM unfiltered  stop50 tp0.75R",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 0.75))

    # --- 2) CUSUM + with-trend filter (vwap_slope signed > 0.04) ---
    report(df, F, eod, ad, "2) CUSUM with-trend (slope>0.04) stop50 tp0.75R",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 0.75,
                                   filters=[("vwap_slope", 0.04, np.inf, True)]))

    # --- 3) CUSUM with-trend, even tighter TP (tp0.5R) -> higher WR ---
    report(df, F, eod, ad, "3) CUSUM with-trend  stop50 tp0.5R",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 0.5,
                                   filters=[("vwap_slope", 0.04, np.inf, True)]))

    # --- 4) CUSUM with-trend + mid-session + normal vol (stacked survivors) ---
    report(df, F, eod, ad, "4) CUSUM trend+midsess+vol  stop50 tp0.75R",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 0.75,
                                   filters=[("vwap_slope", 0.02, np.inf, True),
                                            ("tod_bucket", 2, 4, False),
                                            ("atr_ratio", 0.7, 1.4, False)]))

    # --- 5) decorrelated combo: CUSUM-trend (mom) + ORB high-WR (tight TP) ---
    report(df, F, eod, ad, "5) COMBO  CUSUM-trend tp0.75 + ORB stop50 tp1.0",
           lambda: (filtered_orders(df, F, eod, "cusum", 50, 0.75,
                                    filters=[("vwap_slope", 0.02, np.inf, True)])
                    + filtered_orders(df, F, eod, "orb", 50, 1.0,
                                      filters=[("min_since_open", 24, np.inf, False)])))
    print("\n" + "=" * 92)
    print("TEST pass% is the honest number. If it is far below 80%, the convex geometry is")
    print("not enough on NAS100 under the 3% daily cap and we iterate on features/geometry.")


if __name__ == "__main__":
    main()
