"""Escolhe 1 produto por tema com a MAIOR comissão (venda/nota boas), busca ao vivo; não repete o que já foi pro Instagram.
Grava sp_produtos.json."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, shopee
peneira.env()
pre = peneira.cfg("robos")["dono"]["chaves_env"]
APP, SEC = os.environ[pre + "_SHOPEE_APP_ID"], os.environ[pre + "_SHOPEE_SECRET"]
QTD = int(sys.argv[1]) if len(sys.argv) > 1 else 11
TEMAS = ["fone bluetooth", "escova secadora", "umidificador", "cama pet", "panela eletrica", "smartwatch", "caixa de som", "garrafa termica", "aspirador portatil", "kit ferramentas", "tapete yoga", "lixeira automatica"]
PROIBIR = ("infantil", "criança", "crianca", "bebê", "bebe", "kids", "disney", "marvel", "batman", "sexy", "lingerie")
usados = peneira.ja_usados("dono-instagram", 30) | {p["item_id"] for p in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp_produtos.json"), encoding="utf-8"))}
out = []
for kw in TEMAS:
    if len(out) >= QTD:
        break
    ps = None
    for t in range(4):
        try:
            ps = shopee.search(APP, SEC, kw, sort=5, limit=40); break
        except Exception:
            time.sleep(3)
    bons = [p for p in (ps or []) if p["sold"] >= 50 and p["rating"] >= 4.6 and p["image_url"] and p["item_id"] not in usados
            and not peneira.marca_famosa(p["title"]) and not any(w in p["title"].lower() for w in PROIBIR)]
    bons.sort(key=lambda p: (-p["commission"], -p["sold"]))
    if bons:
        out.append(bons[0])
        json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp_produtos_mais.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(len(out) - 1, f"{bons[0]['commission']*100:.0f}%", bons[0]["sold"], bons[0]["rating"], bons[0]["title"], flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp_produtos_mais.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
