"""Trabalhador v2 (fica rodando):
1. atende os pedidos (vendas do site e o pack diário do dono) usando o ESTOQUE de vídeos;
2. troca o link de cada vídeo pelo link de afiliado do cliente (API dele) e manda no WhatsApp;
3. nas horas vagas, fabrica vídeos para manter o estoque cheio.
"""
import os
import sys
import time
import traceback
from datetime import datetime

import cadastro
import estoque
import pedidos
import peneira
import shopee
import wa

DICAS = ("✅ *Pack completo!*\n\nComo postar cada vídeo:\n1️⃣ Salve o vídeo no celular\n"
         "2️⃣ No Shopee Vídeo, envie o vídeo e cole a legenda pronta\n3️⃣ Em *Adicionar produto*, pesquise pelo *nome do produto* (a última mensagem de cada vídeo)\n"
         "4️⃣ Ative a opção *conteúdo gerado por IA*\n\nDica: poste espalhado ao longo do dia, não todos de uma vez. 🚀")
MAX_SOB_DEMANDA = 60  # limite de vídeos fabricados na hora para um pedido


def log(*a):
    print(datetime.now().strftime("%d/%m %H:%M:%S"), *a, flush=True)


def link_do_cliente(v, cli):
    """link de afiliado do cliente (se ele cadastrou a API); senão o link normal do produto"""
    if cli and cli.get("app_id") and cli.get("secret") and v.get("product_link"):
        for _ in range(2):
            try:
                return shopee.short_link(cli["app_id"], cli["secret"], v["product_link"], sub_id="iashopee")
            except Exception as e:
                log("  aviso link afiliado:", e)
                time.sleep(2)
    if cli and cli.get("dono") and v.get("link_dono"):
        return v["link_dono"]
    return v.get("product_link") or v.get("link_dono") or ""


def atender(ped):
    pid, qtd = ped["id"], ped["qtd"]
    sessao = ped.get("sessao") or "dono"
    cli = cadastro.cliente(ped["cliente_id"]) if ped.get("cliente_id") else None
    try:
        st = wa.status(sessao).get("status")
    except Exception as e:
        st = f"bot fora do ar ({e})"
    if st != "conectado":
        pedidos.atualizar(pid, status="pendente", erro=f"WhatsApp do agente '{sessao}' não está conectado")
        log(f"pedido {pid}: agente {sessao} desconectado; tento depois")
        return False
    pedidos.atualizar(pid, status="fazendo", erro="")
    ja = estoque.reservados(pid)
    if not ja:
        estoque.reservar(qtd, ped["nicho"], ped["cliente"], pid)
        ja = estoque.reservados(pid)
    # faltou no estoque: fabrica na hora
    feitos_agora = 0
    evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
    while len(ja) < qtd and feitos_agora < MAX_SOB_DEMANDA:
        nicho = ped["nicho"] if ped["nicho"] not in ("todos", "", None) else None
        try:
            if nicho:
                vid = estoque.fabricar(nicho, None, evitar)
            else:
                n, f = estoque.proximo_plano()
                vid = estoque.fabricar(n, f, evitar)
        except Exception as e:
            log(f"pedido {pid}: erro fabricando: {e}")
            traceback.print_exc()
            vid = None
        feitos_agora += 1
        if vid:
            estoque.reservar(qtd - len(ja), ped["nicho"], ped["cliente"], pid)
            ja = estoque.reservados(pid)
            pedidos.atualizar(pid, feitos=len(ja))
    enviados = sum(1 for v in ja if v["status"] == "enviado")
    if enviados == 0:
        wa.texto(sessao, ped["whatsapp"], f"Olá, {ped['cliente']}! 🎬\nSeu pack de *{qtd} vídeos* está chegando. Os vídeos vêm um por um. 🚀")
    for i, v in enumerate(ja, 1):
        if v["status"] == "enviado":
            continue
        link = link_do_cliente(v, cli)
        # tudo separado, para copiar fácil: vídeo → legenda → link → nome do produto (para achar na Shopee)
        try:
            wa.video(sessao, ped["whatsapp"], v["arquivo"],
                     f"🎬 *Vídeo {i}/{qtd}*\n⬇️ Abaixo: legenda, link e nome do produto (cada um separado)")
            for txt in (v["legenda"], link, (v.get("titulo") or "").strip()):
                if txt:
                    time.sleep(2)
                    wa.texto(sessao, ped["whatsapp"], txt)
            estoque.marcar_enviado(v["id"])
            peneira.marcar(ped["cliente"], [{"item_id": v["item_id"], "title": v["titulo"]}])
            enviados += 1
            pedidos.atualizar(pid, feitos=len(ja), enviados=enviados)
        except Exception as e:
            log(f"pedido {pid}: erro enviando vídeo {v['id']}: {e}")
            pedidos.atualizar(pid, status="pendente", erro=f"erro no envio: {e}"[:200])
            return False
    wa.texto(sessao, ped["whatsapp"], DICAS)
    pedidos.atualizar(pid, status="enviado" if enviados >= qtd else "incompleto",
                      erro="" if enviados >= qtd else f"só consegui {enviados} vídeos")
    log(f"pedido {pid}: concluído {enviados}/{qtd}")
    return True


def pack_diario():
    """cria (uma vez por dia, no horário) o pedido do dono"""
    if cadastro.get_config("diario_ativo") != "1":
        return
    hoje = datetime.now().strftime("%Y-%m-%d")
    if cadastro.get_config("diario_ultimo") == hoje:
        return
    if datetime.now().strftime("%H:%M") < (cadastro.get_config("diario_hora") or "07:00"):
        return
    dono = cadastro.cliente_dono()
    ag = cadastro.q("select sessao from agentes order by id limit 1", um=True)
    pedidos.novo(dono["nome"], dono["whatsapp"], cadastro.get_config("diario_nicho") or "todos",
                 int(cadastro.get_config("diario_qtd") or 10), cliente_id=dono["id"], sessao=(ag or {}).get("sessao", "dono"))
    cadastro.set_config("diario_ultimo", hoje)
    log("pack diário do dono criado")


def main():
    try:
        os.nice(19)
    except (AttributeError, OSError):
        pass
    log("trabalhador v2 iniciado")
    while True:
        try:
            estoque.limpar_vencidos()
            pack_diario()
            ped = pedidos.proximo()
            if ped:
                if not atender(ped):
                    time.sleep(60)
                continue
            alvo = int(cadastro.get_config("estoque_alvo") or 20)
            if estoque.contar()["disponiveis"] < alvo:
                t = time.time()
                vid = estoque.fabricar()
                log(f"estoque: vídeo {vid} fabricado em {time.time() - t:.0f}s ({estoque.contar()['disponiveis']}/{alvo})")
                continue
        except Exception as e:
            log("erro geral:", e)
            traceback.print_exc()
            time.sleep(60)
        if "--uma-vez" in sys.argv:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
