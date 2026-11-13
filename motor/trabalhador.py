"""Trabalhador: pega pedidos da fila, faz os vídeos e manda no WhatsApp do cliente.

  python trabalhador.py            -> fica rodando (servidor)
  python trabalhador.py --uma-vez  -> processa a fila e sai
  python trabalhador.py --sem-envio -> só gera os vídeos (teste no computador)
"""
import json
import os
import shutil
import sys
import time
import traceback

import pedidos
import peneira
import video
import wa
from peneira import RAIZ, cfg

SAIDA = os.path.join(RAIZ, "saida")
DIAS_GUARDAR = 7

DICAS = ("✅ *Pack completo!*\n\n"
         "Como postar cada vídeo:\n"
         "1️⃣ Salve o vídeo no celular\n"
         "2️⃣ No Shopee Vídeo, envie o vídeo e cole a legenda pronta\n"
         "3️⃣ Marque o produto (use o link enviado junto)\n"
         "4️⃣ Ative a opção *conteúdo gerado por IA*\n\n"
         "Dica: poste espalhado ao longo do dia, não todos de uma vez. 🚀")


def log(*a):
    print(time.strftime("%d/%m %H:%M:%S"), *a, flush=True)


def baixa_prioridade():
    try:
        os.nice(19)  # Linux: não atrapalha os outros programas do servidor
    except (AttributeError, OSError):
        pass


def limpar_antigos():
    if not os.path.isdir(SAIDA):
        return
    lim = time.time() - DIAS_GUARDAR * 86400
    for d in os.listdir(SAIDA):
        p = os.path.join(SAIDA, d)
        if d.startswith("pedido_") and os.path.isdir(p) and os.path.getmtime(p) < lim:
            shutil.rmtree(p, ignore_errors=True)


def mensagem(i, qtd, info, p, robo):
    link = p["link"] if robo.get("tipo_link") == "afiliado" and p.get("link") else (p.get("product_link") or p.get("link"))
    return (f"🎬 *Vídeo {i}/{qtd}*\n\n"
            f"📋 *Legenda pronta (copie):*\n{info['legenda']}\n\n"
            f"🔗 *Produto para marcar:*\n{link}")


def processar(ped, enviar=True):
    pid, qtd = ped["id"], ped["qtd"]
    robo = cfg("robos")[ped["robo"]]
    sessao = robo["whatsapp_sessao"]
    pasta = os.path.join(SAIDA, f"pedido_{pid}")
    os.makedirs(pasta, exist_ok=True)
    mpath = os.path.join(pasta, "pack.json")
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {"videos": [], "intro": False}

    def salvar():
        json.dump(man, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if enviar:
        st = wa.status(sessao)
        if st.get("status") != "conectado":
            pedidos.atualizar(pid, status="pendente", erro=f"WhatsApp '{sessao}' não conectado")
            log(f"pedido {pid}: WhatsApp não conectado, tento depois")
            return False
    pedidos.atualizar(pid, status="fazendo", erro="")
    if enviar and not man["intro"]:
        wa.texto(sessao, ped["whatsapp"], f"Olá, {ped['cliente']}! 🎬\nSeu pack de *{qtd} vídeos* ({ped['nicho']}) está sendo preparado. "
                                          f"Os vídeos vão chegar aqui um por um. 🚀")
        man["intro"] = True
        salvar()

    feitos = [v for v in man["videos"] if v.get("ok")]
    tentativas = 0
    while len(feitos) < qtd and tentativas < 4:
        tentativas += 1
        falta = qtd - len(feitos)
        ja = {v["item_id"] for v in man["videos"]}
        prods = [p for p in peneira.escolher(ped["cliente"], ped["nicho"], falta + 3, ped["robo"]) if p["item_id"] not in ja]
        if not prods:
            break
        clipes_usados = [v.get("clipe") for v in man["videos"] if v.get("clipe")]
        for p in prods:
            if len(feitos) >= qtd:
                break
            n = len(feitos) + 1
            arq = os.path.join(pasta, f"{n:03d}.mp4")
            reg = {"item_id": p["item_id"], "titulo": p["title"], "ok": False}
            man["videos"].append(reg)
            try:
                t = time.time()
                ult_estilos = [v.get("estilo") for v in feitos[-2:]]
                info = video.fazer(p, ped["nicho"], arq, evitar_clipes=clipes_usados[-6:], evitar_estilos=ult_estilos)
                reg.update(ok=True, arquivo=arq, clipe=info["clipe"], estilo=info["roteiro"]["estilo"], legenda=info["legenda"],
                           link=p.get("link"), product_link=p.get("product_link"), enviado=False)
                clipes_usados.append(info["clipe"])
                feitos.append(reg)
                peneira.marcar(ped["cliente"], [p])
                log(f"pedido {pid}: vídeo {n}/{qtd} pronto em {time.time() - t:.0f}s ({info['roteiro']['estilo']})")
                open(arq[:-4] + ".txt", "w", encoding="utf-8").write(mensagem(n, qtd, info, p, robo))
                if enviar:
                    wa.video(sessao, ped["whatsapp"], arq, mensagem(n, qtd, info, p, robo))
                    reg["enviado"] = True
                pedidos.atualizar(pid, feitos=len(feitos), enviados=sum(1 for v in feitos if v.get("enviado")))
            except Exception as e:
                reg["erro"] = str(e)[:300]
                log(f"pedido {pid}: erro no produto {p['item_id']}: {e}")
                traceback.print_exc()
            salvar()

    if len(feitos) < qtd:
        pedidos.atualizar(pid, status="incompleto", erro=f"só achei {len(feitos)} produtos bons para esse nicho")
    else:
        pedidos.atualizar(pid, status="enviado" if enviar else "pronto")
    if enviar:
        wa.texto(sessao, ped["whatsapp"], DICAS)
    log(f"pedido {pid}: concluído ({len(feitos)}/{qtd})")
    return True


def main():
    baixa_prioridade()
    enviar = "--sem-envio" not in sys.argv
    uma_vez = "--uma-vez" in sys.argv or not enviar
    log("trabalhador iniciado", "(sem envio)" if not enviar else "")
    while True:
        limpar_antigos()
        ped = pedidos.proximo()
        if ped:
            try:
                ok = processar(ped, enviar)
                if not ok:
                    time.sleep(60)
            except Exception as e:
                log("erro geral", e)
                traceback.print_exc()
                pedidos.atualizar(ped["id"], status="pendente", erro=str(e)[:200])
                time.sleep(60)
        elif uma_vez:
            break
        else:
            time.sleep(20)


if __name__ == "__main__":
    main()
