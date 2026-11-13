"""Busca produtos na API de afiliados e escolhe os melhores para um pedido.

Regras: bom desconto, muitas vendas, nota alta, boa comissão,
nunca repete produto para o mesmo cliente dentro do prazo.
"""
import json
import math
import os
import random
import sqlite3
import time

import shopee

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(RAIZ, "dados", "historico.db")


def env():
    p = os.path.join(RAIZ, ".env")
    if os.path.exists(p):
        for linha in open(p, encoding="utf-8"):
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                os.environ.setdefault(k, v)


env()  # carrega o .env assim que o módulo é importado (número do dono, chaves etc.)

def cfg(nome):
    return json.load(open(os.path.join(RAIZ, "config", f"{nome}.json"), encoding="utf-8"))


def banco():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("create table if not exists usados(cliente text, item_id text, titulo text, quando real)")
    return c


def chave_cliente(nome):
    return " ".join(nome.lower().split())


def ja_usados(cliente, dias):
    c = banco()
    r = {x[0] for x in c.execute("select item_id from usados where cliente=? and quando>?",
                                  (chave_cliente(cliente), time.time() - dias * 86400))}
    c.close()
    return r


def marcar(cliente, produtos):
    c = banco()
    c.executemany("insert into usados values(?,?,?,?)",
                  [(chave_cliente(cliente), p["item_id"], p["title"], time.time()) for p in produtos])
    c.commit()
    c.close()


MARCAS = ("airpods", "airpod", "apple watch", "iphone 1", "jbl", "nike", "adidas", "lacoste", "gucci", "louis vuitton", "chanel",
          "dior", "rolex", "prada", "tommy", "calvin klein", "ray-ban", "rayban", "oakley", "puma", "disney", "marvel", "stanley", "beauty of joseon", "cerave", "la roche", "loreal", "l'oréal", "natura", "boticário", "boticario", "colar de cordas")


def marca_famosa(titulo):
    t = titulo.lower()
    return any(m in t for m in MARCAS)


def nota(p):
    return (p["discount"] / 100) * 2 + math.log10(max(p["sold"], 1)) * .6 + (p["rating"] - 4.5) * 2 + p["commission"] * 8


def palavras_do_nicho(nicho):
    nichos = cfg("nichos")
    n = (nicho or "todos").strip().lower()
    if n in ("todos", "todos os nichos", "variado", "misto", ""):
        # mistura: intercala palavras de todos os nichos
        listas = [random.sample(v, len(v)) for v in nichos.values()]
        random.shuffle(listas)
        out = []
        for i in range(max(map(len, listas))):
            out += [l[i] for l in listas if i < len(l)]
        return out
    if n in nichos:
        return random.sample(nichos[n], len(nichos[n]))
    # nicho livre digitado pelo cliente: usa o próprio texto como busca + variações
    return [n] + [f"{n} {x}" for x in ("kit", "promoção", "barato", "premium", "acessorios", "presente")]


def buscar(app, sec, kw, sort, pagina):
    for tent in range(3):
        try:
            return shopee.search(app, sec, kw, sort=sort, limit=50, page=pagina)
        except shopee.ShopeeError as e:
            print("  aviso busca", kw, e)
            time.sleep(2 + tent * 3)
    return []


def escolher(cliente, nicho, qtd, robo="dono", palavras=None, proibir=()):
    """Devolve até `qtd` produtos para o pedido. `palavras` troca as buscas do nicho; `proibir` corta títulos com essas palavras."""
    env()
    pre = cfg("robos")[robo]["chaves_env"]
    app, sec = os.environ.get(f"{pre}_SHOPEE_APP_ID"), os.environ.get(f"{pre}_SHOPEE_SECRET")
    pn = cfg("peneira")
    usados = ja_usados(cliente, pn["dias_sem_repetir_cliente"])
    palavras = palavras or palavras_do_nicho(nicho)
    por_palavra = max(2, math.ceil(qtd * 1.3 / max(len(palavras), 1)))
    vistos, bons = set(), []
    for pagina in (1, 2, 3):
        for kw in palavras:
            achados = buscar(app, sec, kw, 2, pagina) + buscar(app, sec, kw, 5, pagina)
            da_palavra = []
            for p in achados:
                if p["item_id"] in usados or p["item_id"] in vistos or not p["image_url"] or marca_famosa(p["title"])                         or any(x in p["title"].lower() for x in proibir):
                    continue
                vistos.add(p["item_id"])
                if (p["discount"] >= pn["desconto_min"] and p["sold"] >= pn["vendas_min"] and p["rating"] >= pn["nota_min"]
                        and p["commission"] >= pn["comissao_min"] and pn["preco_min"] <= p["price"] <= pn["preco_max"]):
                    p["palavra"] = kw
                    da_palavra.append(p)
            da_palavra.sort(key=nota, reverse=True)
            bons += da_palavra[:por_palavra]
            if len(bons) >= qtd * 1.3:
                break
        if len(bons) >= qtd * 1.3:
            break
    bons.sort(key=nota, reverse=True)
    escolhidos = bons[:qtd]
    random.shuffle(escolhidos)  # não deixa o pack todo em sequência do mesmo tipo
    return escolhidos


if __name__ == "__main__":
    import sys
    nicho = sys.argv[1] if len(sys.argv) > 1 else "todos"
    qtd = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    for p in escolher("teste", nicho, qtd):
        print(f'{p["discount"]:>3}% | {p["sold"]:>6} vend | {p["rating"]} | com {p["commission"]:.2f} | R$ {p["price"]:7.2f} | {p["palavra"][:18]:18} | {p["title"][:50]}')
