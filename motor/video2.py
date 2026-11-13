"""Vídeo v2 (1080x1920 desenhado, gravado 720x1280).

Regras do dono:
- o produto aparece SEMPRE com a foto REAL da Shopee, sem IA mexendo nele e sem tremer (só um zoom bem lento);
- o fundo é uma filmagem REAL do nicho (Coverr / Pixabay);
- aberturas: "mulher"/"homem" (apresentador de IA com boca sincronizada), "cachorro" (cachorro real),
  "narrado" (cena real + voz do dono), "produto" (direto no produto);
- antes e depois do preço bem destacado.
"""
import json
import os
import random
import shutil
import subprocess
import urllib.request
import wave

import numpy as np

import audio
import cenas
import falas
import roteiro
import stock
import voz as vozmod
from peneira import RAIZ

AQUI = os.path.dirname(os.path.abspath(__file__))
FPS = 30
FORMATOS = ["cena", "narrado", "cachorro"]  # aprovado: sem pessoa de IA falando; produto real na tela desde o início
DESTAQUES = [("#ffe600", "#ff2e63"), ("#ffd400", "#00d68f"), ("#fff200", "#ff5a1f"), ("#00f0ff", "#ffe600"), ("#ffe600", "#7b2ff7")]


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falhou: {' '.join(str(c) for c in cmd[:5])}...\n{r.stderr[-1500:]}")
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


def apresentadores(genero):
    lista = json.load(open(os.path.join(RAIZ, "dados", "apresentadores", "lista.json")))
    return [a for a in lista if a["genero"] == genero]


class Linha:
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

    def janela(self, t1, t2, de="translateY(40px)"):
        f = [(t1, f"opacity:0;transform:{de}"), (t1 + .3, "opacity:1;transform:none")]
        if t2 is not None:
            f += [(t2, "opacity:1;transform:none"), (t2 + .25, "opacity:0;transform:none")]
        return self.anim(f)

    def pop(self, t, ate=None, de=.4):
        f = [(t, f"opacity:0;transform:scale({de})"), (t + .18, "opacity:1;transform:scale(1.08)"), (t + .32, "opacity:1;transform:scale(1)")]
        if ate is not None:
            f += [(ate, "opacity:1;transform:scale(1)"), (ate + .2, "opacity:0;transform:scale(.9)")]
        return self.anim(f, "ease-out")

    def pulsa(self, t, passo=.6, esc=1.06):
        f = [(t, "opacity:0;transform:scale(.6)"), (t + .25, "opacity:1;transform:scale(1)")]
        x = t + .25
        while x < self.T:
            f += [(x + passo / 2, f"opacity:1;transform:scale({esc})"), (x + passo, "opacity:1;transform:scale(1)")]
            x += passo
        return self.anim(f, "ease-in-out")

    def quica(self, t, passo=.5, alt=22):
        f = [(t, "opacity:0;transform:translateY(-20px)")]
        x = t
        while x < self.T:
            f += [(x + passo / 2, f"opacity:1;transform:translateY({alt}px)"), (x + passo, "opacity:1;transform:translateY(0)")]
            x += passo
        return self.anim(f, "ease-in-out")


def blocos_legenda(palavras):
    blocos, atual = [], []
    for w in palavras:
        atual.append(w)
        if len(atual) == 3 or w["w"][-1:] in ",.!?":
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    res = []
    for i, b in enumerate(blocos):
        t0 = b[0]["t"]
        fim_fala = b[-1]["t"] + b[-1]["d"]
        t1 = blocos[i + 1][0]["t"] if i + 1 < len(blocos) else fim_fala + .4
        res.append({"t0": t0, "t1": min(t1, fim_fala + .45), "w": [{"t": w["t"], "w": w["w"]} for w in b]})
    return res


