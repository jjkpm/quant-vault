"""Implementable version of the passing candidate (Donchian 55/10 long+short, daily), with Quant Vault's own rules:
entry at the daily close, risk a fixed % of equity to the 10-day exit level (min 1 ATR), one position per coin,
total crypto open risk <= 2 % (static, measured at entry like the app), exit at the daily close beyond the 10-day
channel, fees 0.1 %/side + half spread each way. No parameter is chosen here: N=55, M=10 were fixed by the walk-forward."""
import sys, pickle, math, random, statistics as stt
from daily_bt import D, SY, HOLD, CH, perf, block_lcb, Q

def atr(s, k, n=20):
    c, h, l = CH[s]
    if k < n + 1: return None
    return sum(max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1])) for j in range(k - n + 1, k + 1)) / n

def run(N=55, M=10, risk=0.005, cap=0.02, t_from=0, t_to=1e12, costx=1.0):
    days = sorted({x[0] for s in SY for x in D[s]}); ix = {s: {x[0]: k for k, x in enumerate(D[s])} for s in SY}
    cost = {s: costx * (Q.SYMS[s].get("fee", Q.FEE) + Q.SYMS[s]["spread"] / 2) for s in SY}
    eq = 1e4; pos = {}; trades = []; daily = {}; prev_eq = eq
    for t in days:
        if t < t_from - 120 * 86400 or t >= t_to: continue
        live = t >= t_from
        # mark-to-market + exits at today's close
        for s in list(pos):
            if t not in ix[s]: continue
            k = ix[s][t]; c, h, l = CH[s]; p = pos[s]
            ext = min(l[k - M:k]) if p["d"] > 0 else max(h[k - M:k])
            if (c[k] < ext) if p["d"] > 0 else (c[k] > ext):
                px = c[k]; gross = (px - p["e"]) * p["d"] * p["u"]; fee = px * p["u"] * cost[s]
                eq += gross - fee; R = (gross - fee - p["fee"]) / p["risk$"]
                trades.append({"t0": p["t"], "t1": t, "sym": s, "d": p["d"], "R": R, "days": (t - p["t"]) / 86400})
                del pos[s]
        # entries at today's close
        for s in SY:
            if s in pos or t not in ix[s]: continue
            k = ix[s][t]
            if k < max(N, 130): continue
            c, h, l = CH[s]; d = 1 if c[k] > max(h[k - N:k]) else -1 if c[k] < min(l[k - N:k]) else 0
            if not d or not live: continue
            A = atr(s, k); ext = min(l[k - M:k]) if d > 0 else max(h[k - M:k])
            dist = max(abs(c[k] - ext), A or 0)
            openr = sum(p["rp"] for p in pos.values()); rp = min(risk, cap - openr)
            if rp < 0.0025 or not dist: continue
            u = eq * rp / dist; fee = c[k] * u * cost[s]
            if c[k] * u > eq * 0.25 * 2: u = eq * 0.5 / c[k]        # notional cap per coin (50 % of equity)
            eq -= fee
            pos[s] = {"d": d, "e": c[k], "u": u, "t": t, "fee": fee, "risk$": eq * rp, "rp": rp}
        if live:
            m2m = eq + sum((CH[s][0][ix[s][t]] - p["e"]) * p["d"] * p["u"] for s, p in pos.items() if t in ix[s])
            daily[t] = m2m / prev_eq - 1; prev_eq = m2m
    return trades, daily

def report(lab, trades, daily):
    Rs = [x["R"] for x in trades]; n = len(Rs)
    w = [x for x in Rs if x > 0]; ls = [x for x in Rs if x <= 0]
    p = perf(list(daily.values())); lcb = block_lcb(list(daily.values()))
    print(f"{lab}: trades {n}  win {100*len(w)/n:.0f}%  avgR {sum(Rs)/n:+.2f}  avg win {sum(w)/len(w):+.2f}R / avg loss {sum(ls)/len(ls):+.2f}R"
          f" (ratio {abs(sum(w)/len(w)/(sum(ls)/len(ls))):.1f})  hold {stt.median([x['days'] for x in trades]):.0f}d"
          f" | Sharpe {p['sharpe']:.2f} ann {p['ann%']:+.1f}% mdd {p['mdd%']:.1f}% LCB95 {lcb:+.1f}%/yr")
    return p, lcb

if __name__ == "__main__":
    t21 = int(Q.datetime(2021, 1, 1, tzinfo=Q.timezone.utc).timestamp()); t22 = int(Q.datetime(2022, 1, 1, tzinfo=Q.timezone.utc).timestamp())
    for risk in (0.005, 0.01):
        print(f"--- risk {risk*100:.1f}% per trade, crypto open-risk cap 2% ---")
        p, l = report("dev 2021→2025-11 ", *run(risk=risk, t_from=t21, t_to=HOLD))
        report("dev 2022→2025-11 ", *run(risk=risk, t_from=t22, t_to=HOLD))
        report("HOLDOUT 12m      ", *run(risk=risk, t_from=HOLD))
        report("holdout cost x2  ", *run(risk=risk, t_from=HOLD, costx=2))
    tr, _ = run(risk=0.005, t_from=HOLD)
    print("holdout trades:", [(Q.datetime.utcfromtimestamp(x["t0"]).strftime("%y-%m-%d"), x["sym"][:-4], "L" if x["d"] > 0 else "S", round(x["R"], 2)) for x in tr])
