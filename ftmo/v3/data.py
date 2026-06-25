"""
v2/data.py — NAS100 (US100) M1 loader, cache, and audit.

Raw file: tab-separated values wrapped in double-quotes, REVERSE-chronological,
columns: DateTime, Open, High, Low, Close, Volume(=0), TickVolume.
Timestamps are FTMO MT5 server time (to be confirmed by the volume profile).

We cache to a compact .npz (int64 epoch-minutes + float32 OHLC + int32 tickvol)
so the 1.04M-row parse only happens once.
"""
import os, csv, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data_v2")           # raw lives under ftmo/data_v2
RAW  = os.path.join(DATA, "new_data", "1m_data - Copy.csv")
CACHE = os.path.join(HERE, "nas_m1.npz")             # cache local to v2 (gitignored)

COLS = ["DateTime", "Open", "High", "Low", "Close", "Volume", "TickVolume"]

def _parse_raw():
    t0 = time.time()
    df = pd.read_csv(RAW, sep="\t", header=None, skiprows=1, names=COLS,
                     quoting=csv.QUOTE_NONE, dtype=str, engine="c")
    # strip the wrapping quotes that sit on the first and last fields
    df["DateTime"]   = df["DateTime"].str.lstrip('"')
    df["TickVolume"] = df["TickVolume"].str.rstrip('"')
    dt = pd.to_datetime(df["DateTime"], format="%Y.%m.%d %H:%M:%S")
    # NOTE: use .values so positional data is not reindexed against the datetime labels
    out = pd.DataFrame({"open": df["Open"].astype("float32").values,
                        "high": df["High"].astype("float32").values,
                        "low":  df["Low"].astype("float32").values,
                        "close": df["Close"].astype("float32").values,
                        "tickvol": df["TickVolume"].astype("int32").values},
                       index=pd.DatetimeIndex(dt.values))
    out = out[~out.index.duplicated(keep="first")].sort_index()  # ascending, de-dup
    print(f"[parse] {len(out):,} bars in {time.time()-t0:.1f}s  "
          f"{out.index[0]} -> {out.index[-1]}")
    return out

def _build_cache():
    df = _parse_raw()
    np.savez_compressed(CACHE, dt=df.index.values.astype("datetime64[s]"),
                        o=df["open"].values, h=df["high"].values,
                        l=df["low"].values, c=df["close"].values,
                        v=df["tickvol"].values)
    print(f"[cache] wrote {CACHE} ({os.path.getsize(CACHE)/1e6:.1f} MB)")

def load():
    """Return a DataFrame indexed by tz-naive server-time datetime."""
    if not os.path.exists(CACHE):
        _build_cache()
    z = np.load(CACHE, allow_pickle=False)
    idx = pd.DatetimeIndex(z["dt"])
    df = pd.DataFrame({"open": z["o"], "high": z["h"], "low": z["l"],
                       "close": z["c"], "tickvol": z["v"]}, index=idx)
    df.index.name = "dt"
    return df

def audit(df):
    print("\n" + "=" * 70)
    print("DATA AUDIT")
    print("=" * 70)
    print(f"rows           : {len(df):,}")
    print(f"span           : {df.index[0]}  ->  {df.index[-1]}")
    print(f"price range    : {df['close'].min():.1f}  ->  {df['close'].max():.1f}")
    # spacing (unit-safe via pandas)
    deltas = (df.index.to_series().diff().dropna().dt.total_seconds() // 60).astype(int).values
    n1 = int((deltas == 1).sum())
    print(f"1-min bars     : {n1:,} ({100*n1/len(deltas):.1f}%)")
    gaps = deltas[deltas > 1]
    print(f"gaps (>1min)   : {len(gaps):,}  median {np.median(gaps):.0f}m  "
          f"max {gaps.max():.0f}m ({gaps.max()/60:.0f}h)")
    # weekday coverage
    wd = pd.Series(df.index.dayofweek).value_counts().sort_index()
    names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    print("weekday bars   : " + "  ".join(f"{names[i]}={wd.get(i,0)//1000}k" for i in range(7)))
    # hour-of-day tick-volume profile -> locate US cash open / confirm TZ
    hourly = df.groupby(df.index.hour)["tickvol"].mean()
    peak = hourly.idxmax()
    print("\nAvg tick-vol by SERVER hour (US cash open should spike ~16-17 if EET/EEST):")
    bars = hourly / hourly.max()
    for hh in range(24):
        b = "#" * int(round(bars.get(hh, 0) * 40))
        mark = "  <== PEAK" if hh == peak else ""
        print(f"  {hh:02d}:00  {hourly.get(hh,0):6.0f}  {b}{mark}")
    print(f"\nPeak volume hour = {peak:02d}:00 server.")

if __name__ == "__main__":
    df = load()
    audit(df)
