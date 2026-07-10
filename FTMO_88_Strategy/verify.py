"""Reproduce the 88% config stats. Run: python3 FTMO_88_Strategy/verify.py"""
import sys, json
sys.path.insert(0, '/home/user/v4/ftmo/passopt')
from evalcfg import evaluate
CFG=json.load(open('/home/user/v4/FTMO_88_Strategy/strategy.json'))['engine_config']
m=evaluate(CFG, quick=False)
print("FTMO $15k | NAS100 | vol>=0.5 + partial 50%@2R->BE + trail 5R + BE@1R | risk 1.25% (aggressive)\n")
print(f"  PASS static floor(FTMO): {m['bb_static']}%   (blow {m['blow_static']}%)")
print(f"  PASS trailing (stress) : {m['bb_trail']}%   (blow {m['blow_trail']}%)")
print(f"  median time to pass    : ~{m['months']} months")
print(f"  edge OOS (test) 90%CI  : {m['edge_test_ci']}")
