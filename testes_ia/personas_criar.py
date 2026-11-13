"""Cria 2 mulheres e 2 homens de IA (pessoas que NÃO existem) com FLUX.1-schnell (Apache-2.0, grátis no HF).
Cada um: retrato de frente + meio corpo, mesmo seed/descrição. Salva em dados/personas/."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import ia_online
from peneira import RAIZ
PASTA = os.path.join(RAIZ, "dados", "personas")
os.makedirs(PASTA, exist_ok=True)
P = [
    ("ana", "f", "a friendly Brazilian woman in her late 20s, long wavy dark brown hair, warm brown eyes, light olive skin, natural makeup, wearing a plain beige knit top", 101),
    ("julia", "f", "a cheerful Brazilian woman in her early 30s, shoulder-length straight light brown hair with soft highlights, fair skin, green eyes, wearing a plain white t-shirt", 202),
    ("rafael", "m", "a friendly Brazilian man in his early 30s, short dark hair, neat short beard, tan skin, brown eyes, wearing a plain navy blue t-shirt", 303),
    ("lucas", "m", "a cheerful Brazilian man in his late 20s, short curly black hair, clean shaven, dark brown skin, warm smile, wearing a plain light grey polo shirt", 404),
]
ESTILO = "photorealistic, natural soft daylight, plain light grey studio background, sharp focus, high detail skin texture, no text, no logo"
saida = []
for nome, g, desc, seed in P:
    rosto = os.path.join(PASTA, f"{nome}_rosto.jpg")
    corpo = os.path.join(PASTA, f"{nome}_corpo.jpg")
    ia_online.imagem(f"Close-up front portrait photo of {desc}, looking at the camera, gentle smile. {ESTILO}", rosto, w=768, h=1024, seed=seed)
    ia_online.imagem(f"Waist-up photo of {desc}, standing, facing the camera, relaxed arms, gentle smile. {ESTILO}", corpo, w=768, h=1024, seed=seed)
    saida.append({"nome": nome, "genero": g, "descricao": desc, "rosto": rosto, "corpo": corpo})
    print("ok", nome, flush=True)
json.dump(saida, open(os.path.join(PASTA, "personas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
