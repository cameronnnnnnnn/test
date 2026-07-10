"""
newstrat/scan.py — iteration 1: the honest edge-vs-RR scan across ALL instruments. The user's
target is higher-frequency / lower-RR / higher-WR / higher-pass. The project says pass rate loves
HIGH RR — so the first question to settle with data is: does a LOWER-RR setup keep positive
expectancy on ANY instrument after cost? Sweeps session-open breakouts (ATR-scaled stops) across
RR = 1.5..4 on each instrument's relevant sessions, reporting /day, realized WR, realized RR, and
expR-after-cost. Positive expR at LOW RR = a seed for the higher-WR strategy; flat/negative = the
high-RR structure wins again. Run: python3 scan.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import strategies as S, engine                        # noqa: E402
import allinstr                                       # noqa: E402

# which sessions to try per instrument (server minutes)
SESS = {
    "NAS100": [("usidx", 16*60), ("uscash", 16*60+30)],
    "EURUSD": [("london", 10*60), ("usidx", 16*60)],
    "GBPUSD": [("london", 10*60), ("usidx", 16*60)],
    "AUDUSD": [("tokyo", 0), ("london", 10*60)],
    "USDJPY": [("tokyo", 0), ("london", 10*60)],
}
RRS = [1.5, 2.0, 2.5, 3.0, 4.0]
STOP_FRAC = 0.20            # stop = 0.20 x daily ATR


def main():
    print("Loading all instruments ...")
    D = allinstr.load_all()
    print("\n" + "=" * 90)
    print("EDGE vs RR — session-open breakout, 0.20-ATR stop, real cost.  (want: +expR at LOW RR)")
    print("=" * 90)
    print(f"  {'instr':7} {'session':8} {'RR':>4} {'/day':>5} {'WR':>6} {'realRR':>7} {'expR':>7}  {'note':>10}")
    for x in allinstr.ALL:
        info = D[x]; sm = allinstr.stopmap(info, STOP_FRAC); nd = info["ndays"]
        for sname, omin in SESS[x]:
            for rr in RRS:
                orders = S.orb(info["df"], open_min=omin, or_min=30, tp_R=rr, be_R=0.0,
                               vol_filter=True, stop_map=sm)
                tr = engine.simulate(info["df"], orders, cost_pts=info["cost"])
                if not len(tr):
                    continue
                es = engine.edge_stats(tr)
                # realized RR = avg_win / |avg_loss|
                rrr = (es["avg_win"] / abs(es["avg_loss"])) if es["avg_loss"] < 0 else float("nan")
                note = "  <-- +EV" if es["expR"] > 0.02 else ""
                print(f"  {x:7} {sname:8} {rr:>4.1f} {es['n']/nd:5.2f} {es['wr']*100:5.1f}% "
                      f"{rrr:7.2f} {es['expR']:+7.3f}{note}")
            print()
    print("-" * 90)
    print("Reading: if expR turns negative as RR drops (and only high RR is +EV), the pass-rate")
    print("advantage of high-RR structure holds. If some instrument is +EV at RR 1.5-2 with a high")
    print("WR, that's the seed to build the higher-frequency/higher-WR strategy around.")


if __name__ == "__main__":
    main()
