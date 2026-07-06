"""
Load & clean NAS100 M1 data for the Topstep Combine study.

Key facts established in Phase 0:
- File is tab-separated: DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD
- Timestamps are broker/server time (MT "GMT+2/+3", US-DST-aligned).
  The daily maintenance break sits ALWAYS in the server 00:00 hour, which is
  the CME equity-index break 16:00-17:00 CT. => CT = server_time - 8h (fixed).
- True 1-minute data begins 2019-08-12 (earlier rows are daily then hourly).

Output: data/clean_m1_ct.parquet with a CT (Chicago) DatetimeIndex.
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RAW = DATA / "NAS100_M1_20190101_20260101.csv"
OUT = DATA / "clean_m1_ct.parquet"

SERVER_TO_CT_HOURS = -8  # CT = server - 8h (year-round; broker follows US DST)
M1_START = "2019-08-13"  # first full day of true 1-min data


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(
        RAW, sep="\t",
        names=["date", "time", "open", "high", "low", "close",
               "tickvol", "vol", "spread"],
        header=0,
        dtype={"date": str, "time": str},
    )
    ts_server = pd.to_datetime(df["date"] + " " + df["time"],
                               format="%Y.%m.%d %H:%M:%S")
    df["ts_ct"] = ts_server + pd.Timedelta(hours=SERVER_TO_CT_HOURS)
    df = df[["ts_ct", "open", "high", "low", "close", "tickvol", "spread"]]
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("ts_ct").reset_index(drop=True)
    # keep only true M1 era
    df = df[df["ts_ct"] >= pd.Timestamp(M1_START)].copy()
    # drop exact duplicate timestamps (keep last)
    dupes = df["ts_ct"].duplicated().sum()
    df = df.drop_duplicates("ts_ct", keep="last")
    # basic sanity: high>=max(o,c), low<=min(o,c)
    bad = ((df["high"] < df[["open", "close"]].max(axis=1)) |
           (df["low"] > df[["open", "close"]].min(axis=1)))
    df = df[~bad].copy()
    df = df.set_index("ts_ct")
    # derived time fields (CT)
    df["date"] = df.index.normalize()          # calendar date in CT
    df["dow"] = df.index.dayofweek             # 0=Mon .. 6=Sun
    df["minute_of_day"] = df.index.hour * 60 + df.index.minute
    print(f"[clean] dropped {dupes} duplicate timestamps, {bad.sum()} bad OHLC bars")
    return df


def diagnostics(df: pd.DataFrame):
    print("=" * 70)
    print(f"Rows: {len(df):,}")
    print(f"Date range (CT): {df.index.min()}  ->  {df.index.max()}")
    yrs = (df.index.max() - df.index.min()).days / 365.25
    print(f"Span: {yrs:.2f} years")
    # bars per CT hour (should show a break; NQ RTH is 08:30-15:00 CT)
    by_hour = df.groupby(df.index.hour).size()
    print("Bars per CT hour:")
    for h in range(24):
        print(f"  {h:02d}:00  {by_hour.get(h,0):>8,}")
    # trading days
    ndays = df["date"].nunique()
    print(f"Distinct CT calendar days: {ndays:,}")
    # RTH coverage check: bars in 08:30-15:00 CT window per day
    rth = df[(df["minute_of_day"] >= 8*60+30) & (df["minute_of_day"] < 15*60)]
    print(f"RTH (08:30-15:00 CT) bars: {len(rth):,}; "
          f"avg per day: {len(rth)/max(rth['date'].nunique(),1):.1f} (max 390)")
    # gap detection: minute deltas within RTH
    return


def main():
    df = load_raw()
    df = clean(df)
    diagnostics(df)
    df.to_parquet(OUT)
    print(f"[saved] {OUT}  ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
