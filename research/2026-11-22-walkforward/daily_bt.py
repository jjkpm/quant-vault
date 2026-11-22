"""Daily-timeframe candidates for Quant Vault, pre-registered grid + anchored yearly walk-forward.
Holdout (last 12 months, 2025-11-22 .. 2026-11-21) is NOT used for any choice; it is scored once at the end."""
import sys, pickle, math, random, statistics as stt
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q

D = pickle.load(open("daily.pkl", "rb"))
SY = list(Q.SYMS)
HOLD = 1795305600 - 365 * 86400          # 2025-11-22 00:00 UTC
days = sorted({x[0] for s in SY for x in D[s]})
ix = {s: {x[0]: k for k, x in enumerate(D[s])} for s in SY}
COST = {s: Q.SYMS[s].get("fee", Q.FEE) + Q.SYMS[s]["spread"] / 2 for s in SY}   # per unit of turnover
TVOL = 0.20 / math.sqrt(365)            # daily vol target per coin sleeve before the gross cap

def series(s):
    b = D[s]; return [x[4] for x in b], [x[2] for x in b], [x[3] for x in b]

def raw_signal(cfg, s, k):
    """position sign for coin s using bars up to and including index k (decided at that close)"""
    c, h, l = CH[s]; fam = cfg["fam"]
    if fam == "tsmom":
        L = cfg["L"]
        if k < L: return None
        r = c[k] / c[k - L] - 1; return 1 if r > 0 else -1
    if fam == "sma":
        L = cfg["L"]
        if k < L: return None
        m = sum(c[k - L + 1:k + 1]) / L; return 1 if c[k] > m else -1
    if fam == "don":
        return DON[(s, cfg["N"], cfg["M"])][k]
    return None

def don_states(s, N, M):
    c, h, l = CH[s]; st = [None] * len(c); pos = 0
    for k in range(len(c)):
        if k < N + 1: continue
        hiN = max(h[k - N:k]); loN = min(l[k - N:k]); hiM = max(h[k - M:k]); loM = min(l[k - M:k])
        if pos == 1 and c[k] < loM: pos = 0
        elif pos == -1 and c[k] > hiM: pos = 0
        if pos == 0:
            if c[k] > hiN: pos = 1
            elif c[k] < loN: pos = -1
        st[k] = pos
    return st

CH = {s: series(s) for s in SY}
GRID = []
for L in (20, 40, 60, 90, 120): GRID += [{"fam": "tsmom", "L": L, "ls": ls} for ls in (1, 0)]
for L in (20, 50, 100, 200): GRID += [{"fam": "sma", "L": L, "ls": ls} for ls in (1, 0)]
for N, M in ((20, 10), (55, 20), (20, 20), (55, 10)): GRID += [{"fam": "don", "N": N, "M": M, "ls": ls} for ls in (1, 0)]
for L in (14, 30, 60): GRID += [{"fam": "xs", "L": L, "ls": ls} for ls in (1, 0)]
DON = {}
for g in GRID:
    if g["fam"] == "don":
        for s in SY: DON.setdefault((s, g["N"], g["M"]), don_states(s, g["N"], g["M"]))

def vol(s, k, n=30):
    c = CH[s][0]
    if k < n + 1: return None
    r = [c[j] / c[j - 1] - 1 for j in range(k - n + 1, k + 1)]
    return stt.pstdev(r) or None

def daily_returns(cfg):
    """portfolio return for each day d (position decided at close of day d-1, held to close of day d), net of costs"""
    out = {}; prev = {s: 0.0 for s in SY}
    for di in range(1, len(days)):
        t_dec, t = days[di - 1], days[di]
        w = {}
        avail = [s for s in SY if t_dec in ix[s] and t in ix[s] and ix[s][t_dec] >= 130]
        if cfg["fam"] == "xs":
            if di % 7 == 0 or not any(prev.values()):
                L = cfg["L"]; sc = []
                for s in avail:
                    k = ix[s][t_dec]; c = CH[s][0]; sc.append((c[k] / c[k - L] - 1, s))
                sc.sort(); n = 3 if len(sc) >= 6 else len(sc) // 2
                sig = {s: 1 for _, s in sc[-n:]} if n else {}
                if cfg["ls"] and n: sig.update({s: -1 for _, s in sc[:n]})
            else:
                sig = {s: (1 if prev[s] > 0 else -1) for s in avail if prev[s] != 0}
        else:
            sig = {}
            for s in avail:
                x = raw_signal(cfg, s, ix[s][t_dec])
                if x is None: continue
                if x < 0 and not cfg["ls"]: x = 0
                sig[s] = x
        for s, x in sig.items():
            v = vol(s, ix[s][t_dec])
            if v and x: w[s] = x * TVOL / v
        gross = sum(abs(x) for x in w.values())
        if gross > 1: w = {s: x / gross for s, x in w.items()}         # no leverage: gross exposure <= 1
        r = 0.0
        for s in SY:
            ws = w.get(s, 0.0)
            if ws and t in ix[s]:
                k = ix[s][t]; c = CH[s][0]; r += ws * (c[k] / c[k - 1] - 1)
            r -= abs(ws - prev[s]) * COST[s]
        prev = {s: w.get(s, 0.0) for s in SY}
        out[t] = r
    return out

