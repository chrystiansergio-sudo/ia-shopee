"""Gera 10 vídeos v2 (nichos e formatos diferentes) e manda no WhatsApp do dono."""
import os, sys, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video2, wa, trabalhador
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "pack_v2")
os.makedirs(SAIDA, exist_ok=True)
NUM = os.environ.get("DONO_WHATSAPP", "")
PLANO = [("mulher", "beleza"), ("homem", "eletronicos"), ("cachorro", "pet"), ("produto", "casa e cozinha"), ("narrado", "organizacao"),
         ("mulher", "moda"), ("homem", "carro"), ("cachorro", "pet"), ("produto", "fitness"), ("narrado", "casa e decoracao")]
evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
usados = set()
feitos = []
for i, (fmt, nicho) in enumerate(PLANO, 1):
    try:
        ps = [p for p in peneira.escolher("dono-pack-v2", nicho, 4) if p["item_id"] not in usados]
        p = ps[0]
        usados.add(p["item_id"])
        arq = os.path.join(SAIDA, f"{i:02d}_{fmt}_{nicho.replace(' ', '_')}.mp4")
        t = time.time()
        info = video2.fazer(p, nicho, arq, formato=fmt, evitar=evitar)
        msg = (f"🎬 *Vídeo {i}/10* — {fmt.upper()} · {nicho}\n\n"
               f"📋 *Legenda pronta (copie):*\n{info['legenda']}\n\n🔗 *Produto para marcar:*\n{p.get('link') or p.get('product_link')}")
        open(arq[:-4] + ".txt", "w", encoding="utf-8").write(msg)
        feitos.append((arq, msg))
        print(f"OK {i} {fmt} {nicho} {time.time()-t:.0f}s | {p['title'][:50]} | {info['usados']}", flush=True)
    except Exception as e:
        print(f"ERRO {i} {fmt} {nicho}: {e}", flush=True)
        traceback.print_exc()
# envio no WhatsApp
try:
    wa.texto("dono", NUM, f"☀️ Bom dia! Aqui estão os *{len(feitos)} vídeos novos* (versão 2):\n"
                          "• produto SEMPRE com a foto real (sem IA mexendo)\n• fundo com filmagens reais\n"
                          "• apresentadores de IA com a boca sincronizada (o homem fala com a SUA voz)\n• antes e depois do preço\n\nVão chegar um por um 👇")
    for arq, msg in feitos:
        wa.video("dono", NUM, arq, msg)
        print("enviado", os.path.basename(arq), flush=True)
    wa.texto("dono", NUM, trabalhador.DICAS)
except Exception as e:
    print("ERRO envio", e)
