import sys, pickle, random
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q
data = pickle.load(open("bars.pkl", "rb"))
random.seed(1)
rows = []
for fam in Q.FAM:
    for tf in Q.TFS:
        if not Q.fam_tf_ok(fam, tf): continue
        params = [Q.rand_params(fam, default=True)] + [Q.rand_params(fam) for _ in range(2)]
        look = win = tot = nz_full = 0; ex = None
        for sym in ["BTCUSDT", "ETHUSDT", "XRPUSDT", "AVAXUSDT"]:
            B = data[(sym, tf)][-3000:]
            for p in params:
                full = Q.sig_series(fam, B, p)
                idx = random.sample(range(400, len(B)), 60)
                for i in idx:
                    tr = Q.sig_series(fam, B[:i + 1], p)[-1]
                    lw = Q.sig_series(fam, B[max(0, i - 259):i + 1], p)[-1]
                    tot += 1; nz_full += bool(full[i])
                    if tr != full[i]: look += 1; ex = ex or (sym, i, full[i], tr)
                    if lw != full[i]: win += 1
        rows.append((fam, tf, tot, nz_full, look, win, ex))
        print(f"{fam:10s} {tf:>3}m  n={tot}  signals={nz_full}  LOOKAHEAD_diff={look}  live260_diff={win}  {ex or ''}", flush=True)
pickle.dump(rows, open("bias.pkl", "wb"))
