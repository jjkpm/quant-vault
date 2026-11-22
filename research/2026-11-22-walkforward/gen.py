"""Walk-forward signal generator: replays the cloud-2.9 swarm exactly like production (warm on the live spans,
shadow-learn every bar, vote out every 4 h) over ~9 months of real Binance bars, and records every consensus
signal on_bar() would have produced. Everything the swarm sees is strictly in the past of each decision."""
import sys, pickle, random, bisect, math
sys.path.insert(0, "/home/claude/cloud")
import qv_swarm as Q

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
random.seed(seed)
data = pickle.load(open("bars.pkl", "rb"))
SY = list(Q.SYMS); TFS = Q.TFS
T0 = 1760745600 + 120 * 86400            # replay start (first 120 days = warm-up history)
TEND = 1795305600
idx = {k: [x[0] for x in v] for k, v in data.items()}

# ---- swarm built and warmed like a fresh production start (spans 15m 1500 / 1h 1000 / 4h 700 bars) ----
st = {"nextId": 0, "gen": 0, "agents": [], "tags": {}, "ghosts": [], "acct": {"bal": 1e4, "positions": []}}
st["agents"] = Q.make_swarm(st)
sw = Q.Swarm(st, [])
span = {15: 1500, 60: 1000, 240: 700}
hist = {}
for (s, tf), v in data.items():
    j = bisect.bisect_left(idx[(s, tf)], T0 - tf * 60 + 1)   # bars that closed by T0
    hist[(s, tf)] = v[max(0, j - span[tf]):j]
Q.warm(sw, hist)

cache = {}
def sigs(a, sym):
    k = (a["id"], sym)
    if k not in cache:
        B = data[(sym, a["tf"])]; j0 = max(0, bisect.bisect_left(idx[(sym, a["tf"])], T0) - 400)
        cache[k] = (j0, Q.sig_series(a["fam"], B[j0:], a["p"]))
    j0, s = cache[k]; return s, j0

# ---- event list: every bar close of every (sym, tf) after T0 ----
ev = []
for (s, tf), v in data.items():
    for i, x in enumerate(v):
        tc = x[0] + tf * 60
        if T0 < tc <= TEND: ev.append((tc, 0 if tf == 15 else 1, tf, s, i))
ev.sort()
signals = []; last_evolve = T0; nevolve = 0
for tc, _, tf, sym, i in ev:
    B = data[(sym, tf)]; bar = B[i]
    if tf == 15:   # shadow positions of all agents on this symbol, checked on 15m bars (production: every second)
        for a in st["agents"]:
            q = a["pos"].get(sym)
            if not q: continue
            d, sl, tp, risk = q[0], q[1], q[2], abs(q[3]); moved = q[3] < 0
            hs = bar[3] <= sl if d > 0 else bar[2] >= sl; ht = bar[2] >= tp if d > 0 else bar[3] <= tp
            if hs or ht:
                sw.record(a, ((Q.BE_LOCK if moved else -1) if hs else a["tp"] / a["sl"]) - Q.cost_R(sym, bar[4], risk)); del a["pos"][sym]
            elif a.get("be") and not moved:
                entry = tp - d * risk * a["tp"] / a["sl"]
                if (bar[2] >= entry + risk) if d > 0 else (bar[3] <= entry - risk): q[1] = entry + d * Q.BE_LOCK * risk; q[3] = -risk
    if i < 260: continue
    b = B[i - 259:i + 1]
    A = Q.atr_s(b[-80:])[-1]
    if not A: continue
    e = bar[4]; fired = []
    for a in sw.agents_tf(tf):
        s_, j0 = sigs(a, sym); s = s_[i - j0]
        if not s: continue
        if sym not in a["pos"]:
            a["pos"][sym] = [s, e - s * A * a["sl"], e + s * A * a["tp"], A * a["sl"]]
        fired.append((a, s))
    if fired:
        voters = [a for a in sw.agents_tf(tf) if Q.eligible(a)]
        agree = [(a, s) for a, s in fired if Q.eligible(a)]
        if voters and agree:
            tot = sum(Q.weight(a) for a in voters)
            score = sum(Q.weight(a) * s for a, s in agree) / tot
            d = 1 if score > 0 else -1
            side = [a for a, s in agree if s == d]
            if (len(side) >= 2 or (len(side) == 1 and side[0]["n"] >= 30)) and abs(score) >= 0.2:
                ws = sum(Q.weight(a) for a in side)
                slm = sum(Q.weight(a) * a["sl"] for a in side) / ws; tpm = sum(Q.weight(a) * a["tp"] for a in side) / ws
                slD, tpD = A * slm, A * tpm
                tags = []
                j4 = bisect.bisect_right(idx[(sym, 240)], tc - 240 * 60)   # 4h bars closed by tc
                c4 = [x[4] for x in data[(sym, 240)][max(0, j4 - 260):j4]]
                if len(c4) >= 55:
                    e4 = Q.ema_s(c4, 50)
                    t4 = 1 if (c4[-1] > e4[-1] and e4[-1] > e4[-6]) else -1 if (c4[-1] < e4[-1] and e4[-1] < e4[-6]) else 0
                    if t4 and t4 != d: tags.append("against4h")
                atrs = [x for x in Q.atr_s(b[-120:]) if x]
                if len(atrs) > 30 and A > sorted(atrs)[int(len(atrs) * 0.9)]: tags.append("volspike")
                cR = Q.cost_R(sym, e, slD)
                if cR > 0.25: tags.append("highcost")
                if abs(score) < 0.35: tags.append("weakvote")
                if tpm / slm < 2: tags.append("lowrr")
                n_ = sum(a["n"] for a in side); wins = sum(a["wins"] for a in side)
                pwin = wins / n_ if n_ else 0; rr = tpm / slm - cR
                kelly = pwin - (1 - pwin) / rr if rr > 0 else -1
                risk_pct = min(Q.RISK * min(1.0, max(0.25, abs(score))), 0.25 * kelly) if kelly > 0 else 0
                be = 1 if sum(Q.weight(x) for x in side if x.get("be")) * 2 >= ws else 0
                signals.append(dict(t=tc, sym=sym, tf=tf, d=d, e=e, slD=slD, tpD=tpD, A=A, be=be, score=round(score, 3),
                                    kelly=round(kelly, 3), rp=risk_pct, tags=tags, cR=cR, nside=len(side)))
    if tc - last_evolve >= 4 * 3600:
        nevolve += sw.evolve(); last_evolve = tc
pickle.dump({"signals": signals, "seed": seed, "T0": T0}, open(f"signals_s{seed}.pkl", "wb"))
el = sum(1 for a in st["agents"] if Q.eligible(a))
print(f"seed {seed}: {len(signals)} consensus signals, voted out {nevolve}, eligible now {el}, gen {st['gen']}")
