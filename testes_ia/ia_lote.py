"""Lote: por produto, faz 6 cenas de IA UMA vez (na placa) e monta 10 variações (voz, roteiro, ordem, música),
mandando cada uma no WhatsApp assim que fica pronta (vídeo, legenda, link, nome — separados).
Uso: python ia_lote.py cenas <produto>     -> gera as cenas na placa (ComfyUI)
     python ia_lote.py variacoes <produto> [de] [ate]  -> monta e manda"""
import json, os, random, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import numpy as np
import audio, falas, video2, wa, peneira
from video2 import sh

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.abspath(os.path.join(AQUI, "..", "saida", "lote"))
NUM = os.environ.get("DONO_WHATSAPP", "")
FATOS = json.load(open(os.path.join(AQUI, "lote_produtos.json"), encoding="utf-8"))
FECHA = ["Corre, toca no produto aqui embaixo e confere todos os detalhes!", "Toca no produto aqui embaixo e garante o seu!",
         "Vai lá, toca no produto aqui embaixo pra ver mais!", "Clica no produto aqui embaixo antes que acabe!",
         "Confere os detalhes tocando no produto aqui embaixo!"]
REGRA = (" The person is seen from the side, from behind or from the chest down, never facing the camera. "
         "Keep the product exactly identical to the reference photo: same shape, number of parts, colors and design. "
         "The product is big and clearly visible. Realistic photo, vertical frame, no text, no logos, no children.")


def produto(nome):
    if nome == "relogio":
        return json.load(open(os.path.join(AQUI, "roteiro_relogio.json"), encoding="utf-8"))["produto"]
    if nome == "pneu":
        return json.load(open(os.path.join(AQUI, "roteiro_pneu.json"), encoding="utf-8"))["produto"]
    p = json.load(open(os.path.join(AQUI, "ia10_produtos.json"), encoding="utf-8"))[0]
    return {k: p[k] for k in ("title", "image_url", "link", "item_id")}


def cenas(nome):
    import gpu_comfy as G
    pasta = os.path.join(SAIDA, nome); os.makedirs(pasta, exist_ok=True)
    p = produto(nome)
    img = os.path.join(pasta, "prod.jpg")
    if not os.path.exists(img):
        video2.baixar(p["image_url"], img)
    C = FATOS[nome]["cenas"]
    base = os.path.join(pasta, "cena0.png")
    if not os.path.exists(base):
        G.editar([img], C[0] + REGRA, base)
    for k, pr in enumerate(C):
        foto = base if k == 0 else os.path.join(pasta, f"cena{k}.png")
        if k > 0 and not os.path.exists(foto):
            G.editar([base, img], "Using the same place, same person and same clothes as image 1 and the exact product from image 2. New shot: " + pr + REGRA, foto)
        clipe = os.path.join(pasta, f"clipe{k}.mp4")
        if not os.path.exists(clipe):
            G.animar(foto, pr + " Slow, smooth, natural movement; steady camera with a gentle slow push-in. "
                     "The person keeps the mouth closed. The product stays exactly identical.", clipe,
                     neg=G.NEG_WAN + (", person, people, hands" if "no people" in pr.lower() else ""))
    sh(["ffmpeg", "-y", "-loglevel", "error"] + sum([["-i", os.path.join(pasta, f"cena{k}.png")] for k in range(len(C))], []) +
       ["-filter_complex", "".join(f"[{k}]scale=240:-1[s{k}];" for k in range(len(C))) + "".join(f"[s{k}]" for k in range(len(C))) + f"hstack={len(C)}",
        os.path.join(pasta, "_cenas.jpg")])
    print("CENAS OK", nome, flush=True)


def roteiro(nome, v):
    F = FATOS[nome]
    rnd = random.Random(f"{nome}-{v}")
    fatos = F["fatos"][:]; rnd.shuffle(fatos)
    texto = F["ganchos"][v % len(F["ganchos"])] + " " + " ".join(fatos[:3 + (v % 2)]) + " " + FECHA[(v * 3 + 1) % len(FECHA)]
    return texto, F["legendas"][v % len(F["legendas"])] + "\n\nPubli · conteúdo feito com IA\n" + " ".join(F["hashtags"])


def variacao(nome, v):
    pasta = os.path.join(SAIDA, nome)
    clipes = sorted(f for f in os.listdir(pasta) if f.startswith("clipe") and f.endswith(".mp4"))
    tmp = os.path.join(pasta, f"_v{v}"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
    fala, legenda = roteiro(nome, v)
    genero = "fm"[v % 2]
    voz = video2.vozmod.VOZES[genero][(v // 2) % len(video2.vozmod.VOZES[genero])]
    wv = os.path.join(tmp, "fala.wav")
    pal, dur = falas.edge(fala, wv, voz)
    t0 = .15; D = round(t0 + dur + .6, 2)
    rnd = random.Random(f"ordem-{nome}-{v}")
    ordem = clipes[:]; rnd.shuffle(ordem)
    if "clipe0.mp4" in ordem:  # começa com produto em uso, grande
        ordem.remove("clipe0.mp4"); ordem.insert(v % 2, "clipe0.mp4")
    partes, durs, tot, F = [], [], 0.0, .5
    for n, c in enumerate(ordem):
        s = os.path.join(tmp, f"s{n}.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(pasta, c), "-an", "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase:flags=lanczos,crop=720:1280,fps=30,setsar=1,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", s])
        d = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", s]).strip())
        partes.append(s); durs.append(d); tot += d - (F if n else 0)
        if tot >= D:
            break
    ent, filt, ant, off = [], "", "[0:v]", 0.0
    for s in partes:
        ent += ["-i", s]
    for n in range(1, len(partes)):
        off += durs[n - 1] - F
        filt += f"{ant}[{n}:v]xfade=transition=fade:duration={F}:offset={off:.3f}[x{n}];"
        ant = f"[x{n}]"
    filt += f"{ant}tpad=stop_mode=clone:stop_duration={max(0, D - tot) + .2:.2f}[v]"
    fg = os.path.join(tmp, "fg.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", *ent, "-filter_complex", filt, "-map", "[v]", "-t", f"{D:.2f}", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", fg])
    N = int(D * audio.SR)
    vb = np.zeros((N, 2)); audio._soma(vb, video2.ler_wav(wv), t0)
    mus = audio.musica(D, {"bpm": [92, 100, 108, 116][v % 4], "partes": [(0, D, {"kick", "hat", "baixo", "pluck"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    mix = vb + mus * .08; mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    f = int(.3 * audio.SR); mix[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = os.path.join(tmp, "mix.wav"); video2.gravar_wav(wav, mix)
    out = os.path.join(pasta, f"{nome}_v{v + 1:02d}.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", fg, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out])
    shutil.rmtree(tmp, ignore_errors=True)
    return out, legenda


def mandar(nome, v, out, legenda):
    p = produto(nome)
    wa.video("dono", NUM, out, f"🎬 *{nome.capitalize()} — variação {v + 1}/10* (ative 'conteúdo gerado por IA' ao postar)")
    for txt in (legenda, p["link"], p["title"]):
        time.sleep(2); wa.texto("dono", NUM, txt)


if __name__ == "__main__":
    modo, nome = sys.argv[1], sys.argv[2]
    if modo == "cenas":
        cenas(nome)
    else:
        de, ate = int(sys.argv[3]) if len(sys.argv) > 3 else 0, int(sys.argv[4]) if len(sys.argv) > 4 else 9
        for v in range(de, ate + 1):
            out, leg = variacao(nome, v)
            mandar(nome, v, out, leg)
            print("ENVIADO", nome, v + 1, flush=True)
