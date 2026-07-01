"""
challengephasev3/garch.py — GARCH(1,1) conditional-volatility DAY FILTER for NAS100.

Idea the user asked for: only trade on higher-volatility/-volume days. Volatility
CLUSTERS (calm follows calm, wild follows wild), and GARCH(1,1) is the standard model
of that: sigma^2_t = omega + alpha*r^2_{t-1} + beta*sigma^2_{t-1}. We fit it on daily
close-to-close returns using ONLY past data (rolling window, refit every day), take the
1-step-ahead conditional-vol forecast for each session, and rank days by it. That rank
is decided at the OPEN from prior data -> look-ahead-free -> a legitimate "trade today?"
switch. We also keep a plain daily-VOLUME rank as a cross-check (vol and volume co-move).

Caches per-date forecasts to garch_cache.npz. Also prints a VALIDATION: does forecast
vol actually predict realized vol, and does the base ORB+VWpull combo have more edge on
high-forecast-vol days? (If not, the whole filter is worthless and we say so.)

Run: python3 garch.py
"""
import os, sys, time
import numpy as np
import pandas as pd

V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data as _data, strategies as _S            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "garch_cache.npz")
WIN = 500          # rolling window (trading days) for each GARCH refit
MIN_HIST = 150     # need at least this much history before we forecast


def daily_frame(df):
    """Per-date close-to-close return (%) and session tick-volume."""
    g = df.groupby("date").agg(c=("close", "last"), v=("tickvol", "sum"))
    g["ret"] = g["c"].pct_change() * 100.0
    # realized intraday vol proxy: std of M1 close returns within the session (for validation)
    rv = df.groupby("date")["close"].apply(lambda s: np.std(np.diff(np.log(s.values)))*np.sqrt(len(s))*100
                                           if len(s) > 5 else np.nan)
    g["rv"] = rv
    return g.dropna(subset=["ret"])


def compute(df, force=False):
    """Return DataFrame indexed by date with: sigma_fc (GARCH 1-step vol forecast),
    rv (realized), vol (session volume). Look-ahead-free. Cached."""
    g = daily_frame(df)
    dates = g.index.values
    if os.path.exists(CACHE) and not force:
        z = np.load(CACHE, allow_pickle=True)
        if len(z["dates"]) == len(dates) and (z["dates"] == dates.astype("datetime64[ns]")).all():
            return pd.DataFrame({"sigma_fc": z["sigma_fc"], "rv": g["rv"].values,
                                 "vol": g["v"].values}, index=g.index)
    from arch import arch_model
    r = g["ret"].values.astype(float)
    n = len(r)
    sig = np.full(n, np.nan)
    t0 = time.time()
    for t in range(MIN_HIST, n):
        lo = max(0, t - WIN)
        try:
            am = arch_model(r[lo:t], vol="Garch", p=1, q=1, mean="Constant", dist="normal", rescale=False)
            res = am.fit(disp="off", show_warning=False)
            fc = res.forecast(horizon=1, reindex=False)
            sig[t] = float(np.sqrt(fc.variance.values[-1, 0]))
        except Exception:
            sig[t] = np.nan
        if (t - MIN_HIST) % 150 == 0:
            print(f"  GARCH fit {t}/{n}  ({time.time()-t0:.0f}s)")
    np.savez_compressed(CACHE, dates=dates.astype("datetime64[ns]"), sigma_fc=sig)
    print(f"[garch] cached {CACHE}  ({time.time()-t0:.0f}s total)")
    return pd.DataFrame({"sigma_fc": sig, "rv": g["rv"].values, "vol": g["v"].values}, index=g.index)


def regime(df, key="sigma_fc", win=60):
    """Look-ahead-free day rank in [0,1]: percentile of today's forecast within the
    TRAILING `win` days (so 'high vol' is decided only from the past). Returns
    {date(normalized): pct in [0,1]}. NaN early days -> 0.5 (neutral)."""
    g = compute(df)
    x = g[key].values.astype(float)
    pct = np.full(len(x), np.nan)
    for i in range(len(x)):
        lo = max(0, i - win)
        hist = x[lo:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) >= 20 and np.isfinite(x[i]):
            pct[i] = (hist < x[i]).mean()
    pct = np.where(np.isfinite(pct), pct, 0.5)
    return {pd.Timestamp(d).normalize(): float(p) for d, p in zip(g.index.values, pct)}


def _validate(df):
    import engine
    g = compute(df)
    v = g.dropna(subset=["sigma_fc", "rv"])
    # (1) does forecast vol predict realized vol? (Spearman-ish via rank corr)
    fr = pd.Series(v["sigma_fc"]).rank(); rr = pd.Series(v["rv"].values).rank()
    rho = np.corrcoef(fr, rr)[0, 1]
    print("=" * 82)
    print("GARCH VALIDATION")
    print("=" * 82)
    print(f"  forecast-vol vs realized-vol rank corr : {rho:+.3f}  (positive => forecast has signal)")
    # (2) base combo edge on high vs low forecast-vol days
    o = (_S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True)
         + _S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0))
    tr = engine.simulate(df, o, cost_pts=2.0)
    reg = regime(df)
    tr = tr.assign(pct=tr["day"].map(lambda d: reg.get(pd.Timestamp(d).normalize(), 0.5)))
    print("  base ORB+VWpull edge by forecast-vol tercile (trailing rank):")
    for lbl, lo, hi in [("LOW  vol (<33%)", 0.0, 1/3), ("MID  vol", 1/3, 2/3), ("HIGH vol (>67%)", 2/3, 1.01)]:
        s = tr[(tr["pct"] >= lo) & (tr["pct"] < hi)]
        if len(s):
            wr = (s["R"] > 0).mean(); exp = s["R"].mean()
            print(f"     {lbl:16s}: n={len(s):4d}  WR={wr*100:4.1f}%  expR={exp:+.3f}")
    print("  -> if HIGH-vol expR clearly beats LOW-vol, the GARCH day filter is worth using.")


if __name__ == "__main__":
    df = _S.prep(_data.load())
    _validate(df)