def montar_html(p, r, partes, H, D, img, pasta, apresentador_no_gancho):
    L = Linha(D)
    dest, dest2 = random.choice(DESTAQUES)
    s = [x["t0"] for x in partes]  # 0 preço, 1 gancho, 2-3 corpo, 4 cta
    el = []

    def add(html, estilo, anim="", cls=""):
        el.append(f'<div class="ab {cls}" style="{estilo};{anim}">{html}</div>')

    def tempo_palavra(i, teste, padrao):
        return next((w["t"] for w in partes[i]["palavras"] if teste(w["w"])), padrao)

    t_in = H if H > 0 else .05
    # selo IA + #publi (sempre)
    add('<span class="ia">🤖 Conteúdo gerado com IA · #publi</span>', "left:36px;top:40px;z-index:60")

    # ---- gancho: bolinha com a foto REAL do produto
    if H > 0:
        add(f'<img src="{img}" class="espia">', "left:790px;top:120px;z-index:40",
            L.anim([(.4, "opacity:0;transform:scale(.4)"), (.7, "opacity:1;transform:scale(1)"),
                    (H - .05, "opacity:1;transform:scale(1)"), (H, "opacity:0;transform:scale(1)")], "ease-out"))

    # ---- título
    nome = r["nome"]
    tam = 82 if len(nome) <= 18 else 68 if len(nome) <= 26 else 56
    add(f'<span class="achado" style="background:{dest};color:#111">🔥 ACHADO DO DIA</span>', "top:80px;z-index:7", L.pop(.05, None, .5), "c")
    add(f'<span class="titulo">{nome}</span>', f"top:188px;font-size:{min(tam, 62)}px;z-index:6", L.janela(t_in, None, "translateY(-30px)"), "c")

    # ---- cartão com a FOTO REAL (estável: só entra e faz um zoom bem lento)
    cam = L.anim([(t_in, "transform:scale(1)"), (D, "transform:scale(1.045)")], "linear")
    entrada = L.anim([(t_in, "opacity:0;transform:translateY(40px)"), (t_in + .4, "opacity:1;transform:none")])
    add(f'<div class="cartao"><img src="{img}" class="prod" style="{cam}"><span class="real">*Imagem real do produto</span></div>',
        "left:150px;top:285px;width:780px;height:780px;z-index:4", entrada)

    # ---- selo de desconto
    t_desc = tempo_palavra(0, lambda w: "%" in w or "desconto" in w.lower(), s[0] + 1.2)
    if H > 0:
        t_desc = max(t_desc, H + .15)  # na abertura o canto é da bolinha do produto; o selo entra junto com o cartão

    # ---- PREÇO já no primeiro instante (etiqueta grande, fica até a chamada final)
    add(f'<div class="etq" style="background:{dest};color:#111"><small>SÓ</small><b>{r["preco"]}</b></div>',
        "left:0;right:0;top:1090px;z-index:20", L.pop(.05, s[3] - .1, .5), "c")
    add(f'<div class="selo" style="background:{dest};color:#111;zoom:.7"><b>-{p["discount"]}%</b><small>OFF</small></div>',
        "left:872px;top:1092px;z-index:21", L.pop(t_desc, s[3] - .1, .2))

    # ---- estrelas + vendidos
    vend = roteiro.vendas_txt(p["sold"]).replace("mais de ", "+")
    add(f'<span class="chip">⭐ {p["rating"]:.1f} · {vend}</span>', "top:1300px;z-index:6", L.janela(s[2], s[3] - .1), "c")

    # ---- ANTES e DEPOIS
    t_ag = tempo_palavra(3, lambda w: w.lower().strip("!,.") in ("agora", "por", "só"), s[3] + .9)
    if r["de"]:
        painel = (f'<div class="ad"><div class="antes"><small>ANTES</small><s>{r["de"]}</s></div>'
                  f'<div class="seta2">➜</div><div class="agora" style="color:{dest}"><small>AGORA</small><b>{r["preco"]}</b></div></div>')
        add(painel, "left:60px;right:60px;top:1090px;z-index:6", L.janela(s[3], s[4] - .1, "translateY(30px)"))
        add(f'<span class="eco" style="background:{dest2}">💰 Economize {r["economia"]}</span>', "top:1310px;z-index:7", L.pop(t_ag + .4, s[4] - .1), "c")
    else:
        add(f'<span class="preco" style="color:{dest}">{r["preco"]}</span>', "top:1090px;z-index:6", L.pop(t_ag, s[4] - .1), "c")

    # ---- chamada final
    add(f'<span class="cta" style="background:{dest2}">TOQUE NO PRODUTO 🛒</span>', "top:1150px;z-index:8", L.pulsa(s[4]), "c")
    add('<span class="seta">👇</span>', "left:80px;top:1600px;z-index:8", L.quica(s[4] + .2))

    # ---- legenda grande
    todas = [w for x in partes for w in x["palavras"]]
    legendas = blocos_legenda(todas)
    topo_gancho = 1330 if apresentador_no_gancho else 1250
    css = open(os.path.join(AQUI, "estilo2.css"), encoding="utf-8").read().replace("{FONTES}", AQUI.replace("\\", "/"))
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
{css}
.leg b.on{{color:{dest}}}
{chr(10).join(L.kf)}
</style></head><body>
{chr(10).join(el)}
<div class="ab c leg" id="leg" style="top:1460px;z-index:30"></div>
<script>
const LEG={json.dumps(legendas, ensure_ascii=False)}, H={H:.3f};
const leg=document.getElementById('leg');
let ultimo=-1;
window.seek=t=>{{
  document.getAnimations().forEach(a=>{{a.pause();a.currentTime=t*1000}});
  const i=LEG.findIndex(b=>t>=b.t0&&t<b.t1);
  if(i!==ultimo){{ultimo=i;leg.innerHTML=i<0?'':LEG[i].w.map(w=>'<b data-t="'+w.t+'">'+w.w+'</b>').join(' ');
    leg.style.top=(t<H?'{topo_gancho}px':'1460px');}}
  leg.querySelectorAll('b').forEach(b=>b.classList.toggle('on',t>=+b.dataset.t));
  if(i>=0){{const k=Math.min(1,(t-LEG[i].t0)/.12);leg.style.transform='scale('+(0.8+0.2*k)+')';}}
  return 1}};
