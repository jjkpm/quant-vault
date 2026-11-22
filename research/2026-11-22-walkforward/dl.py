import sys, json, time, pickle
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q
from concurrent.futures import ThreadPoolExecutor
end = 1795305600            # 2026-11-22 00:00 UTC (complete bars only)
start = end - 400 * 86400   # ~13 months
def job(j):
    sym, tf = j
    b = Q.klines(sym, Q.IV[tf], start * 1000, end * 1000 - 1)
    return j, [x for x in b if x[0] + tf * 60 <= end]
with ThreadPoolExecutor(6) as ex:
    data = dict(ex.map(job, [(s, tf) for s in Q.SYMS for tf in Q.TFS]))
for k, v in sorted(data.items()): print(k, len(v), v[0][0] if v else None, v[-1][0] if v else None)
pickle.dump(data, open("bars.pkl", "wb"))
