"""
In-depth strategy statistics for the 95% config (both sessions, vol gate, partial+trail, 1% risk).
Trade-level edge, distribution shape, streaks, R-drawdown, session/year splits, fat-tail measure.
Prints a full readout and dumps stats_95_data.json for the tearsheet chart.
"""
import sys, os, json
sys.path.insert(0,'/home/user/v4/ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

CFG=json.load(open('/home/user/v4/FTMO_95_Strategy/strategy.json'))['engine_config']
DAYS,CTX=build_all()
order=[d[0] for d in DAYS]; CAUSAL={}; p=np.nan
for d in order:
    cur=CTX.get(d,{}).get('atrpct',np.nan); cc=dict(CTX.get(d,{})); cc['atrpct']=p; CAUSAL[d]=cc; p=cur
def sess_trades(hr):
    RR,MAE,DTS=orb_v4(DAYS,CAUSAL,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,be_at=1.0,
        trail_k=5.0,tp_R=None,partial_at=2.0,partial_frac=0.5,partial_be=True,cost=2.0,eod_hr=23,
        rng_filter=True,vol_confirm=True,side='both',atr_regime=(0.5,1.0))
    return pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE,'sess':hr})
df=pd.concat([sess_trades(15),sess_trades(16)],ignore_index=True).sort_values('date').reset_index(drop=True)
R=df['R'].values; n=len(R)
w=R[R>0]; l=R[R<=0]

def moments(x):
    m=x.mean(); s=x.std(ddof=1)
    sk=((x-m)**3).mean()/s**3; ku=((x-m)**4).mean()/s**4-3
    return m,s,sk,ku
mean,std,skew,kurt=moments(R)
wr=len(w)/n; expR=mean
pf=w.sum()/-l.sum() if l.sum()<0 else float('inf')
payoff=w.mean()/-l.mean() if len(l) else float('inf')
# fat tail: share of gross positive R from top 10% of trades
srt=np.sort(w)[::-1]; top10=srt[:max(1,int(0.1*n))]; fat=top10.sum()/w.sum()*100
# per-trade sharpe annualized
yrs=(df['date'].max()-df['date'].min()).days/365.25; tpy=n/yrs
sharpe=mean/std*np.sqrt(tpy)
# streaks (non-winner = R<=0)
def streaks(mask):
    best=cur=0
    for x in mask:
        cur=cur+1 if x else 0; best=max(best,cur)
    return best
maxwin=streaks(R>0); maxloss=streaks(R<=0)
# R-drawdown on cumulative R curve
cum=np.cumsum(R); peak=np.maximum.accumulate(cum); dd=peak-cum; maxddR=dd.max()
# bootstrap CI on expectancy
rng=np.random.default_rng(1); bm=np.array([R[rng.integers(0,n,n)].mean() for _ in range(5000)]); ci=(np.percentile(bm,5),np.percentile(bm,95))

print(f"=== 95% CONFIG — IN-DEPTH STATS ({df['date'].min().date()} → {df['date'].max().date()}, {yrs:.1f}y) ===\n")
print(f"TRADES & FREQUENCY")
print(f"  total trades          {n}     (~{tpy/52:.1f}/week, {n/ (yrs*12):.0f}/month)")
print(f"  trading days          {df['date'].dt.normalize().nunique()}")
print(f"\nEDGE (per trade, in R; 1R = 1.0% at 80pt stop)")
print(f"  win rate              {wr*100:.1f}%")
print(f"  expectancy            {expR:+.3f} R   90% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]")
print(f"  avg winner            {w.mean():+.2f} R     avg loser   {l.mean():+.2f} R")
print(f"  payoff ratio          {payoff:.2f}      profit factor {pf:.2f}")
print(f"  best / worst          {R.max():+.1f} R / {R.min():+.1f} R")
print(f"\nDISTRIBUTION SHAPE")
print(f"  std dev               {std:.2f} R")
print(f"  skew                  {skew:+.2f}   (fat right tail)   kurtosis {kurt:+.1f}")
print(f"  profit from top 10%   {fat:.0f}% of gross wins  (concentration -> consistency-rule pressure)")
print(f"  per-trade Sharpe(ann) {sharpe:.2f}")
print(f"\nSTREAKS & DRAWDOWN (in R)")
print(f"  max consec winners    {maxwin}")
print(f"  max consec non-winners{maxloss}")
print(f"  max drawdown          {maxddR:.1f} R   (= {maxddR*1.0:.1f}% of account at 1% risk)")
print(f"\nMAE (adverse excursion, R)")
print(f"  avg MAE               {df['MAE'].mean():.2f} R    winners' avg MAE {df.loc[df['R']>0,'MAE'].mean():.2f} R")
print(f"\nBY SESSION")
for h,g in df.groupby('sess'):
    gr=g['R'].values; print(f"  {h}:00   {len(gr):4d} trades   WR {100*(gr>0).mean():.0f}%   expR {gr.mean():+.3f}")
print(f"\nBY YEAR")
yr_rows=[]
for y,g in df.groupby(df['date'].dt.year):
    gr=g['R'].values; print(f"  {y}   {len(gr):4d} trades   WR {100*(gr>0).mean():.0f}%   expR {gr.mean():+.3f}")
    yr_rows.append(dict(year=int(y),n=int(len(gr)),wr=round(100*(gr>0).mean(),1),exp=round(float(gr.mean()),3)))

# R histogram for chart (clip display at 8R)
edges=[-1.5,-1,-0.5,0,0.5,1,1.5,2,3,4,5,6,8]
hist=[int(x) for x in np.histogram(np.clip(R,-1.5,8),bins=edges)[0]]
json.dump(dict(n=int(n),wr=round(wr*100,1),exp=round(expR,3),ci=[round(ci[0],3),round(ci[1],3)],
    avgW=round(float(w.mean()),2),avgL=round(float(l.mean()),2),pf=round(pf,2),payoff=round(payoff,2),
    best=round(float(R.max()),1),worst=round(float(R.min()),1),std=round(std,2),skew=round(skew,2),
    kurt=round(kurt,1),fat=round(fat,0),sharpe=round(sharpe,2),maxwin=int(maxwin),maxloss=int(maxloss),
    maxddR=round(float(maxddR),1),tpw=round(tpy/52,1),
    rhist_edges=edges,rhist=hist,
    by_session=[dict(s=int(h),n=int(len(g)),wr=round(100*(g['R'].values>0).mean(),0),exp=round(float(g['R'].mean()),3)) for h,g in df.groupby('sess')],
    by_year=yr_rows),
    open('/home/user/v4/FTMO_95_Strategy/stats_95_data.json','w'))
print("\n[chart data -> FTMO_95_Strategy/stats_95_data.json]")
