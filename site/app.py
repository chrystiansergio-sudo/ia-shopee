"""Painel do IA Shopee: clientes, vendas de packs, faturamento por mês, agentes (WhatsApp), estoque e preços."""
import calendar
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.request
from datetime import datetime
from functools import wraps

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, "motor"))
import cadastro  # noqa: E402
import estoque  # noqa: E402
import pedidos  # noqa: E402
from peneira import cfg, env  # noqa: E402

env()
WA = os.environ.get("IA_WA_URL", "http://127.0.0.1:3101")
app = Flask(__name__)
app.secret_key = os.environ.get("SITE_SECRET") or "troque-isto"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=30 * 86400)


# ------------------------------------------------------------------ utilidades
def brl(v):
    s = f"{(v or 0):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def data_br(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else "—"


def hash_senha(s, sal=None):
    sal = sal or secrets.token_hex(8)
    return sal + "$" + hashlib.pbkdf2_hmac("sha256", s.encode(), sal.encode(), 200_000).hex()


def confere(s, h):
    if not h or "$" not in h:
        return False
    return secrets.compare_digest(hash_senha(s, h.split("$")[0]), h)


def csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


@app.before_request
def protege():
    if request.method == "POST" and request.form.get("_csrf") != session.get("csrf"):
        abort(400)


