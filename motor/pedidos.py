"""Fila de pedidos de packs. O site (no futuro) só precisa gravar aqui.

Uso pelo terminal:
  python pedidos.py novo --cliente "Maria" --whatsapp 5511999999999 --nicho pet --qtd 10 [--robo dono]
  python pedidos.py lista
"""
import argparse
import os
import sqlite3
import time

from peneira import RAIZ, cfg

DB = os.path.join(RAIZ, "dados", "pedidos.db")
PACKS = [5, 10, 15, 20, 25, 50, 100]


def banco():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""create table if not exists pedidos(
        id integer primary key autoincrement, cliente text, whatsapp text, nicho text, qtd integer, robo text,
        status text default 'pendente', feitos integer default 0, enviados integer default 0,
        erro text default '', criado real, atualizado real)""")
    cols = {r[1] for r in c.execute("pragma table_info(pedidos)")}
    for col, tipo in (("cliente_id", "integer"), ("sessao", "text"), ("venda_id", "integer")):
        if col not in cols:
            c.execute(f"alter table pedidos add column {col} {tipo}")
    return c


def novo(cliente, whatsapp, nicho, qtd, robo="dono", cliente_id=None, sessao=None, venda_id=None):
    whatsapp = "".join(ch for ch in str(whatsapp) if ch.isdigit())
    if len(whatsapp) <= 11:
        whatsapp = "55" + whatsapp  # número brasileiro sem DDI
    if not 1 <= int(qtd) <= 100:
        raise ValueError("quantidade deve ser de 1 a 100")
    c = banco()
    cur = c.execute("insert into pedidos(cliente,whatsapp,nicho,qtd,robo,criado,atualizado,cliente_id,sessao,venda_id) values(?,?,?,?,?,?,?,?,?,?)",
                    (cliente.strip(), whatsapp, nicho.strip() or "todos", int(qtd), robo, time.time(), time.time(), cliente_id, sessao or "dono", venda_id))
    c.commit()
    pid = cur.lastrowid
    c.close()
    return pid


def proximo():
    c = banco()
    # pedido interrompido (ex.: servidor reiniciou) volta para a fila
    r = c.execute("select * from pedidos where status in ('fazendo','pendente') order by status='fazendo' desc, id limit 1").fetchone()
    c.close()
    return dict(r) if r else None


def atualizar(pid, **campos):
    c = banco()
    campos["atualizado"] = time.time()
    c.execute(f"update pedidos set {', '.join(k + '=?' for k in campos)} where id=?", (*campos.values(), pid))
    c.commit()
    c.close()


def lista(n=30):
    c = banco()
    r = [dict(x) for x in c.execute("select * from pedidos order by id desc limit ?", (n,))]
    c.close()
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("novo")
    a.add_argument("--cliente", required=True)
    a.add_argument("--whatsapp", required=True)
    a.add_argument("--nicho", default="todos")
    a.add_argument("--qtd", type=int, default=10)
    a.add_argument("--robo", default="dono")
    sub.add_parser("lista")
    x = ap.parse_args()
    if x.cmd == "novo":
        print("pedido criado:", novo(x.cliente, x.whatsapp, x.nicho, x.qtd, x.robo))
    else:
        for p in lista():
            print(f'#{p["id"]} {p["cliente"]} | {p["nicho"]} | {p["feitos"]}/{p["enviados"]}/{p["qtd"]} | {p["status"]} {p["erro"][:60]}')
