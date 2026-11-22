"""Pre-registered: the SAME rule that passed on crypto (Donchian 55/10 long+short, stop = 10-day channel trailed once a day,
intraday stop fill, risk 0.5 %/trade) applied unchanged to the app's 6 FX/gold symbols, with the app's own costs:
full spread per round trip (+0.5 spread slippage on stops), overnight swap USD/lot/night charged both directions
(Wed x3, no weekend), lots as in the app. FX open-risk budget 3 % (= all-bot 5 % minus the crypto 2 %).
Gate: dev 2005-01-01 -> 2025-11-21 Sharpe > 0.5 and 95 % block-bootstrap lower bound > 0; then the untouched
holdout 2025-11-22 -> 2026-11-21 must be > 0. No parameter is chosen here."""
import pickle, math, random, statistics as stt, datetime as dt, sys
D = {k: [x for x in v if dt.datetime.utcfromtimestamp(x[0]).weekday() < 5] for k, v in pickle.load(open("daily_fx.pkl", "rb")).items()}
APP = {"EURUSD": (0.0001, 100000, 1.0, 7), "GBPUSD": (0.0001, 100000, 1.3, 7), "USDJPY": (0.01, 100000, 1.2, 7),
       "AUDUSD": (0.0001, 100000, 1.2, 5), "XAUUSD": (0.01, 100, 25, 20), "USDTHB": (0.01, 100000, 3, 10)}  # pip, lot, spread pips, swap $/lot/night
