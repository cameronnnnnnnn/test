"""
challengephaseHF/apex_eval.py — the 6pm-reopen REVERSAL leg (40pt SL / 120pt TP, 1 trade/night)
on APEX 50K evals, modeled to Apex's actual mechanics:

  * target +$3,000 ; trailing drawdown $2,500 off the INTRADAY peak (incl. open-trade highs —
    modeled worst-case: peak updates with the trade's MFE before the MAE low is checked)
  * NO daily loss limit ; 50% consistency (best green night <= 50% of summed green profit —
    soft: delays the pass, never fails it) ; min trading days shown for 1 and 7
  * fixed-$ risk per night (futures sizing; MNQ $2/pt -> $80/micro at 40pt stop; cap 60 micros)

Sweep risk-per-night high (user will buy 10+ accounts). Bootstrap of the real per-trade
(R, mae_R, mfe_R) sequence, block=5. Fees ~$40/mo eval (coupon reality) for cost-per-funded.
Run: python3 apex_eval.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "news")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402

START = 50_000.0; TARGET = 3_000.0; TRAIL = 2_500.0
CONSIST = 0.50
STOP = 40.0; TP_R = 3.0; COST = 1.5
USD_PT_MICRO = 2.0; CAP_MICROS = 60                          # user's stated cap
FEE_MO = 40.0                                               # eval fee w/ typical coupon
NIGHTS = 120                                                # ~6 months horizon
NP = 60_000


def night_trades():
    nas = S.prep(data.load())
    F = build_days(nas)
    spec = ExitSpec(tp_R=TP_R, be_R=0.0, trail_R=0.0, max_bars=600)
    orders = [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=STOP, spec=spec,
                   eod_bar=int(r.eod), day=r.day, tag="rev")
              for _, r in F.iterrows() if r.cdir != 0]
    tr = engine.simulate(nas, orders, cost_pts=COST).sort_values("entry_dt")
    return tr[["R", "mae_R", "mfe_R"]].values


def mc(tri, risk_usd, n_paths=NP, seed=11, block=5, min_days=7, deadline=NIGHTS):
    rng = np.random.default_rng(seed)
    n = len(tri)
    nb = int(np.ceil(deadline / block))
    starts = rng.integers(0, n, size=(n_paths, nb))
    offs = np.arange(block)
    samp = ((starts[:, :, None] + offs[None, None, :]) % n).reshape(n_paths, -1)[:, :deadline]
    R, MAE, MFE = tri[samp, 0], tri[samp, 1], tri[samp, 2]

    E = np.full(n_paths, START)
    peak = np.full(n_paths, START)
    sum_green = np.zeros(n_paths); max_green = np.zeros(n_paths)
    passed = np.zeros(n_paths, bool); blown = np.zeros(n_paths, bool)
    t_pass = np.full(n_paths, -1)
    for t in range(deadline):
        live = ~passed & ~blown
        if not live.any(): break
        hi = E + MFE[:, t] * risk_usd
        lo = E + MAE[:, t] * risk_usd
        peak_t = np.maximum(peak, hi)                        # intraday high trails FIRST
        blow_now = live & (lo <= peak_t - TRAIL)
        blown |= blow_now
        live = ~passed & ~blown
        prof = R[:, t] * risk_usd
        E = np.where(live, E + prof, E)
        peak = np.where(live, np.maximum(peak_t, E), peak)
        gp = np.where(live & (prof > 0), prof, 0.0)
        sum_green += gp; max_green = np.maximum(max_green, gp)
        ok_cons = max_green <= CONSIST * sum_green + 1e-9
        pass_now = live & (E >= START + TARGET) & ok_cons & (t + 1 >= min_days)
        passed |= pass_now
        t_pass = np.where(pass_now & (t_pass == t_pass.max()*0 + t_pass) & (t_pass < 0), t + 1, t_pass)
    mp = t_pass[passed].mean() if passed.any() else np.nan
    md = np.median(t_pass[passed]) if passed.any() else np.nan
    return dict(pass_rate=passed.mean(), blow_rate=blown.mean(),
                timeout=(~passed & ~blown).mean(), mean_n=mp, med_n=md)


def main():
    tri = night_trades()
    print(f"APEX 50K eval — reopen-reversal leg (40/120, 1 trade/night, cost {COST}pt)")
    print(f"trades: {len(tri)} nights, expR {tri[:,0].mean():+.3f}, WR {(tri[:,0]>0).mean()*100:.1f}%")
    print(f"rules: +$3,000 target | $2,500 INTRADAY trailing | 50% consistency (soft) | no daily limit\n")
    print(f"{'risk/night':>11}{'micros':>7} | {'pass%':>6}{'blow%':>7}{'t/o%':>6}{'med nights':>11}"
          f"{'~eval $/funded':>15} |  min_days=1 pass%")
    for usd in (240, 400, 560, 800, 1000, 1250, 1600, 2400):
        mic = usd / (STOP * USD_PT_MICRO)
        if mic > CAP_MICROS: continue
        m7 = mc(tri, usd, min_days=7)
        m1 = mc(tri, usd, min_days=1)
        months = (m7["mean_n"] / 21) if m7["mean_n"] == m7["mean_n"] else 6
        cost_f = FEE_MO * max(months, 1) / max(m7["pass_rate"], 1e-9)
        print(f"{usd:>10}$ {mic:>6.1f} | {m7['pass_rate']*100:5.1f}%{m7['blow_rate']*100:6.1f}%"
              f"{m7['timeout']*100:5.1f}%{m7['med_n']:>10.0f} {cost_f:>13.0f}$ |  {m1['pass_rate']*100:5.1f}%")
    print("\n(consistency modeled soft: a too-big best night only DELAYS the pass; timeout = alive at "
          f"{NIGHTS} nights, would pass later.)")


if __name__ == "__main__":
    main()
