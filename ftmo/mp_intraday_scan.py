import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

PAIRS = {"EURUSD":(0.0001,0.00001),"GBPUSD":(0.0001,0.00001),
         "AUDUSD":(0.0001,0.00001),"USDJPY":(0.01,0.001)}
# Server-time high-volume windows: London 08-11, NY-overlap 14-17 (~2-5am & 8-11am NY)
SESSIONS = [(8,11),(14,17)]

def resample(p, tf="15min"):
    s = pd.read_pickle(f"ftmo/m1/{p}_m1.pkl").set_index("dt")
    b = pd.DataFrame({"open":s["open"].resample(tf).first(),"high":s["high"].resample(tf).max(),
                      "low":s["low"].resample(tf).min(),"close":s["close"].resample(tf).last(),
                      "spread":s["spread"].resample(tf).mean()}).dropna()
    b["date"]=b.index.date; b["hour"]=b.index.hour
    return b.reset_index().rename(columns={"index":"dt"})

def in_session(hour):
    return np.any([(hour>=a)&(hour<c) for a,c in SESSIONS],axis=0)

def backtest(bars, sig, stop_pips, target_R, pip, point, slip_pips=0.2, flat_after=17):
    o=bars["open"].values;h=bars["high"].values;l=bars["low"].values;c=bars["close"].values
    spr=bars["spread"].values*point; hour=bars["hour"].values; day=bars["date"].values
    n=len(bars); stop=stop_pips*pip; slip=slip_pips*pip
    sess=in_session(hour)
    R=[]; dates=[]; mae=[]
    i=0
    while i<n-1:
        s=sig[i]
        if s==0 or not sess[i]: i+=1; continue
        entry=o[i+1]+s*(spr[i+1]/2+slip)
        sp_px=entry-s*stop; tg_px=entry+s*target_R*stop
        m=0.0; ex=None; j=i+1
        while j<n and day[j]==day[i]:
            adv=(entry-l[j]) if s>0 else (h[j]-entry); m=max(m,adv)
            if (s>0 and l[j]<=sp_px) or (s<0 and h[j]>=sp_px): ex=-1.0-slip/stop; break
            if (s>0 and h[j]>=tg_px) or (s<0 and l[j]<=tg_px): ex=target_R-(spr[i+1]/2+slip)/stop; break
            if hour[j]>=flat_after and j>i+1:
                ex=(s*(c[j]-entry)-(spr[i+1]/2+slip))/stop; break
            j+=1
        if ex is None: ex=(s*(c[min(j,n-1)]-entry)-(spr[i+1]/2+slip))/stop
        R.append(ex); dates.append(day[i]); mae.append(m/stop)
        i=max(j,i+1)
    return pd.DataFrame({"date":dates,"R":R,"MAE_R":mae})

def ema(x,n): return pd.Series(x).ewm(span=n,adjust=False).mean().values
def sma(x,n): return pd.Series(x).rolling(n).mean().values
def std(x,n): return pd.Series(x).rolling(n).std().values

def s_mom(b,f=8,s=32):
    c=b["close"].values; ef=ema(c,f); es=ema(c,s)
    o=np.zeros(len(c)); o[(ef>es)&(np.roll(ef<=es,1))]=1; o[(ef<es)&(np.roll(ef>=es,1))]=-1; o[:s]=0; return o
def s_brk(b,n=16):
    c=b["close"].values; hi=pd.Series(c).rolling(n).max().shift(1).values; lo=pd.Series(c).rolling(n).min().shift(1).values
    o=np.zeros(len(c)); o[c>hi]=1; o[c<lo]=-1; o[:n+1]=0; return o
def s_rev(b,n=20,k=2.0):
    c=b["close"].values; m=sma(c,n); sd=std(c,n)
    o=np.zeros(len(c)); o[c<m-k*sd]=1; o[c>m+k*sd]=-1; o[:n]=0; return o

def stat(tr):
    if len(tr)<30: return None
    R=tr["R"].values
    return dict(n=len(R),tpd=len(R)/tr["date"].nunique(),win=(R>0).mean(),
                expR=R.mean(),pf=R[R>0].sum()/(-R[R<0].sum()+1e-9))

print("SESSION-FILTERED intraday edge scan (server 08-11 & 14-17), after real spread")
print(f"{'pair':7s} {'strat':16s} {'n':>5s} {'t/d':>4s} {'win%':>5s} {'expR':>7s} {'PF':>5s}")
for p,(pip,point) in PAIRS.items():
    b=resample(p,"15min")
    tests=[("mom8/32 2R",s_mom(b),12,2.0),("brk16 2R",s_brk(b),12,2.0),
           ("rev20/2 1R",s_rev(b),14,1.0),("rev20/2 1.5R",s_rev(b),14,1.5)]
    for nm,sg,stp,tR in tests:
        st=stat(backtest(b,sg,stp,tR,pip,point))
        if st: print(f"{p:7s} {nm:16s} {st['n']:5d} {st['tpd']:4.1f} {st['win']*100:5.1f} {st['expR']:+7.3f} {st['pf']:5.2f}")
