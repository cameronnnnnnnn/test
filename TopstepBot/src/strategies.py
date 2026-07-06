"""
Strategy families. Each exposes .signals(day) -> (signals, size, stop_pts, target_pts)
aligned to the `day` DataFrame (RTH+pad bars for one CT date).

All indicators are CAUSAL: a signal on bar i's close is executed at bar i+1's
open by the engine. Nothing uses future bars.
"""
import numpy as np
import pandas as pd

RTH_OPEN = 8 * 60 + 30
RTH_CLOSE = 15 * 60


def build_regime(df, sma_n=50, mode="long_flat"):
    """Causal daily trend regime from RTH closes.
    regime[date] in {+1, -1, 0}, computed from PRIOR completed days only.
    Signal: prev RTH close vs SMA_n of prior RTH closes.
    mode: 'long_flat' -> {+1 uptrend, 0 downtrend}; 'both' -> {+1,-1}.
    """
    rth = df[(df["minute_of_day"] >= RTH_OPEN) & (df["minute_of_day"] < RTH_CLOSE)]
    daily_close = rth.groupby("date")["close"].last().sort_index()
    sma = daily_close.rolling(sma_n).mean()
    # shift(1): today's decision uses only data through YESTERDAY's close
    raw = np.sign(daily_close.shift(1) - sma.shift(1))
    if mode == "long_flat":
        reg = raw.clip(lower=0)          # +1 or 0
    else:
        reg = raw                        # +1 or -1 (0 -> flat)
    return reg.fillna(0).astype(int)


class TrendSession:
    """Enter at the RTH open in the direction of the causal daily trend regime,
    protective stop, optional profit target, forced flat by cutoff.
    Captures the intraday drift only when the regime agrees -> sidesteps bear
    regimes (e.g. 2022) that sink naive long-only capture.
    """
    def __init__(self, regime_by_date, stop_pts=40.0, target_pts=None, qty=10,
                 entry_min=RTH_OPEN, last_entry=RTH_OPEN + 1):
        self.regime_by_date = regime_by_date
        self.stop_pts = stop_pts
        self.target_pts = target_pts
        self.qty = qty
        self.entry_min = entry_min
        self.last_entry = last_entry

    def signals(self, day):
        mod = day["minute_of_day"].values
        n = len(day)
        sig = np.zeros(n); size = np.zeros(n)
        date = day["date"].iloc[0]
        reg = int(self.regime_by_date.get(date, 0))
        if reg == 0:
            return sig, size, self.stop_pts, self.stop_pts
        # fire on the bar whose close is just before entry_min so engine enters
        # at the entry_min bar's open (causal)
        cand = np.where((mod >= self.entry_min - 1) & (mod < self.last_entry))[0]
        if len(cand) == 0:
            return sig, size, self.stop_pts, self.stop_pts
        i = cand[0]
        sig[i] = reg; size[i] = self.qty
        tgt = self.target_pts if self.target_pts is not None else self.stop_pts * 1000
        return sig, size, self.stop_pts, tgt

    def __repr__(self):
        return (f"TrendSession(stop={self.stop_pts},target={self.target_pts},"
                f"qty={self.qty})")


class OpeningRangeBreakout:
    """Break of the first `or_min` minutes' range after the RTH open.
    Economic rationale: overnight information + open auction imbalance tends to
    resolve directionally in the first part of the session. One entry/day.
    """
    def __init__(self, or_min=15, stop_pts=25.0, target_R=1.0, qty=5,
                 session_start=8 * 60 + 30, last_entry=13 * 60,
                 direction="both"):
        self.or_min = or_min
        self.stop_pts = stop_pts
        self.target_R = target_R
        self.qty = qty
        self.session_start = session_start
        self.last_entry = last_entry
        self.direction = direction

    def signals(self, day):
        mod = day["minute_of_day"].values
        c = day["close"].values
        h = day["high"].values
        l = day["low"].values
        n = len(day)
        sig = np.zeros(n)
        size = np.zeros(n)
        or_mask = (mod >= self.session_start) & (mod < self.session_start + self.or_min)
        if or_mask.sum() < 2:
            return sig, size, self.stop_pts, self.stop_pts * self.target_R
        or_hi = h[or_mask].max()
        or_lo = l[or_mask].min()
        fired = False
        for i in range(n):
            if fired:
                break
            if mod[i] < self.session_start + self.or_min:
                continue
            if mod[i] > self.last_entry:
                break
            if self.direction in ("both", "long") and c[i] > or_hi:
                sig[i] = 1; size[i] = self.qty; fired = True
            elif self.direction in ("both", "short") and c[i] < or_lo:
                sig[i] = -1; size[i] = self.qty; fired = True
        return sig, size, self.stop_pts, self.stop_pts * self.target_R
