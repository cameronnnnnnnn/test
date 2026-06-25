"""
v2/strategies.py — NAS100 intraday strategy library.

Each strategy(df, **params) -> list[order], where order =
  {entry_bar, dir, stop_pts, spec:ExitSpec, eod_bar, day, tag}.
entry_bar is the bar at which the signal is CONFIRMED; the engine fills at the
NEXT bar's open (no look-ahead). Server time (EET/EEST): US cash open = 16:30.
"""
import numpy as np, pandas as pd
from engine import ExitSpec

CASH_OPEN = 16 * 60 + 30      # 16:30 server
SESS_END  = 22 * 60 + 55      # flat a few min before 23:00 close

def prep(df):
    df = df.copy()
    df["i"]   = np.arange(len(df))
    df["tod"] = (df.index.hour * 60 + df.index.minute).astype(int)
    df["date"] = df.index.normalize()
    return df

def _day_groups(df):
    return df.groupby("date").indices    # date -> positional index array

# ----------------------------------------------------------------------------
# 1) Opening-Range Breakout (baseline; both sides)  -- validates vs prior work
# ----------------------------------------------------------------------------
def orb(df, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, trail_R=0.0,
        long_only=False, open_min=CASH_OPEN, vol_filter=False, range_filter=False):
    o, h, l = df["open"].values, df["high"].values, df["low"].values
    v = df["tickvol"].values.astype(float)
    tod, ii = df["tod"].values, df["i"].values
    orders = []
    or_end = open_min + or_min
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        orb_mask = (t >= open_min) & (t < or_end)
        if orb_mask.sum() < 5:
            continue
        rh = h[gi[orb_mask]].max(); rl = l[gi[orb_mask]].min()
        rng = rh - rl
        if range_filter and (rng < 0.4 * stop_pts or rng > 6 * stop_pts):
            continue
        post = gi[(t >= or_end) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        or_vavg = v[gi[orb_mask]].mean()
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for b in post[:-1]:
            if vol_filter and v[b] <= or_vavg:
                # still allow the level to be crossed but require volume confirmation
                if h[b] >= rh or l[b] <= rl:
                    continue
            if h[b] >= rh:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="orb")); break
            if (not long_only) and l[b] <= rl:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="orb")); break
    return orders

# ----------------------------------------------------------------------------
# 2) Opening-Range FADE (failed-breakout / liquidity sweep reversal)
#    Wait for a poke beyond the OR, then fade back into the range. High WR idea.
# ----------------------------------------------------------------------------
def or_fade(df, or_min=30, poke_pts=15, stop_pts=40, tp_R=1.0, be_R=0.0,
            trail_R=0.0, entry_by=21*60):
    h, l = df["high"].values, df["low"].values
    tod = df["tod"].values
    orders = []
    or_end = CASH_OPEN + or_min
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        om = (t >= CASH_OPEN) & (t < or_end)
        if om.sum() < 5:
            continue
        rh = h[gi[om]].max(); rl = l[gi[om]].min()
        post = gi[(t >= or_end) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for b in post[:-1]:
            if tod[b] > entry_by:
                break
            if h[b] >= rh + poke_pts:      # poked above -> fade short back to range
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="orfade")); break
            if l[b] <= rl - poke_pts:      # poked below -> fade long
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="orfade")); break
    return orders

# ----------------------------------------------------------------------------
# 3) Session-VWAP mean-reversion fade
#    Fade price stretched k*sigma from the cash-session VWAP; target VWAP.
# ----------------------------------------------------------------------------
def vwap_fade(df, k=2.0, stop_pts=50, tp_R=1.0, be_R=0.0, trail_R=0.0,
              start=CASH_OPEN+15, entry_by=21*60, win=30):
    h, l, c, v = (df["high"].values, df["low"].values, df["close"].values,
                  df["tickvol"].values.astype(float))
    tp = (h + l + c) / 3.0
    tod = df["tod"].values
    orders = []
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        sess = gi[(t >= CASH_OPEN) & (t <= SESS_END)]
        if len(sess) < 60:
            continue
        eod = sess[-1]
        pv = tp[sess] * v[sess]
        cum_pv = np.cumsum(pv); cum_v = np.cumsum(v[sess]) + 1e-9
        vwap = cum_pv / cum_v
        dev = c[sess] - vwap
        # rolling sigma of deviation
        sig = pd.Series(dev).rolling(win, min_periods=win).std().values
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        ts = tod[sess]
        for j in range(len(sess) - 1):
            if ts[j] < start or ts[j] > entry_by or not np.isfinite(sig[j]) or sig[j] <= 0:
                continue
            z = dev[j] / sig[j]
            if z >= k:        # stretched above VWAP -> short
                orders.append(dict(entry_bar=sess[j], dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="vwapfade")); break
            if z <= -k:       # stretched below -> long
                orders.append(dict(entry_bar=sess[j], dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="vwapfade")); break
    return orders

def orb_retest(df, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0, trail_R=3.0,
               open_min=16*60, retest_pts=5, max_wait=20, long_only=False):
    """Break the OR, then enter on the RETEST of the broken level (better fill/R)."""
    h, l = df["high"].values, df["low"].values
    tod = df["tod"].values
    orders = []
    or_end = open_min + or_min
    for day, gi in _day_groups(df).items():
        t = tod[gi]
        om = (t >= open_min) & (t < or_end)
        if om.sum() < 5:
            continue
        rh = h[gi[om]].max(); rl = l[gi[om]].min()
        post = gi[(t >= or_end) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        broke = 0  # +1 broke up, -1 broke down
        bbar = None
        for k, b in enumerate(post[:-1]):
            if broke == 0:
                if h[b] >= rh: broke, bbar = 1, k
                elif (not long_only) and l[b] <= rl: broke, bbar = -1, k
                continue
            if k - bbar > max_wait:
                break
            if broke == 1 and l[b] <= rh + retest_pts:     # retest of broken high
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="retest")); break
            if broke == -1 and h[b] >= rl - retest_pts:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="retest")); break
    return orders

REGISTRY = {"orb": orb, "or_fade": or_fade, "vwap_fade": vwap_fade, "orb_retest": orb_retest}
