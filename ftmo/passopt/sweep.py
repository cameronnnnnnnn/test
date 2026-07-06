"""
Comprehensive exit-management sweep for FTMO $15k pass rate. side=both, sessions 15+16.
Crosses BE x hard-TP x trailing x partial scale-out x stepped-lock x vol-regime x risk%.
Ranks by ROBUST score = min(worst-start-half over static & trailing floors) -- the metric that
rewards passing in EVERY sub-period under both drawdown models. Tie-break: fewer months, then
edge-CI-excludes-zero. Multiprocessing over configs.
"""
import sys, os, json, itertools, multiprocessing as mp
sys.path.insert(0,'/home/user/v4/ftmo/passopt')
from evalcfg import evaluate

def grid():
    G=[]
    # Block 1: NO vol filter -- can exit management alone make it robust across both floors?
    for be,tp,trail,part,lock,risk in itertools.product(
            [None,1.0],[None,2.0,3.0,4.0],[None,3.0,5.0],
            [None,(1.5,0.5),(2.0,0.5),(1.0,0.5)],[None,(2.0,1.0)],[0.5,0.75]):
        c=dict(side='both',open_hrs=[15,16],be_at=be,tp_R=tp,trail_k=trail,
               lock_trig=(lock[0] if lock else None),lock_to=(lock[1] if lock else None),
               partial_at=(part[0] if part else None),partial_frac=(part[1] if part else 0.5),
               partial_be=True,risk_pct=risk)
        G.append(c)
    # Block 2: WITH vol filter -- find the FASTEST robust config (raise risk, keep robustness)
    exits=[dict(tp_R=3.0),dict(tp_R=2.0),dict(tp_R=4.0),dict(tp_R=None,trail_k=5.0),
           dict(tp_R=None,trail_k=3.0),dict(tp_R=3.0,partial_at=1.5,partial_frac=0.5),
           dict(tp_R=None,partial_at=2.0,partial_frac=0.5,trail_k=5.0),
           dict(tp_R=3.0,lock_trig=2.0,lock_to=1.0),
           dict(tp_R=None,partial_at=1.5,partial_frac=0.5,trail_k=3.0),
           dict(tp_R=2.5,partial_at=1.25,partial_frac=0.5)]
    for reg,ex,risk in itertools.product([[0.4,1.0],[0.5,1.0]],exits,[0.5,0.75,1.0,1.25]):
        c=dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=reg,risk_pct=risk,partial_be=True); c.update(ex)
        G.append(c)
    return G

def _ev(c):
    try: return evaluate(c, quick=True)
    except Exception as e: return dict(cfg=c, robust=-1, note=str(e))

if __name__=='__main__':
    G=grid(); print(f"evaluating {len(G)} configs on {mp.cpu_count()} cores...")
    with mp.Pool(max(1,mp.cpu_count()-1)) as pool:
        res=pool.map(_ev, G, chunksize=1)
    res=[r for r in res if r.get('robust',-1)>=0]
    def key(r): return (-r['robust'], r.get('months',999), 0 if r.get('edge_ci',[0])[0]>0 else 1)
    res.sort(key=key)
    json.dump(res, open('/home/user/v4/ftmo/passopt/sweep_results.json','w'))
    print(f"\nTOP 30 by robust score (min worst-half over both floors):")
    print(f"{'rob':>5}{'p_st':>6}{'w_st':>6}{'p_tr':>6}{'w_tr':>6}{'mo':>5}{'edge':>7}{'ci>0':>5}  config")
    for r in res[:30]:
        c=r['cfg']; ci0='Y' if r['edge_ci'][0]>0 else 'n'
        tag=[]
        if c.get('atr_regime'): tag.append(f"vol{c['atr_regime'][0]}")
        if c.get('tp_R'): tag.append(f"tp{c['tp_R']}")
        if c.get('trail_k'): tag.append(f"tr{c['trail_k']}")
        if c.get('partial_at'): tag.append(f"pt{c['partial_at']}/{c['partial_frac']}")
        if c.get('lock_trig'): tag.append(f"lk{c['lock_trig']}>{c['lock_to']}")
        if c.get('be_at'): tag.append("be1")
        tag.append(f"r{c['risk_pct']}")
        print(f"{r['robust']:>5.0f}{r['pass_static']:>6.0f}{r['worst_static']:>6.0f}{r['pass_trail']:>6.0f}{r['worst_trail']:>6.0f}{r['months']:>5.1f}{r['edge']:>7.3f}{ci0:>5}  {' '.join(tag)}")
    print(f"\n[full results -> ftmo/passopt/sweep_results.json, {len(res)} configs]")
