import pickle
import daily_bt as DB
from daily_bt import *
P = pickle.load(open("daily_R.pkl","rb")); R, G = P["R"], P["GRID"]
yrs = [(y, int(Q.datetime(y,1,1,tzinfo=Q.timezone.utc).timestamp())) for y in range(2021, 2027)]
def yr(rets):
    out=[]
    for k,(y,a) in enumerate(yrs[:-1]):
        b = yrs[k+1][1]; v=[x for t,x in sorted(rets.items()) if a<=t<b and t<HOLD]; eq=1
        for x in v: eq*=1+x
        out.append(f"{y}:{(eq-1)*100:+.0f}%")
    return out
for i,g in enumerate(G):
    if g["fam"] in ("don","tsmom","sma") and g["ls"]==1:
        dev=perf([x for t,x in sorted(R[i].items()) if yrs[0][1]<=t<HOLD]); ho=perf([x for t,x in sorted(R[i].items()) if t>=HOLD])
        print(f"{g['fam']:5s} {str({k:v for k,v in g.items() if k not in ('fam','ls')}):22s} dev Sharpe {dev['sharpe']:.2f} ann {dev['ann%']:+6.1f}% mdd {dev['mdd%']:4.1f}% | hold Sharpe {ho['sharpe']:.2f} ann {ho['ann%']:+6.1f}% mdd {ho['mdd%']:4.1f}% | {' '.join(yr(R[i]))}")
# cost x2 for the Donchian L/S configs
DB.COST = {s: 2*v for s,v in DB.COST.items()}
for g in G:
    if g["fam"]=="don" and g["ls"]==1:
        r = DB.daily_returns(g); dev=perf([x for t,x in sorted(r.items()) if yrs[0][1]<=t<HOLD]); ho=perf([x for t,x in sorted(r.items()) if t>=HOLD])
        print(f"COSTx2 don N={g['N']} M={g['M']}: dev Sharpe {dev['sharpe']:.2f} ann {dev['ann%']:+.1f}% | hold Sharpe {ho['sharpe']:.2f} ann {ho['ann%']:+.1f}%")
