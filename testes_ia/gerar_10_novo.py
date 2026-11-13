"""10 vídeos no formato aprovado (sem IA falando; preço primeiro; produto real grande). Manda cada um assim que fica pronto."""
import os, sys, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video2, wa, trabalhador
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "pack_novo")
os.makedirs(SAIDA, exist_ok=True)
NUM = os.environ.get("DONO_WHATSAPP", "")
FEM = ["bolsa feminina", "vestido feminino", "sandalia feminina", "blusa feminina", "brinco feminino"]
PLANO = [("cena", "maquiagem"), ("narrado", "casa e cozinha"), ("cachorro", "pet"), ("cena", "beleza"), ("narrado", "saude"),
         ("cena", "fitness"), ("narrado", "organizacao"), ("cachorro", "pet"), ("cena", "moda"), ("narrado", "casa e decoracao")]
evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
usados, n = set(), 0
wa.texto("dono", NUM, "🎬 Começando os *10 vídeos no formato novo* (sem IA falando, preço logo no início, produto real grande).\nCada um chega assim que ficar pronto 👇")
for i, (fmt, nicho) in enumerate(PLANO, 1):
    for tent in range(2):
        try:
            if nicho == "moda":
                ps = peneira.escolher("dono-pack-v2", nicho, 10, palavras=FEM, proibir=("masculin", "homem"))
            else:
                ps = peneira.escolher("dono-pack-v2", nicho, 10)
            ps = [p for p in ps if p["item_id"] not in usados]
            if fmt == "cachorro":
                ps = [p for p in ps if any(w in p["title"].lower() for w in ("cachorro", "cão", "cao", "pet", "dog"))] or ps
            p = ps[0]
            usados.add(p["item_id"])
            arq = os.path.join(SAIDA, f"{i:02d}_{fmt}_{nicho.replace(' ', '_')}.mp4")
            t = time.time()
            info = video2.fazer(p, nicho, arq, formato=fmt, evitar=evitar)
            msg = (f"🎬 *Vídeo {i}/10* — {nicho}\n\n📋 *Legenda pronta (copie):*\n{info['legenda']}\n\n"
                   f"🔗 *Produto para marcar:*\n{p.get('link') or p.get('product_link')}")
            open(arq[:-4] + ".txt", "w", encoding="utf-8").write(msg)
            wa.video("dono", NUM, arq, msg)
            peneira.marcar("dono-pack-v2", [p])
            n += 1
            print(f"OK+ENVIADO {i} {fmt} {nicho} {time.time()-t:.0f}s | {p['title'][:60]}", flush=True)
            break
        except Exception as e:
            print(f"ERRO {i} {fmt} {nicho} tentativa {tent+1}: {e}", flush=True)
            traceback.print_exc()
wa.texto("dono", NUM, f"✅ Pronto: {n} de 10 vídeos enviados.\n\n" + trabalhador.DICAS)
