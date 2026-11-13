"""Estoque de vídeos prontos.

Fluxo: o robô fabrica vídeos e guarda aqui (disponível). Quando um cliente compra, o robô pega
vídeos do estoque que esse cliente nunca recebeu, troca o link pelo link de afiliado DELE, envia
e marca como enviado (um vídeo nunca vai para dois clientes). Depois o robô fabrica mais para repor.
"""
import json
import os
import random
import sqlite3
import time

import peneira
from peneira import RAIZ, cfg

DB = os.path.join(RAIZ, "dados", "estoque.db")
PASTA = os.path.join(RAIZ, "saida", "estoque")
VALIDADE_H = 48  # preço muda: vídeo com mais de 48 h é descartado
FORMATOS = ["cena", "narrado", "cachorro"]  # aprovado pelo dono: sem pessoa de IA falando


def banco():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("""create table if not exists videos(
        id integer primary key autoincrement, item_id text, titulo text, nicho text, formato text, arquivo text,
        legenda text, product_link text, link_dono text, preco real, criado real,
        status text default 'disponivel', pedido_id integer, cliente text, enviado real)""")
    return c


def contar():
    c = banco()
    lim = time.time() - VALIDADE_H * 3600
    tot = c.execute("select count(*) from videos where status='disponivel' and criado>?", (lim,)).fetchone()[0]
    por = {r[0]: r[1] for r in c.execute("select nicho,count(*) from videos where status='disponivel' and criado>? group by nicho", (lim,))}
    env = c.execute("select count(*) from videos where status='enviado'").fetchone()[0]
    c.close()
    return {"disponiveis": tot, "por_nicho": por, "enviados": env}


def limpar_vencidos():
    c = banco()
    lim = time.time() - VALIDADE_H * 3600
    for r in c.execute("select id,arquivo from videos where status='disponivel' and criado<=?", (lim,)).fetchall():
        try:
            os.remove(r["arquivo"])
        except OSError:
            pass
        c.execute("update videos set status='vencido' where id=?", (r["id"],))
    # apaga arquivos enviados há mais de 7 dias (o cliente já recebeu)
    for r in c.execute("select id,arquivo from videos where status='enviado' and enviado<?", (time.time() - 7 * 86400,)).fetchall():
        try:
            os.remove(r["arquivo"])
        except OSError:
            pass
    c.commit()
    c.close()


def proximo_plano():
    """escolhe o próximo nicho/formato a fabricar, equilibrando o estoque"""
    nichos = list(cfg("nichos").keys())
    conta = contar()["por_nicho"]
    menos = min(nichos, key=lambda n: (conta.get(n, 0), random.random()))
    c = banco()
    ult = [r[0] for r in c.execute("select formato from videos order by id desc limit 4")]
    c.close()
    formato = random.choice([f for f in FORMATOS if f not in ult[:2]] or FORMATOS)
    if menos == "pet" and random.random() < .5:
        formato = "cachorro"
    if formato == "cachorro" and menos != "pet":
        formato = random.choice(["cena", "narrado"])
    return menos, formato


def fabricar(nicho=None, formato=None, evitar=None):
    """faz 1 vídeo e guarda no estoque"""
    import video2
    if not nicho:
        nicho, formato = proximo_plano()
    c = banco()
    ja = {r[0] for r in c.execute("select item_id from videos where status='disponivel'")}
    c.close()
    ps = [p for p in peneira.escolher("_estoque", nicho, 6) if p["item_id"] not in ja]
    if not ps:
        return None
    p = ps[0]
    os.makedirs(PASTA, exist_ok=True)
    arq = os.path.join(PASTA, f"{int(time.time())}_{p['item_id']}.mp4")
    n_feitos = banco().execute("select count(*) from videos").fetchone()[0]
    info = video2.fazer(p, nicho, arq, formato=formato, evitar=evitar, genero="fm"[n_feitos % 2])  # alterna voz feminina/masculina
    c = banco()
    cur = c.execute("insert into videos(item_id,titulo,nicho,formato,arquivo,legenda,product_link,link_dono,preco,criado) values(?,?,?,?,?,?,?,?,?,?)",
                    (p["item_id"], p["title"], nicho, info["formato"], arq, info["legenda"], p.get("product_link") or "",
                     p.get("link") or "", p["price"], time.time()))
    c.commit()
    vid = cur.lastrowid
    c.close()
    return vid


def reservar(qtd, nicho, cliente, pedido_id):
    """separa até qtd vídeos para o pedido (que esse cliente nunca recebeu)"""
    limpar_vencidos()
    ja = peneira.ja_usados(cliente, 365)
    c = banco()
    lim = time.time() - VALIDADE_H * 3600
    q = "select * from videos where status='disponivel' and criado>?"
    args = [lim]
    if nicho and nicho.lower() not in ("todos", "todos os nichos", "variado", "misto"):
        q += " and nicho=?"
        args.append(nicho)
    linhas = [dict(r) for r in c.execute(q + " order by criado", args) if r["item_id"] not in ja]
    # variedade: alterna formatos
    linhas.sort(key=lambda r: (FORMATOS.index(r["formato"]) if r["formato"] in FORMATOS else 9, r["criado"]))
    escolha = []
    por_fmt = {}
    for r in linhas:
        por_fmt.setdefault(r["formato"], []).append(r)
    while len(escolha) < qtd and any(por_fmt.values()):
        for f in list(por_fmt):
            if por_fmt[f] and len(escolha) < qtd:
                escolha.append(por_fmt[f].pop(0))
    for r in escolha:
        c.execute("update videos set status='reservado', pedido_id=?, cliente=? where id=?", (pedido_id, cliente, r["id"]))
    c.commit()
    c.close()
    return escolha


def reservados(pedido_id):
    c = banco()
    r = [dict(x) for x in c.execute("select * from videos where pedido_id=? order by id", (pedido_id,))]
    c.close()
    return r


def marcar_enviado(vid):
    c = banco()
    c.execute("update videos set status='enviado', enviado=? where id=?", (time.time(), vid))
    c.commit()
    c.close()


def devolver(pedido_id):
    """se o pedido for cancelado, os vídeos não enviados voltam para o estoque"""
    c = banco()
    c.execute("update videos set status='disponivel', pedido_id=null, cliente=null where pedido_id=? and status='reservado'", (pedido_id,))
    c.commit()
    c.close()
