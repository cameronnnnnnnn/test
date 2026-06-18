import pandas as pd, numpy as np
C = "ftmo/m1/EURUSD_M1_20210101_20260101.csv"
df = pd.read_csv(C, sep="\t")
df.columns = [c.strip("<>").lower() for c in df.columns]
df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
df = df.sort_values("dt").reset_index(drop=True)
print("rows:", len(df), " range:", df["dt"].min(), "->", df["dt"].max())
print("cols:", list(df.columns))
# spread is in points (1 pt = 0.00001 for 5-digit). pips = points/10
sp = df["spread"].astype(float)
print("\nSPREAD (points): min=%d med=%.0f mean=%.1f p95=%.0f max=%d"%(sp.min(),sp.median(),sp.mean(),sp.quantile(.95),sp.max()))
df["hour"] = df["dt"].dt.hour
print("\nMedian spread (pips) by server hour:")
g = (df.groupby("hour")["spread"].median()/10.0)
for h in range(0,24,2):
    print("  h%02d: %.1f"%(h, g.loc[h]))
print("\nbars per weekday:", df["dt"].dt.dayofweek.value_counts().sort_index().to_dict())
# gap check: typical minute spacing
d = df["dt"].diff().dt.total_seconds().div(60)
print("\nbar spacing minutes: ==1:%.1f%%  weekend/gaps>3:%d"%((d==1).mean()*100,(d>3).sum()))
# daily range stats (volatility)
df["day"]=df["dt"].dt.date
dr=df.groupby("day").agg(hi=("high","max"),lo=("low","min"))
rng=((dr["hi"]-dr["lo"])*10000)
print("daily range pips: med=%.0f mean=%.0f p90=%.0f"%(rng.median(),rng.mean(),rng.quantile(.9)))
df.to_parquet("ftmo/m1/eurusd_m1.parquet")
print("\nsaved parquet")
