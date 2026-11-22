"""Entry-quality filters, chosen walk-forward: for each 30-day segment j, pick the filter set that did best on
segments < j (anchored, min 40 trades), apply it unchanged to segment j. Only the OOS segments count."""
import sys, pickle, itertools, json
from sim import *

seed = int(sys.argv[1]); exitpol = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
S = pickle.load(open(f"signals_s{seed}.pkl", "rb")); T0 = S["T0"]
sigs = [g for g in S["signals"] if g["t"] < 1795305600 - 3 * 86400]
res = run_policy(sigs, exitpol); ghost = run_policy(sigs, {"be": 0})
R = [r[1] for r in res]; seg = [int((g["t"] - T0) // (30 * 86400)) for g in sigs]; nseg = max(seg) + 1

GRID = {"tfs": [(15, 60, 240), (60, 240), (240,)], "cmax": [0.25, 0.15, 0.10], "smin": [0.2, 0.35, 0.5],
        "nside": [1, 3], "novol": [False, True]}
combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
def ok(g, f):
    return (g["tf"] in f["tfs"] and g["cR"] <= f["cmax"] and abs(g["score"]) >= f["smin"] and g["nside"] >= f["nside"]
            and not (f["novol"] and "volspike" in g["tags"]))
base_f = {"tfs": (15, 60, 240), "cmax": 9, "smin": 0.2, "nside": 1, "novol": False}
picks = []; keep = [False] * len(sigs)
for j in range(2, nseg):
    past = [i for i in range(len(sigs)) if seg[i] < j]
    def score(f):
        v = [R[i] for i in past if ok(sigs[i], f)]
        return sum(v) / len(v) if len(v) >= 40 else -9
    best = max(combos, key=score); picks.append((j, best, round(score(best), 3)))
    for i in range(len(sigs)):
        if seg[i] == j and ok(sigs[i], best): keep[i] = True
oos_idx = [i for i in range(len(sigs)) if seg[i] >= 2]
sel = [R[i] for i in oos_idx if keep[i]]; allR = [R[i] for i in oos_idx]
n, m, sd = stats(sel); nb, mb, _ = stats(allR)
# block bootstrap of the selected trades' mean (whole days resampled)
days = defaultdict(list)
for i in oos_idx:
    if keep[i]: days[int(sigs[i]["t"] // 86400)].append(R[i])
keys = list(days); rng = random.Random(3); ms = []
for _ in range(4000):
    s = c = 0
    for _ in keys:
        v = days[keys[rng.randrange(len(keys))]]; s += sum(v); c += len(v)
    ms.append(s / c)
ms.sort()
print(f"seed {seed} exit={exitpol}  OOS segments 2..{nseg-1}")
print(f"  all signals : n={nb} meanR={mb:+.3f}")
print(f"  WF-filtered : n={n} meanR={m:+.3f}  95% lower bound {ms[200]:+.3f}  upper {ms[3800]:+.3f}")
segm = defaultdict(list)
for i in oos_idx:
    if keep[i]: segm[seg[i]].append(R[i])
print("  per segment :", {k: (len(v), round(sum(v) / len(v), 3)) for k, v in sorted(segm.items())})
for j, f, sc in picks: print("  pick", j, f, "past meanR", sc)
# portfolio, production rules, on OOS segments only, filtered vs unfiltered
for name, mask in [("unfiltered", [seg[i] >= 2 for i in range(len(sigs))]), ("WF-filtered", keep)]:
    ss = [sigs[i] for i in range(len(sigs)) if mask[i]]; rr = [res[i] for i in range(len(sigs)) if mask[i]]; gg = [ghost[i] for i in range(len(sigs)) if mask[i]]
    p = portfolio(ss, {"pol": rr, "ghost": gg})
    print(f"  portfolio {name:12s}: ret {(p['eq']/1e4-1)*100:+.2f}%  mdd {p['mdd']*100:.2f}%  trades {p['n']}")