HOLD = 1795305600 - 365 * 86400
def usd_per_quote(s, px): return 1 / px if s in ("USDJPY", "USDTHB") else 1.0
def day_of(t): return int((t + 12 * 3600) // 86400)   # Yahoo FX stamps sit around 23:00 UTC of the previous day; map to trading day

def run(syms=tuple(APP), N=55, M=10, risk=0.005, cap=0.03, t_from=0, t_to=1e12, costx=1.0):
    bars = {s: {day_of(x[0]): x for x in D[s]} for s in syms}
    days = sorted(set().union(*[set(b) for b in bars.values()]))
    hist = {s: [] for s in syms}
    eq = 1e4; pos = {}; trades = []; daily = {}; prev = eq
    for d in days:
        t = d * 86400
        if t >= t_to: break
        live = t >= t_from
        wd = dt.datetime.utcfromtimestamp(t).weekday()
        for s in syms:
            if d not in bars[s]: continue
            x = bars[s][d]; pip, lot, spr, swp = APP[s]; o, h, l, c = x[1:]
            if s in pos:
                p = pos[s]
                hit = (l <= p["sl"]) if p["d"] > 0 else (h >= p["sl"])
                if hit:
                    px = (min(o, p["sl"]) if p["d"] > 0 else max(o, p["sl"])) - p["d"] * 0.5 * spr * pip * costx
                    pnl = (px - p["e"]) * p["d"] * p["u"] * usd_per_quote(s, px) - p["swap"]
                    eq += (px - p["e"]) * p["d"] * p["u"] * usd_per_quote(s, px)
                    trades.append({"t0": p["t"], "t1": t, "sym": s, "d": p["d"], "R": pnl / p["risk$"], "days": (t - p["t"]) / 86400})
                    del pos[s]
                else:
                    nights = 3 if wd == 2 else 1
                    sw = swp * p["u"] / lot * nights * costx; eq -= sw; p["swap"] += sw
            hist[s].append(x)
            b = hist[s]; k = len(b) - 1
            if s in pos:
                p = pos[s]; ext = min(z[3] for z in b[k - M + 1:]) if p["d"] > 0 else max(z[2] for z in b[k - M + 1:])
                if (ext > p["sl"]) if p["d"] > 0 else (ext < p["sl"]): p["sl"] = ext
                continue
            if k < max(N, 21) + 1 or not live: continue
            hiN = max(z[2] for z in b[k - N:k]); loN = min(z[3] for z in b[k - N:k]); dd = 1 if c > hiN else -1 if c < loN else 0
            if not dd: continue
            A = sum(max(b[j][2] - b[j][3], abs(b[j][2] - b[j - 1][4]), abs(b[j][3] - b[j - 1][4])) for j in range(k - 19, k + 1)) / 20
            ext = min(z[3] for z in b[k - M + 1:]) if dd > 0 else max(z[2] for z in b[k - M + 1:])
            dist = max(abs(c - ext), A)
            openr = sum(p["rp"] for p in pos.values()); rp = min(risk, cap - openr)
            if rp < 0.0025: continue
            e = c + dd * 0.5 * spr * pip * costx                     # pay half the spread on entry, half on exit (above)
            u = eq * rp / ((dist + spr * pip * costx) * usd_per_quote(s, e))
            pos[s] = {"d": dd, "e": e, "u": u, "t": t, "sl": c - dd * dist, "risk$": eq * rp, "rp": rp, "swap": 0.0}
        if live:
            m2m = eq
            for s, p in pos.items():
                if hist[s]: m2m += (hist[s][-1][4] - p["e"]) * p["d"] * p["u"] * usd_per_quote(s, hist[s][-1][4])
            daily[t] = m2m / prev - 1; prev = m2m
    return trades, daily

def perf(v):
    v = list(v); m = sum(v) / len(v); sd = stt.pstdev(v); eq = 1; pk = 1; mdd = 0
    for x in v: eq *= 1 + x; pk = max(pk, eq); mdd = max(mdd, 1 - eq / pk)
    return m / sd * math.sqrt(252) if sd else 0, (eq ** (252 / len(v)) - 1) * 100, mdd * 100
def lcb(v, block=10, iters=4000):
    rng = random.Random(5); n = len(v); ms = []
    for _ in range(iters):
        s = c = 0
        while c < n: j = rng.randrange(0, n - block); s += sum(v[j:j + block]); c += block
        ms.append(s / c)
    ms.sort(); return ms[int(0.05 * iters)] * 252 * 100
def report(lab, tr, daily):
    R = [x["R"] for x in tr]; w = [x for x in R if x > 0]; ls = [x for x in R if x <= 0]; v = list(daily.values())
    sh, ann, mdd = perf(v); lb = lcb(v)
    print(f"{lab:30s} trades {len(R):4d} win {100*len(w)/len(R):3.0f}% avgR {sum(R)/len(R):+.2f} win/loss {abs(sum(w)/len(w)/(sum(ls)/len(ls))):.1f}"
          f" | Sharpe {sh:.2f} ann {ann:+.1f}% mdd {mdd:.1f}% LCB95 {lb:+.1f}%/yr")
    return sh, lb, ann

if __name__ == "__main__":
    t05 = int(dt.datetime(2005, 1, 1).timestamp())
    sh, lb, _ = report("DEV 2005→2025-11", *run(t_from=t05, t_to=HOLD))
    report("dev 2015→2025-11", *run(t_from=int(dt.datetime(2015, 1, 1).timestamp()), t_to=HOLD))
    _, _, ho = report("HOLDOUT 12m", *run(t_from=HOLD))
    report("holdout cost x2", *run(t_from=HOLD, costx=2))
    report("dev cost x2", *run(t_from=t05, t_to=HOLD, costx=2))
    print("GATE:", "PASS" if sh > 0.5 and lb > 0 and ho > 0 else "fail", f"(dev Sharpe {sh:.2f}, LCB {lb:+.1f}, holdout {ho:+.1f}%)")
    for N, M in ((20, 10), (55, 20), (20, 20)):
        report(f"  neighbour {N}/{M} dev", *run(N=N, M=M, t_from=t05, t_to=HOLD)); report(f"  neighbour {N}/{M} hold", *run(N=N, M=M, t_from=HOLD))
    for s in APP:
        try: report(f"  only {s} dev", *run(syms=(s,), cap=0.005, t_from=t05, t_to=HOLD))
        except ZeroDivisionError: print("  only", s, "no trades")
