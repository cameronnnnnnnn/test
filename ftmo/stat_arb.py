import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

# ---- DAILY stat-arb: EURUSD vs GBPUSD spread reversion ----
d=pd.read_pickle("ftmo/m1/daily_all.pkl")
e=np.log(d["EURUSD_close"].values); g=np.log(d["GBPUSD_close"].values)
# rolling hedge ratio + spread z-score
N=20
beta=pd.Series(e).rolling(N).cov(pd.Series(g))/pd.Series(g).rolling(N).var()
spread=e-beta.values*g
z=(spread-pd.Series(spread).rolling(N).mean())/(pd.Series(spread).rolling(N).std()+1e-12)
z=z.values
# trade: z>+1 -> short spread (short EUR, long GBP); z<-1 -> long spread. exit next day.
# cost: two legs, ~ (1.1+1.2)/2 pips each leg round trip in return terms
costE=(1.1+0.2)*0.0001/d["EURUSD_close"].values
costG=(1.2+0.2)*0.0001/d["GBPUSD_close"].values
retE=np.diff(e,append=np.nan); retG=np.diff(g,append=np.nan)  # next-day log ret approx
R=[]
for t in range(N+1,len(d)-1):
    if abs(z[t])<1: continue
    s=-np.sign(z[t])  # +1 = long spread (long EUR short GBP)
    # next-day pnl of spread position (beta-weighted), minus 2-leg cost
    pnl = s*( (e[t+1]-e[t]) - beta.values[t]*(g[t+1]-g[t]) ) - (costE[t]+costG[t])
    # normalize by spread vol to get R-like
    vol=pd.Series(spread).rolling(N).std().values[t]
    R.append(pnl/ (vol+1e-12))
R=np.array(R); R=R[np.isfinite(R)]
print("DAILY EUR/GBP spread reversion:")
print(f"  n={len(R)} win={ (R>0).mean()*100:4.1f}% mean/vol={R.mean():+.3f} "
      f"PF={R[R>0].sum()/(-R[R<0].sum()+1e-9):.2f}")

# ---- INTRADAY 15m stat-arb ----
def load15(p):
    s=pd.read_pickle(f"ftmo/m1/{p}_m1.pkl").set_index("dt")["close"].resample("15min").last().dropna()
    return s
E=load15("EURUSD"); G=load15("GBPUSD")
j=pd.concat([E.rename("E"),G.rename("G")],axis=1).dropna()
le=np.log(j["E"].values); lg=np.log(j["G"].values)
M=64
bs=pd.Series(le).rolling(M).cov(pd.Series(lg))/pd.Series(lg).rolling(M).var()
sp=le-bs.values*lg
zz=((sp-pd.Series(sp).rolling(M).mean())/(pd.Series(sp).rolling(M).std()+1e-12)).values
cE=(1.1+0.2)*0.0001/j["E"].values; cG=(1.2+0.2)*0.0001/j["G"].values
hour=j.index.hour.values
R2=[]
for t in range(M+1,len(j)-1):
    if abs(zz[t])<2: continue
    if not (8<=hour[t]<11 or 14<=hour[t]<17): continue  # high-vol sessions
    s=-np.sign(zz[t])
    pnl=s*((le[t+1]-le[t])-bs.values[t]*(lg[t+1]-lg[t]))-(cE[t]+cG[t])
    vol=pd.Series(sp).rolling(M).std().values[t]
    R2.append(pnl/(vol+1e-12))
R2=np.array(R2); R2=R2[np.isfinite(R2)]
print("INTRADAY 15m EUR/GBP spread reversion (sessions, z>2):")
print(f"  n={len(R2)} win={ (R2>0).mean()*100:4.1f}% mean/vol={R2.mean():+.3f} "
      f"PF={R2[R2>0].sum()/(-R2[R2<0].sum()+1e-9):.2f}")
