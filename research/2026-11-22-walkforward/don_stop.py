"""Same candidate, but exits implemented the way the app can do them: a real stop order at the 10-day channel
(moved once a day after each daily close, only in the trade's favour), triggered intraday; gap -> fill at the open."""
from don_trades import *
def run2(N=55, M=10, risk=0.005, cap=0.02, t_from=0, t_to=1e12, costx=1.0, slip=1.0):
    days = sorted({x[0] for s in SY for x in D[s]}); ix = {s: {x[0]: k for k, x in enumerate(D[s])} for s in SY}
    O = {s: [x[1] for x in D[s]] for s in SY}
    cost = {s: costx * (Q.SYMS[s].get("fee", Q.FEE) + Q.SYMS[s]["spread"] / 2) for s in SY}
    eq = 1e4; pos = {}; trades = []; daily = {}; prev_eq = eq
    for t in days:
        if t < t_from - 120 * 86400 or t >= t_to: continue
        live = t >= t_from
        for s in list(pos):
            if t not in ix[s]: continue
            k = ix[s][t]; c, h, l = CH[s]; p = pos[s]; o = O[s][k]
            hit = (l[k] <= p["sl"]) if p["d"] > 0 else (h[k] >= p["sl"])
            if hit:
                px = min(o, p["sl"]) if p["d"] > 0 else max(o, p["sl"])
                px -= p["d"] * px * Q.SYMS[s]["spread"] * slip * 0.5          # stop slippage
                gross = (px - p["e"]) * p["d"] * p["u"]; fee = px * p["u"] * cost[s]
                eq += gross - fee; R = (gross - fee - p["fee"]) / p["risk$"]
                trades.append({"t0": p["t"], "t1": t, "sym": s, "d": p["d"], "R": R, "days": (t - p["t"]) / 86400}); del pos[s]; continue
            ext = min(l[k - M + 1:k + 1]) if p["d"] > 0 else max(h[k - M + 1:k + 1])   # channel incl. today, used from tomorrow
            if (ext > p["sl"]) if p["d"] > 0 else (ext < p["sl"]): p["sl"] = ext
        for s in SY:
            if s in pos or t not in ix[s]: continue
            k = ix[s][t]
            if k < max(N, 130): continue
            c, h, l = CH[s]; d = 1 if c[k] > max(h[k - N:k]) else -1 if c[k] < min(l[k - N:k]) else 0
            if not d or not live: continue
            A = atr(s, k); ext = min(l[k - M + 1:k + 1]) if d > 0 else max(h[k - M + 1:k + 1])
            dist = max(abs(c[k] - ext), A or 0)
            openr = sum(p["rp"] for p in pos.values()); rp = min(risk, cap - openr)
            if rp < 0.0025 or not dist: continue
            u = eq * rp / dist
            if c[k] * u > eq * 0.5: u = eq * 0.5 / c[k]
            fee = c[k] * u * cost[s]; eq -= fee
            pos[s] = {"d": d, "e": c[k], "u": u, "t": t, "fee": fee, "risk$": eq * rp, "rp": rp, "sl": c[k] - d * dist}
        if live:
            m2m = eq + sum((CH[s][0][ix[s][t]] - p["e"]) * p["d"] * p["u"] for s, p in pos.items() if t in ix[s])
            daily[t] = m2m / prev_eq - 1; prev_eq = m2m
    return trades, daily
t21 = int(Q.datetime(2021, 1, 1, tzinfo=Q.timezone.utc).timestamp()); t22 = int(Q.datetime(2022, 1, 1, tzinfo=Q.timezone.utc).timestamp())
for risk in (0.005,):
    report("STOP dev 2021→2025-11", *run2(risk=risk, t_from=t21, t_to=HOLD))
    report("STOP dev 2022→2025-11", *run2(risk=risk, t_from=t22, t_to=HOLD))
    report("STOP HOLDOUT 12m     ", *run2(risk=risk, t_from=HOLD))
    report("STOP holdout cost x2 ", *run2(risk=risk, t_from=HOLD, costx=2, slip=2))
    for N, M in ((20, 10), (55, 20), (20, 20)):
        report(f"  neighbour N{N}/M{M} dev21", *run2(N=N, M=M, risk=risk, t_from=t21, t_to=HOLD)); report(f"  neighbour N{N}/M{M} hold ", *run2(N=N, M=M, risk=risk, t_from=HOLD))
