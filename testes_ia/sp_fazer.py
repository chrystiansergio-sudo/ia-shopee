"""Formato SEM PREÇO (Stories do Instagram): "Olha esse achado..." descrevendo as funções, foto REAL do produto o maior possível,
legenda narrada embaixo. Manda no WhatsApp: vídeo, legenda (com hashtags) e nome do produto (sem link).
Uso: python sp_fazer.py de ate     (índices de sp_produtos.json; falas em sp_falas.json)"""
import json, os, random, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import numpy as np
import audio, falas, video2, wa, peneira
from video2 import Linha, blocos_legenda, sh

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.join(AQUI, "..", "motor")
SAIDA = os.path.abspath(os.path.join(AQUI, "..", "saida", "sem_preco"))
NUM = os.environ.get("DONO_WHATSAPP", "")
os.makedirs(SAIDA, exist_ok=True)


def html(nome, legendas, D, img, pasta):
    L = Linha(D)
    el = []
    add = lambda h, est, an="", cls="": el.append(f'<div class="ab {cls}" style="{est};{an}">{h}</div>')
    add('<span class="ia">🤖 Conteúdo feito com IA · #publi</span>', "left:36px;top:36px;z-index:60")
    add('<span class="achado" style="background:#ffe600;color:#111">🔥 OLHA ESSE ACHADO</span>', "top:84px;z-index:7", L.pop(.05, None, .5), "c")
    tam = 66 if len(nome) <= 22 else 54 if len(nome) <= 32 else 46
    add(f'<span class="titulo">{nome}</span>', f"top:184px;font-size:{tam}px;z-index:6", L.janela(.1, None, "translateY(-30px)"), "c")
    cam = L.anim([(.1, "transform:scale(1)"), (D, "transform:scale(1.06)")], "linear")
    ent = L.anim([(.1, "opacity:0;transform:translateY(40px)"), (.5, "opacity:1;transform:none")])
    add(f'<div class="grande"><img src="{img}" style="{cam}"><span class="real">*Imagem real do produto</span></div>',
        "left:24px;top:290px;z-index:4", ent)
    css = open(os.path.join(MOTOR, "estilo2.css"), encoding="utf-8").read().replace("{FONTES}", os.path.abspath(MOTOR).replace("\\", "/"))
    h = f'''<!doctype html><html><head><meta charset="utf-8"><style>
{css}
.grande{{position:relative;width:1032px;height:1080px;border-radius:44px;background:#fff;overflow:hidden;
  box-shadow:0 30px 70px rgba(0,0,0,.55),0 0 0 8px rgba(255,255,255,.95)}}
.grande img{{width:100%;height:100%;object-fit:contain;background:#fff;transform-origin:50% 50%}}
.leg{{font-size:92px}}
.leg b.on{{color:#ffe600}}
{chr(10).join(L.kf)}
</style></head><body>
{chr(10).join(el)}
<div class="ab c leg" id="leg" style="top:1430px;z-index:30"></div>
<script>
const LEG={json.dumps(legendas, ensure_ascii=False)};
const leg=document.getElementById('leg');let ultimo=-1;
window.seek=t=>{{document.getAnimations().forEach(a=>{{a.pause();a.currentTime=t*1000}});
  const i=LEG.findIndex(b=>t>=b.t0&&t<b.t1);
  if(i!==ultimo){{ultimo=i;leg.innerHTML=i<0?'':LEG[i].w.map(w=>'<b data-t="'+w.t+'">'+w.w+'</b>').join(' ');}}
  leg.querySelectorAll('b').forEach(b=>b.classList.toggle('on',t>=+b.dataset.t));
  if(i>=0){{const k=Math.min(1,(t-LEG[i].t0)/.12);leg.style.transform='scale('+(0.8+0.2*k)+')';}}
  return 1}};
</script></body></html>'''
    cam_html = os.path.join(pasta, "v.html")
    open(cam_html, "w", encoding="utf-8").write(h)
    return cam_html


def fazer(i, p, f):
    pasta = os.path.join(SAIDA, f"_tmp{i:02d}")
    shutil.rmtree(pasta, ignore_errors=True); os.makedirs(pasta, exist_ok=True)
    img = os.path.join(pasta, "prod.jpg")
    video2.baixar(p["image_url"], img)
    genero = "fm"[i % 2]
    wv = os.path.join(pasta, "fala.wav")
    pal, dur = falas.edge(f["fala"], wv, random.choice(video2.vozmod.VOZES[genero]))
    t0 = .2
    pal = [{"t": t0 + w["t"], "d": w["d"], "w": w["w"]} for w in pal]
    D = round(t0 + dur + .7, 2)
    bg = os.path.join(pasta, "bg.mp4")
    video2._base_foto(img, D, bg)
    h = html(f["nome"], blocos_legenda(pal), D, "file:///" + img.replace("\\", "/"), pasta)
    q = os.path.join(pasta, "q")
    sh(["node", os.path.join(MOTOR, "render.mjs"), h, q, "30", "0", f"{D:.3f}", "png"])
    N = int(D * audio.SR)
    vb = np.zeros((N, 2)); audio._soma(vb, video2.ler_wav(wv), t0)
    mus = audio.musica(D, {"bpm": random.choice([104, 112, 120]), "partes": [(0, D, {"kick", "hat", "baixo", "pluck"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    sfx = np.zeros((N, 2)); audio._soma(sfx, audio.EFEITOS["pop"](f0=900), .05)
    mix = vb + mus * .1 + sfx * .25
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    fade = int(.3 * audio.SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    wav = os.path.join(pasta, "mix.wav"); video2.gravar_wav(wav, mix)
    out = os.path.join(SAIDA, f"{i + 1:02d}.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", bg, "-framerate", "30", "-i", os.path.join(q, "f%04d.png"), "-i", wav,
        "-filter_complex", "[0:v]fps=30,format=yuv420p[b];[b][1:v]overlay=0:0:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", out])
    sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", "3", "-i", out, "-frames:v", "1", out[:-4] + "_quadro.jpg"])
    shutil.rmtree(pasta, ignore_errors=True)
    return out


if __name__ == "__main__":
    de, ate = int(sys.argv[1]), int(sys.argv[2])
    enviar = "--nao-enviar" not in sys.argv
    PS = json.load(open(os.path.join(AQUI, "sp_produtos.json"), encoding="utf-8"))
    FS = json.load(open(os.path.join(AQUI, "sp_falas.json"), encoding="utf-8"))
    total = len(PS)
    for i in range(de, min(ate, total - 1) + 1):
        p, f = PS[i], FS[i]
        t = time.time()
        out = fazer(i, p, f)
        if enviar:
            wa.video("dono", NUM, out, f"🎬 *Vídeo {i + 1}/{total}*\n⬇️ Abaixo: legenda e nome do produto")
            leg = f["legenda"] + "\n\n#publi · conteúdo feito com IA\n" + " ".join(f["hashtags"])
            for txt in (leg, p["title"]):
                time.sleep(2); wa.texto("dono", NUM, txt)
            peneira.marcar("dono-instagram", [p])
        print(f"OK {i + 1}/{total} {time.time() - t:.0f}s {'ENVIADO' if enviar else ''} | {p['title'][:60]}", flush=True)
