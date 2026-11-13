"""Teste IA-10: escolhe 10 produtos que pagam MAIS comissão (com venda e nota boas), 1 por tema.
Só aceita FOTO LIMPA (fundo branco nas bordas = sem banner/texto em volta), porque a IA estraga textos da foto.
Grava ia10_produtos.json"""
import io, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, shopee
from ia10_olho import foto_ok
from PIL import Image
peneira.env()
pre = peneira.cfg("robos")["dono"]["chaves_env"]
APP, SEC = os.environ[pre + "_SHOPEE_APP_ID"], os.environ[pre + "_SHOPEE_SECRET"]
TEMAS = ["mini processador", "organizador cozinha", "panela eletrica", "fogao", "saco de pancada", "aspirador portatil", "cama pet",
         "luminaria led", "massageador eletrico", "patinete eletrico", "garrafa termica", "mop giratorio", "escova secadora",
         "caixa de som bluetooth", "ventilador portatil", "air fryer", "liquidificador portatil", "cadeira gamer",
         "bicicleta ergometrica", "umidificador", "fone bluetooth", "smartwatch", "tapete yoga", "kit ferramentas", "cafeteira", "espremedor", "lixeira automatica", "relogio parede"]
PROIBIR = ("infantil", "criança", "crianca", "bebê", "bebe", "kids", "homem aranha", "spider", "disney", "marvel", "barbie",
           "minnie", "mickey", "batman", "harry potter", "pokemon", "sexy", "lingerie")


def foto_limpa(url):
    """bordas quase todas brancas/claras = foto de produto no fundo liso"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("L").resize((200, 200))
    except Exception:
        return False
    px = im.load()
    borda = [px[x, y] for x in range(200) for y in (0, 1, 2, 3, 196, 197, 198, 199)] + \
            [px[x, y] for y in range(200) for x in (0, 1, 2, 3, 196, 197, 198, 199)]
    return sum(1 for v in borda if v >= 235) / len(borda) >= .85


usados = peneira.ja_usados("dono-ia10", 30)
saida = []
for kw in TEMAS:
    if len(saida) >= 10:
        break
    ps = None
    for tent in range(4):  # a API da Shopee às vezes devolve "System Error"; tenta de novo
        try:
            ps = shopee.search(APP, SEC, kw, sort=5, limit=50); break
        except Exception as e:
            time.sleep(4 + tent * 3)
    if not ps:
        print("sem resposta:", kw); continue
    bons = [p for p in ps if p["sold"] >= 50 and p["rating"] >= 4.5 and p["image_url"]
            and not peneira.marca_famosa(p["title"]) and p["item_id"] not in usados and p["item_id"] not in {x["item_id"] for x in saida}
            and not any(w in p["title"].lower() for w in PROIBIR)]
    bons.sort(key=lambda p: (-p["commission"], -p["sold"]))
    for p in bons[:15]:
        try:
            ok = foto_ok(p["image_url"])[0]  # IA olha a foto: só produto, sem texto/selo/montagem
        except Exception:
            ok = False
        if ok:
            p["palavra"] = kw
            saida.append(p)
            print(f"{p['commission']*100:4.1f}% | {p['sold']:>6} vend | {p['rating']:.1f} | {kw:20} | {p['title'][:60]}", flush=True)
            break
    else:
        print("sem foto limpa:", kw, flush=True)
    time.sleep(1)
json.dump(saida, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ia10_produtos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(saida), "produtos")
