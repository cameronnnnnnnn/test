"""
Merge 20 years of XAUUSD M1 (12 TSV chunks, 2004-2024) + the 2025-26 file already
loaded. Parse, sort, dedupe, profile BY YEAR (regimes), build daily+intraday bars.
This is the multi-regime sample needed to honestly validate a gold edge.
"""
import sys, os, glob; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

files=sorted(glob.glob("ftmo/xau_full/*/XAU_1m_data_*.tsv"),
             key=lambda p:int(p.split("_")[-1].split(".")[0]))
print(f"merging {len(files)} chunks...")
parts=[]
for f in files:
    df=pd.read_csv(f,sep="\t",header=0,names=["dt","open","high","low","close","vol"])
    parts.append(df)
df=pd.concat(parts,ignore_index=True)
df["dt"]=pd.to_datetime(df["dt"],format="%Y.%m.%d %H:%M",errors="coerce")
for c in ["open","high","low","close","vol"]:
    df[c]=pd.to_numeric(df[c],errors="coerce")
df=df.dropna(subset=["dt","open","high","low","close"])
df=df.drop_duplicates(subset="dt").sort_values("dt").reset_index(drop=True)
df["tv"]=df["vol"]  # only one volume col here
df=df[["dt","open","high","low","close","tv"]]

print(f"\n=== XAUUSD 20y M1 PROFILE ===")
print(f"bars: {len(df):,}")
print(f"range: {df['dt'].min()} -> {df['dt'].max()}")
print(f"price: {df['close'].min():.1f} .. {df['close'].max():.1f}")

# per-year regime profile
df["year"]=df["dt"].dt.year
df["date"]=df["dt"].dt.date
yr=df.groupby("year").agg(bars=("close","size"),
    px_lo=("close","min"),px_hi=("close","max"),
    first=("close","first"),last=("close","last"))
yr["ret%"]=(yr["last"]/yr["first"]-1)*100
print("\nper-year (regime map):")
for y,r in yr.iterrows():
    tag = "BULL" if r["ret%"]>8 else ("BEAR" if r["ret%"]<-8 else "range")
    print(f"  {y}: bars={int(r['bars']):>7d}  px {r['px_lo']:.0f}-{r['px_hi']:.0f}  "
          f"yr-ret {r['ret%']:+6.1f}%  [{tag}]")

# session volume map
hv=df.groupby(df['dt'].dt.hour)['tv'].mean()
print("\navg vol by server hour:", " ".join(f"{h:02d}:{int(v)}" for h,v in hv.items()))

# build daily
g=df.groupby("date")
daily=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),
    "low":g["low"].min(),"close":g["close"].last(),
    "bars":g["close"].count(),"tv":g["tv"].sum()}).reset_index()
daily["date"]=pd.to_datetime(daily["date"])
daily=daily[daily["bars"]>=60].reset_index(drop=True)
daily["range"]=daily["high"]-daily["low"]
print(f"\ndaily bars: {len(daily)}  (~{len(daily)/250:.1f} yrs of trading days)")
print(f"median daily range $ by era:")
for lo,hi in [(2004,2011),(2011,2016),(2016,2020),(2020,2023),(2023,2027)]:
    sub=daily[(daily['date'].dt.year>=lo)&(daily['date'].dt.year<hi)]
    if len(sub): print(f"  {lo}-{hi-1}: median ${sub['range'].median():.1f}  "
                       f"({sub['range'].median()/sub['close'].median()*100:.2f}% of px)")

df[["dt","open","high","low","close","tv"]].to_pickle("ftmo/xau_full/xau20_m1.pkl")
daily.to_pickle("ftmo/xau_full/xau20_daily.pkl")
print("\nsaved xau20_m1.pkl + xau20_daily.pkl")
