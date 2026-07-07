"""
challengephaseHF/hf_strats.py — high-frequency, high-win-rate, low-RR (RR<1) setups plus
a few uncorrelated decorrelators, grounded in published SSRN intraday research:

  mean reversion / short-term reversal (Brogaard-Han-Kim 2024; Miwa; Bhatti regime-Z):
    mr_z    : fade z-score stretch from a fast EMA back toward it (tight TP, wide stop)
    revN    : fade after N consecutive same-direction M1 closes (short-term reversal)
    rsi2    : Connors RSI(2) oversold/overbought reversion
    bbfade  : Bollinger-band fade back to the middle band
  momentum (Gao-Han-Li-Zhou, Market Intraday Momentum, JFE 2018):
    mim     : trade the last part of the session in the sign of the first 30-min return
  gap (Liu-Liu-Wang-Zhou-Zhu, Overnight-Intraday Reversal):
    gaprev  : fade the overnight gap at the US open, target prior close
  session-open behaviour:
    orfade  : fade the first poke beyond the opening range

The mean-reversion setups are the low-RR/high-WR/high-frequency core. mim/gaprev/orfade
are there to DECORRELATE (momentum + gap + range fade win on different days). Each setup
holds at most one position at a time (a cooldown >= max_bars keeps trades sequential, so
the per-day intraday-low aggregation stays honest). Orders plug straight into ftmo/v4 engine.
"""
import os, sys
import numpy as np, pandas as pd
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S          # noqa: E402
from engine import ExitSpec           # noqa: E402

SESS_START = 16 * 60 + 30
SESS_END   = 22 * 60 + 55
WARM       = 30                        # minutes into the session before mean-reversion may fire


def prep_ind(df, ema_n=20, std_win=20, rsi_n=2, bb_win=20):
    c = df["close"].values.astype(float); h = df["high"].values.astype(float)
    l = df["low"].values.astype(float); v = df["tickvol"].values.astype(float)
    ema = pd.Series(c).ewm(span=ema_n, adjust=False).mean().values
    ret1 = np.concatenate([[0.0], np.diff(c)])
    rstd = pd.Series(ret1).rolling(std_win, min_periods=std_win).std().values
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (c - ema) / rstd
    up = np.where(ret1 > 0, ret1, 0.0); dn = np.where(ret1 < 0, -ret1, 0.0)
    ru = pd.Series(up).ewm(alpha=1.0 / rsi_n, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1.0 / rsi_n, adjust=False).mean().values
    with np.errstate(invalid="ignore", divide="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + ru / rd)
    sma = pd.Series(c).rolling(bb_win, min_periods=bb_win).mean().values
    bstd = pd.Series(c).rolling(bb_win, min_periods=bb_win).std().values
    # consecutive-close run length (signed)
    sgn = np.sign(ret1); run = np.zeros(len(c))
    for i in range(1, len(c)):
        run[i] = run[i-1] + sgn[i] if sgn[i] == sgn[i-1] and sgn[i] != 0 else sgn[i]
    # session vwap
    vwap = np.full(len(c), np.nan); tod = df["tod"].values
    for day, gi in df.groupby("date").indices.items():
        s = gi[(tod[gi] >= SESS_START) & (tod[gi] <= SESS_END)]
        if len(s) < 5: continue
        tp = (h[s] + l[s] + c[s]) / 3.0
        vwap[s] = np.cumsum(tp * v[s]) / (np.cumsum(v[s]) + 1e-9)
    return dict(c=c, h=h, l=l, ema=ema, z=z, rstd=rstd, rsi=rsi, sma=sma, bstd=bstd,
                run=run, vwap=vwap, ret1=ret1)


def _eod(df):
    tod = df["tod"].values; out = {}
    for day, gi in df.groupby("date").indices.items():
        s = gi[(tod[gi] >= SESS_START) & (tod[gi] <= SESS_END)]
        if len(s): out[day] = s[-1]
    return out


def _emit(df, sig_fn, tag, stop_pts, tp_R, cooldown, max_bars, be_R=0.0, trail_R=0.0,
          start=SESS_START + WARM, entry_by=22*60+30, long_only=False):
    """Generic driver: walk each session, call sig_fn(b)->+1/-1/0, honour a cooldown so
    at most one position is live at a time. sig_fn sees precomputed indicators via closure."""
    tod = df["tod"].values; eod = _eod(df); dates = df["date"].values
    orders = []
    spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=max_bars)
    for day, gi in df.groupby("date").indices.items():
        if day not in eod: continue
        sess = gi[(tod[gi] >= start) & (tod[gi] <= entry_by)]
        last_b = -10**9
        for b in sess:
            if b - last_b < cooldown: continue
            d = sig_fn(b)
            if d == 0 or (long_only and d < 0): continue
            orders.append(dict(entry_bar=b, dir=int(d), stop_pts=stop_pts, spec=spec,
                               eod_bar=eod[day], day=pd.Timestamp(day), tag=tag))
            last_b = b
    return orders


