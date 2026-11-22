"""Exit-policy + portfolio-rule tests on the walk-forward signals (all out-of-sample by construction).
Trade paths are walked on 15m bars; when a bar touches both stop and target, the stop counts (same as the engine)."""
import sys, pickle, bisect, math, random, json
from collections import defaultdict
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q

data = pickle.load(open("bars.pkl", "rb"))
B15 = {s: data[(s, 15)] for s in Q.SYMS}
I15 = {s: [x[0] for x in v] for s, v in B15.items()}
MAXH = 30 * 96   # 30 days of 15m bars

def walk(sig, pol):
    """returns (exit_time, R_net, reason). pol: dict(be, trail, notp, tlim, part)"""
    s = sig["sym"]; d = sig["d"]; e = sig["e"]; r = sig["slD"]; B = B15[s]
    j = bisect.bisect_left(I15[s], sig["t"])            # first 15m bar that opens at/after the decision
    sl = e - d * r; tp = None if pol.get("notp") else e + d * sig["tpD"]
    be = pol.get("be", sig["be"]); trail = pol.get("trail"); part = pol.get("part")
    moved = False; best = e; banked = 0.0; w = 1.0
    tlim = sig["t"] + pol["tlim"] * sig["tf"] * 60 if pol.get("tlim") else None
    cR = sig["cR"]
    for k in range(j, min(len(B), j + MAXH)):
        t0, o, h, l, c = B[k]
        if tlim and t0 >= tlim:                          # time barrier: out at the open of the first bar past the limit
            return t0, banked + w * (o - e) * d / r - cR, "TIME"
        if (l <= sl) if d > 0 else (h >= sl):
            return t0 + 900, banked + w * (sl - e) * d / r - cR, ("BE" if moved else "SL")
        if tp is not None and ((h >= tp) if d > 0 else (l <= tp)):
            return t0 + 900, banked + w * (tp - e) * d / r - cR, "TP"
        best = max(best, h) if d > 0 else min(best, l)
        if not moved and ((best >= e + r) if d > 0 else (best <= e - r)):
            if part:  # bank half at +1R
                banked += 0.5 * 1.0; w = 0.5
            if be or trail or part:
                sl = e + d * Q.BE_LOCK * r; moved = True
        if moved and trail:
            nsl = best - d * trail * r
            if (nsl > sl) if d > 0 else (nsl < sl): sl = nsl
    t0, o, h, l, c = B[min(len(B), j + MAXH) - 1]
    return t0 + 900, banked + w * (c - e) * d / r - cR, "END"

def run_policy(sigs, pol):
    return [walk(g, pol) for g in sigs]

def portfolio(sigs, res, dircap=None, slguard=None, tagrules=True):
    """production rules: one position per coin, open risk <= 2 %, Kelly > 0, learned tag rules (from ghosts closed
    before the decision), Guardian -3 %/day on realized P&L. Optional: same-direction cap, StoplossGuard."""
    eq = 1e4; peak = eq; mdd = 0; openp = []; taken = []; tagst = defaultdict(lambda: [0, 0.0]); ghost_q = []
    day = None; day_start = eq; halted = False; sl_times = []; pause_until = 0
    order = sorted(range(len(sigs)), key=lambda i: sigs[i]["t"])
    # ghost outcomes for tag learning use the plain engine ghost rule (SL=-1 / TP=rr), known only once closed
    for i in order:
        g = sigs[i]; t = g["t"]
        # close positions that ended before t
        for p in sorted([p for p in openp if p["xt"] <= t], key=lambda p: p["xt"]):
            pnl = p["R"] * p["risk$"]; eq += pnl; openp.remove(p)
            peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
            if p["R"] <= -0.5: sl_times.append(p["xt"])
        while ghost_q and ghost_q[0][0] <= t:
            _, tg, R = ghost_q.pop(0)
            for x in tg: tagst[x][0] += 1; tagst[x][1] += R
        dd_ = g.get("_day") or int((t + 7 * 3600) // 86400)
        if dd_ != day: day = dd_; day_start = eq; halted = False
        if (eq - day_start) / day_start * 100 <= -Q.DAY_LOSS: halted = True
        # ghost for this signal
        gR = res["ghost"][i]; ghost_q.append((gR[0], g["tags"], gR[1])); ghost_q.sort(key=lambda x: x[0])
        if tagrules and any(x in tagst and tagst[x][0] >= 12 and tagst[x][1] / tagst[x][0] < -0.15 for x in g["tags"]): continue
        if g["rp"] <= 0 or halted or t < pause_until: continue
        if any(p["sym"] == g["sym"] for p in openp): continue
        if dircap and sum(1 for p in openp if p["d"] == g["d"]) >= dircap: continue
        if slguard:
            n_, win_h, pause_h = slguard
            recent = [x for x in sl_times if t - x <= win_h * 3600]
            if len(recent) >= n_: pause_until = max(recent) + pause_h * 3600; sl_times = [x for x in sl_times if x > max(recent)]
            if t < pause_until: continue
        openr = sum(p["rp"] for p in openp)
        rp = min(g["rp"], Q.MAX_OPEN_RISK - openr)
        if rp < 0.0025: continue
        xt, R, why = res["pol"][i]
        p = {"sym": g["sym"], "d": g["d"], "rp": rp, "risk$": eq * rp, "R": R, "xt": xt, "t": t}
        openp.append(p); taken.append((t, R, rp, g["sym"], g["d"], why))
    for p in sorted(openp, key=lambda p: p["xt"]):
        eq += p["R"] * p["risk$"]; peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
    return {"eq": eq, "mdd": mdd, "n": len(taken), "trades": taken}

def stats(Rs):
    n = len(Rs); m = sum(Rs) / n if n else 0
    sd = math.sqrt(sum((x - m) ** 2 for x in Rs) / (n - 1)) if n > 1 else 0
    return n, m, sd

def block_boot_diff(t, a, b, iters=4000, seed=7):
    """mean(a-b) with a 95% one-sided lower bound; resampling whole days so same-day correlated trades stay together"""
    days = defaultdict(list)
    for ti, x, y in zip(t, a, b): days[int(ti // 86400)].append(x - y)
    keys = list(days); rng = random.Random(seed); means = []
    tot = sum(sum(v) for v in days.values()); cnt = sum(len(v) for v in days.values())
    for _ in range(iters):
        s = c = 0
        for _ in keys:
            v = days[keys[rng.randrange(len(keys))]]; s += sum(v); c += len(v)
        means.append(s / c)
    means.sort()
    return tot / cnt, means[int(0.05 * iters)]
