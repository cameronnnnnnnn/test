"""
challengephaseHF/creative.py — INVENT NEW strategies (not the ORB/VWpull/fade/RSI/MIM/gaprev
templates already exhausted) and test each honestly on NAS100 M1. Five genuinely different
signal structures, each probing a distinct real market regularity:

  1 coil_break   — volatility-COMPRESSION expansion. Find the tightest M-bar coil (narrowest
                   range in L bars), trade its breakout. Tests volatility clustering (quiet
                   precedes violent), with a natural tight stop = coil height -> big R skew.
  2 climax_fade  — microstructure EXHAUSTION. A bar with extreme tick-volume AND a wide range
                   is a climax; fade it back. Tests one-bar overreaction.
  3 sweep_reclaim— liquidity STOP-RUN reversal ("turtle soup"). Pre-US-open range high/low is
                   swept then reclaimed in the first 90 min -> reversal. Tests stop hunts.
  4 xasset_orb   — cross-asset RISK FILTER. NAS100 US-open ORB, but only take the direction
                   USDJPY (risk proxy) agrees with. Uses the ~0 NAS/JPY correlation as a
                   SIGNAL, not a diversifier. Tests index/JPY risk-on lead-lag.
  5 tom_long     — turn-of-month SEASONAL. Long NAS100 at the US open on the last trading day
                   of the month + first 3 of the next (documented equity turn-of-month drift).

Honest TRAIN(70%)/TEST(30%) expR for each. Anything with stable +OOS edge is carried into
the combine step (combine_new.py) to test whether it lifts the 52% monthly pass. Overfit
in-sample-only numbers are called out. Run: python3 creative.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine, fx_data     # noqa: E402
from engine import ExitSpec                         # noqa: E402

OPEN = 16 * 60 + 30            # US cash open (server EET)
SESS_END = 22 * 60 + 55


def _grp(df):
    return df.groupby("date").indices


# ---------------------------------------------------------------- 1) coil breakout
def coil_break(df, M=15, L=90, stop_pts=0.0, coil_stop_k=1.0, min_stop=18,
               tp_R=0.0, trail_R=3.0, be_R=1.0, start=OPEN, entry_by=21*60, max_wait=30):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    orders = []
    for day, gi in _grp(df).items():
        t = tod[gi]
        sess = gi[(t >= start - 60) & (t <= SESS_END)]   # allow coil to form from ~1h before
        if len(sess) < L + M + 5:
            continue
        hh, ll, ts = h[sess], l[sess], tod[sess]
        # rolling M-bar range ending at each bar (past-only)
        rng = np.full(len(sess), np.nan)
        for j in range(M - 1, len(sess)):
            rng[j] = hh[j-M+1:j+1].max() - ll[j-M+1:j+1].min()
        eod = sess[-1]
        armed = False; coilH = coilL = 0.0; arm_j = -1
        for j in range(L, len(sess) - 1):
            if ts[j] < start:
                continue
            if not armed:
                # narrowest M-range in the last L bars -> a coil is set
                if np.isfinite(rng[j]) and rng[j] <= np.nanmin(rng[j-L:j+1]) + 1e-9:
                    coilH = hh[j-M+1:j+1].max(); coilL = ll[j-M+1:j+1].min()
                    armed = True; arm_j = j
                continue
            if j - arm_j > max_wait:
                armed = False; continue          # coil went stale, look for a new one
            if ts[j] > entry_by:
                break
            ch = coilH - coilL
            stp = stop_pts if stop_pts > 0 else max(coil_stop_k * ch, min_stop)
            spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
            if hh[j] >= coilH:
                orders.append(dict(entry_bar=sess[j], dir=1, stop_pts=stp, spec=spec,
                                   eod_bar=eod, day=day, tag="coil")); break
            if ll[j] <= coilL:
                orders.append(dict(entry_bar=sess[j], dir=-1, stop_pts=stp, spec=spec,
                                   eod_bar=eod, day=day, tag="coil")); break
    return orders


# ---------------------------------------------------------------- 2) volume-climax fade
def climax_fade(df, W=60, vmult=4.0, rng_mult=2.0, stop_pts=45, tp_R=1.5, be_R=0.0,
                trail_R=0.0, start=OPEN, entry_by=21*60):
    h, l, c, o = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    v = df["tickvol"].values.astype(float)
    tod = df["tod"].values
    orders = []
    for day, gi in _grp(df).items():
        t = tod[gi]
        sess = gi[(t >= start - 90) & (t <= SESS_END)]
        if len(sess) < W + 10:
            continue
        hh, ll, cc, oo, vv, ts = h[sess], l[sess], c[sess], o[sess], v[sess], tod[sess]
        rng = hh - ll
        eod = sess[-1]
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for j in range(W, len(sess) - 1):
            if ts[j] < start or ts[j] > entry_by:
                continue
            medv = np.median(vv[j-W:j]); medr = np.median(rng[j-W:j])
            if medv <= 0 or medr <= 0:
                continue
            if vv[j] >= vmult * medv and rng[j] >= rng_mult * medr and abs(cc[j]-oo[j]) > 0:
                d = -1 if (cc[j] - oo[j]) > 0 else 1     # fade the climax bar's direction
                orders.append(dict(entry_bar=sess[j], dir=d, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="climax")); break
    return orders


# ---------------------------------------------------------------- 3) pre-open sweep & reclaim
def sweep_reclaim(df, stop_pts=40, tp_R=0.0, trail_R=2.5, be_R=1.0, poke=4,
                  react_by=18*60+30, hold=8):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    orders = []
    for day, gi in _grp(df).items():
        t = tod[gi]
        pre = gi[(t >= 0) & (t < OPEN)]
        sess = gi[(t >= OPEN) & (t <= SESS_END)]
        if len(pre) < 60 or len(sess) < 30:
            continue
        preH = h[pre].max(); preL = l[pre].min()
        eod = sess[-1]
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        swept = 0; swb = -1
        for k, b in enumerate(sess[:-1]):
            if tod[b] > react_by:
                break
            if swept == 0:
                if h[b] >= preH + poke: swept, swb = 1, k
                elif l[b] <= preL - poke: swept, swb = -1, k
                continue
            if k - swb > hold:
                swept = 0; continue               # no reclaim in time -> reset
            if swept == 1 and c[b] < preH:        # reclaimed back below swept high -> short
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="sweep")); break
            if swept == -1 and c[b] > preL:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="sweep")); break
    return orders


# ---------------------------------------------------------------- 4) cross-asset risk filter
def jpy_risk_sign(win_lo=8*60, win_hi=16*60):
    """Per server-date risk-on/off sign from USDJPY move over [win_lo, win_hi) (rise=risk-on)."""
    dj = S.prep(fx_data.load("USDJPY"))
    c = dj["close"].values; tod = dj["tod"].values
    sign = {}
    for day, gi in dj.groupby("date").indices.items():
        t = tod[gi]
        w = gi[(t >= win_lo) & (t < win_hi)]
        if len(w) < 30:
            continue
        sign[day] = np.sign(c[w[-1]] - c[w[0]])
    return sign


def xasset_orb(df, sign, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, open_min=16*60,
               vol_filter=True, agree=True):
    """US-open ORB, but only take the breakout whose direction USDJPY agrees (agree=True)
    or disagrees (agree=False) with. agree=False is the control (should be worse if real)."""
    base = S.orb(df, or_min=or_min, stop_pts=stop_pts, tp_R=tp_R, be_R=be_R,
                 open_min=open_min, vol_filter=vol_filter)
    out = []
    for od in base:
        s = sign.get(od["day"], 0.0)
        if s == 0:
            continue
        ok = (od["dir"] == s) if agree else (od["dir"] != s)
        if ok:
            out.append(od)
    return out


# ---------------------------------------------------------------- 5) turn-of-month long
def tom_long(df, stop_pts=60, tp_R=0.0, trail_R=3.0, be_R=1.0, last_n=1, first_n=3,
             open_min=16*60):
    h, l = df["high"].values, df["low"].values
    tod = df["tod"].values
    groups = list(_grp(df).items())
    dates = [d for d, _ in groups]
    # rank trading days within their month; tag last_n of a month and first_n of the next
    dser = pd.Series(range(len(dates)), index=pd.to_datetime(dates))
    ym = dser.index.to_period("M")
    tom = np.zeros(len(dates), bool)
    for _, idxs in pd.Series(range(len(dates))).groupby(ym.values):
        arr = idxs.values
        for p in arr[-last_n:]:
            tom[p] = True
    # first_n of each month
    seen = {}
    for i, d in enumerate(dates):
        key = (d.year, d.month)
        seen.setdefault(key, 0)
        if seen[key] < first_n:
            tom[i] = True
        seen[key] += 1
    orders = []
    for i, (day, gi) in enumerate(groups):
        if not tom[i]:
            continue
        t = tod[gi]
        sess = gi[(t >= open_min) & (t <= SESS_END)]
        if len(sess) < 10:
            continue
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        orders.append(dict(entry_bar=sess[0], dir=1, stop_pts=stop_pts, spec=spec,
                           eod_bar=sess[-1], day=day, tag="tom"))
    return orders


# ---------------------------------------------------------------- honest edge report
def split_dates(df, frac=0.7):
    ad = np.array(sorted(df["date"].unique()))
    cut = ad[int(len(ad) * frac)]
    return set(ad[ad <= cut]), set(ad[ad > cut])


def report(df, name, orders, dtr, dte, ndays, cost=2.0):
    tr = engine.simulate(df, orders, cost_pts=cost)
    if not len(tr):
        print(f"  {name:16} no trades"); return None
    a = engine.edge_stats(tr)
    ttr = tr[tr["day"].isin(dtr)]; tte = tr[tr["day"].isin(dte)]
    etr = engine.edge_stats(ttr)["expR"] if len(ttr) else float("nan")
    ete = engine.edge_stats(tte)["expR"] if len(tte) else float("nan")
    flag = "  <-- +OOS" if (etr > 0 and ete > 0.02) else ""
    print(f"  {name:16} {a['n']/ndays:5.2f} {a['wr']*100:5.1f}% {a['expR']:+7.3f} "
          f"{etr:+7.3f} {ete:+7.3f} {a['pf']:5.2f}{flag}")
    return tr


def main():
    df = S.prep(data.load()); ndays = df["date"].nunique()
    dtr, dte = split_dates(df)
    print(f"NAS100 creative strategies — {ndays} days.  edge = /day, WR, expR(all/train/test), PF\n")
    print(f"  {'strategy':16} {'/day':>5} {'WR':>6} {'expR':>7} {'exp_tr':>7} {'exp_te':>7} {'PF':>5}")

    report(df, "coil_break natS", coil_break(df), dtr, dte, ndays)
    report(df, "coil_break s50", coil_break(df, stop_pts=50, tp_R=4.0, trail_R=0.0), dtr, dte, ndays)
    report(df, "climax_fade", climax_fade(df), dtr, dte, ndays)
    report(df, "sweep_reclaim", sweep_reclaim(df), dtr, dte, ndays)

    sign = jpy_risk_sign()
    report(df, "orb_base", xasset_orb(df, sign, agree=True) + xasset_orb(df, sign, agree=False), dtr, dte, ndays)
    report(df, "xasset agree", xasset_orb(df, sign, agree=True), dtr, dte, ndays)
    report(df, "xasset disagree", xasset_orb(df, sign, agree=False), dtr, dte, ndays)

    report(df, "tom_long", tom_long(df), dtr, dte, ndays)
    print("\n(agree vs disagree is the cross-asset control: if the risk filter is real, 'agree'")
    print(" should clearly beat 'disagree'. tom_long is a long-only seasonal, few trades.)")


if __name__ == "__main__":
    main()
