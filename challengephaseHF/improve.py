"""
challengephaseHF/improve.py — can the low-RR/high-WR mean-reversion core be made
net-positive after costs? Two levers:
  (1) selectivity + regime filter: only fade bigger stretches, and only in a FLAT regime
      (slow EMA not trending), which is where mean reversion is supposed to work.
  (2) TP sweep: raise tp_R and find where expR crosses zero, and what RR that implies.
If positive expR only appears once RR climbs past ~1, then RR<1 cannot win here and we
say so. Run: python3 improve.py
"""
import numpy as np, pandas as pd
import hf_strats as HF
import data, strategies as S, engine
from hf_strats import _emit, prep_ind

df = S.prep(data.load()); IND = prep_ind(df); ND = df["date"].nunique()
# slow-trend regime: flat if the 60-bar EMA barely moved over the last 30 bars
ema_slow = pd.Series(IND["c"]).ewm(span=60, adjust=False).mean().values
slope30 = np.abs(ema_slow - np.concatenate([np.full(30, np.nan), ema_slow[:-30]]))


def mr_z_f(k=2.0, stop=40, tp=0.5, flat=None, cooldown=20, max_bars=25):
    z = IND["z"]
    def sig(b):
        zz = z[b]
        if not np.isfinite(zz): return 0
        if flat is not None and not (np.isfinite(slope30[b]) and slope30[b] <= flat): return 0
        if zz >= k: return -1
        if zz <= -k: return 1
        return 0
    return _emit(df, sig, "mr_z", stop, tp, cooldown, max_bars)


def stat(orders):
    tr = engine.simulate(df, orders, cost_pts=2.0)
    if not len(tr): return None
    es = engine.edge_stats(tr)
    return es["n"], es["wr"], es["expR"], es["pf"], (es["n"] / ND)


print("=" * 78)
print("(1) mr_z TP sweep (k=2, stop=40, no filter): where does expR cross zero?")
print("=" * 78)
print(f"  {'tp_R':>5} {'RR(real)':>9} {'trades':>7} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5}")
for tp in (0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    r = stat(mr_z_f(tp=tp))
    if r:
        tr = engine.simulate(df, mr_z_f(tp=tp), cost_pts=2.0); es = engine.edge_stats(tr)
        rr = abs(es["avg_win"]/es["avg_loss"]) if es["avg_loss"] else 0
        n, wr, e, pf, pd_ = r
        print(f"  {tp:5.2f} {rr:9.2f} {n:7d} {pd_:5.1f} {wr*100:5.1f}% {e:+.3f} {pf:5.2f}")

print("\n" + "=" * 78)
print("(2) mr_z selectivity + FLAT-regime filter (tp=0.5, RR<1): can WR beat breakeven?")
print("=" * 78)
print(f"  {'k':>4} {'flat':>6} {'trades':>7} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5}")
for k in (2.0, 2.5, 3.0):
    for flat in (None, 12.0, 6.0):
        r = stat(mr_z_f(k=k, tp=0.5, flat=flat))
        if r:
            n, wr, e, pf, pd_ = r
            fl = "off" if flat is None else f"{flat:g}"
            print(f"  {k:4.1f} {fl:>6} {n:7d} {pd_:5.1f} {wr*100:5.1f}% {e:+.3f} {pf:5.2f}")
print("-" * 78)
print("Read: if expR only turns positive at tp_R>~1 (RR>1), then RR<1 loses on NAS100")
print("after costs, no matter the win rate. Filters raise WR a little but cost trades.")
