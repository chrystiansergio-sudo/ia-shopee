"""Cenas REAIS (filmagens) por nicho, do Coverr e da Pixabay, já cortadas em pé (720x1280) e guardadas.

As cenas servem de fundo atrás da foto real do produto e de abertura nos vídeos "narrado"/"cachorro".
Nunca usamos clipes feitos por IA aqui (o Coverr marca is_ai_generated).
"""
import json
import os
import random
import subprocess
import urllib.parse
import urllib.request

from peneira import RAIZ, env

PASTA = os.path.join(RAIZ, "dados", "cenas")
UA = {"User-Agent": "Mozilla/5.0"}
POR_NICHO = 8  # quantas cenas guardar por nicho
# a cena só entra se as etiquetas/título tiverem uma destas palavras (evita cena fora do assunto)
EXIGE = {
    "casa e cozinha": ["kitchen", "cooking", "food", "cook", "pan", "chef"],
    "organizacao": ["organiz", "closet", "drawer", "folding", "wardrobe", "storage", "shelf"],
    "limpeza": ["clean", "mop", "wash", "dish", "dust", "vacuum"],
    "beleza": ["makeup", "skincare", "cream", "beauty", "cosmetic", "hair", "brush", "lipstick"],
    "moda": ["fashion", "clothes", "clothing", "shoe", "bag", "store", "dress", "outfit"],
    "eletronicos": ["phone", "smartphone", "headphone", "laptop", "charger", "gadget", "tech", "computer"],
    "pet": ["dog", "cat", "puppy", "kitten", "pet"],
    "fitness": ["gym", "workout", "exercise", "fitness", "yoga", "training", "dumbbell"],
    "casa e decoracao": ["living room", "interior", "bedroom", "decor", "home", "sofa", "candle"],
    "carro": ["car", "driving", "vehicle", "dashboard", "steering"],
    "ferramentas": ["tool", "drill", "workshop", "repair", "diy", "hammer", "screwdriver"],
    "bebe e infantil": ["nursery", "toy", "crib", "baby room"],
    "papelaria": ["desk", "notebook", "writing", "pencil", "pen", "office", "study"],
    "viagem": ["travel", "suitcase", "airport", "luggage", "trip"],
    "maquiagem": ["makeup", "lipstick", "mascara", "eyeshadow", "cosmetic", "beauty", "eyeliner"],
    "saude": ["massage", "stretch", "relax", "wellness", "health", "spa", "posture"],
    "_cachorro": ["dog", "puppy"],
}
PROIBIDO = ["nude", "naked", "topless", "lingerie", "sexy", "underwear", "angry", "aggressive", "attack", "bark", "growl", "weapon", "blood", "fight", "drone", "aerial", "beach",
            "bikini", "sexy", "kiss", "funeral", "sick", "hospital", "dead", "smok", "alcohol", "beer", "wine"]

BUSCAS = {
    "casa e cozinha": ["kitchen cooking", "kitchen counter", "cooking pan", "cutting vegetables"],
    "organizacao": ["organized closet", "home organization", "folding clothes", "drawer organize"],
    "limpeza": ["cleaning home", "cleaning kitchen", "mopping floor", "washing dishes"],
    "beleza": ["makeup brush", "skincare routine", "applying cream", "hair brushing"],
    "moda": ["clothing store", "fashion clothes rack", "shoes closeup", "handbag"],
    "eletronicos": ["smartphone hands", "headphones music", "laptop desk", "charging phone"],
    "pet": ["dog at home", "happy dog", "cat at home", "puppy playing"],
    "fitness": ["gym workout", "home workout", "running shoes", "yoga mat"],
    "casa e decoracao": ["living room interior", "cozy bedroom", "home decor", "candles cozy"],
    "carro": ["car interior", "driving car", "car dashboard", "car wash"],
    "ferramentas": ["workshop tools", "drilling wall", "diy repair", "measuring tape"],
    "bebe e infantil": ["baby room", "baby toys", "nursery room"],
    "papelaria": ["desk study", "writing notebook", "office desk", "drawing pencils"],
    "viagem": ["travel suitcase", "airport travel", "packing suitcase", "road trip"],
    "maquiagem": ["applying lipstick", "makeup brush", "eyeshadow makeup", "mascara eyelashes"],
    "saude": ["neck massage", "stretching exercise", "morning stretch", "relaxing wellness"],
    "_cachorro": ["happy dog", "dog looking at camera", "dog tilting head", "excited puppy", "dog running home"],
    "_geral": ["shopping online phone", "unboxing package", "home lifestyle", "delivery package door"],
}


