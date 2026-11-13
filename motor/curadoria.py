"""Ferramenta de curadoria (uso único): lista candidatos da Pixabay e gera folha de miniaturas."""
import json, os, sys, urllib.parse, urllib.request
from peneira import RAIZ, env

PROIBIDO = {"bikini", "swimsuit", "beach", "sexy", "kiss", "lingerie", "underwear", "body", "bed", "erotic", "nude",
            "smoking", "cigarette", "alcohol", "beer", "wine", "gun", "blood", "child", "kid", "baby", "boy", "girl child"}
TERMOS = sys.argv[1:] or ["surprised woman face", "shocked woman", "excited woman", "woman wow face", "surprised man face",
                          "shocked man", "excited man", "man wow", "excited dog", "happy dog face", "woman pointing", "man pointing"]
env()
out, vistos = [], set()
for termo in TERMOS:
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": os.environ["PIXABAY_KEY"], "q": termo, "per_page": 30, "safesearch": "true"})
    hits = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))["hits"]
    for h in hits:
        tags = {t.strip() for t in h["tags"].split(",")}
        if h["id"] in vistos or tags & PROIBIDO or not (3 <= h["duration"] <= 30):
            continue
        vistos.add(h["id"])
        out.append({"id": h["id"], "termo": termo, "tags": h["tags"], "dur": h["duration"],
                    "thumb": h["videos"]["medium"]["thumbnail"], "url": h["videos"]["medium"]["url"]})
json.dump(out, open(os.path.join(RAIZ, "dados", "candidatos.json"), "w"), indent=1)
print(len(out), "candidatos")
