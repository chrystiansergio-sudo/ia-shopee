"""1 vídeo de teste com fundo = foto do produto sombreada + legenda nova. NÃO manda no WhatsApp."""
import os, sys, time, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import peneira, video2
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "saida", "teste_fundo_foto")
os.makedirs(SAIDA, exist_ok=True)
p = peneira.escolher("dono-teste-fundo", "casa e cozinha", 3)[0]
arq = os.path.join(SAIDA, "teste.mp4")
t = time.time()
info = video2.fazer(p, "casa e cozinha", arq, formato="cena", genero="f")
open(arq[:-4] + ".txt", "w", encoding="utf-8").write(info["legenda"])
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "4", "-i", arq, "-frames:v", "1", arq[:-4] + "_quadro.jpg"])
print(f"OK {time.time()-t:.0f}s | {p['title'][:70]}")
print(info["legenda"])
