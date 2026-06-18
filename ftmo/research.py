"""
Strategy research on real daily EURUSD/GBPUSD.
Everything measured in R-multiples (P&L / intended risk) so it is
currency-agnostic and feeds straight into the FTMO simulator + Monte Carlo.

Trade model (honest given daily-close data):
  - Signal decided on close[t]; trade entered at close[t] (+spread cost).
  - Exit at close[t+1]. No weekend holds -> no entries on Friday.
  - Stop distance = stop_mult * ATR(price). If the move against us at the
    exit close exceeds the stop, the loss is floored at -1R (stop fill,
    plus slippage already in costs). Upside capped only by the next close.
  - Round-turn cost applied in price terms (spread + slippage).
"""
import numpy as np
import pandas as pd

COST = {"EURUSD": 0.00012, "GBPUSD": 0.00016}  # ~1.2 / 1.6 pip round turn (conservative)

def atr(s, n=14):
    # daily-close proxy: ATR ~ rolling mean of |close-to-close| move
    d = s.diff().abs()
    return d.rolling(n).mean()

def load():
    df = pd.read_csv("ftmo/prices.csv", parse_dates=["Date"])
    df["dow"] = df["Date"].dt.dayofweek  # 0=Mon ... 4=Fri
    return df

def trade_R(entry, nxt, direction, stopdist, cost):
    """Return R-multiple for a one-day close-to-close trade."""
    raw = direction * (nxt - entry) - cost  # price units, cost always paid
    R = raw / stopdist
    return max(R, -1.0)  # stop floors loss at -1R

def backtest(df, signal_fn, stop_mult=1.5, atr_n=14):
    trades = []
    for pair in ("EURUSD", "GBPUSD"):
        s = df[pair].values
        a = atr(df[pair], atr_n).values
        sig = signal_fn(df, pair)  # array of -1/0/+1, decision at close[t]
        for t in range(len(df) - 1):
            if df["dow"].iloc[t] == 4:      # Friday -> would hold over weekend
                continue
            if not np.isfinite(a[t]) or a[t] <= 0:
                continue
            d = sig[t]
            if d == 0:
                continue
            stopdist = stop_mult * a[t]
            R = trade_R(s[t], s[t + 1], d, stopdist, COST[pair])
            trades.append({"i": t, "date": df["Date"].iloc[t], "pair": pair, "dir": d, "R": R})
    return pd.DataFrame(trades).sort_values("date").reset_index(drop=True)

def stats(tr, name):
    if len(tr) == 0:
        print(f"{name:28s} NO TRADES"); return None
    R = tr["R"].values
    wr = (R > 0).mean()
    exp = R.mean()
    pf = R[R > 0].sum() / (-R[R < 0].sum() + 1e-9)
    print(f"{name:28s} n={len(R):4d}  win={wr*100:5.1f}%  expR={exp:+.3f}  PF={pf:4.2f}  sumR={R.sum():7.1f}")
    return exp

# ---------- candidate signals ----------
def sig_donchian(df, pair, n=20):
    s = df[pair]
    hi = s.rolling(n).max(); lo = s.rolling(n).min()
    out = np.zeros(len(s))
    out[s >= hi.shift(1)] = 1
    out[s <= lo.shift(1)] = -1
    return out

def sig_sma_trend(df, pair, fast=10, slow=40):
    s = df[pair]
    f = s.rolling(fast).mean(); sl = s.rolling(slow).mean()
    return np.where(f > sl, 1, np.where(f < sl, -1, 0))

def sig_meanrev(df, pair, n=5, k=1.0):
    s = df[pair]
    ma = s.rolling(n).mean(); sd = s.rolling(n).std()
    z = (s - ma) / (sd + 1e-9)
    return np.where(z < -k, 1, np.where(z > k, -1, 0))

def sig_momentum(df, pair, n=3):
    s = df[pair]
    mom = s - s.shift(n)
    return np.where(mom > 0, 1, np.where(mom < 0, -1, 0))

if __name__ == "__main__":
    df = load()
    print(f"data: {df['Date'].min().date()} -> {df['Date'].max().date()}  bars={len(df)}\n")
    for sm in (1.0, 1.5, 2.0):
        print(f"--- stop_mult={sm} ---")
        stats(backtest(df, sig_donchian, sm), "donchian20 breakout")
        stats(backtest(df, sig_sma_trend, sm), "sma10/40 trend")
        stats(backtest(df, sig_meanrev, sm), "meanrev z5 k1")
        stats(backtest(df, sig_momentum, sm), "momentum 3d")
        print()
