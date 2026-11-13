"""Vídeo melhorado na PLACA (RunPod): produto REAL na cena (Qwen-Image-Edit-2509) + animação Wan 2.2 14B.
Sem nada escrito, sem preço, ninguém olhando pra câmera (sem boca fora de sincronia), mesma cena/pessoa, transição suave.
Uso: python ia_gpu.py roteiro.json   (o json tem: produto{title,image_url,link,item_id}, nome, fala, cenas[5], legenda, hashtags, genero)"""
import json, os, random, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import numpy as np
import audio, falas, video2
from video2 import sh
import gpu_comfy as G

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.abspath(os.path.join(AQUI, "..", "saida", "ia_gpu"))
os.makedirs(SAIDA, exist_ok=True)


def fazer(arq_json):
    R = json.load(open(arq_json, encoding="utf-8"))
    p = R["produto"]
    nome_saida = os.path.splitext(os.path.basename(arq_json))[0].replace("roteiro_", "")
    pasta = os.path.join(SAIDA, "_tmp_" + nome_saida)
    shutil.rmtree(pasta, ignore_errors=True); os.makedirs(pasta, exist_ok=True)
    img = os.path.join(pasta, "prod.jpg")
    video2.baixar(p["image_url"], img)

    # voz (narração)
    wv = os.path.join(pasta, "fala.wav")
    voz = random.choice(video2.vozmod.VOZES[R.get("genero", "f")])
    pal, dur = falas.edge(R["fala"], wv, voz)
    t0 = .15
    D = round(t0 + dur + .6, 2)

    regra = (" The person is seen from the side, from behind or from the chest down, never facing the camera. "
             "Keep the product exactly identical to the reference photo: same shape, number of parts, colors and design. "
             "The product is big and clearly visible. Realistic photo, vertical frame, no text, no logos, no children.")
    base = os.path.join(pasta, "cena0.png")
    G.editar([img], R["cenas"][0] + regra, base)
    n_cenas = min(len(R["cenas"]), max(3, int((D + .5) / 4.5) + 1))
    clipes = []
    for k in range(n_cenas):
        foto = base if k == 0 else os.path.join(pasta, f"cena{k}.png")
        if k > 0:
            G.editar([base, img], "Using the same place, same person and same clothes as image 1 and the exact product from image 2. New shot: "
                     + R["cenas"][k] + regra, foto)
        c = os.path.join(pasta, f"clipe{k}.mp4")
        G.animar(foto, R["cenas"][k] + " Slow, smooth, natural movement; steady camera with a gentle slow push-in. "
                 "The person keeps the mouth closed. The product stays exactly identical.", c,
                 neg=G.NEG_WAN + (", person, people, hands" if "no people" in R["cenas"][k].lower() else ""))
        clipes.append(c)

    # junta: 720x1280 30fps, transição suave de 0,5 s
    partes = []
    for n, c in enumerate(clipes):
        s = os.path.join(pasta, f"s{n}.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", c, "-an", "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase:flags=lanczos,crop=720:1280,fps=30,setsar=1,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", s])
        partes.append(s)
    durs = [float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", s]).strip()) for s in partes]
    F, ent, filt, ant, off = .5, [], "", "[0:v]", 0.0
    for s in partes:
        ent += ["-i", s]
    for n in range(1, len(partes)):
        off += durs[n - 1] - F
        filt += f"{ant}[{n}:v]xfade=transition=fade:duration={F}:offset={off:.3f}[x{n}];"
        ant = f"[x{n}]"
    total = sum(durs) - F * (len(partes) - 1)
    filt += f"{ant}tpad=stop_mode=clone:stop_duration={max(0, D - total) + .2:.2f}[v]"
    fg = os.path.join(pasta, "fg.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", *ent, "-filter_complex", filt, "-map", "[v]", "-t", f"{D:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", fg])

    # áudio: voz + música baixinha
    N = int(D * audio.SR)
    vb = np.zeros((N, 2)); audio._soma(vb, video2.ler_wav(wv), t0)
    mus = audio.musica(D, {"bpm": random.choice([96, 104, 112]), "partes": [(0, D, {"kick", "hat", "baixo", "pluck"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    mix = vb + mus * .08
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    f = int(.3 * audio.SR); mix[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = os.path.join(pasta, "mix.wav"); video2.gravar_wav(wav, mix)

    out = os.path.join(SAIDA, f"{nome_saida}.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", fg, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out])
    legenda = R["legenda"].strip() + "\n\nPubli · conteúdo feito com IA\n" + " ".join(R["hashtags"][:5])
    json.dump({"legenda": legenda, "link": p["link"], "nome": p["title"], "item_id": p["item_id"]},
              open(out[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-vf", "fps=1,scale=200:-1,tile=8x3", "-frames:v", "1", out[:-4] + "_tira.jpg"])
    print("OK", out, D, "s", flush=True)


if __name__ == "__main__":
    fazer(sys.argv[1])
