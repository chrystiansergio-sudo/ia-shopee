import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video, ia_online as ia
T = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(os.path.join(T, "apresentador.jpg")):
    ia.imagem("vertical smartphone selfie photo, friendly brazilian man around 32 years old with short dark hair and light beard, looking straight at the camera, warm natural smile, mouth closed, casual polo shirt, bright modern kitchen background, realistic skin texture, natural daylight, sharp focus",
              os.path.join(T, "apresentador.jpg"), seed=21)
casa = json.load(open(os.path.join(T, "produto.json"), encoding="utf-8"))
pet = peneira.escolher("teste-ia", "pet", 1)[0]
elet = peneira.escolher("teste-ia", "eletronicos", 1)[0]
jobs = [
    ("teste1_apresentadora.mp4", casa, "casa e cozinha", dict(apresentador={"imagem": os.path.join(T, "apresentadora.jpg"), "genero": "f"}, estilo="achado")),
    ("teste2_cachorro.mp4", pet, "pet", dict(clipe_gancho=os.path.join(T, "cachorro_ia.mp4"), estilo="preco")),
    ("teste3_apresentador.mp4", elet, "eletronicos", dict(apresentador={"imagem": os.path.join(T, "apresentador.jpg"), "genero": "m"}, estilo="nao_compre")),
]
for nome, p, nicho, kw in jobs:
    t = time.time()
    info = video.fazer(p, nicho, os.path.join(T, nome), produto_ia=True, **kw)
    print(f"OK {nome} {time.time()-t:.0f}s | {p['title'][:50]} | {info['roteiro']['falas'][0]}", flush=True)
    open(os.path.join(T, nome[:-4] + ".txt"), "w", encoding="utf-8").write(info["legenda"] + "\n\n" + (p.get("link") or ""))
