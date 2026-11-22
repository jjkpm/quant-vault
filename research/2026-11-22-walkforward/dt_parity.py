import pickle, json, sys
from playwright.sync_api import sync_playwright
from dt_ref import dt_sig
D = pickle.load(open("daily.pkl", "rb"))
cases = []
for s, b in D.items():
    for k in range(len(b) - 900, len(b)): cases.append((s, k))
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///home/claude/qv8/Quant%20Vault.html?selftest", wait_until="load"); pg.wait_for_timeout(1500)
    bad = 0; nsig = 0; maxrel = 0
    for s in D:
        b = D[s]; ks = [k for (ss, k) in cases if ss == s]
        js = pg.evaluate("([b,ks])=>ks.map(k=>dtSig(b.slice(Math.max(0,k-119),k+1)))", [b, ks])
        for k, j in zip(ks, js):
            py = dt_sig(b[max(0, k - 119):k + 1])
            if (py is None) != (j is None): bad += 1; continue
            if py is None: continue
            if py["d"] != j["d"]: bad += 1; continue
            nsig += bool(py["d"])
            for key in ("c", "A", "lo", "hi") + (("dist",) if py["d"] else ()):
                rel = abs(py[key] - j[key]) / abs(py[key]); maxrel = max(maxrel, rel)
                if rel > 1e-9: bad += 1
    print(f"cases {len(cases)}  mismatches {bad}  entry signals {nsig}  max rel diff {maxrel:.2e}  page errors {errs[:3]}")
    print("version:", pg.evaluate("VERSION"))
    br.close()
