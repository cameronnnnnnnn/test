"""
challengephasev2/signal_lab.py — find which CONTEXTS give an event predictive edge.

The "quant process" core loop, step 1: take an event-defining feature (ORB break,
sweep, CUSUM burst, prior-day break), label each occurrence with a double-barrier
outcome (the engine: does +1R or -1R hit first?), attach the contextual features at
the signal bar, then measure how win-rate / expectancy shift across context buckets.

Crucially this is done TRAIN (first 70% of dates) vs TEST (last 30%): a context only
counts as predictive if the edge survives out-of-sample. That guards against the
single biggest failure mode here — mining a high pass-rate that is pure overfit.

Run: python3 signal_lab.py
"""
import os, sys
import numpy as np
import pandas as pd

import features as FE
V4 = FE.V4
import data, strategies as S, engine          # noqa: E402
from engine import ExitSpec                    # noqa: E402

COST = 2.0
# label geometry per event: a clean symmetric-ish double barrier (stop, +1R target)
GEOM = {"orb": 50, "sweep": 40, "cusum": 50, "pdh": 60, "pdl": 60}

# contextual features we test as predictors (continuous -> quantile buckets)
CONT = ["atr_ratio", "vwap_slope", "dist_vwap_atr", "mom5_atr", "mom15_atr",
        "mom30_atr", "realvol_atr", "body_frac", "upper_wick", "lower_wick",
        "min_since_open"]
ORD  = ["vol_regime", "tod_bucket", "dow", "trend_sign", "bar_dir"]


def _eod_map(df):
    """date -> last session bar position (for engine eod_bar)."""
    tod = df["tod"].values; out = {}
    for day, gi in df.groupby("date").indices.items():
        sess = gi[(tod[gi] >= FE.CASH_OPEN) & (tod[gi] <= FE.SESS_END)]
        if len(sess): out[day] = sess[-1]
    return out


def label_event(df, F, ev_name, tp_R=1.0):
    """Run an event through the engine; return a per-trade DataFrame with R, win,
    direction-signed context features attached at the SIGNAL bar (look-ahead-free)."""
    fn = FE.EVENTS[ev_name]
    raw = fn(df)                                   # list of (b0, dir, tag)
    eod = _eod_map(df)
    dates = df["date"].values
    orders = []
    meta = []
    for b0, d, tag in raw:
        day = dates[b0]
        if day not in eod: continue
        stop = GEOM.get(tag, 50)
        orders.append(dict(entry_bar=b0, dir=d, stop_pts=stop,
                           spec=ExitSpec(tp_R=tp_R, be_R=0.0, trail_R=0.0, max_bars=10**9),
                           eod_bar=eod[day], day=pd.Timestamp(day), tag=tag))
        meta.append((b0, d))
    tr = engine.simulate(df, orders, cost_pts=COST)
    if len(tr) == 0: return tr
    # align: simulate keeps orders whose b0+1 < n, in order. Rebuild entry bar via dt.
    pos = {ts: i for i, ts in enumerate(df.index)}
    b0s = np.array([pos[t] - 1 for t in tr["entry_dt"].values])
    dirs = tr["dir"].values
    rows = {"R": tr["R"].values, "win": (tr["R"].values > 0).astype(int),
            "date": df["date"].values[b0s], "dir": dirs}
    for f in CONT + ORD:
        v = F[f][b0s]
        # sign continuous trend/momentum/distance features by trade direction so a
        # single "with us / against us" axis emerges instead of a long/short split
        if f in ("vwap_slope", "dist_vwap_atr", "mom5_atr", "mom15_atr", "mom30_atr"):
            v = v * dirs
        rows[f] = v
    return pd.DataFrame(rows)


