"""
FairPriceStrategy/user_spec.py — the strategy EXACTLY as the user trades it, finalized from his
two annotated chart examples (IMG_6082/6083) and his answers. NY 9:30 only.

FAIR PRICE = the CLOSE of the 9:29 candle (single level). Price above it -> shorts only;
price below it -> longs only. Every trade after the open must be TOWARD fair; the only
away-from-fair trade allowed is the opening continuation.

  P1  OPENING CONTINUATION (0-10 min): 0-1 trade, in the opening candle's direction (the "unfair"
      move away from fair). Trigger = displacement (body > each of the last 2 candles, tiny wick,
      closes beyond the prior candle) OR break of structure, in that direction.
  P2  REVERSION (10-90 min, until 11:00): trade TOWARD fair. Direction set by side of fair.
      Trigger = displacement toward fair OR break of structure toward fair (close beyond a prior
      swing / wick cluster). A+ = displacement AND BOS; B+ = displacement only (still taken).
      From 10:30 on, only A+ (displacement AND BOS) — volume is thinning.
  EXIT: fixed 1:1.5, nothing moved. 25pt stop / 37.5pt TP; if the trigger candle's BODY > 25pts,
      50pt stop / 75pt TP (same $ risk, same R:R). No room-skip, no breakeven.
  DAY STOPS: 0.75% risk/trade; the day ends at 3 losses or 11:00. (No win cap — keeping the
      3-loss floor but letting green days run is a small, free pass-rate gain: OOS 20/40/60d
      12.8/30.1/41.1% -> 13.8/31.7/43.1%, blow unchanged, because 3 wins/day rarely binds anyway.)

Reported honestly: freq, WR, expR train/test at BOTH zero cost (what a manual chart backtest
sees) and the real 2pt CFD spread, then the FTMO 0.75% MC. Run: python3 user_spec.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from engine import ExitSpec                              # noqa: E402
from search import build_days                            # noqa: E402
from fairprice import fractal_swings                     # noqa: E402

CFG = dict(
    stop_small=25.0, stop_big=50.0, big_thresh=25.0, rr=1.5,   # body > big_thresh -> big stop
    cont_win=10, rev_end=90, aplus_after=60,                   # 60 min after open = 10:30
    wick_max=0.30, swing_k=2, bos_lookback=45,
    risk=0.0075, max_losses=3, max_wins=99, cost_pts=2.0,   # 3-loss floor kept; no win cap
)
OPEN = 16*60 + 30                                              # NY 9:30 = 16:30 server (EET)


def orders_user(df, cfg=CFG):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    rng = np.maximum(h - l, 1e-9); body = np.abs(c - o)
    wickr = (rng - body) / rng
    cdirs = np.sign(c - o)
    out = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t < OPEN + cfg["rev_end"])]
        pre = gi[t < OPEN]
        if len(sess) < 30 or len(pre) < 5:
            continue
        fair = c[pre[-1]]                                   # fair price = close of the 9:29 candle
        cdir = cdirs[sess[0]]
        win = np.concatenate([pre[-cfg["bos_lookback"]:], sess])
        swH, swL = fractal_swings(h[win], l[win], cfg["swing_k"])
        base = len(win) - len(sess)
        for j in range(2, len(sess) - 1):
            b = sess[j]; lm = base + j
            mins = tod[b] - OPEN
            phase = 1 if mins <= cfg["cont_win"] else 2
            if phase == 1:
                if cdir == 0: continue
                d = int(cdir)                              # continuation of the opening (unfair) move
            else:
                if c[b] > fair:   d = -1                   # above fair -> short back toward it
                elif c[b] < fair: d = +1                   # below fair -> long back toward it
                else:             continue
            # displacement: stands out vs the last 2 candles, tiny wick, closes beyond prior extreme
            disp = (cdirs[b] == d and rng[b] > max(rng[b-1], rng[b-2])
                    and wickr[b] <= cfg["wick_max"]
                    and ((c[b] > h[b-1]) if d > 0 else (c[b] < l[b-1])))
            # break of structure: close beyond nearest still-unbroken fractal swing in direction d
            if d > 0:
                lv = [h[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                      if swH[i2] and (c[win[i2+1:lm]] <= h[win[i2]]).all()]
                bos = bool(lv) and c[b] > min(lv)
            else:
                lv = [l[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                      if swL[i2] and (c[win[i2+1:lm]] >= l[win[i2]]).all()]
                bos = bool(lv) and c[b] < max(lv)
            aplus = disp and bos
            if phase == 2 and mins >= cfg["aplus_after"]:
                if not aplus: continue                     # 10:30 on: A+ only
            elif not (disp or bos):
                continue
            stop = cfg["stop_small"] if body[b] <= cfg["big_thresh"] else cfg["stop_big"]
            spec = ExitSpec(tp_R=cfg["rr"], be_R=0.0, trail_R=0.0, max_bars=cfg["rev_end"])
            out.append(dict(entry_bar=b, dir=d, stop_pts=stop, spec=spec, eod_bar=sess[-1],
                            day=day, tag=f"P{phase}|{'Ap' if aplus else 'Bp'}|s{stop:.0f}"))
    return out


def seq(tr, cfg=CFG):
    """Time-ordered, no overlap; max 1 opening continuation; day ends at 3 wins or 3 losses."""
    tr = tr.copy()
    tr["phase"] = tr["tag"].str.split("|").str[0]
    keep = []
    for day, g in tr.groupby("day"):
        g = g.sort_values("entry_dt")
        last = None; n1 = 0; wins = 0; losses = 0
        for i, r in g.iterrows():
            if wins >= cfg["max_wins"] or losses >= cfg["max_losses"]: break
            if last is not None and r["entry_dt"] <= last: continue
            if r["phase"] == "P1" and n1 >= 1: continue
            keep.append(i); last = r["exit_dt"]
            if r["phase"] == "P1": n1 += 1
            if r["R"] > 0: wins += 1
            elif r["R"] < 0: losses += 1
    return tr.loc[keep]


def build(df, cost):
    return seq(engine.simulate(df, orders_user(df), cost_pts=cost))


def es(g):
    if len(g) < 20: return "        (n<20)"
    e = engine.edge_stats(g)
    return f"n={e['n']:4d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]

    tr = build(df, CFG["cost_pts"])
    tr["phase"] = tr["tag"].str.split("|").str[0]
    tr["grade"] = tr["tag"].str.split("|").str[1]
    print(f"USER SPEC (final) — {len(tr)} trades, {len(tr)/len(ad):.2f}/day  "
          f"({len(tr[tr.phase=='P1'])} openers, {len(tr[tr.phase=='P2'])} reversions)\n")

    print("Per-trade edge (2pt CFD cost):")
    print(f"{'':12}{'TRAIN':>32}{'TEST':>32}")
    for key, vals in [("phase", ["P1", "P2"]), ("grade", ["Ap", "Bp"])]:
        for v in vals:
            g = tr[tr[key] == v]
            print(f"  {v:8} {es(g[g['day']<=cut]):>32} {es(g[g['day']>cut]):>32}")
    print(f"  {'ALL':8} {es(tr[tr['day']<=cut]):>32} {es(tr[tr['day']>cut]):>32}")

    tr0 = build(df, 0.0)                                    # what a manual chart backtest sees
    print("\nReconciliation — same rules, cost swept:")
    for lbl, t in [("zero cost ", tr0), ("2pt spread", tr)]:
        gtr = t[t["day"] <= cut]; gte = t[t["day"] > cut]
        print(f"  {lbl}: {es(gtr)}  |  {es(gte)}")

    print(f"\nFTMO 15k 1-Step MC — {CFG['risk']*100:.2f}% risk (2pt cost, -3 loss day stop):")
    dte = ad[ad > cut]
    for lbl, t, dd_days in [("ALL", tr, ad), ("OOS", tr[tr["day"].isin(set(dte))], dte)]:
        dd = build_days(t, dd_days, 2.0)
        row = []
        for dl in (20, 40, 60):
            m = ftmo.run_mc(dd, CFG["risk"], dl, n_paths=60000, seed=11, block=5)
            row.append(f"{dl}d {m['pass_rate']*100:4.1f}%/{m['blow_rate']*100:4.1f}%")
        print(f"  [{lbl}] " + "  ".join(row) + "  (pass/blow)")


if __name__ == "__main__":
    main()
