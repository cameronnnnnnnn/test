"""
challengephaseHF/fx_data.py — loader for the forex M1 data (EURUSD/GBPUSD/AUDUSD/USDJPY,
2021-2026, MT5 tab-separated export). Parses to the same OHLC+tickvol frame the NAS100
strategies expect, caches to .npz (gitignored). Also audits each: span, session/timezone
profile (hourly tick-volume), and daily ATR in PRICE units so stops can be scaled per
instrument (a NAS100 "50pt" stop makes no sense on EURUSD at 1.22). Run: python3 fx_data.py
"""
import os, csv, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FXDIR = os.path.normpath(os.path.join(HERE, "..", "ftmo", "data_fx"))
INSTR = {"EURUSD": "EURUSD_M1_20210101_20260101.csv",
         "GBPUSD": "GBPUSD_M1_20210101_20260101.csv",
         "AUDUSD": "AUDUSD_M1_20210101_20260101.csv",
         "USDJPY": "USDJPY_M1_20210101_20260101.csv"}
COLS = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL", "VOL", "SPREAD"]


def _parse(path):
    t0 = time.time()
    df = pd.read_csv(path, sep="\t", header=0, names=COLS, quoting=csv.QUOTE_NONE,
                     dtype={"DATE": str, "TIME": str}, engine="c")
    dt = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
    out = pd.DataFrame({"open": df["OPEN"].astype("float64").values,
                        "high": df["HIGH"].astype("float64").values,
                        "low":  df["LOW"].astype("float64").values,
                        "close": df["CLOSE"].astype("float64").values,
                        "tickvol": df["TICKVOL"].astype("int32").values,
                        "spread": df["SPREAD"].astype("int32").values},
                       index=pd.DatetimeIndex(dt.values))
    out = out[~out.index.duplicated(keep="first")].sort_index()
    print(f"[parse] {os.path.basename(path)}: {len(out):,} bars in {time.time()-t0:.0f}s")
    return out


def load(instr):
    cache = os.path.join(HERE, f"fx_{instr}.npz")
    if not os.path.exists(cache):
        df = _parse(os.path.join(FXDIR, INSTR[instr]))
        np.savez_compressed(cache, dt=df.index.values.astype("datetime64[s]"),
                            o=df["open"].values, h=df["high"].values, l=df["low"].values,
                            c=df["close"].values, v=df["tickvol"].values, s=df["spread"].values)
    z = np.load(cache, allow_pickle=False)
    return pd.DataFrame({"open": z["o"], "high": z["h"], "low": z["l"], "close": z["c"],
                         "tickvol": z["v"], "spread": z["s"]},
                        index=pd.DatetimeIndex(z["dt"]))


def daily_atr_price(df, n=14):
    g = df.groupby(df.index.normalize()).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g["c"].shift(1)
    tr = np.maximum(g["h"]-g["l"], np.maximum((g["h"]-pc).abs(), (g["l"]-pc).abs()))
    return tr.rolling(n, min_periods=5).mean().median()


if __name__ == "__main__":
    for instr in INSTR:
        df = load(instr)
        pip = 0.01 if instr.endswith("JPY") else 0.0001
        atr = daily_atr_price(df)
        hourly = df.groupby(df.index.hour)["tickvol"].mean()
        peak = int(hourly.idxmax()); quiet = int(hourly.idxmin())
        print(f"\n{instr}: {len(df):,} bars  {df.index[0].date()} -> {df.index[-1].date()}  "
              f"price ~{df['close'].iloc[-1]:.4f}")
        print(f"   daily ATR ~{atr:.5f} ({atr/pip:.0f} pips)   median spread {df['spread'].median():.0f} pts")
        print(f"   busiest hour {peak:02d}:00  quietest {quiet:02d}:00 (server time -> infers session/tz)")