def edge_table(lab, feat, is_ord, q=4):
    """WR / expR per bucket of `feat`, computed on TRAIN and echoed on TEST."""
    d = lab.dropna(subset=[feat])
    if len(d) < 60: return None
    cut = d["date"].quantile(0.70)
    tr, te = d[d["date"] <= cut], d[d["date"] > cut]
    if is_ord:
        buckets = sorted(d[feat].unique())
        binner = lambda x: x[feat]
        labels = {b: f"{b:g}" for b in buckets}
    else:
        edges = np.quantile(tr[feat], np.linspace(0, 1, q + 1))
        edges[0], edges[-1] = -np.inf, np.inf
        edges = np.unique(edges)
        binner = lambda x: pd.cut(x[feat], edges, labels=False, include_lowest=True)
        labels = {i: f"[{edges[i]:+.2f},{edges[i+1]:+.2f})" for i in range(len(edges) - 1)}
    tr = tr.assign(_b=binner(tr)); te = te.assign(_b=binner(te))
    out = []
    base_tr = tr["win"].mean()
    for b in sorted(labels):
        gt = tr[tr["_b"] == b]; ge = te[te["_b"] == b]
        if len(gt) < 25: continue
        out.append(dict(bucket=labels[b], n_tr=len(gt),
                        wr_tr=gt["win"].mean(), exp_tr=gt["R"].mean(),
                        n_te=len(ge), wr_te=ge["win"].mean() if len(ge) else np.nan,
                        exp_te=ge["R"].mean() if len(ge) else np.nan))
    return base_tr, tr["R"].mean(), pd.DataFrame(out)


def main():
    df = S.prep(data.load())
    F = FE.compute(df)
    print("=" * 100)
    print("SIGNAL LAB — conditional edge of each event by context  (TRAIN 70% | TEST 30%, double-barrier ±1R)")
    print("=" * 100)
    for ev in ["orb", "sweep", "cusum", "pdhl"]:
        lab = label_event(df, F, ev, tp_R=1.0)
        if len(lab) == 0:
            print(f"\n### {ev.upper()}: no trades"); continue
        cut = lab["date"].quantile(0.70)
        base = lab["win"].mean()
        baseR = lab["R"].mean()
        print(f"\n### {ev.upper()}  n={len(lab)}  base WR={base*100:.1f}%  base expR={baseR:+.3f}  "
              f"(train {(lab['date']<=cut).sum()} / test {(lab['date']>cut).sum()})")
        # rank features by how much the best surviving bucket lifts WR out-of-sample
        ranked = []
        for f, is_ord in [(x, False) for x in CONT] + [(x, True) for x in ORD]:
            res = edge_table(lab, f, is_ord)
            if res is None: continue
            _, _, tab = res
            if len(tab) == 0: continue
            tab = tab.dropna(subset=["wr_te"])
            if len(tab) == 0: continue
            # surviving lift = best train bucket that ALSO beats base on test
            tab["lift_tr"] = tab["wr_tr"] - base
            tab["lift_te"] = tab["wr_te"] - base
            best = tab.sort_values("wr_tr", ascending=False).iloc[0]
            ranked.append((f, best["bucket"], best["wr_tr"], best["wr_te"],
                           best["exp_tr"], best["exp_te"], best["n_tr"], best["n_te"]))
        ranked.sort(key=lambda r: r[3], reverse=True)   # by TEST win-rate
        print(f"  {'feature':15s} {'best bucket':18s} {'WRtr':>6} {'WRte':>6} "
              f"{'expRtr':>7} {'expRte':>7} {'ntr':>5} {'nte':>5}  survives?")
        for f, bk, wtr, wte, etr, ete, ntr, nte in ranked:
            surv = "YES" if (wte > base + 0.02 and ete > 0) else "."
            print(f"  {f:15s} {bk:18s} {wtr*100:5.1f}% {wte*100:5.1f}% "
                  f"{etr:+6.3f} {ete:+6.3f} {ntr:5.0f} {nte:5.0f}    {surv}")
    print("\n" + "=" * 100)
    print("Reading it: a context only matters if WRte clearly beats base WR AND expRte>0 (out-of-sample).")
    print("Those survivors become the FILTERS for iteration-2 strategies.")


if __name__ == "__main__":
    main()
