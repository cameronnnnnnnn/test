import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import intraday_engine as E

m1 = E.load_m1()
b15 = E.resample(m1, "15min")

# 1) Hour-of-day edge probe: for each server hour, avg next-1h return per direction
#    (is there persistent drift or reversion by hour?)  -- net of ~1.3p cost
c = b15.set_index("dt")["close"]
ret1h = (c.shift(-4)/c - 1.0)  # 4x15m = 1h forward return
hr = b15["dt"].dt.hour.values
cost = 1.3*E.PIP / c.values  # ~round trip cost as return
print("Hour | mean 1h fwd ret (pips) | abs>cost?")
for h in range(24):
    m = hr==h
    if m.sum()<50: continue
    mr = ret1h.values[m]
    mr = mr[np.isfinite(mr)]
    print(f"  {h:02d}  {np.mean(mr)*10000:+6.2f}p   std {np.std(mr)*10000:5.1f}p   n={len(mr)}")

# 2) Opening-range breakout: range over [or_start, or_end), trade break until flat_hour
def make_orb(or_start, or_end):
    def sig(bars):
        out=np.zeros(len(bars))
        d=bars["dt"].dt.date.values; hh=bars["dt"].dt.hour.values
        hi=bars["high"].values; lo=bars["low"].values; cl=bars["close"].values
        day_hi={}; day_lo={}; fired={}
        for i in range(len(bars)):
            day=d[i]
            if or_start<=hh[i]<or_end:
                day_hi[day]=max(day_hi.get(day,-1e9),hi[i])
                day_lo[day]=min(day_lo.get(day, 1e9),lo[i])
            elif hh[i]>=or_end and day in day_hi and day not in fired:
                if cl[i]>day_hi[day]: out[i]=1; fired[day]=1
                elif cl[i]<day_lo[day]: out[i]=-1; fired[day]=1
        return out
    return sig

print("\nLondon/NY opening-range breakout (1 trade/day max):")
for (s_,e_,label) in [(6,7,"OR6-7 London"),(7,8,"OR7-8 London"),(13,14,"OR13-14 NY")]:
    for stop,tR in [(15,1.5),(20,1.5),(20,2.0),(25,2.0)]:
        tr=E.backtest(b15, make_orb(s_,e_), stop, tR,
                      session=(e_,20), flat_hour=20, slip_pips=0.2, max_trades_day=1)
        st=E.trade_stats(tr)
        if st: print(f"  {label} s{stop} t{tR}R: n={st['n']:4d} t/day={st['tpd']:.2f} "
                     f"win={st['win']*100:4.1f}% expR={st['expR']:+.3f} PF={st['pf']:.2f}")
