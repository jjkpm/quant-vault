"""Reference for Quant Vault v0.9.8 daily trend bot (Donchian 55/10). Same decision function as the app's dtSig()
and as the walk-forward test (don_stop.run2). b = closed daily bars [t, o, h, l, c]; decision at the last close."""
N, M, ATRN = 55, 10, 20
def dt_sig(b):
    k = len(b) - 1
    if k < max(N, ATRN) + 1: return None
    c = b[k][4]; hiN = max(x[2] for x in b[k - N:k]); loN = min(x[3] for x in b[k - N:k])
    lo = min(x[3] for x in b[k - M + 1:k + 1]); hi = max(x[2] for x in b[k - M + 1:k + 1])
    A = sum(max(b[j][2] - b[j][3], abs(b[j][2] - b[j - 1][4]), abs(b[j][3] - b[j - 1][4])) for j in range(k - ATRN + 1, k + 1)) / ATRN
    d = 1 if c > hiN else -1 if c < loN else 0
    ext = lo if d > 0 else hi
    return {"d": d, "c": c, "A": A, "lo": lo, "hi": hi, "dist": max(abs(c - ext), A) if d else None}
