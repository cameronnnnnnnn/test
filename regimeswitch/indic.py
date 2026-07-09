"""
regimeswitch/indic.py — regime-detection indicators (ADX, Choppiness Index, ATR, EMA slope),
computed on DAILY bars aggregated from the NAS100 M1 data and SHIFTED one day so a day's
regime label uses only prior completed days (no look-ahead). Also an intraday choppiness of
the first N minutes of a session (a within-day, still-causal read of how the open is behaving).

Standard readings: ADX>25 trending / <20 weak-ranging; Choppiness>61.8 choppy-consolidation /
<38.2 strong-trend. These are the exact tools the "88%" regime-switch EAs use.
"""
import numpy as np, pandas as pd


def daily_bars(df):
    """df: M1 frame with a 'date' column (from strategies.prep). -> daily OHLC frame."""
    g = df.groupby("date").agg(o=("open", "first"), h=("high", "max"),
                               l=("low", "min"), c=("close", "last"))
    return g


def _tr(d):
    pc = d["c"].shift(1)
    return np.maximum(d["h"] - d["l"], np.maximum((d["h"] - pc).abs(), (d["l"] - pc).abs()))


def adx(d, n=14):
    """Wilder ADX + directional indices on daily bars."""
    up = d["h"].diff(); dn = -d["l"].diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=d.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=d.index)
    tr = _tr(d)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / atr
    mdi = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi


def choppiness(d, n=14):
    """Choppiness Index on daily bars (high=choppy/range, low=trend)."""
    tr = _tr(d)
    atrsum = tr.rolling(n).sum()
    rng = d["h"].rolling(n).max() - d["l"].rolling(n).min()
    return 100 * np.log10(atrsum / rng) / np.log10(n)


def daily_features(df):
    """Per-date regime features, SHIFTED 1 day (causal). Returns a DataFrame indexed by date
    with adx, +di, -di, chop, ema_slope (all 'as known at the open of that day')."""
    d = daily_bars(df)
    a, pdi, mdi = adx(d)
    ci = choppiness(d)
    ema = d["c"].ewm(span=20, adjust=False).mean()
    slope = (ema - ema.shift(5)) / ema.shift(5)
    feats = pd.DataFrame({"adx": a, "pdi": pdi, "mdi": mdi, "chop": ci, "slope": slope}, index=d.index)
    return feats.shift(1)          # only prior days inform today


def intraday_chop(df, start_min, win_min=60, n=14):
    """Choppiness of the first win_min minutes of the session (>= start_min), per date. Causal
    within the day: only uses bars up to start_min+win_min, decision made after. -> {date: CI}."""
    tod = df["tod"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    out = {}
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        w = gi[(t >= start_min) & (t < start_min + win_min)]
        if len(w) < n + 2:
            continue
        hh, ll, cc = h[w], l[w], c[w]
        pc = np.concatenate([[cc[0]], cc[:-1]])
        tr = np.maximum(hh - ll, np.maximum(np.abs(hh - pc), np.abs(ll - pc)))
        atrsum = tr[-n:].sum()
        rng = hh[-n:].max() - ll[-n:].min()
        if rng > 0 and atrsum > 0:
            out[day] = 100 * np.log10(atrsum / rng) / np.log10(n)
    return out
