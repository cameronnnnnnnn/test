"""
Lucid/search.py — build many strategies, backtest, Monte-Carlo the FLEX EVAL, and
rank by MONTHLY (21-trading-day) pass rate. Iterate this to find the best.

Run: python3 search.py
"""
import numpy as np, pandas as pd
import data, strategies as S, engine, lucid

COST = 1.0                       # NQ round-turn (micro commission + ~1 tick); conservative-ish
RISKS = [50, 75, 100, 150, 200, 250, 300, 400, 500, 650, 800]   # $ risked per 1R (per stop-out)
DEADLINE = 21
NP = 30000

def combo(df, parts):
    """Sum orders from several (fn, params) into one strategy (multiple setups/day)."""
    out = []
    for fn, params in parts:
        out += fn(df, **params)
    return out

def eval_strategy(name, orders, df, all_dates, stop_hint, verbose=True):
    trades = engine.simulate(df, orders, cost_pts=COST)
    if len(trades) == 0:
        if verbose: print(f"  {name:28s} -- no trades");
        return None
    es = engine.edge_stats(trades)
    days = lucid.build_days(trades, all_dates)
    n_weeks = len(all_dates)/5.0
    best = None
    for rd in RISKS:
        if lucid.micros_for(rd, stop_hint) > 20.0 + 1e-9:    # exceeds 2-mini cap -> skip
            continue
        m = lucid.run_eval_mc(days, rd, DEADLINE, n_paths=NP, seed=7)
        if best is None or m["pass_rate"] > best[1]["pass_rate"]:
            best = (rd, m)
    if best is None:
        if verbose: print(f"  {name:28s} -- no feasible size (stop too wide for $1k DD)")
        return None
    rd, m = best
    mic = lucid.micros_for(rd, stop_hint)
    if verbose:
        print(f"  {name:28s} n={es['n']:4d} {es['n']/n_weeks:4.1f}/wk WR={es['wr']*100:4.1f}% "
              f"expR={es['expR']:+.3f} | risk=${rd:<4.0f}({mic:4.1f}mic) "
              f"PASS={m['pass_rate']*100:4.1f}% blow={m['blow_rate']*100:4.1f}% "
              f"to={m['timeout_rate']*100:4.1f}% med={m['med_days']:.0f}d")
    return dict(name=name, risk=rd, micros=mic, stop=stop_hint, **es,
                pass_rate=m["pass_rate"], blow_rate=m["blow_rate"],
                timeout=m["timeout_rate"], med_days=m["med_days"])

def main():
    df = S.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print(f"loaded {len(df):,} bars, {len(all_dates)} weekdays "
          f"({pd.Timestamp(all_dates[0]).date()}..{pd.Timestamp(all_dates[-1]).date()})")
    print(f"FLEX EVAL: $25k, +$1,250 target, $1,000 EOD-trailing DD, no daily limit, 50% consist.")
    print(f"COST={COST}pt round-turn. Monthly = {DEADLINE} trading days. {NP} paths.")
    print("="*118)

    OM = 16*60        # US cash open ~16:30 server (data is EET); strategies default open_min=16:00
    battery = []
    # --- single setups ---
    battery.append(("ORB15 s50 tp3",   S.orb(df, open_min=OM, or_min=15, stop_pts=50, tp_R=3.0, vol_filter=True), 50))
    battery.append(("ORB15 s50 tp4",   S.orb(df, open_min=OM, or_min=15, stop_pts=50, tp_R=4.0, vol_filter=True), 50))
    battery.append(("ORB15 s40 tp3",   S.orb(df, open_min=OM, or_min=15, stop_pts=40, tp_R=3.0, vol_filter=True), 40))
    battery.append(("ORB30 s60 tp3",   S.orb(df, open_min=OM, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0), 60))
    battery.append(("ORB15 s30 tp2",   S.orb(df, open_min=OM, or_min=15, stop_pts=30, tp_R=2.0, vol_filter=True), 30))
    battery.append(("VWpull s40 tp4",  S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0), 40))
    battery.append(("VWpull s40 tr3",  S.vwap_pullback(df, stop_pts=40, trail_R=3.0), 40))
    battery.append(("ORfade s40 tp1",  S.or_fade(df, or_min=30, poke_pts=15, stop_pts=40, tp_R=1.0), 40))
    battery.append(("ORfade s40 tp1.5",S.or_fade(df, or_min=30, poke_pts=15, stop_pts=40, tp_R=1.5), 40))
    battery.append(("VWfade k2 s40 t1",S.vwap_fade(df, k=2.0, stop_pts=40, tp_R=1.0), 40))
    battery.append(("VWfadeSel s40",   S.vwap_fade_sel(df, k=2.0, stop_pts=40, trail_R=2.0, partial_R=1.0), 40))
    battery.append(("PDHL s60 tr3",    S.pdh_pdl(df, stop_pts=60, trail_R=3.0, open_min=OM), 60))
    battery.append(("Drive s50 tr3",   S.open_drive(df, stop_pts=50, trail_R=3.0, open_min=OM), 50))
    # --- combos (more trades/day -> reach target faster; decorrelate) ---
    battery.append(("ORB15+VWpull 4R",
        combo(df, [(S.orb, dict(open_min=OM, or_min=15, stop_pts=50, tp_R=4.0, vol_filter=True)),
                   (S.vwap_pullback, dict(stop_pts=40, tp_R=4.0))]), 45))
    battery.append(("ORB15+VWpull 3R",
        combo(df, [(S.orb, dict(open_min=OM, or_min=15, stop_pts=50, tp_R=3.0, vol_filter=True)),
                   (S.vwap_pullback, dict(stop_pts=40, tp_R=3.0))]), 45))
    battery.append(("ORB+VWpull+fade",
        combo(df, [(S.orb, dict(open_min=OM, or_min=15, stop_pts=50, tp_R=4.0, vol_filter=True)),
                   (S.vwap_pullback, dict(stop_pts=40, tp_R=4.0)),
                   (S.vwap_fade_sel, dict(k=2.0, stop_pts=40, trail_R=2.0, partial_R=1.0))]), 43))

    results = []
    for name, orders, stop in battery:
        r = eval_strategy(name, orders, df, all_dates, stop)
        if r: results.append(r)
    print("="*118)
    results.sort(key=lambda x: x["pass_rate"], reverse=True)
    print("TOP by MONTHLY PASS RATE:")
    for r in results[:8]:
        print(f"  {r['name']:28s} PASS={r['pass_rate']*100:4.1f}%  blow={r['blow_rate']*100:4.1f}%  "
              f"to={r['timeout']*100:4.1f}%  WR={r['wr']*100:4.1f}%  risk=${r['risk']:.0f}  med={r['med_days']:.0f}d")

if __name__ == "__main__":
    main()