# ---------------- mean-reversion / reversal core (RR<1, high WR, high freq) ----------------
def mr_z(df, IND, k=2.0, stop_pts=40, tp_R=0.5, cooldown=20, max_bars=25):
    z = IND["z"]
    def sig(b):
        zz = z[b]
        if not np.isfinite(zz): return 0
        if zz >= k: return -1          # stretched above EMA -> fade short
        if zz <= -k: return 1          # stretched below -> fade long
        return 0
    return _emit(df, sig, "mr_z", stop_pts, tp_R, cooldown, max_bars)


def revN(df, IND, n=3, stop_pts=35, tp_R=0.5, cooldown=10, max_bars=18):
    run = IND["run"]
    def sig(b):
        if run[b] <= -n: return 1      # n down closes -> buy the bounce
        if run[b] >= n:  return -1     # n up closes -> fade
        return 0
    return _emit(df, sig, "revN", stop_pts, tp_R, cooldown, max_bars)


def rsi2(df, IND, lo=5.0, hi=95.0, stop_pts=40, tp_R=0.5, cooldown=20, max_bars=30):
    rsi = IND["rsi"]
    def sig(b):
        r = rsi[b]
        if not np.isfinite(r): return 0
        if r <= lo: return 1
        if r >= hi: return -1
        return 0
    return _emit(df, sig, "rsi2", stop_pts, tp_R, cooldown, max_bars)


def bbfade(df, IND, k=2.0, stop_pts=40, tp_R=0.5, cooldown=20, max_bars=30):
    c, sma, bstd = IND["c"], IND["sma"], IND["bstd"]
    def sig(b):
        if not np.isfinite(bstd[b]) or bstd[b] <= 0: return 0
        if c[b] >= sma[b] + k*bstd[b]: return -1
        if c[b] <= sma[b] - k*bstd[b]: return 1
        return 0
    return _emit(df, sig, "bbfade", stop_pts, tp_R, cooldown, max_bars)


# ---------------- decorrelators ----------------
def mim(df, first_min=30, trade_from=21*60+30, stop_pts=50, tp_R=1.0, thresh_pts=8.0):
    """Market Intraday Momentum (Gao et al): sign of the first `first_min` session return
    -> one trade in the last part of the session, same direction. Once/day, RR ~1."""
    o = df["open"].values; c = df["close"].values; tod = df["tod"].values
    eod = _eod(df); orders = []
    spec = ExitSpec(tp_R=tp_R, be_R=0.0, trail_R=0.0, max_bars=10**9)
    for day, gi in df.groupby("date").indices.items():
        if day not in eod: continue
        first = gi[(tod[gi] >= SESS_START) & (tod[gi] < SESS_START + first_min)]
        post = gi[(tod[gi] >= trade_from) & (tod[gi] <= SESS_END)]
        if len(first) < 5 or len(post) < 3: continue
        r = c[first[-1]] - o[first[0]]
        if abs(r) < thresh_pts: continue
        d = 1 if r > 0 else -1
        orders.append(dict(entry_bar=post[0], dir=d, stop_pts=stop_pts, spec=spec,
                           eod_bar=post[-1], day=pd.Timestamp(day), tag="mim"))
    return orders


