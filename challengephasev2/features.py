"""
challengephasev2/features.py — bar-level FEATURE ENGINEERING for NAS100 M1.

Following the "quant process" methodology: take raw OHLCV and transform it into
meaningful, look-ahead-free features grouped by PURPOSE:

  * event-defining  : flags that mark which bars are part of an experiment
                      (ORB breakout, prior-session sweep, CUSUM movement burst,
                       prior-day H/L break)
  * contextual      : numbers that explain why the same event behaves differently
                      (volatility regime, VWAP trend slope, wick fractions,
                       ATR-short/long ratio, distance-to-VWAP, time-of-day,
                       opening-range size, day-of-week)

All features are computed ONCE over the whole frame as aligned numpy arrays so a
strategy can index them by entry bar in O(1). Everything is normalised (ATR /
percentage / z-score) so scale does not dominate, and every rolling/daily term is
SHIFTED so a feature at bar b only uses information available at the close of b
(the engine then fills at b+1 open — no look-ahead).

Reuses ftmo/v4 (engine/strategies/data) via sys.path injection.
"""
import os, sys
import numpy as np
import pandas as pd

V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path:
    sys.path.insert(0, V4)

import data as _data           # noqa: E402
import strategies as _strat    # noqa: E402

CASH_OPEN = 16 * 60 + 30       # US cash open, server time (EET/EEST)
SESS_END  = 22 * 60 + 55

