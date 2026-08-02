"""
news/reopen_trade.py — is there a tradeable setup off the 6pm ET reopen candle (01:00 server)?

User spec: 25pt stop / 37.5pt TP (1:1.5). Entry right after the reopen candle closes (fills at
the 01:01 open). Exit: TP/SL, else flat before the EU open (09:55 server). One trade/day.

Candidate direction rules (small, principled set — features known at the 01:00 close):
  long / short          unconditional (tests the documented overnight-drift effect)
  cand_cont / cand_rev  continue / reverse the reopen candle's body direction
  gap_cont / gap_fade   continue / fade the reopen gap (open vs pre-break close)
  gap_fade_big          fade only |gap| >= 15pt
  cand_cont_body        continue only when the body >= 10pt (conviction candle)
  rejwick_rev           reverse when the far-side rejection wick >= 40% of range
  mon_long              long only on the weekend reopen (server Monday = Sunday 6pm ET)

Honesty protocol: 70/30 train/test by date; ALL rules shown on both halves; the "pick" is the
train-best only. 2pt cost (NOTE: real overnight spread is often wider — treat results as upper
bounds). Run: python3 reopen_trade.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402

STOP = 25.0; TP_R = 1.5; COST = 2.0
EOD_MIN = 9*60 + 55                                          # flat before EU open


def build_days(nas):
    idx = nas.index.values.astype("datetime64[m]")
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    tod = nas["tod"].values
    feats = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        pos = gi[t == 60]
        if len(pos) != 1: continue
        b0 = pos[0]
        if b0 == 0: continue
        gap_min = int((idx[b0] - idx[b0-1]) / np.timedelta64(1, "m"))
        if gap_min < 30: continue                            # not a true reopen (DST desync days)
        eod = gi[(t > 60) & (t <= EOD_MIN)]
        if len(eod) < 120: continue
        body = c[b0] - o[b0]; rng = max(h[b0] - l[b0], 1e-9)
        cdir = np.sign(body)
        rej = (h[b0] - max(o[b0], c[b0])) if cdir > 0 else (min(o[b0], c[b0]) - l[b0])
        feats.append(dict(day=day, b0=b0, eod=eod[-1],
                          gap=o[b0] - c[b0-1], body=body, cdir=cdir,
                          rejfrac=rej / rng,
                          dow=pd.Timestamp(day).dayofweek))
    return pd.DataFrame(feats)


RULES = {
    "long":           lambda f: np.ones(len(f)),
    "short":          lambda f: -np.ones(len(f)),
    "cand_cont":      lambda f: f["cdir"],
    "cand_rev":       lambda f: -f["cdir"],
    "gap_cont":       lambda f: np.sign(f["gap"]),
    "gap_fade":       lambda f: -np.sign(f["gap"]),
    "gap_fade_big":   lambda f: np.where(f["gap"].abs() >= 15, -np.sign(f["gap"]), 0),
    "cand_cont_body": lambda f: np.where(f["body"].abs() >= 10, f["cdir"], 0),
    "rejwick_rev":    lambda f: np.where(f["rejfrac"] >= 0.4, -f["cdir"], 0),
    "mon_long":       lambda f: np.where(f["dow"] == 0, 1.0, 0.0),
}


def run_rule(nas, F, dirs, tag):
    spec = ExitSpec(tp_R=TP_R, be_R=0.0, trail_R=0.0, max_bars=600)
    orders = [dict(entry_bar=int(r.b0), dir=int(d), stop_pts=STOP, spec=spec,
                   eod_bar=int(r.eod), day=r.day, tag=tag)
              for (_, r), d in zip(F.iterrows(), dirs) if d != 0]
    if not orders: return None
    return engine.simulate(nas, orders, cost_pts=COST)


def stats(tr, days):
    if tr is None or len(tr) < 15: return None
    e = engine.edge_stats(tr)
    return f"n={e['n']:3d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"


def main():
    nas = S.prep(data.load())
    F = build_days(nas)
    ad = np.array(sorted(F["day"].unique())); cut = ad[int(len(ad)*0.7)]
    print(f"{len(F)} true-reopen days.  gap: mean|{F['gap'].abs().mean():.0f}|pt  "
          f"body: mean|{F['body'].abs().mean():.0f}|pt")
    # ground the mechanism: raw overnight drift 01:01 -> 09:55 (no stops)
    idx = nas.index.values; o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    drift = [c[int(r.eod)] - o[int(r.b0)+1] for _, r in F.iterrows()]
    print(f"raw overnight drift (01:01->09:55, no stops): mean {np.mean(drift):+.1f}pt  "
          f"median {np.median(drift):+.1f}pt  up {np.mean(np.array(drift)>0)*100:.0f}%\n")

    print(f"{'rule':16}{'TRAIN':>34}{'TEST':>34}")
    results = {}
    for name, fn in RULES.items():
        dirs = np.asarray(fn(F), float)
        tr = run_rule(nas, F, dirs, name)
        if tr is None: continue
        g = tr[tr["day"] <= cut]; gte = tr[tr["day"] > cut]
        str_tr = stats(g, None); str_te = stats(gte, None)
        etr = engine.edge_stats(g)["expR"] if len(g) >= 15 else float("nan")
        results[name] = (etr, str_tr, str_te)
        print(f"{name:16}{str_tr or '(n<15)':>34}{str_te or '(n<15)':>34}")
    best = max(results, key=lambda k: results[k][0] if results[k][0] == results[k][0] else -9)
    print(f"\ntrain-best rule: {best} -> judge it ONLY by its TEST column above.")


if __name__ == "__main__":
    main()
