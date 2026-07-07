"""
challengephaseHF/fx_fade.py — since forex majors are more mean-reverting intraday than
NAS100, test whether FADE / mean-reversion setups have edge there (they would be the
positive-EV, uncorrelated legs that could actually help a mixed portfolio). Result: no.
Every fade on every pair is net-negative after the spread. Run: python3 fx_fade.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import strategies as S, engine, fx_data          # noqa: E402

print("Forex mean-reversion probe (fades, ATR-scaled stops, spread cost)")
print(f"{'instr':8} {'setup':12} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5}")
for x in ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]:
    df = S.prep(fx_data.load(x))
    pt = 0.001 if df["close"].iloc[-1] > 50 else 0.00001
    cost = 1.5 * df["spread"].median() * pt
    atr = S.daily_atr(df, n=14); med = np.nanmedian([v for v in atr.values() if v == v])
    sm = {d: 0.3*v for d, v in atr.items() if v == v}
    tests = {"vwfade_k2":  S.vwap_fade(df, k=2.0, stop_pts=0.3*med, tp_R=1.0),
             "vwfadeSel":  S.vwap_fade_sel(df, k=2.0, stop_map=sm, partial_R=1.0, trail_R=2.0),
             "orfade":     S.or_fade(df, poke_pts=0.2*med, stop_pts=0.3*med, tp_R=1.0)}
    for nm, o in tests.items():
        tr = engine.simulate(df, o, cost_pts=cost)
        if not len(tr): print(f"{x:8} {nm:12} no trades"); continue
        es = engine.edge_stats(tr)
        print(f"{x:8} {nm:12} {es['n']/df['date'].nunique():5.2f} {es['wr']*100:5.1f}% {es['expR']:+.3f} {es['pf']:5.2f}")
    print()
print("Verdict: forex majors have no intraday edge (momentum OR mean-reversion) after costs.")
print("So mixing them into the NAS100 account hurts, despite ~0 correlation. Edge is the wall.")
