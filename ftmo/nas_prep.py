"""
Load + clean user-supplied NAS100 M1 (tab-sep, quoted, reverse-chrono, no spread col).
Profile it honestly, build real daily OHLC, save pickles.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

RAW = "ftmo/m1_nas/1m_data - Copy.csv"

# each physical line is wrapped in quotes: "DateTime<TAB>Open<TAB>..."
rows=[]
with open(RAW) as f:
    header=f.readline()
    for line in f:
        line=line.strip().strip('"')
        if not line: continue
        p=line.split("\t")
        if len(p)<6: continue
        rows.append(p[:7] if len(p)>=7 else p[:6]+[p[5]])
cols=["DateTime","Open","High","Low","Close","Volume","TickVolume"]
df=pd.DataFrame(rows,columns=cols[:len(rows[0])])
df["dt"]=pd.to_datetime(df["DateTime"],format="%Y.%m.%d %H:%M:%S")
for c in ["Open","High","Low","Close","TickVolume"]:
    df[c]=pd.to_numeric(df[c],errors="coerce")
df=df.dropna(subset=["Open","High","Low","Close"]).sort_values("dt").reset_index(drop=True)
df=df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","TickVolume":"tv"})
df=df[["dt","open","high","low","close","tv"]]

print("=== NAS100 M1 PROFILE ===")
print(f"bars: {len(df):,}")
print(f"range: {df['dt'].min()}  ->  {df['dt'].max()}")
span_days=(df['dt'].max()-df['dt'].min()).days
print(f"span: {span_days} days = {span_days/365.25:.2f} years")
print(f"price: {df['close'].min():.1f} .. {df['close'].max():.1f}")

# bar spacing quality
gap=df["dt"].diff().dt.total_seconds().div(60).values[1:]
print(f"\nbar spacing (min): 1m={np.mean(gap==1)*100:.1f}%  >1m={np.mean(gap>1)*100:.1f}%  "
      f"median={np.median(gap):.0f}")
# session coverage (server hour histogram)
hr=df["dt"].dt.hour.value_counts().sort_index()
print("\nbars per server-hour (coverage):")
print("  " + " ".join(f"{h:02d}:{int(v/1000)}k" for h,v in hr.items()))

# weekday coverage
wd=df["dt"].dt.dayofweek.value_counts().sort_index()
print("weekday bars:", {int(k):int(v) for k,v in wd.items()})

# Build DAILY OHLC (server-day). Index has overnight gaps; use full server day.
df["date"]=df["dt"].dt.date
g=df.groupby("date")
daily=pd.DataFrame({
    "open":g["open"].first(),"high":g["high"].max(),
    "low":g["low"].min(),"close":g["close"].last(),
    "bars":g["close"].count(),"tv":g["tv"].sum(),
}).reset_index()
daily["date"]=pd.to_datetime(daily["date"])
daily=daily[daily["bars"]>=60].reset_index(drop=True)  # drop thin/holiday days
daily["range_pts"]=daily["high"]-daily["low"]
daily["range_pct"]=daily["range_pts"]/daily["close"]*100

print(f"\n=== DAILY bars: {len(daily)} (>=60 m1 bars/day) ===")
print(f"avg daily range: {daily['range_pts'].mean():.1f} pts = {daily['range_pct'].mean():.2f}% of price")
print(f"median daily range: {daily['range_pts'].median():.1f} pts")
print(f"daily range pctiles (pts): "
      f"10%={daily['range_pts'].quantile(.1):.0f} 50%={daily['range_pts'].quantile(.5):.0f} "
      f"90%={daily['range_pts'].quantile(.9):.0f} 99%={daily['range_pts'].quantile(.99):.0f}")

# spread reality check: NAS100 typical broker spread ~1-2 pts. ratio vs range:
for spr in (1.0,2.0,3.0):
    print(f"  range/spread ratio @ {spr}pt spread: {daily['range_pts'].median()/spr:.0f}:1")

df.to_pickle("ftmo/m1_nas/nas_m1.pkl")
daily.to_pickle("ftmo/m1_nas/nas_daily.pkl")
print("\nsaved nas_m1.pkl + nas_daily.pkl")
