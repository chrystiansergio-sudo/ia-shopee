"""5 vídeos com o PREÇO primeiro (maquiagem, beleza, saúde, cachorro, mulher) e manda no WhatsApp do dono."""
import os, sys, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video2, wa, trabalhador
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "pack_preco")
os.makedirs(SAIDA, exist_ok=True)
NUM = os.environ.get("DONO_WHATSAPP", "")
FEM = ("feminin", "mulher", "vestido", "brinco", "colar", "bolsa", "saia", "blusa", "cropped", "sandália", "sandalia")
PLANO = [("mulher", "maquiagem", None), ("produto", "beleza", None), ("homem", "saude", None),
         ("cachorro", "pet", ("cachorro", "cão", "cao", "dog", "pet")), ("mulher", "moda", FEM)]
BUSCAS_FEM = ["bolsa feminina", "vestido feminino", "brinco feminino", "sandalia feminina", "blusa feminina", "colar feminino"]
evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
usados, feitos = set(), []
SO_GERAR = "--sem-envio" in sys.argv
SO = [int(x) for x in sys.argv[sys.argv.index("--so") + 1].split(",")] if "--so" in sys.argv else None
FORA = ("fadvan", "colar de cordas", "pulseira")
for i, (fmt, nicho, filtro) in enumerate(PLANO, 1):
    if SO and i not in SO:
        continue
    try:
        if nicho == "moda":
            ps = peneira.escolher("dono-pack-v2", nicho, 12, palavras=BUSCAS_FEM, proibir=("masculin", "homem"))
        else:
            ps = peneira.escolher("dono-pack-v2", nicho, 12)
        ps = [p for p in ps if p["item_id"] not in usados and not any(x in p["title"].lower() for x in FORA)]
        if filtro:
            ps = [p for p in ps if any(f in p["title"].lower() for f in filtro)] or ps
        p = ps[0]
        usados.add(p["item_id"])
        arq = os.path.join(SAIDA, f"{i:02d}_{fmt}_{nicho}.mp4")
        t = time.time()
        info = video2.fazer(p, nicho, arq, formato=fmt, evitar=evitar)
        rot = "mulher" if nicho == "moda" else nicho
        msg = (f"🎬 *Vídeo {i}/5* — {fmt.upper()} · {rot}\n\n"
               f"📋 *Legenda pronta (copie):*\n{info['legenda']}\n\n🔗 *Produto para marcar:*\n{p.get('link') or p.get('product_link')}")
        open(arq[:-4] + ".txt", "w", encoding="utf-8").write(msg)
        feitos.append((arq, msg))
        print(f"OK {i} {fmt} {nicho} {time.time()-t:.0f}s | {p['title'][:60]} | abre: {info['roteiro']['abre']} | {info['usados']} | apres={info['apresentador_ok']}", flush=True)
    except Exception as e:
        print(f"ERRO {i} {fmt} {nicho}: {e}", flush=True)
        traceback.print_exc()
if SO_GERAR:
    sys.exit()
try:
    wa.texto("dono", NUM, f"Aqui estão os *{len(feitos)} vídeos novos* com o *preço logo no início* 💰\n"
                          "(o preço é a primeira fala e aparece numa etiqueta grande desde o 1º segundo)\n\nVão chegar um por um 👇")
    for arq, msg in feitos:
        wa.video("dono", NUM, arq, msg)
        print("enviado", os.path.basename(arq), flush=True)
except Exception as e:
    print("ERRO envio", e)
