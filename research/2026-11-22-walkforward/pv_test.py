import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br=p.chromium.launch(); pg=br.new_page(); errs=[]; pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto("file:///home/claude/qv9/Quant%20Vault.html?selftest",wait_until="load"); pg.wait_for_timeout(1500)
    out=pg.evaluate("""()=>{const R={};S.bot.mode="auto";S.settings.botSym="ALL";S.acct.positions=[];
      M.ETHUSDT.last=3000;const r={d:1,slD:60,tpD:150,riskPct:0.005,score:0.6,side:[{id:"a1",fam:"trend"}],tags:[],kelly:0.2,be:0};
      const B={market:"cr",maxOpenRisk:0.02};
      R.provenDefault=S.proven; cbAct("ETHUSDT",60,r,B); R.posWhenProven=S.acct.positions.length; R.log1=S.bot.log[0].msg;
      S.proven=false; cbAct("ETHUSDT",60,r,B); R.posWhenOff=S.acct.positions.length;
      S.acct.positions=[]; S.proven=true;
      // local brain path
      const ag=agents("BTCUSDT")[0]; window.pickable=()=>true; window.tradable=()=>true; M.BTCUSDT.last=60000;
      S.bot.mode="signal"; let toasts=0; const ot=window.toast; window.toast=()=>{toasts++}; delete S.bot["pv_BTCUSDT"];
      const cbA=window.cbActive, mkA=window.mkActive; window.cbActive=()=>false;
      botAct("BTCUSDT",[{ag,s:1}],500); R.localToastsWhenProven=toasts; R.log2=S.bot.log[0].msg;
      S.proven=false; botAct("BTCUSDT",[{ag,s:1}],500); R.localToastsWhenOff=toasts; window.toast=ot; window.cbActive=cbA;
      S.proven=undefined; R.undefinedIsSafe=provenOnly(); S.proven=true;
      renderBrain(); R.panel=document.getElementById("t-brain").innerText.slice(0,120); R.ver=VERSION; return R}""")
    print(json.dumps(out,ensure_ascii=False,indent=1)); print("errors:",errs); br.close()
