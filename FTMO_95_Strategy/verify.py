"""
Reproduce the verified stats for the FTMO $15k 95% static-floor config.
Run: python3 FTMO_95_Strategy/verify.py
Loads strategy.json, evaluates it through the committed MC engine (ftmo/passopt/evalcfg.py),
and prints pass/blow under both floor models (static = real FTMO, trailing = stress) plus edge CIs.
"""
import sys, os, json
sys.path.insert(0, '/home/user/v4/ftmo/passopt')
from evalcfg import evaluate

CFG = json.load(open('/home/user/v4/FTMO_95_Strategy/strategy.json'))['engine_config']
m = evaluate(CFG, quick=False)
print("FTMO $15k 1-Step | NAS100 | vol>=0.5 + partial 50%@2R->BE + trail 5R + BE@1R | risk 1.0%\n")
print(f"  trades in sample        : {m['n']}")
print(f"  PASS  static floor(FTMO): {m['bb_static']}%   (blow {m['blow_static']}%)")
print(f"  PASS  trailing (stress) : {m['bb_trail']}%   (blow {m['blow_trail']}%)")
print(f"  median time to pass     : ~{m['months']} months (calendar)")
print(f"  per-trade edge          : {m['edge']:+.3f}  90%CI {m['edge_ci']}")
print(f"  edge OOS (test) 90%CI   : {m['edge_test_ci']}  ({'clears 0' if m['edge_test_ci'][0]>0 else 'grazes 0'})")
