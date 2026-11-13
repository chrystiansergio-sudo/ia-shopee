"""Busca vários temas (maior comissão + venda/nota) e monta uma folha com as fotos para eu escolher. Grava _varios.json"""
import json, os, sys, time, urllib.request, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, shopee
peneira.env()
pre = peneira.cfg("robos")["dono"]["chaves_env"]
APP, SEC = os.environ[pre + "_SHOPEE_APP_ID"], os.environ[pre + "_SHOPEE_SECRET"]
AQUI = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(AQUI, "_varios"); os.makedirs(D, exist_ok=True)
TEMAS = sys.argv[1:]
PROIBIR = ("infantil", "criança", "crianca", "bebê", "bebe", "kids", "disney", "marvel", "batman", "sexy", "lingerie", "kit 2", "kit 3", "kit 4", "kit 5")
todos = []
for kw in TEMAS:
    ps = None
    for t in range(5):
        try:
            ps = shopee.search(APP, SEC, kw, sort=5, limit=40); break
        except Exception:
            time.sleep(4)
    bons = [p for p in (ps or []) if p["sold"] >= 50 and p["rating"] >= 4.6 and p["image_url"]
            and not peneira.marca_famosa(p["title"]) and not any(w in p["title"].lower() for w in PROIBIR)]
    bons.sort(key=lambda p: (-p["commission"], -p["sold"]))
    for p in bons[:3]:
        i = len(todos)
        arq = os.path.join(D, f"{i:02d}.jpg")
        try:
            open(arq, "wb").write(urllib.request.urlopen(urllib.request.Request(p["image_url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        except Exception:
            continue
        p["palavra"] = kw; todos.append(p)
        print(i, kw, f"{p['commission']*100:.0f}%", p["sold"], p["rating"], p["title"][:70], flush=True)
json.dump(todos, open(os.path.join(AQUI, "_varios.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n = len(todos)
ent = sum([["-i", os.path.join(D, f"{i:02d}.jpg")] for i in range(n)], [])
f = "".join(f"[{i}]scale=200:200,drawtext=text='{i}':x=5:y=5:fontsize=28:fontcolor=red:box=1[s{i}];" for i in range(n))
cols = 6
linhas = (n + cols - 1) // cols
lay = "|".join(f"{(i % cols) * 200}_{(i // cols) * 200}" for i in range(n))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ent, "-filter_complex", f + "".join(f"[s{i}]" for i in range(n)) + f"xstack=inputs={n}:layout={lay}:fill=black",
                os.path.join(AQUI, "_varios.jpg")])
