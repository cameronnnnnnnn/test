"""
newstrat/regime_optimize.py — duplicate 52p and try to optimise it with regime switching, HONESTLY.
The regime matrix showed: on NAS100, momentum owns unclear/trend days, but on prior-day-RANGE days
momentum is unreliable while FADE is the clean edge (+0.11/+0.20, 55% WR). So the switch to test:

  base    : 52p momentum every day (current)
  add     : 52p every day + fade on prior-day-range days
  switch  : 52p momentum on non-range days, FADE INSTEAD on range days (the real regime switch)

Standard untuned regime thresholds (ADX/chop). MC 20-day pass, risk on TRAIN, reported on TEST +
4-fold. Only an improvement if TEST and worst-fold both rise vs base. Run: python3 regime_optimize.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine, ftmo                  # noqa: E402
from search import build_days                          # noqa: E402
import ChallengePhase52p as CP52                        # noqa: E402
import allinstr                                         # noqa: E402
from regime_matrix import regime_map                    # noqa: E402

BREAKER = 2.0; NP = 60000
RISKS = (0.004, 0.005, 0.006, 0.0075, 0.01, 0.0125)


def mc(ds, r, dl=20): return ftmo.run_mc(ds, r, dl, n_paths=NP, seed=11, block=5)
def best_risk(ds, dl=20): return max(RISKS, key=lambda r: mc(ds, r, dl)["pass_rate"])


def main():
    D = allinstr.load_all(verbose=False)
    df = D["NAS100"]["df"]; sm = allinstr.stopmap(D["NAS100"], 0.20)
    ad = np.array(sorted(df["date"].unique()))
    reg = regime_map(df)
    range_days = set(d for d in ad if reg.get(d) == "range")

    mom = engine.simulate(df, CP52.build(df), cost_pts=2.0)                       # 52p momentum
    fade = engine.simulate(df, S.vwap_fade_sel(df, k=2.0, open_min=16*60, trail_R=2.0,
                           partial_R=1.0, stop_map=sm), cost_pts=2.0)
    fade_range = fade[fade["day"].isin(range_days)]
    mom_nonrange = mom[~mom["day"].isin(range_days)]

    variants = {
        "base 52p":            [mom],
        "add fade|range":      [mom, fade_range],
        "switch (fade on range)": [mom_nonrange, fade_range],
    }

    print(f"NAS100 regime-switched 52p — all-data pass, risk optimised per horizon. "
          f"range days: {len(range_days)}/{len(ad)}\n")
    print(f"  {'variant':26} {'/day':>5} | {'1-month (20d)':>22} | {'2-month (40d)':>22} | {'eventual (60d)':>22}")
    print(f"  {'':26} {'':>5} | {'r*':>6}{'pass':>8}{'blow':>8} | {'r*':>6}{'pass':>8}{'blow':>8} | {'r*':>6}{'pass':>8}{'blow':>8}")
    for nm, parts in variants.items():
        t = pd.concat(parts, ignore_index=True)
        perday = len(t) / len(ad)
        ds = build_days(t[t["day"].isin(set(ad))], ad, BREAKER)
        row = f"  {nm:26} {perday:5.2f} |"
        for dl in (20, 40, 60):
            r = best_risk(ds, dl); m = mc(ds, r, dl)
            row += f" {r*100:5.2f}%{m['pass_rate']*100:7.1f}%{m['blow_rate']*100:7.1f}% |"
        print(row)
    print("\n" + "-"*94)
    print("The switch removes momentum on range days (whipsaw-prone) and fades instead -> lower blow.")
    print("On a no-time-limit challenge, watch the EVENTUAL (40-60d) column: if the switch's lower")
    print("blow lifts eventual pass above base, it's a genuine improvement for a 2-month player.")


if __name__ == "__main__":
    main()
