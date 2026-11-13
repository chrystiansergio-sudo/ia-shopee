"""Cadastro do site: clientes, agentes (robôs de WhatsApp), preços, vendas e configurações."""
import os
import sqlite3
import time

from peneira import RAIZ, env

DB = os.path.join(RAIZ, "dados", "site.db")
PRECOS_PADRAO = [(1, "Pack 10 vídeos", 10, 0.0), (2, "Pack 20 vídeos", 20, 0.0), (3, "Pack 30 vídeos", 30, 0.0)]
CONFIG_PADRAO = {"estoque_alvo": "20", "diario_ativo": "1", "diario_hora": "07:00", "diario_qtd": "10", "diario_nicho": "todos"}


def banco():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript("""
    create table if not exists clientes(id integer primary key autoincrement, nome text, whatsapp text, app_id text, secret text,
        nicho text default 'todos', ativo integer default 1, dono integer default 0, obs text default '', criado real);
    create table if not exists agentes(id integer primary key autoincrement, apelido text, sessao text unique, criado real);
    create table if not exists precos(id integer primary key, nome text, qtd integer, valor real);
    create table if not exists vendas(id integer primary key autoincrement, cliente_id integer, qtd integer, valor real,
        pago integer default 0, data real, pedido_id integer, obs text default '');
    create table if not exists config(chave text primary key, valor text);
    """)
    if not c.execute("select 1 from precos").fetchone():
        c.executemany("insert into precos values(?,?,?,?)", PRECOS_PADRAO)
    for k, v in CONFIG_PADRAO.items():
        c.execute("insert or ignore into config values(?,?)", (k, v))
    if not c.execute("select 1 from agentes").fetchone():
        c.execute("insert into agentes(apelido,sessao,criado) values(?,?,?)", ("Robô principal", "dono", time.time()))
    if not c.execute("select 1 from clientes where dono=1").fetchone():
        env()
        c.execute("insert into clientes(nome,whatsapp,app_id,secret,nicho,dono,criado,obs) values(?,?,?,?,?,1,?,?)",
                  ("Eu (dono)", os.environ.get("DONO_WHATSAPP", ""), os.environ.get("DONO_SHOPEE_APP_ID", ""), os.environ.get("DONO_SHOPEE_SECRET", ""),
                   "todos", time.time(), "Recebe os vídeos diários"))
    c.commit()
    return c


def q(sql, args=(), um=False):
    c = banco()
    cur = c.execute(sql, args)
    r = cur.fetchone() if um else cur.fetchall()
    c.close()
    return (dict(r) if r else None) if um else [dict(x) for x in r]


def exe(sql, args=()):
    c = banco()
    cur = c.execute(sql, args)
    c.commit()
    rid = cur.lastrowid
    c.close()
    return rid


def get_config(chave):
    r = q("select valor from config where chave=?", (chave,), um=True)
    return r["valor"] if r else CONFIG_PADRAO.get(chave)


def set_config(chave, valor):
    exe("insert into config values(?,?) on conflict(chave) do update set valor=excluded.valor", (chave, str(valor)))


def cliente(cid):
    return q("select * from clientes where id=?", (cid,), um=True)


def cliente_dono():
    return q("select * from clientes where dono=1", um=True)


def numero_br(n):
    n = "".join(ch for ch in str(n) if ch.isdigit())
    if len(n) <= 11:
        n = "55" + n
    return n


def testar_api(app_id, secret):
    """confere se as chaves de afiliado do cliente funcionam"""
    import shopee
    try:
        shopee.search(app_id, secret, "garrafa", limit=1)
        return True, "API da Shopee funcionando"
    except Exception as e:
        return False, f"API da Shopee recusou: {e}"
