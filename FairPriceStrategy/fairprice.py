"""
FairPriceStrategy/fairprice.py — v3, faithful to BOTH video transcripts, NY 9:30 session ONLY
(user scope: ignore other sessions and 8:30 news — no news calendar available).

The strategy (from the videos):
  * FAIR PRICE = the pre-open candle (a ZONE = its full range). The 9:30 open brings an influx
    of participants whose flow moves price "unfairly" away from fair.
  * PHASE 1 — CONTINUATION (first ~15 min): trade the direction of the opening candle. Entry =
    a candle that breaks & closes beyond prior structure, or a clean displacement, in that
    direction. Up to 2 entries ("if you miss the first one, it's fine to get in here").
  * PHASE 2 — REVERSION (until 11:00): trade back toward the fair zone whenever there's room
    (points in your favor). Entry = BREAK OF STRUCTURE with a close beyond it, toward fair —
    "always stick to the rules... wait until it actually breaks structure". Displacement on the
    trigger = A+ (strength), otherwise A. Re-enter on each new BOS (win-loss-win-loss-win);
    halt only after several consecutive losses.
  * RISK (adaptive, from video 2): normally 25pt stop / 38pt TP (1:1.5). If the trigger candle
    is >25 points, use 50/76 at half size instead (same $ risk, same R:R, wider survival).
  * Done at 11:00 (volume dies). Positions still open may play out (engine: eod at window end).

Judged the way the videos themselves demand: FTMO pass rate under full rules, train/test.
Run: python3 fairprice.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from engine import ExitSpec                              # noqa: E402
from search import build_days                            # noqa: E402

# ---------------- configuration (all tunable; defaults per the videos) ----------------
CFG = dict(
    stop_small=25.0, stop_big=50.0,    # adaptive: big stop when trigger candle > big_thresh
    big_thresh=25.0,
    rr=1.52,                           # TP = rr x stop (38/25 = 76/50)
    disp_mult=1.0,                     # displacement: range > mult x prior candle range
    disp_close_beyond=True,            # ...and closes beyond the prior candle's extreme
    wick_max=0.30,                     # ...with near-zero wick
    swing_k=2,                         # fractal width for structure
    bos_lookback=45,                   # bars back a swing stays relevant
    cont_win=15,                       # phase-1 window (minutes after open)
    rev_end=90,                        # phase 2 ends 90 min after open (11:00)
    min_room=30.0,                     # phase-2 room to the NEAR EDGE of the fair zone
    max_p1=2,                          # continuation entries allowed
    max_per_session=5,                 # total accepted trades per session
    rev_loss_halt=3,                   # halt phase 2 after this many CONSECUTIVE losses
    p2_need_bos=True,                  # reversion entry REQUIRES break-of-structure (video 2)
    cost_pts=2.0,
)
OPEN = 16*60 + 30                      # NY 9:30 EST = 16:30 server (EET)


def fractal_swings(h, l, k):
    n = len(h)
    swH = np.zeros(n, bool); swL = np.zeros(n, bool)
    for i in range(k, n-k):
        if h[i] == max(h[i-k:i+k+1]) and h[i] > h[i-1] and h[i] > h[i+1]: swH[i] = True
        if l[i] == min(l[i-k:i+k+1]) and l[i] < l[i-1] and l[i] < l[i+1]: swL[i] = True
    return swH, swL


def session_orders(df, cfg=CFG):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    body = np.abs(c - o); rng = np.maximum(h - l, 1e-9)
    wickr = (rng - body) / rng
    cand_dir = np.sign(c - o)
    orders = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t < OPEN + cfg["rev_end"])]
        pre = gi[t < OPEN]
        if len(sess) < 30 or len(pre) < 5:
            continue
        zone_hi = h[pre[-1]]; zone_lo = l[pre[-1]]        # fair price ZONE = pre-open candle
        ob = sess[0]
        cdir = cand_dir[ob]
        win = np.concatenate([pre[-cfg["bos_lookback"]:], sess])
        swH, swL = fractal_swings(h[win], l[win], cfg["swing_k"])
        base = len(win) - len(sess)
        n_p1 = 0
        for j in range(1, len(sess) - 1):
            b = sess[j]; lm = base + j
            mins = tod[b] - OPEN
            phase = 1 if mins <= cfg["cont_win"] else 2
            if phase == 1:
                if cdir == 0 or n_p1 >= cfg["max_p1"]:
                    continue
                d = int(cdir)
            else:
                if c[b] > zone_hi:   d = -1; room = c[b] - zone_hi
                elif c[b] < zone_lo: d = +1; room = zone_lo - c[b]
                else:                continue                 # inside fair zone: no trade
                if room < cfg["min_room"]:
                    continue
            # displacement: range bigger than prior candle, near-zero wick, closes beyond it
            disp = (cand_dir[b] == d and rng[b] > cfg["disp_mult"]*rng[b-1]
                    and wickr[b] <= cfg["wick_max"])
            if disp and cfg["disp_close_beyond"]:
                disp = (c[b] > h[b-1]) if d > 0 else (c[b] < l[b-1])
            # break of structure: close beyond nearest UNBROKEN fractal swing
            bos = False
            if d > 0:
                lvls = [h[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                        if swH[i2] and (c[win[i2+1:lm]] <= h[win[i2]]).all()]
                if lvls and c[b] > min(lvls): bos = True
            else:
                lvls = [l[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                        if swL[i2] and (c[win[i2+1:lm]] >= l[win[i2]]).all()]
                if lvls and c[b] < max(lvls): bos = True
            if phase == 2 and cfg["p2_need_bos"]:
                trigger = bos
            else:
                trigger = bos or disp
            if not trigger:
                continue
            grade = "A+" if (bos and disp) else "A"
            stop = cfg["stop_small"] if rng[b] <= cfg["big_thresh"] else cfg["stop_big"]
            spec = ExitSpec(tp_R=cfg["rr"], be_R=0.0, trail_R=0.0, max_bars=cfg["rev_end"])
            orders.append(dict(entry_bar=b, dir=d, stop_pts=stop, spec=spec,
                               eod_bar=sess[-1], day=day, tag=f"P{phase}|{grade}|s{stop:.0f}"))
            if phase == 1:
                n_p1 += 1
    return orders


def sequential_filter(tr, cfg=CFG):
    """Trades in time order; a new one only after the prior exits; session cap; phase-2 halts
    after N consecutive losses (a win resets — he re-enters after single losses)."""
    tr = tr.copy()
    tr["phase"] = tr["tag"].str.split("|").str[0]
    keep = []
    for day, g in tr.groupby("day"):
        g = g.sort_values("entry_dt")
        last_exit = None; n_acc = 0; rev_losses = 0
        for i, r in g.iterrows():
            if n_acc >= cfg["max_per_session"]: break
            if last_exit is not None and r["entry_dt"] <= last_exit: continue
            if r["phase"] == "P2" and rev_losses >= cfg["rev_loss_halt"]: continue
            keep.append(i); n_acc += 1; last_exit = r["exit_dt"]
            if r["phase"] == "P2":
                rev_losses = rev_losses + 1 if r["R"] < 0 else 0
    return tr.loc[keep]


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    raw = engine.simulate(df, session_orders(df), cost_pts=CFG["cost_pts"])
    tr = sequential_filter(raw)
    tr["phase"] = tr["tag"].str.split("|").str[0]
    tr["grade"] = tr["tag"].str.split("|").str[1]
    tr["stop"] = tr["tag"].str.split("|").str[2]
    print(f"NY 9:30 only. candidates {len(raw)} -> accepted {len(tr)} ({len(tr)/len(ad):.2f}/day)\n")

    def es(g):
        if len(g) < 20: return "        (n<20)"
        e = engine.edge_stats(g)
        return f"n={e['n']:4d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"
    print(f"{'':16}{'TRAIN':>34}{'TEST':>34}")
    for key, vals in [("phase", ["P1", "P2"]), ("grade", ["A+", "A"]), ("stop", ["s25", "s50"])]:
        for v in vals:
            g = tr[tr[key] == v]
            print(f"  {key}={v:8} {es(g[g['day']<=cut]):>34} {es(g[g['day']>cut]):>34}")
        print()
    print(f"  {'ALL':12} {es(tr[tr['day']<=cut]):>34} {es(tr[tr['day']>cut]):>34}")

    print("\nFTMO 15k 1-Step MC (-2R breaker):")
    dte = ad[ad > cut]
    for lbl, dd in [("ALL ", build_days(tr, ad, 2.0)),
                    ("OOS ", build_days(tr[tr["day"].isin(set(dte))], dte, 2.0))]:
        best = (-1, None, None)
        for r in (0.005, 0.0075, 0.01, 0.0125, 0.015):
            m = ftmo.run_mc(dd, r, 20, n_paths=40000, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        m40 = ftmo.run_mc(dd, r, 40, n_paths=40000, seed=11, block=5)
        print(f"  [{lbl}] 20d pass {p*100:4.1f}% blow {m['blow_rate']*100:4.1f}% (risk {r*100:.2f}%)"
              f"   40d pass {m40['pass_rate']*100:4.1f}%")
    print("\nReference: 52p ~55/72 (20d/40d), 52pPlus ~58/75.")


if __name__ == "__main__":
    main()
