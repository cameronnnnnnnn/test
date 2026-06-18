import numpy as np, pandas as pd
import research as R
import ftmo_sim as F

df = R.load()

SIGNALS = {
    "meanrev_z5k1":  lambda d, p: R.sig_meanrev(d, p, 5, 1.0),
    "sma_10_40":     lambda d, p: R.sig_sma_trend(d, p, 10, 40),
    "donchian20":    lambda d, p: R.sig_donchian(d, p, 20),
}

def combo_meanrev_trend(d, p):
    mr = R.sig_meanrev(d, p, 5, 1.0)
    tr = R.sig_sma_trend(d, p, 10, 40)
    # mean-revert only in direction of higher-timeframe trend (pullback entries)
    out = np.where((mr == 1) & (tr == 1), 1, np.where((mr == -1) & (tr == -1), -1, 0))
    return out
SIGNALS["combo_pullback"] = combo_meanrev_trend

print(f"Real data {df['Date'].min().date()}..{df['Date'].max().date()}  bars={len(df)}\n")
for name, fn in SIGNALS.items():
    tr = R.backtest(df, fn, stop_mult=1.0)
    e = R.stats(tr, name)
    blocks = F.build_day_blocks(tr)
    # single real sequential path at r=1%
    rng = np.random.default_rng(0)
    seq = F.run_attempt(blocks, 0.01, rng, sequential=True)
    print(f"     real-path@1%: {seq['result']} eq={seq['equity']:.0f} days={seq['days']}")
    for r in (0.005, 0.0075, 0.01, 0.015):
        mc = F.monte_carlo(tr, r, n=4000)
        print(f"     MC r={r*100:4.2f}%  PASS={mc['pass']*100:5.1f}%  failG={mc['fail_global']*100:4.1f}%  TO={mc['timeout']*100:4.1f}%  medDays={mc['med_days_to_pass']}")
    print()