def gaprev(df, gap_pts=15.0, stop_pts=50, tp_R=1.0, entry_by=17*60):
    """Overnight-Intraday Reversal (Liu et al): fade the open gap vs prior session close."""
    o = df["open"].values; c = df["close"].values; tod = df["tod"].values
    groups = list(df.groupby("date").indices.items()); eod = _eod(df); orders = []
    spec = ExitSpec(tp_R=tp_R, be_R=0.0, trail_R=0.0, max_bars=10**9)
    for k in range(1, len(groups)):
        day, gi = groups[k]
        if day not in eod: continue
        prevday, pgi = groups[k-1]
        psess = pgi[(tod[pgi] >= SESS_START) & (tod[pgi] <= SESS_END)]
        sess = gi[(tod[gi] >= SESS_START) & (tod[gi] <= entry_by)]
        if len(psess) < 5 or len(sess) < 3: continue
        prev_close = c[psess[-1]]; opn = o[sess[0]]
        gap = opn - prev_close
        if abs(gap) < gap_pts: continue
        d = -1 if gap > 0 else 1        # gap up -> short back, gap down -> long
        orders.append(dict(entry_bar=sess[0], dir=d, stop_pts=stop_pts, spec=spec,
                           eod_bar=eod[day], day=pd.Timestamp(day), tag="gaprev"))
    return orders


def orfade(df, or_min=15, poke_pts=12, stop_pts=35, tp_R=0.6, cooldown=25, max_bars=30):
    """Fade the first poke beyond the opening range (failed-breakout reversal)."""
    h, l = df["high"].values, df["low"].values; tod = df["tod"].values
    eod = _eod(df); orders = []; or_end = SESS_START + or_min
    spec = ExitSpec(tp_R=tp_R, be_R=0.0, trail_R=0.0, max_bars=max_bars)
    for day, gi in df.groupby("date").indices.items():
        if day not in eod: continue
        om = gi[(tod[gi] >= SESS_START) & (tod[gi] < or_end)]
        if len(om) < 5: continue
        rh = h[om].max(); rl = l[om].min()
        post = gi[(tod[gi] >= or_end) & (tod[gi] <= 21*60)]
        for b in post:
            if h[b] >= rh + poke_pts:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod[day], day=pd.Timestamp(day), tag="orfade")); break
            if l[b] <= rl - poke_pts:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod[day], day=pd.Timestamp(day), tag="orfade")); break
    return orders


REGISTRY = {"mr_z": mr_z, "revN": revN, "rsi2": rsi2, "bbfade": bbfade,
            "mim": mim, "gaprev": gaprev, "orfade": orfade}

if __name__ == "__main__":
    df = S.prep(data.load()); IND = prep_ind(df); ndays = df["date"].nunique()
    import engine
    print(f"{'strat':8} {'trades':>7} {'/day':>6} {'WR':>6} {'avgRR(win/loss)':>16} {'expR':>7} {'PF':>5}")
    for nm, fn in REGISTRY.items():
        orders = fn(df, IND) if nm in ("mr_z","revN","rsi2","bbfade") else fn(df)
        tr = engine.simulate(df, orders, cost_pts=2.0)
        if not len(tr): print(f"{nm:8} no trades"); continue
        es = engine.edge_stats(tr)
        rr = abs(es["avg_win"]/es["avg_loss"]) if es["avg_loss"] else 0
        print(f"{nm:8} {es['n']:7d} {es['n']/ndays:5.1f} {es['wr']*100:5.1f}% "
              f"{rr:15.2f} {es['expR']:+.3f} {es['pf']:5.2f}")