def logado(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


def wa_get(caminho, timeout=5):
    try:
        with urllib.request.urlopen(WA + caminho, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def wa_post(caminho, dados):
    try:
        req = urllib.request.Request(WA + caminho, data=json.dumps(dados).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"erro": str(e)}


ROTULO_STATUS = {"conectado": "Conectado", "aguardando_qr": "Aguardando QR", "reconectando": "Reconectando", "iniciando": "Iniciando",
                 "desconectado": "Desconectado", "inexistente": "Desligado", None: "Bot desligado"}
ROTULO_PEDIDO = {"pendente": "Na fila", "fazendo": "Enviando", "enviado": "Entregue", "incompleto": "Incompleto", "pronto": "Pronto", "cancelado": "Cancelado"}


@app.context_processor
def globais():
    return {"csrf": csrf, "brl": brl, "data_br": data_br, "ROTULO_STATUS": ROTULO_STATUS, "ROTULO_PEDIDO": ROTULO_PEDIDO,
            "NICHOS": list(cfg("nichos").keys())}


# ------------------------------------------------------------------ acesso
@app.route("/login", methods=["GET", "POST"])
def login():
    if not cadastro.get_config("senha_hash"):
        return render_template("mensagem.html", titulo="Primeiro acesso",
                               texto="Use o link de primeiro acesso que o Claude te passou para criar sua senha.")
    if request.method == "POST":
        if confere(request.form.get("senha", ""), cadastro.get_config("senha_hash")):
            session.clear()
            session["ok"] = True
            session.permanent = True
            return redirect(url_for("geral"))
        time.sleep(1)
        flash("Senha incorreta.", "erro")
    return render_template("login.html")


@app.route("/primeiro-acesso/<token>", methods=["GET", "POST"])
def primeiro(token):
    if not os.environ.get("SITE_TOKEN") or not secrets.compare_digest(token, os.environ["SITE_TOKEN"]) or cadastro.get_config("senha_hash"):
        abort(404)
    if request.method == "POST":
        s1, s2 = request.form.get("senha", ""), request.form.get("senha2", "")
        if len(s1) < 6 or s1 != s2:
            flash("A senha precisa ter 6 caracteres ou mais e as duas precisam ser iguais.", "erro")
        else:
            cadastro.set_config("senha_hash", hash_senha(s1))
            session.clear()
            session["ok"] = True
            session.permanent = True
            flash("Senha criada! Bem-vindo ao painel.", "ok")
            return redirect(url_for("geral"))
    return render_template("primeiro.html")


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    return redirect(url_for("login"))


@app.route("/robo-tela.svg")
@logado
def robo_tela():
    try:
        n = max(0, int(request.args.get("n", "0")))
    except ValueError:
        n = 0
    rot = (request.args.get("r") or "")[:22].upper()
    return Response(render_template("_robo.svg", numero=n, rotulo=rot), mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.route("/robo.svg")
def robo_svg():
    return Response(render_template("_robo.svg"), mimetype="image/svg+xml", headers={"Cache-Control": "max-age=86400"})


@app.route("/manifest.webmanifest")
def manifest():
    return Response(json.dumps({"name": "IA Shopee", "short_name": "IA Shopee", "start_url": "/", "display": "standalone",
                                "background_color": "#fff5f1", "theme_color": "#ee4d2d",
                                "icons": [{"src": "/robo.svg", "sizes": "any", "type": "image/svg+xml"}]}), mimetype="application/manifest+json")


# ------------------------------------------------------------------ visão geral (faturamento por mês)
def limites_mes(ano, mes):
    ini = datetime(ano, mes, 1).timestamp()
    fim = datetime(ano + (mes == 12), mes % 12 + 1, 1).timestamp()
    return ini, fim


MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def meus_pedidos():
    dono = cadastro.cliente_dono()
    return [p for p in pedidos.lista(1000) if dono and p.get("cliente_id") == dono["id"]], dono


def mes_da_url():
    hoje = datetime.now()
    try:
        ano, mes = map(int, (request.args.get("mes") or hoje.strftime("%Y-%m")).split("-"))
        datetime(ano, mes, 1)
    except ValueError:
        ano, mes = hoje.year, hoje.month
    return ano, mes


@app.route("/")
@logado
def geral():
    hoje = datetime.now()
    ini, fim = limites_mes(hoje.year, hoje.month)
    vendas = cadastro.q("select * from vendas where data>=? and data<?", (ini, fim))
    recebido = sum(v["valor"] or 0 for v in vendas if v["pago"])
    a_receber = sum(v["valor"] or 0 for v in vendas if not v["pago"])
    est = estoque.contar()
    todos = pedidos.lista(2000)
    fila = [p for p in todos if p["status"] in ("pendente", "fazendo")]
    meus, dono = meus_pedidos()
    meus_mes = sum(p["enviados"] or 0 for p in meus if (p["criado"] or 0) >= ini)
    meus_total = sum(p["enviados"] or 0 for p in meus)
    sess = wa_get("/sessoes") or {}
    ag_ok = sum(1 for v in sess.values() if v == "conectado")
    clientes_lista = cadastro.q("""select c.*, (select coalesce(sum(qtd),0) from vendas v where v.cliente_id=c.id) as n_videos
                                   from clientes c where c.dono=0 order by c.nome""")
    vendidos = cadastro.q("""select coalesce(sum(v.qtd),0) s from vendas v join clientes c on c.id=v.cliente_id where c.dono=0""", um=True)["s"]
    return render_template("geral.html", aba="geral", recebido=recebido, a_receber=a_receber, vendas_mes=len(vendas),
                           titulo_mes=f"{MESES[hoje.month]} de {hoje.year}", est=est, fila=fila, ag_ok=ag_ok, ag_total=len(sess),
                           ag_off=max(0, len(sess) - ag_ok), meus_mes=meus_mes, meus_total=meus_total,
                           pedidos_entregues=sum(1 for p in todos if p["status"] == "enviado"),
                           vendidos=vendidos, clientes_lista=clientes_lista[:10],
                           alvo=int(cadastro.get_config("estoque_alvo") or 20))


@app.route("/faturamento")
@logado
def faturamento():
    ano, mes = mes_da_url()
    ini, fim = limites_mes(ano, mes)
    vendas = cadastro.q("""select v.*, c.nome as cliente from vendas v left join clientes c on c.id=v.cliente_id
                           where v.data>=? and v.data<? order by v.data desc""", (ini, fim))
    ant = (ano - (mes == 1), (mes - 2) % 12 + 1)
    prox = (ano + (mes == 12), mes % 12 + 1)
    return render_template("faturamento.html", aba="geral", vendas=vendas,
                           recebido=sum(v["valor"] or 0 for v in vendas if v["pago"]),
                           a_receber=sum(v["valor"] or 0 for v in vendas if not v["pago"]),
                           videos=sum(v["qtd"] or 0 for v in vendas),
                           titulo_mes=f"{MESES[mes]} de {ano}", ant=f"{ant[0]}-{ant[1]:02d}", prox=f"{prox[0]}-{prox[1]:02d}")


@app.route("/meus-videos", methods=["GET", "POST"])
@logado
def meus_videos():
    meus, dono = meus_pedidos()
    if request.method == "POST":
        try:
            qtd = int(request.form.get("qtd") or 0)
        except ValueError:
            qtd = 0
        if not dono:
            flash("Cadastro do dono não encontrado.", "erro")
        elif not 1 <= qtd <= 100:
            flash("A quantidade deve ser de 1 a 100 vídeos.", "erro")
        else:
            agente = cadastro.q("select * from agentes where id=?", (int(request.form.get("agente") or 0),), um=True)                 or cadastro.q("select * from agentes order by id limit 1", um=True)
            pedidos.novo(dono["nome"], dono["whatsapp"], request.form.get("nicho") or "todos", qtd,
                         cliente_id=dono["id"], sessao=agente["sessao"])
            flash(f"Pronto! O robô vai mandar {qtd} vídeos no seu WhatsApp. Os que já estão no estoque saem na hora.", "ok")
            return redirect(url_for("meus_videos"))
    hoje = datetime.now()
    ini, _ = limites_mes(hoje.year, hoje.month)
    return render_template("meus.html", aba="meus", meus=meus[:30], dono=dono,
                           total=sum(p["enviados"] or 0 for p in meus),
                           mes=sum(p["enviados"] or 0 for p in meus if (p["criado"] or 0) >= ini),
                           hoje_n=sum(p["enviados"] or 0 for p in meus if (p["criado"] or 0) >= datetime(hoje.year, hoje.month, hoje.day).timestamp()),
                           fila=sum(1 for p in meus if p["status"] in ("pendente", "fazendo")),
                           est=estoque.contar(), agentes=cadastro.q("select * from agentes order by id"))


# ------------------------------------------------------------------ clientes
@app.route("/clientes", methods=["GET", "POST"])
@logado
def clientes():
    if request.method == "POST":
        f = request.form
        nome, whats = f.get("nome", "").strip(), cadastro.numero_br(f.get("whatsapp", ""))
        if not nome or len(whats) < 12:
            flash("Preencha o nome e um WhatsApp com DDD.", "erro")
        else:
            app_id, sec = f.get("app_id", "").strip(), f.get("secret", "").strip()
            cid = cadastro.exe("insert into clientes(nome,whatsapp,app_id,secret,nicho,obs,criado) values(?,?,?,?,?,?,?)",
                               (nome, whats, app_id, sec, f.get("nicho") or "todos", f.get("obs", ""), time.time()))
            if app_id and sec:
                ok, msg = cadastro.testar_api(app_id, sec)
                flash(msg, "ok" if ok else "erro")
            flash("Cliente cadastrado.", "ok")
            return redirect(url_for("cliente", cid=cid))
    lista = cadastro.q("""select c.*, (select count(*) from vendas v where v.cliente_id=c.id) as n_vendas,
                          (select coalesce(sum(valor),0) from vendas v where v.cliente_id=c.id and pago=1) as total
                          from clientes c order by c.dono desc, c.ativo desc, c.nome""")
    return render_template("clientes.html", aba="clientes", clientes=lista)


@app.route("/clientes/<int:cid>", methods=["GET", "POST"])
@logado
def cliente(cid):
    c = cadastro.cliente(cid) or abort(404)
    if c["dono"]:
        return redirect(url_for("meus_videos"))  # o dono pede vídeos sem venda
    if request.method == "POST":
        f = request.form
        app_id, sec = f.get("app_id", "").strip(), f.get("secret", "").strip()
        if sec == "••••••":
            sec = c["secret"]
        cadastro.exe("update clientes set nome=?,whatsapp=?,app_id=?,secret=?,nicho=?,obs=?,ativo=? where id=?",
                     (f.get("nome", c["nome"]).strip(), cadastro.numero_br(f.get("whatsapp", c["whatsapp"])), app_id, sec,
                      f.get("nicho") or "todos", f.get("obs", ""), 1 if f.get("ativo") else 0, cid))
        if app_id and sec and (app_id != c["app_id"] or sec != c["secret"]):
            ok, msg = cadastro.testar_api(app_id, sec)
            flash(msg, "ok" if ok else "erro")
        flash("Dados salvos.", "ok")
        return redirect(url_for("cliente", cid=cid))
    vendas = cadastro.q("select * from vendas where cliente_id=? order by data desc", (cid,))
    peds = {p["id"]: p for p in pedidos.lista(500)}
    for v in vendas:
        v["pedido"] = peds.get(v["pedido_id"])
    return render_template("cliente.html", aba="clientes", c=c, vendas=vendas, precos=cadastro.q("select * from precos order by id"),
                           agentes=cadastro.q("select * from agentes order by id"), sess=wa_get("/sessoes") or {})


@app.route("/clientes/<int:cid>/testar", methods=["POST"])
@logado
def cliente_testar(cid):
    c = cadastro.cliente(cid) or abort(404)
    if not (c["app_id"] and c["secret"]):
        flash("Esse cliente ainda não tem a API da Shopee cadastrada.", "erro")
    else:
        ok, msg = cadastro.testar_api(c["app_id"], c["secret"])
        flash(msg, "ok" if ok else "erro")
    return redirect(url_for("cliente", cid=cid))


@app.route("/clientes/<int:cid>/vender", methods=["POST"])
@logado
def vender(cid):
    c = cadastro.cliente(cid) or abort(404)
    f = request.form
    try:
        qtd = int(f.get("qtd") or 0)
        valor = float((f.get("valor") or "0").replace(".", "").replace(",", ".")) if "," in (f.get("valor") or "") else float(f.get("valor") or 0)
    except ValueError:
        qtd, valor = 0, 0
    if not 1 <= qtd <= 100:
        flash("Quantidade de vídeos deve ser de 1 a 100.", "erro")
        return redirect(url_for("cliente", cid=cid))
    agente = cadastro.q("select * from agentes where id=?", (int(f.get("agente") or 0),), um=True) or cadastro.q("select * from agentes order by id limit 1", um=True)
    vid = cadastro.exe("insert into vendas(cliente_id,qtd,valor,pago,data,obs) values(?,?,?,?,?,?)",
                       (cid, qtd, valor, 1 if f.get("pago") else 0, time.time(), f.get("obs", "")))
    pid = pedidos.novo(c["nome"], c["whatsapp"], f.get("nicho") or c["nicho"] or "todos", qtd,
                       cliente_id=cid, sessao=agente["sessao"], venda_id=vid)
    cadastro.exe("update vendas set pedido_id=? where id=?", (pid, vid))
    flash(f"Venda registrada! O robô {agente['apelido']} vai mandar {qtd} vídeos para {c['nome']}.", "ok")
    return redirect(url_for("cliente", cid=cid))


@app.route("/vendas/<int:vid>/pago", methods=["POST"])
@logado
def venda_pago(vid):
    v = cadastro.q("select * from vendas where id=?", (vid,), um=True) or abort(404)
    cadastro.exe("update vendas set pago=? where id=?", (0 if v["pago"] else 1, vid))
    return redirect(request.referrer or url_for("geral"))


@app.route("/pedidos/<int:pid>/cancelar", methods=["POST"])
@logado
def pedido_cancelar(pid):
    pedidos.atualizar(pid, status="cancelado")
    estoque.devolver(pid)
    flash("Pedido cancelado. Os vídeos não enviados voltaram para o estoque.", "ok")
    return redirect(request.referrer or url_for("pedidos_pg"))


@app.route("/pedidos/<int:pid>/reenviar", methods=["POST"])
@logado
def pedido_reenviar(pid):
    pedidos.atualizar(pid, status="pendente", erro="")
    flash("Pedido voltou para a fila.", "ok")
    return redirect(request.referrer or url_for("pedidos_pg"))


@app.route("/pedidos")
@logado
def pedidos_pg():
    return render_template("pedidos.html", aba="pedidos", pedidos=pedidos.lista(100))


# ------------------------------------------------------------------ agentes (robôs de WhatsApp)
@app.route("/agentes", methods=["GET", "POST"])
@logado
def agentes():
    if request.method == "POST":
        apelido = request.form.get("apelido", "").strip() or "Novo agente"
        sessao = "ag" + secrets.token_hex(3)
        cadastro.exe("insert into agentes(apelido,sessao,criado) values(?,?,?)", (apelido, sessao, time.time()))
        wa_post("/iniciar", {"sessao": sessao})
        flash("Agente criado. Escaneie o QR Code com o WhatsApp do novo número.", "ok")
        return redirect(url_for("agentes"))
    sess = wa_get("/sessoes")
    return render_template("agentes.html", aba="agentes", agentes=cadastro.q("select * from agentes order by id"), sess=sess or {}, bot_ok=sess is not None)


@app.route("/agentes/<int:aid>/qr.png")
@logado
def agente_qr(aid):
    a = cadastro.q("select * from agentes where id=?", (aid,), um=True) or abort(404)
    try:
        with urllib.request.urlopen(f"{WA}/qr.png?sessao={a['sessao']}", timeout=5) as r:
            return Response(r.read(), mimetype="image/png", headers={"Cache-Control": "no-store"})
    except Exception:
        abort(404)


@app.route("/agentes/<int:aid>/status")
@logado
def agente_status(aid):
    a = cadastro.q("select * from agentes where id=?", (aid,), um=True) or abort(404)
    st = wa_get(f"/status?sessao={a['sessao']}") or {}
    return {"status": st.get("status"), "rotulo": ROTULO_STATUS.get(st.get("status"), st.get("status")), "qr": st.get("temQR", False)}


@app.route("/agentes/<int:aid>/ligar", methods=["POST"])
@logado
def agente_ligar(aid):
    a = cadastro.q("select * from agentes where id=?", (aid,), um=True) or abort(404)
    wa_post("/iniciar", {"sessao": a["sessao"]})
    return redirect(url_for("agentes"))


@app.route("/agentes/<int:aid>/desconectar", methods=["POST"])
@logado
def agente_desconectar(aid):
    a = cadastro.q("select * from agentes where id=?", (aid,), um=True) or abort(404)
    wa_post("/sair", {"sessao": a["sessao"]})
    flash("Agente desconectado do WhatsApp.", "ok")
    return redirect(url_for("agentes"))


@app.route("/agentes/<int:aid>/remover", methods=["POST"])
@logado
def agente_remover(aid):
    if cadastro.q("select count(*) n from agentes", um=True)["n"] <= 1:
        flash("Precisa ficar pelo menos um agente.", "erro")
        return redirect(url_for("agentes"))
    a = cadastro.q("select * from agentes where id=?", (aid,), um=True) or abort(404)
    wa_post("/sair", {"sessao": a["sessao"]})
    cadastro.exe("delete from agentes where id=?", (aid,))
    flash("Agente removido.", "ok")
    return redirect(url_for("agentes"))


# ------------------------------------------------------------------ estoque
@app.route("/estoque", methods=["GET", "POST"])
@logado
def estoque_pg():
    if request.method == "POST":
        try:
            cadastro.set_config("estoque_alvo", max(0, min(200, int(request.form.get("alvo") or 20))))
            flash("Tamanho do estoque salvo.", "ok")
        except ValueError:
            flash("Número inválido.", "erro")
        return redirect(url_for("estoque_pg"))
    c = estoque.banco()
    ult = [dict(r) for r in c.execute("select * from videos order by id desc limit 30")]
    c.close()
    return render_template("estoque.html", aba="estoque", est=estoque.contar(), alvo=cadastro.get_config("estoque_alvo"), ultimos=ult)


# ------------------------------------------------------------------ configurações (preços, pack diário, senha)
@app.route("/config", methods=["GET", "POST"])
@logado
def config():
    if request.method == "POST":
        f = request.form
        if f.get("acao") == "precos":
            for p in cadastro.q("select * from precos"):
                try:
                    qtd = int(f.get(f"qtd{p['id']}") or p["qtd"])
                    txt = (f.get(f"valor{p['id']}") or "0").replace("R$", "").strip()
                    valor = float(txt.replace(".", "").replace(",", ".")) if "," in txt else float(txt or 0)
                    cadastro.exe("update precos set nome=?,qtd=?,valor=? where id=?", (f.get(f"nome{p['id']}") or p["nome"], qtd, valor, p["id"]))
                except ValueError:
                    flash(f"Valor inválido no preço {p['id']}.", "erro")
            flash("Preços salvos.", "ok")
        elif f.get("acao") == "diario":
            cadastro.set_config("diario_ativo", "1" if f.get("ativo") else "0")
            cadastro.set_config("diario_hora", f.get("hora") or "07:00")
            cadastro.set_config("diario_qtd", max(1, min(30, int(f.get("qtd") or 10))))
            cadastro.set_config("diario_nicho", f.get("nicho") or "todos")
            flash("Pack diário salvo.", "ok")
        elif f.get("acao") == "senha":
            if not confere(f.get("atual", ""), cadastro.get_config("senha_hash")):
                flash("Senha atual incorreta.", "erro")
            elif len(f.get("nova", "")) < 6:
                flash("A nova senha precisa ter 6 caracteres ou mais.", "erro")
            else:
                cadastro.set_config("senha_hash", hash_senha(f["nova"]))
                flash("Senha trocada.", "ok")
        return redirect(url_for("config"))
    cfgs = {k: cadastro.get_config(k) for k in ("diario_ativo", "diario_hora", "diario_qtd", "diario_nicho")}
    return render_template("config.html", aba="config", precos=cadastro.q("select * from precos order by id"), c=cfgs)


@app.route("/api/precos")
@logado
def api_precos():
    return {"precos": cadastro.q("select * from precos order by id")}


if __name__ == "__main__":
    from waitress import serve
    porta = int(os.environ.get("SITE_PORTA", "5055"))
    host = os.environ.get("SITE_HOST", "0.0.0.0")  # 0.0.0.0 = abre também no celular pelo Wi-Fi de casa
    print(f"Painel IA Shopee em http://127.0.0.1:{porta}")
    serve(app, host=host, port=porta, threads=8)
