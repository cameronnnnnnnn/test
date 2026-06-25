"""
v3/data_xau.py — XAUUSD (Gold) M1 loader. Format differs from NAS: tab-separated,
NO wrapping quotes, columns Date/Open/High/Low/Close/Volume, datetime '%Y.%m.%d %H:%M'
(no seconds). 12 split files spanning ~2004-2026. Cached to npz.
"""
import os, glob, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_GLOB = os.path.join(HERE, "..", "data_v3", "*", "*", "XAU_1m_data_*.tsv")
CACHE = os.path.join(HERE, "xau_m1.npz")
COLS = ["Date", "Open", "High", "Low", "Close", "Volume"]

def _parse():
    files = glob.glob(RAW_GLOB)
    files.sort(key=lambda p: int(os.path.basename(p).split("_")[-1].split(".")[0]))
    t0 = time.time(); parts = []
    for f in files:
        d = pd.read_csv(f, sep="\t", header=0, names=COLS, dtype=str, engine="c")
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    dt = pd.to_datetime(df["Date"], format="%Y.%m.%d %H:%M", errors="coerce")
    out = pd.DataFrame({"open": df["Open"].astype("float32").values,
                        "high": df["High"].astype("float32").values,
                        "low":  df["Low"].astype("float32").values,
                        "close": df["Close"].astype("float32").values,
                        "tickvol": pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype("int32").values},
                       index=pd.DatetimeIndex(dt.values))
    out = out[~out.index.isna()]
    out = out[~out.index.duplicated(keep="first")].sort_index()
    print(f"[xau] {len(out):,} bars in {time.time()-t0:.1f}s  {out.index[0]} -> {out.index[-1]}")
    return out

def _build_cache():
    df = _parse()
    np.savez_compressed(CACHE, dt=df.index.values.astype("datetime64[s]"),
                        o=df["open"].values, h=df["high"].values, l=df["low"].values,
                        c=df["close"].values, v=df["tickvol"].values)
    print(f"[xau] cache {CACHE} ({os.path.getsize(CACHE)/1e6:.1f} MB)")

def load(since=None):
    if not os.path.exists(CACHE):
        _build_cache()
    z = np.load(CACHE)
    idx = pd.DatetimeIndex(z["dt"])
    df = pd.DataFrame({"open": z["o"], "high": z["h"], "low": z["l"],
                       "close": z["c"], "tickvol": z["v"]}, index=idx)
    df.index.name = "dt"
    if since:
        df = df[df.index >= pd.Timestamp(since)]
    return df

def audit(df):
    print("="*64); print("XAU AUDIT"); print("="*64)
    print(f"rows {len(df):,}  span {df.index[0]} -> {df.index[-1]}")
    print(f"price {df['close'].min():.1f} -> {df['close'].max():.1f}")
    deltas = (df.index.to_series().diff().dropna().dt.total_seconds()//60).astype(int)
    print(f"1-min bars: {(deltas==1).mean()*100:.1f}%   gaps>1: {(deltas>1).sum():,}")
    wd = pd.Series(df.index.dayofweek).value_counts().sort_index()
    print("weekday bars: " + " ".join(f"{['M','T','W','T','F','S','S'][i]}={wd.get(i,0)//1000}k" for i in range(7)))
    hourly = df.groupby(df.index.hour)["tickvol"].mean()
    peak = hourly.idxmax()
    print(f"vol by hour (peak={peak:02d}:00) — gold most active ~London/NY overlap:")
    mx = hourly.max()
    for h in range(24):
        print(f"  {h:02d} {'#'*int(round(hourly.get(h,0)/mx*40))}")

if __name__ == "__main__":
    audit(load())