def _json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def _coverr(termo):
    k = os.environ.get("COVERR_KEY")
    if not k:
        return []
    d = _json("https://api.coverr.co/videos?" + urllib.parse.urlencode({"query": termo, "page_size": 20, "urls": "true"}),
              {"Authorization": f"Bearer {k}"})
    out = []
    for h in d.get("hits", []):
        if h.get("is_ai_generated") or not (h.get("urls") or {}).get("mp4"):
            continue
        out.append({"id": f"cv_{h['id']}", "url": h["urls"]["mp4"], "dur": float(h.get("duration") or 10),
                    "tags": " ".join(h.get("tags") or []), "titulo": h.get("title") or "", "fonte": "coverr", "cid": h["id"]})
    return out


def _pixabay(termo):
    k = os.environ.get("PIXABAY_KEY")
    if not k:
        return []
    d = _json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": k, "q": termo, "per_page": 20, "safesearch": "true", "video_type": "film"}))
    proib = {"bikini", "swimsuit", "sexy", "lingerie", "underwear", "kiss", "blood", "gun", "alcohol", "smoking", "child", "kid", "baby girl", "boy"}
    out = []
    for h in d.get("hits", []):
        tags = {t.strip() for t in h["tags"].split(",")}
        if tags & proib or not (4 <= h["duration"] <= 40) or h.get("type", "film") != "film"                 or tags & {"3d", "animation", "render", "cartoon", "ai generated", "ai", "illustration", "cgi"}:
            continue
        v = h["videos"].get("medium") or h["videos"].get("small")
        if v and v.get("url"):
            out.append({"id": f"px_{h['id']}", "url": v["url"], "dur": h["duration"], "tags": h["tags"], "fonte": "pixabay"})
    return out


def _preparar(c, destino):
    """baixa e corta em pé 720x1280, 30 fps, sem som, até 14 s"""
    bruto = destino + ".bruto"
    req = urllib.request.Request(c["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(bruto, "wb") as f:
        f.write(r.read())
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", bruto, "-t", "14", "-an",
                        "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,setsar=1",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", destino], check=True)
    finally:
        os.remove(bruto)
    if c["fonte"] == "coverr":  # o Coverr pede para registrar os downloads
        try:
            req = urllib.request.Request(f"https://api.coverr.co/videos/{c['cid']}/stats/downloads", method="PATCH",
                                         headers={**UA, "Authorization": f"Bearer {os.environ.get('COVERR_KEY')}"})
            urllib.request.urlopen(req, timeout=15).read()
        except Exception:
            pass


def abastecer(nicho, qtd=POR_NICHO):
    env()
    pasta = os.path.join(PASTA, nicho)
    os.makedirs(pasta, exist_ok=True)
    tem = [f for f in os.listdir(pasta) if f.endswith(".mp4")]
    if len(tem) >= qtd:
        return
    termos = BUSCAS.get(nicho, BUSCAS["_geral"])[:]
    random.shuffle(termos)
    cand = []
    for t in termos:
        try:
            cand += _coverr(t)
        except Exception as e:
            print("  aviso coverr", e)
        try:
            cand += _pixabay(t)
        except Exception as e:
            print("  aviso pixabay", e)
    random.shuffle(cand)
    vistos = set(f[:-4] for f in tem)
    rej = os.path.join(os.path.dirname(pasta), "rejeitadas.txt")  # cenas reprovadas no olho: nunca baixar de novo
    if os.path.exists(rej):
        vistos |= set(open(rej, encoding="utf-8").read().split())
    for c in cand:
        if len(tem) >= qtd:
            break
        txt = (c.get("tags", "") + " " + c.get("titulo", "")).lower()
        if c["id"] in vistos or any(p in txt for p in PROIBIDO) or not any(e in txt for e in EXIGE.get(nicho, [""])):
            continue
        vistos.add(c["id"])
        dest = os.path.join(pasta, c["id"] + ".mp4")
        try:
            _preparar(c, dest)
            tem.append(c["id"] + ".mp4")
            json.dump(c, open(dest[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        except Exception as e:
            print("  aviso cena", c["id"], e)


def cena(nicho, evitar=()):
    """caminho de uma cena real do nicho (abastece se faltar)"""
    if nicho not in BUSCAS:
        nicho = "_geral"
    abastecer(nicho)
    pasta = os.path.join(PASTA, nicho)
    ops = [os.path.join(pasta, f) for f in os.listdir(pasta) if f.endswith(".mp4")]
    novos = [o for o in ops if os.path.basename(o) not in evitar] or ops
    return random.choice(novos) if novos else None


if __name__ == "__main__":
    import sys
    for n in (sys.argv[1:] or ["casa e cozinha"]):
        abastecer(n)
        print(n, os.listdir(os.path.join(PASTA, n)))
