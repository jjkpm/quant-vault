import sys, pickle, json
from sim import *
POL = {"base": {},
       "BE@1.0 (all)": {"be": 1},
       "BE@0.5 lock+0.1": {"be": 1, "trig": 0.5, "lock": 0.1},
       "BE@0.5 lock 0": {"be": 1, "trig": 0.5, "lock": 0.0},
       "BE@0.75 lock+0.1": {"be": 1, "trig": 0.75, "lock": 0.1},
       "half@0.5 +BE": {"part": 1, "trig": 0.5, "lock": 0.1},
       "trail0.5 from 0.5": {"trail": 0.5, "trig": 0.5, "lock": 0.1},
       "trail1.0 from 0.5": {"trail": 1.0, "trig": 0.5, "lock": 0.1}}
for seed in (0, 1):
    S = pickle.load(open(f"signals_s{seed}.pkl", "rb")); T0 = S["T0"]
    sigs = [g for g in S["signals"] if g["t"] < 1795305600 - 3 * 86400]
    seg = [int((g["t"] - T0) // (30 * 86400)) for g in sigs]; nseg = max(seg) + 1; t = [g["t"] for g in sigs]
    ghost = run_policy(sigs, {"be": 0}); res = {k: run_policy(sigs, v) for k, v in POL.items()}
    base = [x[1] for x in res["base"]]
    print(f"=== seed {seed}: {len(sigs)} signals ===")
    print(f"{'rule':20s} {'meanR':>7} {'diff':>7} {'lb95':>7} {'segs+':>6} {'win%':>5} {'1h diff':>8} | {'port ret%':>9} {'mdd%':>6}")
    for k, r in res.items():
        Rs = [x[1] for x in r]; n, m, _ = stats(Rs)
        diff, lb = block_boot_diff(t, Rs, base) if k != "base" else (0, 0)
        segd = []
        for j in range(nseg):
            a = [Rs[i] for i in range(len(sigs)) if seg[i] == j]; b = [base[i] for i in range(len(sigs)) if seg[i] == j]
            if a: segd.append(sum(a) / len(a) - sum(b) / len(b))
        h1 = [i for i in range(len(sigs)) if sigs[i]["tf"] == 60]
        d1 = sum(Rs[i] - base[i] for i in h1) / len(h1)
        p = portfolio(sigs, {"pol": r, "ghost": ghost})
        print(f"{k:20s} {m:7.3f} {diff:7.3f} {lb:7.3f} {sum(1 for x in segd if x > 0):>3}/{len(segd):<2} {100*sum(1 for x in Rs if x > 0)/n:5.1f} {d1:8.3f} | {(p['eq']/1e4-1)*100:9.2f} {p['mdd']*100:6.2f}")
