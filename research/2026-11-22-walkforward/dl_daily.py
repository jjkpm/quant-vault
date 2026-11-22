import sys, pickle
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q
end = 1795305600
out = {}
for s in Q.SYMS:
    b = Q.klines(s, "1d", 1500000000 * 1000, end * 1000 - 1)
    out[s] = [x for x in b if x[0] + 86400 <= end]
    print(s, len(out[s]), Q.datetime.utcfromtimestamp(out[s][0][0]).date())
pickle.dump(out, open("daily.pkl", "wb"))