</script></body></html>'''
    caminho = os.path.join(pasta, "v.html")
    open(caminho, "w", encoding="utf-8").write(html)
    return caminho, t_desc, t_ag


def _base_cena(arq, ini, dur, escuro, saida):
    """filmagem real em pé 720x1280; 'escuro' escurece e desfoca de leve (fundo atrás do produto)"""
    vf = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30"
    if escuro:
        vf += ",boxblur=3:1,eq=brightness=-0.16:saturation=1.08"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{ini:.2f}", "-i", arq, "-t", f"{dur:.3f}", "-an",
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", saida])


FUNDO_FOTO = True


def _base_foto(img, dur, saida):
    """foto do produto em tela cheia, desfocada e escurecida, com zoom lento (só fundo; a foto nítida vai na frente)"""
    n = int(dur * 30) + 2
    sh(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", img, "-frames:v", str(n), "-an",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
               "boxblur=14:2,eq=brightness=-0.24:saturation=1.15,"
               f"zoompan=z='min(1+0.0009*on,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", saida])


def _base_apresentador(clip, dur, saida):
    """rosto falando (quadrado 512) em destaque sobre ele mesmo desfocado"""
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-t", f"{dur:.3f}", "-an", "-filter_complex",
        "[0:v]split[a][b];[a]scale=1280:1280,crop=720:1280,boxblur=18:2,eq=brightness=-0.12[bg];"
        "[b]scale=680:680[fg];[bg][fg]overlay=20:150,fps=30,setsar=1,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", saida])


def fazer(p, nicho, saida_mp4, formato=None, evitar=None, pasta_tmp=None, genero=None):
    """Cria o vídeo. evitar = {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()} (variedade no pack)."""
    evitar = evitar if evitar is not None else {"cenas": set(), "apresentadores": set(), "gravacoes": set(), "clipes": set()}
    formato = formato or random.choice(FORMATOS)
    saida_mp4 = os.path.abspath(saida_mp4)
    pasta = pasta_tmp or os.path.join(os.path.dirname(saida_mp4), f"_tmp_{p['item_id']}")
    shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta)
    img = os.path.join(pasta, "prod.jpg")
    baixar(p["image_url"], img)
    r = roteiro.montar2(p, formato, nicho)
    n = r["nicho"]

    # ---------------- vozes (narrado = voz do dono clonada; demais = voz grátis)
    genero = genero or random.choice("fm")
    voz_edge = random.choice(vozmod.VOZES[genero])
    usa_dono = False  # dono pediu: não usar a voz dele; só vozes grátis (feminina/masculina alternando)
    partes = []

    def nova(texto, tipo):
        w = os.path.join(pasta, f"fala{len(partes)}.wav")
        info = {"texto": texto, "tipo": tipo}
        if tipo == "gravacao":
            pal, dur = falas.gravacao(texto, w)
            info["texto"] = texto["texto"]
        elif tipo == "clonada":
            try:
                pal, dur = falas.clonada(texto, w)
            except Exception as e:
                print("  aviso voz clonada, usando voz grátis:", e)
                pal, dur = falas.edge(texto, w, "pt-BR-AntonioNeural")
        else:
            pal, dur = falas.edge(texto, w, voz_edge)
        info.update(wav=w, palavras=pal, dur=dur)
        partes.append(info)

    gr_g = [g for g in falas.gravacoes("gancho") if g["arquivo"] not in evitar["gravacoes"]] or falas.gravacoes("gancho")
    gr_c = falas.gravacoes("cta")
    nova(r["abre"], "clonada" if usa_dono else "edge")  # ACHADO + PREÇO sempre primeiro
    if usa_dono and gr_g:
        g = random.choice(gr_g)
        evitar["gravacoes"].add(g["arquivo"])
        nova(g, "gravacao")
    else:
        nova(r["gancho"], "edge")
    for frase in r["corpo"]:
        nova(frase, "clonada" if usa_dono else "edge")
    if usa_dono and gr_c:
        nova(gr_c[0], "gravacao")
    else:
        nova(r["cta"], "clonada" if usa_dono else "edge")

    t = .1
    for i, x in enumerate(partes):
        x["t0"] = t
        x["palavras"] = [{"t": t + w["t"], "d": w["d"], "w": w["w"]} for w in x["palavras"]]
        t += x["dur"] + (.08 if i == 0 else .12)
    D = round(t + .5, 2)
    H = 0.0  # produto real na tela desde o primeiro quadro

    # ---------------- fundo: a PRÓPRIA foto do produto, grandona e sombreada (pedido do dono, 12/11)
    usados = {"formato": formato, "fundo": "foto"}
    b1 = os.path.join(pasta, "base1.mp4")
    if FUNDO_FOTO:
        _base_foto(img, D, b1)
    elif formato == "cachorro":
        c = stock.clipe("pet", evitar["clipes"])
        evitar["clipes"].add(c["id"])
        _base_cena(stock.caminho(c), random.uniform(0, max(0, c["dur"] - 6)), D, True, b1)
        usados["clipe"] = c["id"]
    else:
        fundo = cenas.cena(n, evitar["cenas"])
        evitar["cenas"].add(os.path.basename(fundo))
        usados["cena_fundo"] = os.path.basename(fundo)
        _base_cena(fundo, random.uniform(0, 2), D, True, b1)
    bases = [b1]
    apres_ok = False

    # ---------------- quadros transparentes por cima (foto real, textos, preço)
    url_img = "file:///" + img.replace("\\", "/")
    html, t_desc, t_preco = montar_html(p, r, partes, H, D, url_img, pasta, apres_ok)
    quadros = os.path.join(pasta, "q")
    sh(["node", os.path.join(AQUI, "render.mjs"), html, quadros, str(FPS), "0", f"{D:.3f}", "png"])

    # ---------------- áudio: vozes + música baixa + efeitos
    N = int(D * audio.SR)
    vozbuf = np.zeros((N, 2))
    for x in partes:
        audio._soma(vozbuf, ler_wav(x["wav"]), x["t0"])
    mus = audio.musica(D, {"bpm": random.choice([108, 116, 122]), "partes": [(0, D, {"kick", "hat", "baixo", "pluck"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    sfx = np.zeros((N, 2))
    for tt, tipo, kw in ([(H, "whoosh", {})] if H > 0 else []) + [(.05, "moeda", {}), (t_desc, "pop", {"f0": 900}), (t_preco, "moeda", {}), (partes[4]["t0"], "ding", {})]:
        audio._soma(sfx, audio.EFEITOS[tipo](**kw), tt)
    mix = vozbuf + mus * .11 + sfx * .3
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    f = int(.3 * audio.SR)
    mix[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = os.path.join(pasta, "mix.wav")
    gravar_wav(wav, mix)

    # ---------------- junta tudo
    entradas, filtro = [], ""
    for i, b in enumerate(bases):
        entradas += ["-i", b]
        filtro += f"[{i}:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[b{i}];"
    filtro += "".join(f"[b{i}]" for i in range(len(bases))) + f"concat=n={len(bases)}:v=1:a=0[base];"
    k = len(bases)
    filtro += f"[base][{k}:v]overlay=0:0:shortest=1,format=yuv420p[v]"
    sh(["ffmpeg", "-y", "-loglevel", "error", *entradas, "-framerate", str(FPS), "-i", os.path.join(quadros, "f%04d.png"),
        "-i", wav, "-filter_complex", filtro, "-map", "[v]", "-map", f"{k + 1}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", saida_mp4])
    shutil.rmtree(pasta, ignore_errors=True)
    return {"formato": formato, "nicho": n, "roteiro": r, "duracao": D, "usados": usados,
            "legenda": roteiro.legenda2(p, r, formato), "apresentador_ok": apres_ok}
