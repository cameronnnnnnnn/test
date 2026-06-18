import sys, os; sys.path.insert(0, 'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import research as R, ftmo_sim as F
import strategy as S

df = R.load()
sig = lambda d, p: S.signal(d, p)
tr = R.backtest(df, sig, S.STOP_MULT, S.ATR_N)

def stat(t):
    Rv = t["R"].values
    return dict(n=len(Rv), win=(Rv>0).mean(), expR=Rv.mean(),
                pf=Rv[Rv>0].sum()/(-Rv[Rv<0].sum()+1e-9), sumR=Rv.sum())

st = stat(tr)
print("="*72)
print("FINAL STRATEGY REPORT — Trend-Aligned Pullback")
print("Data: U.S. Federal Reserve daily FX via FRED/datahub (REAL).")
print(f"Period: {df['Date'].min().date()} -> {df['Date'].max().date()}  ({len(df)} bars)")
print("="*72)
print(f"Trades: {st['n']}   Win%: {st['win']*100:.1f}   Expectancy: {st['expR']:+.3f}R   "
      f"ProfitFactor: {st['pf']:.2f}   SumR: {st['sumR']:.0f}")

# real sequential path at final risk
blocks = F.build_day_blocks(tr)
seq = F.run_attempt(blocks, S.RISK, np.random.default_rng(0), sequential=True)
print(f"\nReal historical path @ {S.RISK*100:.2f}% risk: {seq['result']}  "
      f"final equity ${seq['equity']:.0f}  in {seq['days']} trading days")

# equity curve (sequential, fixed risk) saved to csv
eq = [F.START]; e = F.START
for d in blocks:
    for r in d:
        e += S.RISK * r * e
    eq.append(e)
pd.DataFrame({"step": range(len(eq)), "equity": eq}).to_csv("ftmo/equity_curve.csv", index=False)

print("\n" + "-"*72)
print("MONTE CARLO — pass the FTMO 1-Step challenge (5000 resampled attempts)")
print("-"*72)
def mc_block(name, frame):
    t = R.backtest(frame, sig, S.STOP_MULT, S.ATR_N)
    mc = F.monte_carlo(t, S.RISK, n=5000)
    print(f"{name:34s} PASS={mc['pass']*100:5.1f}%  failGlobal={mc['fail_global']*100:4.1f}%  "
          f"timeout={mc['timeout']*100:4.1f}%  medDays={mc['med_days_to_pass']}")
    return mc['pass']
p_full = mc_block("Full 5 years (in-sample)", df)
cut = int(len(df)*0.6)
p_oos = mc_block("Out-of-sample 2024-26 (untuned)", df.iloc[cut:].reset_index(drop=True))
mc_block("Last 12 months (stress)", df.iloc[-252:].reset_index(drop=True))

print("\n" + "="*72)
verdict = "PASS (>=80%)" if (p_full >= 0.80 and p_oos >= 0.80) else "REVIEW"
print(f"VERDICT: full={p_full*100:.1f}%  oos={p_oos*100:.1f}%  ->  {verdict}")
print("="*72)
