"""10 vídeos no formato antigo (foto real + preço + voz grátis), com busca ATUALIZADA na Shopee (preço de agora),
para os Stories do Instagram. Manda cada um no WhatsApp assim que fica pronto: vídeo, legenda, link, nome (separados).
Uso: python gerar_insta.py [qtd] [lote]"""
import os, sys, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video2, wa
QTD = int(sys.argv[1]) if len(sys.argv) > 1 else 10
LOTE = sys.argv[2] if len(sys.argv) > 2 else time.strftime("%d%m_%H%M")
NUM = os.environ.get("DONO_WHATSAPP", "")
SAIDA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "insta_" + LOTE))
os.makedirs(SAIDA, exist_ok=True)
CLIENTE = "dono-instagram"  # não repete produto já mandado nesse canal
evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
ps = peneira.escolher(CLIENTE, "todos", QTD + 4)
feitos = 0
for p in ps:
    if feitos >= QTD:
        break
    i = feitos + 1
    arq = os.path.join(SAIDA, f"{i:02d}.mp4")
    try:
        t = time.time()
        info = video2.fazer(p, p.get("palavra") or "todos", arq, formato="cena", evitar=evitar, genero="fm"[i % 2])
        wa.video("dono", NUM, arq, f"🎬 *Vídeo {i}/{QTD}* — preço de agora\n⬇️ Abaixo: legenda, link e nome do produto")
        for txt in (info["legenda"], p.get("link") or p.get("product_link"), p["title"]):
            time.sleep(2); wa.texto("dono", NUM, txt)
        peneira.marcar(CLIENTE, [p])
        feitos += 1
        print(f"ENVIADO {i}/{QTD} em {time.time() - t:.0f}s | R$ {p['price']:.2f} | {p['title'][:60]}", flush=True)
    except Exception as e:
        print("ERRO", p.get("title", "")[:50], e, flush=True); traceback.print_exc()
print("FIM", feitos, flush=True)
