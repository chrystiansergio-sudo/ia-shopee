"""Manda o vídeo N do teste IA-10 no WhatsApp do dono: vídeo, legenda, link de afiliado e nome do produto (cada um separado)."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, wa
NUM = os.environ.get("DONO_WHATSAPP", "")
SAIDA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "ia10"))
n = int(sys.argv[1])
arq = os.path.join(SAIDA, f"{n:02d}.mp4")
d = json.load(open(arq[:-4] + ".json", encoding="utf-8"))
wa.video("dono", NUM, arq, f"🎬 *Teste IA {n}/10*\n⬇️ Abaixo: legenda, link e nome do produto")
for txt in (d["legenda"], d["link"], d["nome"]):
    time.sleep(2)
    wa.texto("dono", NUM, txt)
peneira.marcar("dono-ia10", [{"item_id": d["item_id"], "title": d["nome"]}])
print("enviado", n)
