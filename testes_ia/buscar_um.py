"""Busca candidatos de UM tema (maior comissão + venda/nota boas) e baixa as fotos para eu olhar. Uso: python buscar_um.py "pneu aro 15" """
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, shopee
peneira.env()
pre = peneira.cfg("robos")["dono"]["chaves_env"]
APP, SEC = os.environ[pre + "_SHOPEE_APP_ID"], os.environ[pre + "_SHOPEE_SECRET"]
kw = sys.argv[1]
AQUI = os.path.dirname(os.path.abspath(__file__))
ps = None
for t in range(5):
    try:
        ps = shopee.search(APP, SEC, kw, sort=5, limit=50); break
    except Exception as e:
        time.sleep(4)
bons = [p for p in (ps or []) if p["sold"] >= 20 and p["rating"] >= 4.5 and p["image_url"] and not peneira.marca_famosa(p["title"])]
bons.sort(key=lambda p: (-p["commission"], -p["sold"]))
out = []
for i, p in enumerate(bons[:6]):
    arq = os.path.join(AQUI, f"_cand{i}.jpg")
    open(arq, "wb").write(urllib.request.urlopen(urllib.request.Request(p["image_url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
    print(i, f"{p['commission']*100:.0f}%", p["sold"], p["rating"], p["title"][:80])
    out.append(p)
json.dump(out, open(os.path.join(AQUI, "_cand.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
