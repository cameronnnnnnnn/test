"""
challengephaseHF/gbp_opens.py — does the open-candle pattern (reverse OR continue the first 1m
candle) exist anywhere on GBPUSD? Tests every significant open with HONEST per-open costs taken
from the data's own spread column (median spread at that minute + 0.3 pip slippage) — FX spreads
vary 10x by hour and the rollover window is a known artifact zone.

Opens tested (server EET/EEST): rollover 00:00, Tokyo 02:00, Frankfurt 09:00, LONDON 10:00,
US data 15:30, NY equities 16:30, and the WEEKLY Monday reopen (the only true halt in FX —
the analog of the NAS 6pm edge). SL 15 pips, TP {1, 1.5, 3}R, both directions, 70/30 split.
Run: python3 gbp_opens.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
V4 = os.path.normpath(os.path.join(HERE, "..", "ftmo", "v4"))
for p in (V4, HERE):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine, fx_data                     # noqa: E402
from engine import ExitSpec                                  # noqa: E402

PIP = 0.0001; PT = 0.00001
SL = 15 * PIP
TPS = (1.0, 1.5, 3.0)
OPENS = {"rollover 00:00": 0, "Tokyo 02:00": 2*60, "Frankfurt 09:00": 9*60,
         "LONDON 10:00": 10*60, "USdata 15:30": 15*60+30, "NY 16:30": 16*60+30}


def main():
    df = S.prep(fx_data.load("GBPUSD"))
    tod = df["tod"].values
    o = df["open"].values; c = df["close"].values
    sp = df["spread"].values
    idx = df.index.values.astype("datetime64[m]")
    groups = df.groupby("date").indices
    ad = np.array(sorted(groups.keys())); cut = ad[int(len(ad)*0.7)]

    def run(sig_bars, cost, tp, direction):
        spec = ExitSpec(tp_R=tp, be_R=0.0, trail_R=0.0, max_bars=480)
        orders = []
        for day, b0, eod in sig_bars:
            d = direction * np.sign(c[b0] - o[b0])
            if d == 0: continue
            orders.append(dict(entry_bar=int(b0), dir=int(d), stop_pts=SL, spec=spec,
                               eod_bar=int(eod), day=day, tag="x"))
        return engine.simulate(df, orders, cost_pts=cost)

    def collect(om):
        out = []
        for day, gi in groups.items():
            t = tod[gi]
            pos = gi[t == om]
            if len(pos) != 1: continue
            b0 = pos[0]
            eod = gi[(t > om) & (t <= min(om + 480, 23*60+55))]
            if len(eod) < 60: continue
            out.append((day, b0, eod[-1]))
        return out

    def weekly():
        out = []
        gap = np.diff(idx).astype("timedelta64[m]").astype(int)
        starts = np.where(gap >= 2000)[0] + 1                  # first bar after a weekend gap
        date_arr = df["date"].values
        for b0 in starts:
            day = date_arr[b0]
            gi = groups[pd.Timestamp(day)]
            t = tod[gi]
            om = tod[b0]
            eod = gi[(t > om) & (t <= min(om + 480, 23*60+55))]
            if len(eod) < 60: continue
            out.append((day, b0, eod[-1]))
        return out

    print(f"GBPUSD open-candle test — SL 15 pips, honest per-open cost, 70/30 split")
    print(f"{'open':18}{'cost(pip)':>10}{'dir':>5}{'TP':>5} | {'train n/WR/expR':>24} | {'test n/WR/expR':>24}")
    for name, om in {**OPENS, "WEEKLY Mon reopen": -1}.items():
        bars = weekly() if om == -1 else collect(om)
        if len(bars) < 100:
            print(f"{name:18}  (only {len(bars)} sessions)"); continue
        med_sp = np.median([sp[b0] for _, b0, _ in bars]) * PT
        cost = med_sp + 0.3 * PIP
        for direction, dlab in ((-1, "REV"), (+1, "CONT")):
            for tp in TPS:
                tr = run(bars, cost, tp, direction)
                g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
                if len(g) < 50 or len(ge) < 20:
                    continue
                def fmt(x):
                    e = engine.edge_stats(x)
                    return f"n={e['n']:4d} {e['wr']*100:4.1f}% {e['expR']:+.3f}"
                both = "  <-- BOTH+" if (g["R"].mean() > 0 and ge["R"].mean() > 0) else ""
                print(f"{name:18}{med_sp/PIP+0.3:>9.1f}p{dlab:>5}{tp:>4.1f}R | {fmt(g):>24} | {fmt(ge):>24}{both}")
        print()


if __name__ == "__main__":
    main()
