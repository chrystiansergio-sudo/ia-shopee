"""Clipes de reação APROVADOS (lista em config/clipes.json), baixados uma vez e guardados."""
import json
import os
import random
import urllib.request

from peneira import RAIZ

CACHE = os.path.join(RAIZ, "dados", "clipes")


def lista():
    return json.load(open(os.path.join(RAIZ, "config", "clipes.json"), encoding="utf-8"))


def caminho(c):
    return os.path.join(CACHE, f'{c["id"]}.mp4')


def baixar_todos():
    os.makedirs(CACHE, exist_ok=True)
    for c in lista():
        if not os.path.exists(caminho(c)) and c.get("url"):
            req = urllib.request.Request(c["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(caminho(c), "wb") as f:
                f.write(r.read())
            print("baixado", c["id"])


def clipe(tipo, evitar=()):
    """Sorteia um clipe aprovado do tipo (f, m, pet), evitando os já usados no pack."""
    ops = [c for c in lista() if c["tipo"] == tipo and os.path.exists(caminho(c))]
    novos = [c for c in ops if c["id"] not in evitar] or ops
    return random.choice(novos) if novos else None


if __name__ == "__main__":
    baixar_todos()
