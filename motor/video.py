"""Monta 1 vídeo vertical (1080x1920) de um produto: reação + produto animado + voz + legenda grande."""
import json
import os
import random
import shutil
import subprocess
import urllib.request
import wave

import numpy as np

import audio
import roteiro
import stock
import voz

AQUI = os.path.dirname(os.path.abspath(__file__))
FPS = 30
PALETAS = [  # fundo1, fundo2, destaque, destaque2
    ("#ff5a1f", "#ff2e63", "#ffe600", "#00e08a"),
    ("#6a11cb", "#2575fc", "#ffe600", "#ff3d7f"),
    ("#00b09b", "#0a6e63", "#ffe600", "#ff4d4d"),
    ("#141e30", "#243b55", "#ffd000", "#ff2e88"),
    ("#ee0979", "#ff6a00", "#fff200", "#00e5ff"),
    ("#f7971e", "#e94e1b", "#ffffff", "#1aff8c"),
    ("#1d2b64", "#7b2ff7", "#00f0ff", "#ffe600"),
]


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falhou: {' '.join(cmd[:4])}...\n{r.stderr[-1500:]}")
    return r.stdout


def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
        f.write(r.read())


def ler_wav(p):
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        return x.reshape(-1, w.getnchannels())


def gravar_wav(p, mix):
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(p, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(audio.SR)
        w.writeframes(pcm.tobytes())


class Linha:
    """Linha do tempo: gera @keyframes CSS em segundos absolutos."""

    def __init__(self, T):
        self.T, self.kf, self.n = T, [], 0

    def anim(self, frames, ease="cubic-bezier(.2,.8,.2,1)"):
        self.n += 1
        nome = f"k{self.n}"
        partes = [f"0%{{{frames[0][1]}}}"]
        for t, c in frames:
            pc = max(0.0, min(100.0, t / self.T * 100))
            partes.append(f"{pc:.4f}%{{{c};animation-timing-function:{ease}}}")
        partes.append(f"100%{{{frames[-1][1]}}}")
        self.kf.append(f"@keyframes {nome}{{{''.join(partes)}}}")
        return f"animation:{nome} {self.T}s linear both"

    def pop(self, t, ate=None, de=.3):
        f = [(t, f"opacity:0;transform:scale({de})"), (t + .2, "opacity:1;transform:scale(1.12)"), (t + .36, "opacity:1;transform:scale(1)")]
        if ate:
            f += [(ate, "opacity:1;transform:scale(1)"), (ate + .2, "opacity:0;transform:scale(.6)")]
        return self.anim(f, "ease-out")

    def entra(self, t, de="translateY(80px)", ate=None):
        f = [(t, f"opacity:0;transform:{de}"), (t + .35, "opacity:1;transform:none")]
        if ate:
            f += [(ate, "opacity:1;transform:none"), (ate + .25, "opacity:0;transform:translateY(-60px)")]
        return self.anim(f)

    def pulsa(self, t, passo=.55, esc=1.08):
        f = [(t, "opacity:0;transform:scale(.4)"), (t + .22, "opacity:1;transform:scale(1.1)"), (t + .4, "opacity:1;transform:scale(1)")]
        x = t + .4
        while x < self.T:
            f += [(x + passo / 2, f"opacity:1;transform:scale({esc})"), (x + passo, "opacity:1;transform:scale(1)")]
            x += passo
        return self.anim(f, "ease-in-out")

    def quica(self, t, passo=.5, alt=26):
        f = [(t, "opacity:0;transform:translateY(-30px)")]
        x = t
        while x < self.T:
            f += [(x + passo / 2, f"opacity:1;transform:translateY({alt}px)"), (x + passo, "opacity:1;transform:translateY(0)")]
            x += passo
        return self.anim(f, "ease-in-out")


def blocos_legenda(falas_t):
    """Agrupa palavras em blocos de até 3 (quebra em pontuação)."""
    out = []
    for f in falas_t:
        atual = []
        for w in f["palavras"]:
            atual.append(w)
            if len(atual) == 3 or w["w"][-1:] in ",.!?":
                out.append(atual)
                atual = []
        if atual:
            out.append(atual)
    res = []
    for i, b in enumerate(out):
        t0 = b[0]["t"]
        t1 = out[i + 1][0]["t"] if i + 1 < len(out) else b[-1]["t"] + b[-1]["d"] + .4
        t1 = min(t1, b[-1]["t"] + b[-1]["d"] + .5)
        res.append({"t0": t0, "t1": t1, "w": [{"t": w["t"], "w": w["w"]} for w in b]})
    return res


def montar_html(p, r, falas_t, H, D, pal, img, fala_rosto, amp, pasta, quadros_prod=None):
    L = Linha(D)
    c1, c2, dest, dest2 = pal
    s = [f["t0"] for f in falas_t]  # início de cada fala
    nome = r["nome"]
    # instante em que o preço novo aparece: palavra "por"/"apenas"/"só" na fala de preço
    fp = falas_t[3]
    t_preco = next((w["t"] for w in fp["palavras"] if w["w"].lower().strip("!,.") in ("por", "apenas", "só")), fp["t0"] + .5)
    t_preco_novo = next((w["t"] for w in fp["palavras"] if w["w"].startswith("R$") and w["t"] > t_preco - .01), t_preco + .4)
    el = []

    def add(html, estilo, anim="", cls=""):
        el.append(f'<div class="ab {cls}" style="{estilo};{anim}">{html}</div>')

    # ---- fundo do produto (some durante o gancho, se houver clipe)
    vis_fundo = L.anim([(H - .001, "opacity:0"), (H, "opacity:1")], "steps(1,end)") if H > 0 else ""
    fundo = (f'<div class="fundo" style="background:linear-gradient(160deg,{c1},{c2})">'
             f'<img class="borrado" src="{img}" style="{L.anim([(0, "transform:scale(1.4) rotate(0deg)"), (D, "transform:scale(1.7) rotate(8deg)")], "linear")}">'
             f'<div class="raios"></div></div>')
    add(fundo, "left:0;top:0;width:1080px;height:1920px;z-index:0", vis_fundo)
    # brilhos subindo
    for i in range(16):
        x, sz = random.randint(30, 1050), random.choice([6, 8, 10, 14])
        d0 = random.uniform(0, 3)
        fr = [(0, f"opacity:0;transform:translateY(0)")]
        t = H + d0
        while t < D:
            fr += [(t, "opacity:0;transform:translateY(0)"), (t + .3, "opacity:.9;transform:translateY(-200px)"), (t + 2.4, "opacity:0;transform:translateY(-900px)")]
            t += 2.6
        add("", f"left:{x}px;top:1700px;width:{sz}px;height:{sz}px;border-radius:50%;background:#fff;box-shadow:0 0 12px #fff;z-index:1", L.anim(fr, "linear"))

    # ---- flash de transição
    if H > 0:
        add("", "left:0;top:0;width:1080px;height:1920px;background:#fff;z-index:50",
            L.anim([(H - .02, "opacity:0"), (H, "opacity:.85"), (H + .22, "opacity:0")], "ease-out"))

    # ---- título (nome do produto)
    tam = 84 if len(nome) <= 18 else 70 if len(nome) <= 26 else 58
    add(f'<span class="titulo">{nome}</span>', f"top:120px;font-size:{tam}px;z-index:6", L.entra(max(H, s[1] - .1), "translateY(-80px)"), "c")

    # ---- cartão com a foto do produto + zoom em detalhes (câmera)
    zx, zy = random.choice([(30, 30), (70, 35), (40, 70), (65, 65)])
    zx2, zy2 = 100 - zx, 100 - zy
    t_in = H if H > 0 else .05
    cam = L.anim([
        (t_in, "transform:scale(1.0) translate(0,0)"),
        (s[2] - .2, "transform:scale(1.12) translate(0,0)"),
        (s[2] + .25, f"transform:scale(1.75) translate({(50 - zx) * .6:.0f}%,{(50 - zy) * .6:.0f}%)"),
        (s[3] - .3, f"transform:scale(1.9) translate({(50 - zx) * .6:.0f}%,{(50 - zy) * .6:.0f}%)"),
        (s[3] + .15, f"transform:scale(1.6) translate({(50 - zx2) * .5:.0f}%,{(50 - zy2) * .5:.0f}%)"),
        (t_preco + .1, f"transform:scale(1.65) translate({(50 - zx2) * .5:.0f}%,{(50 - zy2) * .5:.0f}%)"),
        (t_preco + .5, "transform:scale(1.0) translate(0,0)"),
        (D, "transform:scale(1.08) translate(0,0)"),
    ])
    rosto = ""
    if fala_rosto:
        rosto = ('<div class="olho" style="left:31%"><i></i></div><div class="olho" style="left:57%"><i></i></div>'
                 '<div class="boca" id="boca"></div>')
    if quadros_prod:  # produto animado por IA: troca o quadro conforme o tempo
        miolo = "".join(f'<img src="{q}" class="prod pq" style="position:absolute;inset:0;display:none">' for q in quadros_prod)
        cam = cam.replace("transform:scale(1.9)", "transform:scale(1.3)").replace("transform:scale(1.75)", "transform:scale(1.25)")                  .replace("transform:scale(1.6)", "transform:scale(1.2)").replace("transform:scale(1.65)", "transform:scale(1.2)")
    else:
        miolo = f'<img src="{img}" class="prod">'
    cartao = (f'<div class="cartao"><div class="cam" style="{cam}">{miolo}{rosto}</div></div>')
    entrada = L.anim([(t_in, "opacity:0;transform:scale(.2) rotate(-12deg)"), (t_in + .3, "opacity:1;transform:scale(1.06) rotate(2deg)"),
                      (t_in + .5, "opacity:1;transform:scale(1) rotate(0)"),
                      (s[1], "opacity:1;transform:scale(1)"), (s[1] + .12, "opacity:1;transform:scale(1.05)"), (s[1] + .3, "opacity:1;transform:scale(1)"),
                      (s[4], "opacity:1;transform:scale(1) translateY(0)"), (s[4] + .4, "opacity:1;transform:scale(.92) translateY(-30px)"),
                      (D, "opacity:1;transform:scale(.92) translateY(-30px)")])
    add(cartao, "left:160px;top:290px;width:760px;height:760px;z-index:4", entrada)

    # ---- selo de desconto
    t_desc = next((w["t"] for w in falas_t[1]["palavras"] if "%" in w["w"]), s[1] + .8)
    add(f'<div class="selo" style="background:{dest};color:#111"><b>-{p["discount"]}%</b><small>OFF</small></div>',
        "left:760px;top:215px;z-index:7", L.anim([(t_desc - .05, "opacity:0;transform:scale(3) rotate(-30deg)"), (t_desc + .2, "opacity:1;transform:scale(.9) rotate(8deg)"),
                                                  (t_desc + .35, "opacity:1;transform:scale(1) rotate(8deg)"), (D, "opacity:1;transform:scale(1) rotate(8deg)")]))

    # ---- estrelas + vendidos
    vend = roteiro.vendas_txt(p["sold"]).replace("mais de ", "+")
    estrelas = "★" * int(round(p["rating"]))
    add(f'<span class="chip">⭐ {p["rating"]:.1f} <span style="color:#f5a400">{estrelas}</span> · {vend}</span>',
        "top:1072px;z-index:6", L.entra(s[2], "translateY(60px)", s[4] - .1), "c")

    # ---- preço
    if r["de"]:
        add(f'<span class="de">{r["de"]}</span>', "top:1150px;z-index:6", L.entra(t_preco - .5, "translateX(-200px)", s[4] - .1), "c")
        add("", f"left:380px;top:1188px;height:8px;background:{dest2};z-index:7;border-radius:4px",
            L.anim([(t_preco - .1, "opacity:0;width:0"), (t_preco + .15, "opacity:1;width:320px"), (s[4] - .1, "opacity:1;width:320px"), (s[4] + .1, "opacity:0;width:320px")]))
    add(f'<span class="preco" style="color:{dest}">{r["preco"]}</span>', "top:1225px;z-index:6", L.pop(t_preco_novo, s[4] - .1, de=2.2), "c")

    # ---- chamada final
    add(f'<span class="cta" style="background:{dest2}">TOQUE NO PRODUTO 🛒</span>', "top:1170px;z-index:8", L.pulsa(s[4]), "c")
    add('<span class="seta">👇</span>', "left:90px;top:1560px;z-index:8", L.quica(s[4] + .2))

    # ---- etiqueta IA (exigência: conteúdo feito com IA)
    add('<span class="ia">✨ Conteúdo gerado com IA</span>', "left:36px;top:40px;z-index:60", "")

    # ---- gancho (sobre o clipe)
    if H > 0:
        add(f'<img src="{img}" class="espia">', "left:760px;top:250px;z-index:40",
            L.anim([(.5, "opacity:0;transform:scale(0) rotate(-40deg)"), (.8, "opacity:1;transform:scale(1.1) rotate(6deg)"),
                    (.95, "opacity:1;transform:scale(1) rotate(6deg)"), (H - .05, "opacity:1;transform:scale(1) rotate(6deg)"), (H, "opacity:0;transform:scale(1)")]))

    legendas = blocos_legenda(falas_t)
    css = open(os.path.join(AQUI, "estilo.css"), encoding="utf-8").read().replace("{FONTES}", AQUI.replace("\\", "/"))
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
{css}
.leg b.on{{color:{dest}}}
{chr(10).join(L.kf)}
</style></head><body>
{chr(10).join(el)}
<div class="ab c leg" id="leg" style="top:{1430 if H > 0 else 1430}px;z-index:30"></div>
<script>
const LEG={json.dumps(legendas, ensure_ascii=False)}, AMP={json.dumps(amp)}, H={H:.3f};
const leg=document.getElementById('leg'), boca=document.getElementById('boca'), PQ=[...document.querySelectorAll('.pq')], T_IN={(H if H > 0 else .05):.3f};
let ultimo=-1;
window.seek=t=>{{
  document.getAnimations().forEach(a=>{{a.pause();a.currentTime=t*1000}});
  const i=LEG.findIndex(b=>t>=b.t0&&t<b.t1);
  if(i!==ultimo){{ultimo=i;leg.innerHTML=i<0?'':LEG[i].w.map(w=>'<b data-t="'+w.t+'">'+w.w+'</b>').join(' ');
    leg.style.top=(t<H?'1180px':'1450px');leg.classList.remove('salta');void leg.offsetWidth;}}
  leg.querySelectorAll('b').forEach(b=>b.classList.toggle('on',t>=+b.dataset.t));
  if(i>=0){{const k=Math.min(1,(t-LEG[i].t0)/.12);leg.style.transform='scale('+(0.7+0.3*k)+')';}}
  if(PQ.length){{const k=Math.max(0,Math.floor((t-T_IN)*16)),n=PQ.length,j=(Math.floor(k/(n-1))%2?n-1-k%(n-1):k%(n-1));PQ.forEach((e,x)=>e.style.display=x===j?'block':'none');}}
  if(boca){{const a=AMP[Math.min(AMP.length-1,Math.round(t*{FPS}))]||0;boca.style.height=(10+a*120)+'px';boca.style.marginTop=(-a*60)+'px';}}
  return 1}};
</script></body></html>'''
    caminho = os.path.join(pasta, "v.html")
    open(caminho, "w", encoding="utf-8").write(html)
    return caminho, t_preco_novo, t_desc


def fazer(p, nicho, saida_mp4, estilo=None, evitar_clipes=(), pasta_tmp=None, evitar_estilos=(),
          apresentador=None, clipe_gancho=None, produto_ia=False):
    """apresentador={"imagem": caminho, "genero": "f"|"m"}; clipe_gancho=mp4 pronto (ex.: cachorro IA); produto_ia=animar a foto com IA."""
    """Cria o vídeo. Devolve dict com informações (roteiro, legenda, clipe usado...)."""
    saida_mp4 = os.path.abspath(saida_mp4)
    pasta = pasta_tmp or os.path.join(os.path.dirname(saida_mp4), f"_tmp_{p['item_id']}")
    shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta)
    img = os.path.join(pasta, "prod.jpg")
    baixar(p["image_url"], img)

    r = roteiro.montar(p, estilo, evitar_estilos)
    if (apresentador or clipe_gancho) and r["estilo"] == "produto_fala":
        r = roteiro.montar(p, "achado")
    fala_rosto = r["estilo"] == "produto_fala"
    pet = any(k in (p.get("palavra", "") + " " + nicho).lower() for k in ("pet", "cachorro", "gato", "coleira", "arranhador"))
    tipo_clipe = None if fala_rosto else ("pet" if pet and random.random() < .7 else random.choice("ffm"))
    genero = random.choice("fm") if tipo_clipe in (None, "pet") else tipo_clipe
    if apresentador:
        genero = apresentador["genero"]
    voz_nome = random.choice(voz.VOZES[genero])

    # ---- voz: cada fala separada (tempo exato de cada frase)
    falas_t, t, partes = [], (0.0 if apresentador else .15), []
    for i, txt in enumerate(r["falas"]):
        w = os.path.join(pasta, f"fala{i}.wav")
        _, pal, dur = voz.falar(txt, w, voz=voz_nome)
        falas_t.append({"t0": t, "t1": t + dur, "palavras": [{"t": t + x["t"], "d": x["d"], "w": x["w"]} for x in pal]})
        partes.append((t, w))
        t += dur + (.05 if i == 0 else .1)
    D = round(t + .6, 2)
    H = 0.0 if fala_rosto else round(falas_t[1]["t0"] - .08, 3)

    # ---- áudio: voz + música + efeitos
    N = int(D * audio.SR)
    vozbuf = np.zeros((N, 2))
    for t0, w in partes:
        audio._soma(vozbuf, ler_wav(w), t0)
    bpm = random.choice([110, 118, 124, 128])
    mus = audio.musica(D, {"bpm": bpm, "partes": [(0, D, {"kick", "hat", "baixo", "pluck"} if random.random() < .5 else {"kick", "hat", "ohat", "baixo", "clap"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    # amplitude da voz por quadro (para a boca do produto falante)
    env_ = np.abs(vozbuf[:, 0])
    passo = audio.SR // FPS
    amp = [float(min(1, env_[i:i + passo].mean() * 9)) for i in range(0, N, passo)]
    amp = [round(a, 3) for a in amp]

    pal_cores = random.choice(PALETAS)
    url_img = "file:///" + img.replace("\\", "/")
    quadros = None
    if produto_ia:
        try:
            import ia_online
            clip = os.path.join(pasta, "prod_ia.mp4")
            ia_online.anima_foto(img, "slow smooth cinematic camera push-in toward the product, soft light sweeping across it, the product stays still, rigid and unchanged, all printed text unchanged", clip,
                                 neg="deformed, warped, melting, morphing, changing shape, changing text, new objects, blurry, low quality, watermark, shaky camera")
            pq = os.path.join(pasta, "pq"); os.makedirs(pq)
            sh(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-vf", "fps=16,scale=760:-2", "-q:v", "3", os.path.join(pq, "%03d.jpg")])
            quadros = ["file:///" + os.path.join(pq, f).replace("\\", "/") for f in sorted(os.listdir(pq))]
        except Exception as e:
            print("  aviso produto IA (usando foto):", e)
    html, t_preco, t_desc = montar_html(p, r, falas_t, H, D, pal_cores, url_img, fala_rosto, amp, pasta, quadros)

    sfx = np.zeros((N, 2))
    for tt, tipo, kw in [(H, "whoosh", {}), (t_desc, "impacto", {}), (t_preco, "moeda", {}), (falas_t[4]["t0"], "pop", {"f0": 1000})] + \
                        ([(0.05, "boom", {})] if H > 0 else []):
        audio._soma(sfx, audio.EFEITOS[tipo](**kw), tt)
    mix = vozbuf * 1.0 + mus * .13 + sfx * .35
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    f = int(.3 * audio.SR)
    mix[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = os.path.join(pasta, "mix.wav")
    gravar_wav(wav, mix)

    # ---- quadros
    render = os.path.join(AQUI, "render.mjs")
    corpo = os.path.join(pasta, "corpo")
    sh(["node", render, html, corpo, str(FPS), f"{H:.3f}", f"{D:.3f}", "jpg"])
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    v_corpo = os.path.join(pasta, "corpo.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(corpo, "f%04d.jpg"), *enc, v_corpo])
    clipe_info = None
    if H > 0:
        gancho = os.path.join(pasta, "gancho")
        sh(["node", render, html, gancho, str(FPS), "0", f"{H:.3f}", "png"])
        if apresentador:
            import ia_online
            w16 = os.path.join(pasta, "fala0_16k.wav")
            sh(["ffmpeg", "-y", "-loglevel", "error", "-i", partes[0][1], "-ar", "16000", "-ac", "1", w16])
            arq = os.path.join(pasta, "apresentador.mp4")
            ia_online.pessoa_falando(apresentador["imagem"], w16, arq)
            c = {"id": "apresentador_ia", "arquivo": arq, "chroma": None, "dur": H}
        elif clipe_gancho:
            c = {"id": os.path.basename(clipe_gancho), "arquivo": clipe_gancho, "chroma": None, "dur": H}
        else:
            c = stock.clipe(tipo_clipe, evitar_clipes)
        clipe_info = c["id"]
        ini = 0 if c.get("arquivo") else round(random.uniform(0, max(0, c["dur"] - H - .5)), 2)
        cor = {"verde": "0x00b140", "azul": "0x2ab0ff"}.get(c["chroma"])
        if c["chroma"]:
            # recorta o fundo verde/azul e põe a pessoa sobre o degradê da paleta
            key = "chromakey" if c["chroma"] == "verde" else "colorkey"
            filtro = (f"color=c={pal_cores[0]}:s=720x1280:r={FPS}:d={H:.3f}[bg];"
                      f"[0:v]scale=-2:1000,crop=720:1000,{key}={cor}:0.16:0.08[p];"
                      f"[bg][p]overlay=0:280:shortest=1[b];[b][1:v]overlay=0:0:shortest=1,format=yuv420p")
        else:
            filtro = f"[0:v]scale=-2:1280,crop=720:1280,setsar=1,fps={FPS}[b];[b][1:v]overlay=0:0:shortest=1,format=yuv420p"
        v_gancho = os.path.join(pasta, "gancho.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(ini), "-t", f"{H:.3f}", *(["-stream_loop", "-1"] if clipe_gancho else []), "-i", c.get("arquivo") or stock.caminho(c),
            "-framerate", str(FPS), "-i", os.path.join(gancho, "f%04d.png"), "-filter_complex", filtro, "-an", *enc, v_gancho])
        v_mudo = os.path.join(pasta, "mudo.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", v_gancho, "-i", v_corpo, "-filter_complex",
            "[0:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[a];[1:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[b];[a][b]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-an", *enc, v_mudo])
    else:
        v_mudo = v_corpo
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", v_mudo, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", saida_mp4])
    shutil.rmtree(pasta, ignore_errors=True)
    return {"roteiro": r, "voz": voz_nome, "clipe": clipe_info, "duracao": D, "legenda": roteiro.legenda(p, r, nicho)}