# ---------------------------------------------------------------------------
# session VWAP (cumulative within the US cash session) -> per-bar array
# ---------------------------------------------------------------------------
def _session_vwap(df):
    """Per-bar session VWAP over [CASH_OPEN, SESS_END]; NaN outside the session."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    v = df["tickvol"].values.astype(float)
    tp = (h + l + c) / 3.0
    tod = df["tod"].values
    vwap = np.full(len(df), np.nan)
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= CASH_OPEN) & (t <= SESS_END)]
        if len(sess) < 5:
            continue
        cpv = np.cumsum(tp[sess] * v[sess]); cv = np.cumsum(v[sess]) + 1e-9
        vwap[sess] = cpv / cv
    return vwap

# ---------------------------------------------------------------------------
# main entry point: a dict of aligned, look-ahead-free feature arrays
# ---------------------------------------------------------------------------
def compute(df, fast=14, slow=100):
    """df must already be strategies.prep()'d (has i / tod / date).
    Returns dict[str, np.ndarray] all of length len(df)."""
    n = len(df)
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    tod = df["tod"].values
    dow = df.index.dayofweek.values.astype(float)

    F = {}

    # --- candle geometry (contextual, normalised by the bar's own range) ---
    rng = np.maximum(h - l, 1e-9)
    body = np.abs(c - o)
    F["body_frac"]  = body / rng                       # 0..1, how decisive the bar
    F["upper_wick"] = (h - np.maximum(o, c)) / rng     # 0..1
    F["lower_wick"] = (np.minimum(o, c) - l) / rng     # 0..1
    F["bar_dir"]    = np.sign(c - o)                   # -1/0/+1

    # --- daily ATR & vol regime (SHIFTED -> prior days only) ---
    atr_map  = _strat.daily_atr(df, n=fast)            # {date: points}
    vr_map   = _strat.vol_ratio(df, fast=fast, slow=slow, lo=0.4, hi=2.5)
    dates    = df["date"].values
    atr = np.array([atr_map.get(pd.Timestamp(d), np.nan) for d in dates], float)
    vr  = np.array([vr_map.get(pd.Timestamp(d), 1.0)     for d in dates], float)
    atr = np.where(np.isfinite(atr) & (atr > 0), atr, np.nanmedian(atr[np.isfinite(atr)]))
    F["atr_pts"]   = atr
    F["atr_ratio"] = vr                                # ATR(fast)/ATR(slow), trailing
    # ordinal volatility regime 1..5 from the trailing ratio
    F["vol_regime"] = np.clip(np.digitize(vr, [0.7, 0.9, 1.1, 1.4]) + 1, 1, 5).astype(float)

    # --- session VWAP, distance & slope (trend context) ---
    vwap = _session_vwap(df)
    F["vwap"] = vwap
    F["dist_vwap_atr"] = (c - vwap) / atr              # signed, ATR-normalised
    # VWAP slope over the last 20 bars, ATR-normalised (trend strength + sign)
    slope = np.full(n, np.nan)
    vwap_sh = np.concatenate([np.full(20, np.nan), vwap[:-20]])
    with np.errstate(invalid="ignore"):
        slope = (vwap - vwap_sh) / atr
    # only valid within a session where both ends are non-NaN (same day handled by NaN)
    F["vwap_slope"] = slope
    F["trend_sign"] = np.sign(np.nan_to_num(slope))

    # --- momentum: ATR-normalised return over the last k bars (no look-ahead) ---
    for k in (5, 15, 30):
        cprev = np.concatenate([np.full(k, np.nan), c[:-k]])
        F[f"mom{k}_atr"] = (c - cprev) / atr

    # --- rolling realised vol over last 30 bars (bar-to-bar), ATR-normalised ---
    r1 = np.concatenate([[np.nan], np.diff(c)])
    rv = pd.Series(r1).rolling(30, min_periods=15).std().values
    F["realvol_atr"] = rv / atr

    # --- time-of-day bucket within the US session (ordinal early/mid/late) ---
    since_open = tod - CASH_OPEN
    F["min_since_open"] = since_open.astype(float)
    F["tod_bucket"] = np.where(since_open < 30, 1.0,
                       np.where(since_open < 120, 2.0,
                       np.where(since_open < 300, 3.0, 4.0)))
    F["dow"] = dow

    return F


# ---------------------------------------------------------------------------
# EVENT-DEFINING features: per-day signal generators that emit candidate entry
# bars (and direction). These mark "which moments are part of the experiment".
# Each returns list of (entry_bar, dir, tag). The contextual features above are
# then attached at each entry_bar by the signal lab.
# ---------------------------------------------------------------------------
def _day_groups(df):
    return df.groupby("date").indices

def ev_orb(df, or_min=15, open_min=CASH_OPEN, long_only=False):
    """First touch beyond the opening range -> breakout event (both sides)."""
    h, l, tod = df["high"].values, df["low"].values, df["tod"].values
    or_end = open_min + or_min; out = []
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        om = (t >= open_min) & (t < or_end)
        if om.sum() < 5: continue
        rh = h[gi[om]].max(); rl = l[gi[om]].min()
        post = gi[(t >= or_end) & (t <= SESS_END)]
        for b in post[:-1]:
            if h[b] >= rh:
                out.append((b, 1, "orb")); break
            if (not long_only) and l[b] <= rl:
                out.append((b, -1, "orb")); break
    return out

def ev_sweep(df, open_min=CASH_OPEN, lookback_min=60, revert_bars=3):
    """Liquidity sweep + reversal: price pokes beyond the prior-session-window
    extreme then closes back inside within revert_bars -> fade event."""
    h, l, c, tod = (df["high"].values, df["low"].values, df["close"].values, df["tod"].values)
    out = []
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        ref = gi[(t >= open_min - lookback_min) & (t < open_min)]   # pre-open window
        if len(ref) < 10: continue
        rh = h[ref].max(); rl = l[ref].min()
        sess = gi[(t >= open_min) & (t <= SESS_END)]
        swept_hi = swept_lo = -1
        for k, b in enumerate(sess[:-1]):
            if swept_hi < 0 and h[b] > rh: swept_hi = k
            if swept_lo < 0 and l[b] < rl: swept_lo = k
            if swept_hi >= 0 and k - swept_hi <= revert_bars and c[b] < rh:
                out.append((b, -1, "sweep")); break     # swept highs, reverse short
            if swept_lo >= 0 and k - swept_lo <= revert_bars and c[b] > rl:
                out.append((b, 1, "sweep")); break       # swept lows, reverse long
    return out

def ev_cusum(df, open_min=CASH_OPEN, k_atr=0.5):
    """CUSUM movement detector: accumulate ATR-normalised returns; fire when the
    cumulative one-sided move exceeds k_atr (a directional 'burst' event). Resets
    on fire and on sign flip. Look-ahead-free (uses closes up to b)."""
    c, tod = df["close"].values, df["tod"].values
    atr_map = _strat.daily_atr(df, n=14)
    out = []
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        sess = gi[(t >= open_min) & (t <= SESS_END)]
        if len(sess) < 10: continue
        a = atr_map.get(pd.Timestamp(df["date"].values[sess[0]]), np.nan)
        if not (a == a) or a <= 0: continue
        sp = sn = 0.0
        for k in range(1, len(sess) - 1):
            r = (c[sess[k]] - c[sess[k - 1]]) / a
            sp = max(0.0, sp + r); sn = min(0.0, sn + r)
            if sp > k_atr:
                out.append((sess[k], 1, "cusum")); break
            if sn < -k_atr:
                out.append((sess[k], -1, "cusum")); break
    return out

def ev_pdhl(df, open_min=CASH_OPEN, buf=2):
    """Prior-DAY high/low break during the US session -> breakout event."""
    h, l, tod = df["high"].values, df["low"].values, df["tod"].values
    groups = list(_day_groups(df).items())
    dayHL = {day: (h[gi].max(), l[gi].min()) for day, gi in groups}
    out = []
    for kk in range(1, len(groups)):
        day, gi = groups[kk]; pH, pL = dayHL[groups[kk - 1][0]]
        t = tod[gi]
        sess = gi[(t >= open_min) & (t <= SESS_END)]
        for b in sess[:-1]:
            if h[b] >= pH + buf: out.append((b, 1, "pdh")); break
            if l[b] <= pL - buf: out.append((b, -1, "pdl")); break
    return out

EVENTS = {"orb": ev_orb, "sweep": ev_sweep, "cusum": ev_cusum, "pdhl": ev_pdhl}

if __name__ == "__main__":
    df = _strat.prep(_data.load())
    F = compute(df)
    print(f"computed {len(F)} features over {len(df):,} bars")
    for kf in sorted(F):
        a = F[kf]; fin = np.isfinite(a)
        print(f"  {kf:16s} finite={fin.mean()*100:5.1f}%  "
              f"med={np.nanmedian(a):+.3f}  iqr=[{np.nanpercentile(a,25):+.3f},{np.nanpercentile(a,75):+.3f}]")
    for nm, fn in EVENTS.items():
        ev = fn(df)
        print(f"  event {nm:7s}: {len(ev):4d} signals  ({len(ev)/len(df.groupby('date')):.2f}/day)")
