import sys, pickle, json
from sim import *

POL = {
    "base": {},                                   # production today: fixed SL/TP, +1R->+0.1R only if the voters' majority uses it
    "be_all": {"be": 1},
    "trail1.0": {"trail": 1.0}, "trail1.5": {"trail": 1.5}, "trail2.0": {"trail": 2.0},
    "trail1.5_noTP": {"trail": 1.5, "notp": 1}, "trail2.0_noTP": {"trail": 2.0, "notp": 1},
    "time24": {"tlim": 24}, "time48": {"tlim": 48}, "time96": {"tlim": 96},
    "be+time48": {"be": 1, "tlim": 48},
    "partial": {"part": 1}, "partial+trail1.5": {"part": 1, "trail": 1.5},
}
FAMS = {"trail": ["trail1.0", "trail1.5", "trail2.0"], "time": ["time24", "time48", "time96"]}

def main(seed):
    S = pickle.load(open(f"signals_s{seed}.pkl", "rb")); sigs = S["signals"]; T0 = S["T0"]
    sigs = [g for g in sigs if g["t"] < 1795305600 - 3 * 86400]       # leave room for exits at the end
    res = {k: run_policy(sigs, v) for k, v in POL.items()}
    ghost = run_policy(sigs, {"be": 0})
    t = [g["t"] for g in sigs]; seg = [int((g["t"] - T0) // (30 * 86400)) for g in sigs]
    nseg = max(seg) + 1
    out = {"seed": seed, "n_signals": len(sigs), "signal_level": {}, "segments": {}, "portfolio": {}}
    base = [r[1] for r in res["base"]]
    for k, r in res.items():
        Rs = [x[1] for x in r]; n, m, sd = stats(Rs)
        diff, lb = block_boot_diff(t, Rs, base) if k != "base" else (0, 0)
        segm = []
        for j in range(nseg):
            a = [Rs[i] for i in range(len(sigs)) if seg[i] == j]; b = [base[i] for i in range(len(sigs)) if seg[i] == j]
            segm.append(round(sum(a) / len(a) - sum(b) / len(b), 4) if a else None)
        wins = sum(1 for x in segm if x is not None and x > 0)
        reasons = defaultdict(int)
        for x in r: reasons[x[2]] += 1
        out["signal_level"][k] = {"meanR": round(m, 4), "diff_vs_base": round(diff, 4), "lb95": round(lb, 4),
                                  "seg_better": f"{wins}/{sum(1 for x in segm if x is not None)}", "seg_diff": segm,
                                  "win%": round(100 * sum(1 for x in Rs if x > 0) / n, 1), "exits": dict(reasons)}
    # anchored walk-forward choice of the parameter inside each family (choose on past segments, score the next one)
    for fam, ks in FAMS.items():
        picks = []; oos = []; oosb = []
        for j in range(2, nseg):
            past = [i for i in range(len(sigs)) if seg[i] < j]; nxt = [i for i in range(len(sigs)) if seg[i] == j]
            best = max(ks, key=lambda k: sum(res[k][i][1] for i in past) / len(past))
            picks.append(best); oos += [res[best][i][1] for i in nxt]; oosb += [base[i] for i in nxt]
        out["segments"][fam] = {"picks": picks, "oos_meanR": round(sum(oos) / len(oos), 4), "base_same_period": round(sum(oosb) / len(oosb), 4)}
    # portfolio with production rules
    for k in res:
        p = portfolio(sigs, {"pol": res[k], "ghost": ghost})
        out["portfolio"][k] = {"ret%": round((p["eq"] / 1e4 - 1) * 100, 2), "mdd%": round(p["mdd"] * 100, 2), "n": p["n"],
                               "meanR": round(sum(x[1] for x in p["trades"]) / max(1, p["n"]), 4)}
    for k in ["base", "be_all", "trail1.5", "time48"]:
        for name, kw in [("dircap2", {"dircap": 2}), ("slguard3/24/4", {"slguard": (3, 24, 4)}), ("both", {"dircap": 2, "slguard": (3, 24, 4)})]:
            p = portfolio(sigs, {"pol": res[k], "ghost": ghost}, **kw)
            out["portfolio"][f"{k}+{name}"] = {"ret%": round((p["eq"] / 1e4 - 1) * 100, 2), "mdd%": round(p["mdd"] * 100, 2), "n": p["n"],
                                               "meanR": round(sum(x[1] for x in p["trades"]) / max(1, p["n"]), 4)}
    json.dump(out, open(f"result_s{seed}.json", "w"), ensure_ascii=False, indent=1)
    print(f"=== seed {seed}: {len(sigs)} signals ===")
    print(f"{'policy':18s} {'meanR':>7} {'diff':>7} {'lb95':>7} {'segs+':>6} {'win%':>5} | {'ret%':>7} {'mdd%':>6} {'n':>4} {'tradeR':>7}")
    for k, v in out["signal_level"].items():
        p = out["portfolio"][k]
        print(f"{k:18s} {v['meanR']:7.3f} {v['diff_vs_base']:7.3f} {v['lb95']:7.3f} {v['seg_better']:>6} {v['win%']:5.1f} | {p['ret%']:7.2f} {p['mdd%']:6.2f} {p['n']:4d} {p['meanR']:7.3f}")
    print("-- portfolio rules --")
    for k, p in out["portfolio"].items():
        if "+" in k and k.split("+")[-1] in ("dircap2", "slguard3/24/4", "both"):
            print(f"{k:28s} ret {p['ret%']:7.2f}%  mdd {p['mdd%']:6.2f}%  n {p['n']:4d}  meanR {p['meanR']:.3f}")
    print("-- anchored WF parameter choice --", json.dumps(out["segments"], ensure_ascii=False))

if __name__ == "__main__":
    main(int(sys.argv[1]))
