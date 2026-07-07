"""
challengephaseHF/asian_break.py — the CLASSIC Asian-range breakout on the 4 forex majors
(user request). Define the overnight Asian consolidation range, then trade the breakout at
the London open with ATR-scaled stops and real spread cost. Honest TRAIN(70%)/TEST(30%)
edge so a positive in-sample number that decays out-of-sample is exposed.

Timezone: fx server is EET (busiest fx hour 17:00 server = London/NY overlap ~15:00 GMT),
so GMT = server-2. Tokyo/Asian session ~00:00-08:00 GMT = 02:00-10:00 server; London opens
08:00 GMT = 10:00 server. We take the range over [range_start, break_start) server and trade
the first breakout after break_start, flat by 22:55 server (same FTMO day). A small grid of
range windows is reported (not one cherry-picked window) so the verdict is robust.

Run: python3 asian_break.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import strategies as S, engine, fx_data          # noqa: E402
from engine import ExitSpec                       # noqa: E402

SESS_END = 22 * 60 + 55        # flat before the 23:00/rollover, keeps trade in one server day
FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]


def asian_break(df, range_start, break_start, stop_map, tp_R=3.0, trail_R=0.0, be_R=0.0,
                fade=False, buf_frac=0.0, entry_span=4*60, min_bars=30):
    """Range over [range_start, break_start); first break of that hi/lo traded after
    break_start (fade=True trades back INTO the range instead). Stop = ATR-scaled (stop_map),
    flat at 22:55. One trade/day. No look-ahead: range is fully formed before break_start."""
    h, l = df["high"].values, df["low"].values
    tod = df["tod"].values
    orders = []
    entry_by = break_start + entry_span
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        rng_mask = (t >= range_start) & (t < break_start)
        if rng_mask.sum() < min_bars:
            continue
        rh = h[gi[rng_mask]].max(); rl = l[gi[rng_mask]].min()
        stp = stop_map.get(day, np.nan)
        if not (stp == stp) or stp <= 0:
            continue
        buf = buf_frac * (rh - rl)
        post = gi[(t >= break_start) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        spec = ExitSpec(tp_R=tp_R, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for b in post[:-1]:
            if tod[b] > entry_by:
                break
            up = h[b] >= rh + buf
            dn = l[b] <= rl - buf
            if up:
                d = -1 if fade else 1
                orders.append(dict(entry_bar=b, dir=d, stop_pts=stp, spec=spec,
                                   eod_bar=eod, day=day, tag="asianbrk")); break
            if dn:
                d = 1 if fade else -1
                orders.append(dict(entry_bar=b, dir=d, stop_pts=stp, spec=spec,
                                   eod_bar=eod, day=day, tag="asianbrk")); break
    return orders


def fx_cost(df):
    pt = 0.001 if df["close"].iloc[-1] > 50 else 0.00001
    return 1.5 * df["spread"].median() * pt


def split_dates(df, frac=0.7):
    ad = np.array(sorted(df["date"].unique()))
    cut = ad[int(len(ad) * frac)]
    return set(ad[ad <= cut]), set(ad[ad > cut])


def stats(tr, days_tr, days_te, ndays):
    def es(t):
        if not len(t): return None
        return engine.edge_stats(t)
    a = es(tr); tr_tr = tr[tr["day"].isin(days_tr)]; tr_te = tr[tr["day"].isin(days_te)]
    return a, es(tr_tr), es(tr_te)


def main():
    # window grid (server minutes): (range_start, break_start)
    WINDOWS = [(0*60, 8*60), (2*60, 10*60), (0*60, 10*60)]
    print("CLASSIC Asian-range breakout — 4 forex majors, ATR-scaled stops, real spread cost")
    print("Honest edge: expR on ALL / TRAIN(70%) / TEST(30%). Positive+stable = real; decays = noise.\n")
    any_edge = False
    for x in FX:
        df = S.prep(fx_data.load(x))
        cost = fx_cost(df)
        atr = S.daily_atr(df, n=14)
        sm = {d: 0.30 * v for d, v in atr.items() if v == v}   # 0.30 ATR stop -> 3R ~ 0.9 ATR
        dtr, dte = split_dates(df)
        ndays = df["date"].nunique()
        print(f"=== {x}  (cost {cost:.5f}, {ndays} days) ===")
        print(f"  {'window':14} {'mode':10} {'/day':>5} {'WR':>6} {'expR_all':>9} {'expR_tr':>8} {'expR_te':>8} {'PF':>5}")
        for (rs, bs) in WINDOWS:
            wl = f"{rs//60:02d}-{bs//60:02d}"
            configs = [("brk 3R", dict(tp_R=3.0)),
                       ("brk trail3", dict(tp_R=0.0, trail_R=3.0, be_R=1.0)),
                       ("fade 1.5R", dict(tp_R=1.5, fade=True))]
            for mode, kw in configs:
                tr = engine.simulate(df, asian_break(df, rs, bs, sm, **kw), cost_pts=cost)
                if not len(tr):
                    print(f"  {wl:14} {mode:10} no trades"); continue
                a, atr_, ate = stats(tr, dtr, dte, ndays)
                pd_ = a["n"] / ndays
                te_exp = ate["expR"] if ate else float("nan")
                tr_exp = atr_["expR"] if atr_ else float("nan")
                flag = "  <-- +OOS" if (ate and ate["expR"] > 0.02 and atr_ and atr_["expR"] > 0) else ""
                if flag: any_edge = True
                print(f"  {wl:14} {mode:10} {pd_:5.2f} {a['wr']*100:5.1f}% {a['expR']:+8.3f} "
                      f"{tr_exp:+8.3f} {te_exp:+8.3f} {a['pf']:5.2f}{flag}")
        print()
    print("-" * 84)
    if any_edge:
        print("At least one Asian-breakout config shows +OOS edge — worth stacking onto NAS100 (see combine step).")
    else:
        print("VERDICT: no Asian-range breakout config has stable positive out-of-sample edge on any")
        print("major after the spread. Consistent with every other forex intraday test — majors are")
        print("efficiently priced vs the spread; the overnight-range breakout is just another")
        print("momentum template with no edge to harvest. Stacking it onto NAS100 would only add cost.")


if __name__ == "__main__":
    main()
