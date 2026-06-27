"""
Lucid/strategy_lucid.py — FINAL verified strategy + results for the 25K FLEX EVAL.

Reproduces the headline numbers. Engine + Monte-Carlo are bug-checked in test_lucid.py
(8 golden cases + full vectorized-vs-scalar equivalence + zero-look-ahead engine checks).

RULES MODELED (from the card):
  $25,000 ; +$1,250 target (5%) ; $1,000 max loss, EOD TRAILING drawdown ;
  NO daily loss limit ; 50% consistency (eval) ; max 2 minis / 20 micros ($40/pt).
  NQ contract: $20/pt (mini), $2/pt (micro). Data = NAS100 M1 (NQ proxy), 2022-10..2025-10.

ASSUMPTIONS (flagged — they're one-line params if a rule differs):
  * "EOD drawdown" => the breach is judged on the END-OF-DAY balance (intraday swings are
    free, consistent with 'no daily limit'). 'intraday' breach is ~1pp stricter (similar).
  * consistency denominator = total NET profit (best green day <= 50% of net).
  * round-turn cost = 1.0 index pt (MNQ commission + ~1 tick); robust to 0.5..2.5pt.
"""
import numpy as np
import data, strategies as S, engine, lucid

COST = 1.0; NP = 80000; FEE = 70.0; RESET = 60.0

def evaluate(orders, stop, n_micros):
    tr = engine.simulate(DF, orders, cost_pts=COST)
    es = engine.edge_stats(tr); days = lucid.build_days(tr, AD)
    rd = stop * lucid.PT_MICRO * n_micros
    m21 = lucid.run_eval_mc(days, rd, 21, n_paths=NP, seed=11, breach="eod")
    m63 = lucid.run_eval_mc(days, rd, 63, n_paths=NP, seed=11, breach="eod")
    cost_fund = FEE + (1.0/m63["pass_rate"] - 1.0)*RESET
    return es, rd, m21, m63, cost_fund

def line(tag, orders, stop, n_micros):
    es, rd, m21, m63, cf = evaluate(orders, stop, n_micros)
    print(f"{tag}")
    print(f"    setup: 30-min ORB, {stop}pt stop, 3R TP, vol-confirmed | {n_micros} micro(s) = ${rd:.0f} risk/trade")
    print(f"    edge : {es['n']} trades, WR {es['wr']*100:.1f}%, expR {es['expR']:+.3f}")
    print(f"    MONTHLY pass {m21['pass_rate']*100:.1f}%   |   EVENTUAL pass {m63['pass_rate']*100:.1f}%   "
          f"blow {m63['blow_rate']*100:.1f}%   median {m21['med_days']:.0f}d")
    print(f"    EV   : ~{1/m63['pass_rate']:.2f} evals/funded -> ${cf:.0f} to fund a $25k account\n")

def main():
    global DF, AD
    DF = S.prep(data.load()); AD = np.array(sorted(DF["date"].unique()))
    print("="*94)
    print("LUCID 25K FLEX EVAL — FINAL STRATEGIES (verified; see test_lucid.py)")
    print(f"$25k, +$1,250 / -$1,000 EOD-trailing, no daily limit, 50% consist. COST={COST}pt, {NP} paths")
    print("server time = ET+7 (EET): 16:00 server ~ 09:00 ET (US) ; 11:00 server ~ 04:00 ET (EU)")
    print("="*94)

    print(">> BEST MONTHLY PASS RATE (your objective):")
    line("   [A] EUROPEAN-open ORB  (11:00 server / ~04:00 ET)",
         S.orb(DF, open_min=660, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True), 60, 2)

    print(">> CONVENIENT US-SESSION ALTERNATIVE (nearly as good, 09:00 ET):")
    line("   [B] US-open ORB  (16:00 server / ~09:00 ET)",
         S.orb(DF, open_min=960, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True), 60, 2)

    print(">> BEST TO ACTUALLY GET FUNDED (no time limit -> max eventual pass, lowest blow):")
    line("   [C] BOTH sessions, half size  (diversified)",
         S.orb(DF, open_min=960, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
         + S.orb(DF, open_min=660, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True), 60, 1)

    print("="*94)
    print("TAKEAWAYS")
    print(" - The $1,000 EOD-trailing DD (4%) vs the +$1,250 target (5%) is the binding constraint;")
    print("   with NQ's thin intraday edge the monthly pass ceiling is ~40-42% (robust across both")
    print("   data halves and costs 0.5-2.5pt). No config beats this materially — it's structural.")
    print(" - For passing THIS MONTH: [A] European ORB, 2 micros -> ~42%.")
    print(" - For getting FUNDED cheaply (evals have no time limit): [C] both-session combo at 1 micro")
    print("   -> ~57% eventual pass (rising with time), ~42% blow, ~$115 per funded $25k acct. Best EV.")
    print(" - Sizing is tiny by design (1-2 micros): the tight trailing DD punishes size. Do NOT use")
    print("   the 2-mini cap — that risks ~$2,400/trade and blows instantly.")

if __name__ == "__main__":
    main()
