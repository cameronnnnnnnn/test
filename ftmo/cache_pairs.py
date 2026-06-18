"""Cache all 4 pairs' M1 to pickle (pair-aware) and build real daily bars."""
import pandas as pd, numpy as np

PAIRS = {
    "EURUSD": dict(pip=0.0001, point=0.00001),
    "GBPUSD": dict(pip=0.0001, point=0.00001),
    "AUDUSD": dict(pip=0.0001, point=0.00001),
    "USDJPY": dict(pip=0.01,   point=0.001),
}

daily = {}
for p, meta in PAIRS.items():
    df = pd.read_csv(f"ftmo/m1/{p}_M1_20210101_20260101.csv", sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df[["dt", "open", "high", "low", "close", "spread"]].sort_values("dt").reset_index(drop=True)
    df.to_pickle(f"ftmo/m1/{p}_m1.pkl")
    # liquid-hour median spread in pips
    h = df["dt"].dt.hour
    liq = df.loc[(h >= 7) & (h < 20), "spread"].median() * meta["point"] / meta["pip"]
    # real daily bars (server-day)
    s = df.set_index("dt")
    d = pd.DataFrame({
        "open": s["open"].resample("1D").first(),
        "high": s["high"].resample("1D").max(),
        "low":  s["low"].resample("1D").min(),
        "close":s["close"].resample("1D").last(),
    }).dropna()
    d["dow"] = d.index.dayofweek
    daily[p] = d
    print(f"{p}: m1={len(df)}  days={len(d)}  liq-spread={liq:.2f} pip  "
          f"range {d.index.min().date()}..{d.index.max().date()}")

# merge daily closes/oc into one frame keyed by date
out = None
for p, d in daily.items():
    dd = d[["open","high","low","close"]].copy()
    dd.columns = [f"{p}_{c}" for c in dd.columns]
    out = dd if out is None else out.join(dd, how="inner")
out = out.reset_index().rename(columns={"index":"dt","dt":"Date"})
out = out.rename(columns={out.columns[0]:"Date"})
out.to_pickle("ftmo/m1/daily_all.pkl")
print("\nmerged daily rows:", len(out), " cols:", len(out.columns))
print(out.head(2).to_string())