def perf(rets):
    v = list(rets)
    if len(v) < 30: return {"sharpe": -9}
    m = sum(v) / len(v); sd = stt.pstdev(v)
    eq = 1; pk = 1; mdd = 0
    for x in v: eq *= 1 + x; pk = max(pk, eq); mdd = max(mdd, 1 - eq / pk)
    return {"sharpe": m / sd * math.sqrt(365) if sd else 0, "ann%": ((eq) ** (365 / len(v)) - 1) * 100, "mdd%": mdd * 100, "n": len(v)}

def block_lcb(v, block=10, iters=4000, seed=11):
    rng = random.Random(seed); n = len(v); ms = []
    for _ in range(iters):
        s = 0; c = 0
        while c < n:
            j = rng.randrange(0, n - block); s += sum(v[j:j + block]); c += block
        ms.append(s / c)
    ms.sort(); return ms[int(0.05 * iters)] * 365 * 100   # annualised %

if __name__ == "__main__":
    R = {i: daily_returns(g) for i, g in enumerate(GRID)}
    name = lambda g: g["fam"] + "".join(f" {k}={v}" for k, v in g.items() if k not in ("fam",))
    years = [(f"{y}", int(Q.datetime(y, 1, 1, tzinfo=Q.timezone.utc).timestamp())) for y in range(2021, 2026)]
    def wf(cands, label):
        oos = []; picks = []
        bounds = [t for _, t in years] + [HOLD]
        for yi in range(len(years)):
            a, b = bounds[yi], bounds[yi + 1]
            best = max(cands, key=lambda i: perf([x for t, x in R[i].items() if t < a and t >= a - 3 * 365 * 86400])["sharpe"])
            picks.append(name(GRID[best])); oos += [x for t, x in sorted(R[best].items()) if a <= t < b]
        p = perf(oos); lcb = block_lcb(oos)
        final = max(cands, key=lambda i: perf([x for t, x in R[i].items() if t < HOLD and t >= HOLD - 3 * 365 * 86400])["sharpe"])
        hold = perf([x for t, x in sorted(R[final].items()) if t >= HOLD])
        ok = p["sharpe"] > 0.5 and lcb > 0
        print(f"[{label}] WF-OOS 2021→2025-11: Sharpe {p['sharpe']:.2f}  ann {p['ann%']:+.1f}%  mdd {p['mdd%']:.1f}%  LCB95 {lcb:+.1f}%/yr  -> {'PASS' if ok else 'fail'}")
        print(f"      picks per year: {picks}")
        print(f"      holdout config: {name(GRID[final])} | holdout 12m: Sharpe {hold['sharpe']:.2f} ann {hold['ann%']:+.1f}% mdd {hold['mdd%']:.1f}%  -> {'PASS' if ok and hold['ann%'] > 0 else '-'}")
        return ok
    fams = {}
    for i, g in enumerate(GRID): fams.setdefault(g["fam"] + (" L/S" if g["ls"] else " long-only"), []).append(i)
    for f, c in fams.items(): wf(c, f)
    wf(list(range(len(GRID))), "ALL (choose among every config)")
    bh = {}
    for di in range(1, len(days)):
        t = days[di]; xs = [CH[s][0][ix[s][t]] / CH[s][0][ix[s][t] - 1] - 1 for s in SY if t in ix[s] and ix[s][t] >= 1]
        bh[t] = sum(xs) / len(xs) if xs else 0
    for lab, a, b in [("dev 2021→2025-11", years[0][1], HOLD), ("holdout 12m", HOLD, 1e12)]:
        p = perf([x for t, x in sorted(bh.items()) if a <= t < b]); print(f"buy&hold equal-weight {lab}: Sharpe {p['sharpe']:.2f} ann {p['ann%']:+.1f}% mdd {p['mdd%']:.1f}%")
    pickle.dump({"R": R, "GRID": GRID}, open("daily_R.pkl", "wb"))
