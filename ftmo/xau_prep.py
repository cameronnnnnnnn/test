"""
Load + profile user-supplied XAUUSD M1 (tab-sep, chronological, 7 cols:
Time O H L C Volume TickVol). Build daily OHLC. Flag the short-sample caveat.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

RAW="/root/.claude/uploads/2a4ce614-5c7b-5acc-ae5c-470c2749f842/b98aac2f-XAUUSD_M1.csv"
df=pd.read_csv(RAW,sep="\t",header=0,
               names=["dt","open","high","low","close","vol","tv"])
df["dt"]=pd.to_datetime(df["dt"])
for c in ["open","high","low","close","tv"]:
    df[c]=pd.to_numeric(df[c],errors="coerce")
df=df.dropna(subset=["open","high","low","close"]).sort_values("dt").reset_index(drop=True)
df=df[["dt","open","high","low","close","tv"]]

print("=== XAUUSD M1 PROFILE ===")
print(f"bars: {len(df):,}")
print(f"range: {df['dt'].min()} -> {df['dt'].max()}")
span=(df['dt'].max()-df['dt'].min()).days
print(f"span: {span} days = {span/30.4:.1f} months  (NAS100 had 36 months)")
print(f"price: {df['close'].min():.1f} .. {df['close'].max():.1f}")

gap=df["dt"].diff().dt.total_seconds().div(60).values[1:]
print(f"bar spacing: 1m={np.mean(gap==1)*100:.1f}%  >1m={np.mean(gap>1)*100:.1f}%  median={np.median(gap):.0f}")
hv=df.groupby(df['dt'].dt.hour)['tv'].mean()
print("avg tick-vol by server hour (find cash session):")
print("  " + " ".join(f"{h:02d}:{int(v)}" for h,v in hv.items()))
print("  highest-vol hours:", list(hv.sort_values(ascending=False).head(6).index))

df["date"]=df["dt"].dt.date
g=df.groupby("date")
daily=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),
    "low":g["low"].min(),"close":g["close"].last(),
    "bars":g["close"].count(),"tv":g["tv"].sum()}).reset_index()
daily["date"]=pd.to_datetime(daily["date"])
daily=daily[daily["bars"]>=60].reset_index(drop=True)
daily["range"]=daily["high"]-daily["low"]
print(f"\n=== DAILY bars: {len(daily)} (>=60 m1/day) ===")
print(f"avg daily range: ${daily['range'].mean():.1f} = {daily['range'].mean()/daily['close'].mean()*100:.2f}% of price")
print(f"median range: ${daily['range'].median():.1f}  90pct: ${daily['range'].quantile(.9):.1f}  99pct: ${daily['range'].quantile(.99):.1f}")
for spr in (0.3,0.5,1.0):
    print(f"  range/spread @ ${spr}: {daily['range'].median()/spr:.0f}:1")

df.to_pickle("ftmo/m1_nas/xau_m1.pkl")
daily.to_pickle("ftmo/m1_nas/xau_daily.pkl")
print("\nsaved xau_m1.pkl + xau_daily.pkl")
