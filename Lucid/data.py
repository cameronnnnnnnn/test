"""
Lucid/data.py — NQ/NAS100 M1 loader. Reuses the v4 NAS100 cache (the index tracks
NQ futures 1:1; 1 index point = 1 NQ point = $20/mini = $2/micro).

The compact .npz cache (nas_m1.npz) is copied in alongside this file, so load()
never re-parses the 1M-row raw CSV. RAW path is fixed only as a fallback.
"""
import os, csv, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(HERE, "..", "ftmo", "data_v2", "new_data", "1m_data - Copy.csv")
CACHE = os.path.join(HERE, "nas_m1.npz")

COLS = ["DateTime", "Open", "High", "Low", "Close", "Volume", "TickVolume"]

def _parse_raw():
    t0 = time.time()
    df = pd.read_csv(RAW, sep="\t", header=None, skiprows=1, names=COLS,
                     quoting=csv.QUOTE_NONE, dtype=str, engine="c")
    df["DateTime"]   = df["DateTime"].str.lstrip('"')
    df["TickVolume"] = df["TickVolume"].str.rstrip('"')
    dt = pd.to_datetime(df["DateTime"], format="%Y.%m.%d %H:%M:%S")
    out = pd.DataFrame({"open": df["Open"].astype("float32").values,
                        "high": df["High"].astype("float32").values,
                        "low":  df["Low"].astype("float32").values,
                        "close": df["Close"].astype("float32").values,
                        "tickvol": df["TickVolume"].astype("int32").values},
                       index=pd.DatetimeIndex(dt.values))
    out = out[~out.index.duplicated(keep="first")].sort_index()
    print(f"[parse] {len(out):,} bars in {time.time()-t0:.1f}s  {out.index[0]} -> {out.index[-1]}")
    return out

def _build_cache():
    df = _parse_raw()
    np.savez_compressed(CACHE, dt=df.index.values.astype("datetime64[s]"),
                        o=df["open"].values, h=df["high"].values,
                        l=df["low"].values, c=df["close"].values, v=df["tickvol"].values)
    print(f"[cache] wrote {CACHE} ({os.path.getsize(CACHE)/1e6:.1f} MB)")

def load():
    if not os.path.exists(CACHE):
        _build_cache()
    z = np.load(CACHE, allow_pickle=False)
    idx = pd.DatetimeIndex(z["dt"])
    df = pd.DataFrame({"open": z["o"], "high": z["h"], "low": z["l"],
                       "close": z["c"], "tickvol": z["v"]}, index=idx)
    df.index.name = "dt"
    return df

if __name__ == "__main__":
    df = load()
    print(f"{len(df):,} bars  {df.index[0]} -> {df.index[-1]}")
    print(f"price range {df['close'].min():.0f} -> {df['close'].max():.0f}")
