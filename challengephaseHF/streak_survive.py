"""
challengephaseHF/streak_survive.py — "how many losses IN A ROW from the initial balance can I take
and still pass within 40 trading days?" Two caps: (1) hard survival — consecutive 1R losses before
the equity hits the 10% floor ($13,500); (2) practical — after N losses (which also EAT trading
days, ~3 losses/day with the -2R breaker), the pass rate over the remaining days out of 40.
Reports the curve so you can see where a cold start goes from 'recoverable' to 'cooked'.
Run: python3 streak_survive.py [risk_pct]   (default 0.5)
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402

NP = 100_000; DEADLINE = 40; LOSS_PER_DAY = 3.0      # ~3 losses/day with the -2R breaker + clustering


def main():
    risk = (float(sys.argv[1]) if len(sys.argv) > 1 else 0.5) / 100.0
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    # hard survival cap: consecutive 1R losses until equity <= 0.90 (10% floor)
    floor_hit = int(np.ceil(np.log(0.90) / np.log(1 - risk)))
    print(f"52p at {risk*100:.2f}% risk, 40 trading-day window, start $15,000\n")
    print(f"HARD SURVIVAL CAP: {floor_hit} losses in a row hits the $13,500 floor (=blown).")
    print(f"  (each loss ~{risk*100:.2f}% ; a losing day caps ~-2 to -3 losses via the -2R breaker,")
    print(f"   so {floor_hit} straight losses would span ~{int(np.ceil(floor_hit/LOSS_PER_DAY))} trading days.)\n")

    print("PRACTICAL: after N straight losses (which also burn ~N/3 days), can you still pass in 40d?")
    print(f"  {'N losses':>9}{'drawdown':>10}{'days used':>11}{'days left':>11}{'pass%':>8}")
    for N in range(0, floor_hit + 2, 2):
        e0 = (1 - risk) ** N
        used = int(np.ceil(N / LOSS_PER_DAY))
        left = DEADLINE - used
        if e0 <= 0.90 + 1e-9 or left <= 0:
            print(f"  {N:>9}{(1-e0)*100:>9.1f}%{used:>11}{max(left,0):>11}{'BLOWN/no time':>13}")
            continue
        p = ftmo.run_mc(days, risk, left, n_paths=NP, seed=11, block=5, e0=e0)["pass_rate"]
        tag = "  <- still >50%" if p > 0.5 else ("  <- long shot" if p < 0.15 else "")
        print(f"  {N:>9}{(1-e0)*100:>9.1f}%{used:>11}{left:>11}{p*100:>7.1f}%{tag}")
    print("\nRead: the pass % is your realistic chance IF you go on a cold streak of N to open the")
    print("account, then trade normally. It stays high for a while (small early losses barely dent")
    print("a 40-day window), then falls off as buffer + time run out well before the hard blow cap.")


if __name__ == "__main__":
    main()
