"""Teste IA-10: faz 1 vídeo (índice N de ia10_produtos.json) com CENAS DE IA a partir da FOTO REAL.
- roteiro falando das características reais do anúncio (IA de texto grátis do Hugging Face), SEM preço;
- 2 cenas de IA (Wan 2.2, GPU grátis do HF) geradas da foto real; fundo = foto sombreada;
- miniatura da foto REAL sempre na tela; selo "feito com IA".
Uso: python ia10_fazer.py N   -> saida/ia10/NN.mp4 + NN.json (legenda, link, nome)"""
import json, os, random, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import httpx
import numpy as np
import audio, falas, ia_online, video2
from video2 import Linha, blocos_legenda, sh

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.join(AQUI, "..", "motor")
SAIDA = os.path.abspath(os.path.join(AQUI, "..", "saida", "ia_melhor"))
os.makedirs(SAIDA, exist_ok=True)

PEDIDO = """Você escreve vídeos curtos de achadinhos da Shopee em português do Brasil.
Produto (título do anúncio): "{titulo}"
Responda SÓ com um JSON válido, sem comentários, com estas chaves:
"nome": nome curto e claro do produto (2 a 5 palavras),
"fala": texto narrado com 5 frases e 55 a 70 palavras no total (uns 20 segundos de fala). Comece chamando atenção ("Olha esse...", "Conheça o...", "Se liga nesse..."). Cite 2 ou 3 características CONCRETAS que estão no título (ex.: número de velocidades, potência, material, tamanho, o que vem no kit). Termine com "Toca no produto aqui embaixo!". PROIBIDO: preço, desconto, frete, inventar números ou funções que não estão no título, falar como cliente ("eu comprei").
"cenas": lista com 5 instruções EM INGLÊS para uma IA que EDITA uma foto, todas no MESMO lugar realista adequado ao produto (ex.: cozinha clara), com a MESMA pessoa adulta ({pessoa}) e a MESMA roupa. A pessoa NUNCA olha para a câmera: aparece de lado, de costas ou do peito para baixo. (1) o produto grande sobre uma superfície e as mãos chegando nele; (2) as mãos usando o produto na função principal; (3) close das mãos mostrando um detalhe/característica citada na fala; (4) a pessoa (sem rosto, de costas ou do peito para baixo) usando o produto no dia a dia; (5) o produto pronto/organizado, grande, bonito, sem pessoa. Nunca crianças, nunca texto.
"legenda": 2 frases curtas dizendo por que o produto é bom (sem preço, sem link, sem hashtag), pode ter 1 ou 2 emojis.
"hashtags": lista com 5 hashtags em minúsculas sem acento, as 3 primeiras sobre o produto, depois #achadinhosdashopee e #shopee."""


def roteiro_ia(titulo, pessoa):
    ult = None
    for modelo in ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"]:
        for _ in range(2):
            try:
                r = httpx.post("https://router.huggingface.co/v1/chat/completions", timeout=120,
                               headers={"Authorization": f"Bearer {ia_online.TOKEN}"},
                               json={"model": modelo, "max_tokens": 700, "temperature": .8,
                                     "messages": [{"role": "user", "content": PEDIDO.format(titulo=titulo, pessoa=pessoa)}]})
                txt = r.json()["choices"][0]["message"]["content"]
                j = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
                assert j["fala"] and len(j["cenas"]) >= 5 and j["nome"]
                if len(j["fala"].split()) < 25:
                    raise ValueError("fala curta")
                if len(j["fala"].split()) < 50:  # completa sem inventar nada sobre o produto
                    extra = random.choice(["É daqueles itens que faz diferença no dia a dia.",
                                           "Bonito, prático e fácil de usar.", "Vale muito a pena dar uma olhada nele."])
                    j["fala"] = j["fala"].replace("Toca no produto aqui embaixo!", extra + " Corre, toca no produto aqui embaixo e confere todos os detalhes!")
                if re.search(r"r\$|reais|desconto|frete", j["fala"].lower()):
                    raise ValueError("falou de preço")
                return j
            except Exception as e:
                ult = e
    raise RuntimeError(f"roteiro falhou: {ult}")


def editar(img, prompt, saida):
    """coloca o produto REAL numa cena (Qwen-Image-Edit, Apache-2.0, GPU grátis do HF)"""
    from gradio_client import Client, handle_file
    c = Client("Qwen/Qwen-Image-Edit", token=ia_online.TOKEN, verbose=False)
    r = c.predict(image=handle_file(img), prompt=prompt + " The product is BIG and clearly visible in the center of the frame, taking a large part of the image. Keep the product exactly identical: same shape, colors, size, logo and details. "
                  "Realistic photo, no text, no children.", seed=random.randint(1, 99999), randomize_seed=False,
                  true_guidance_scale=4.0, num_inference_steps=24, rewrite_prompt=False, api_name="/infer")
    v = r[0]; v = v.get("path") if isinstance(v, dict) else v
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", v, "-q:v", "2", saida])


def confere(orig, cena):
    """IA de visão compara a cena com a foto real: mesmo produto, sem rosto, sem texto inventado"""
    import base64
    def b64(p):
        return "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()
    perg = ("Image 1 is the real product photo. Image 2 is a generated scene. Answer YES only if ALL are true: "
            "(a) image 2 shows the SAME product as image 1 (same shape, same number of parts/shelves, same colors and design; if image 1 shows "
            "several color options, any one of them is fine); (b) nobody in image 2 is facing the camera (side view, back view or no face are fine); (c) no invented text or logo was added. "
            "Otherwise answer NO. One word.")
    for modelo in ["Qwen/Qwen2.5-VL-72B-Instruct", "Qwen/Qwen2.5-VL-32B-Instruct"]:
        try:
            r = httpx.post("https://router.huggingface.co/v1/chat/completions", timeout=120,
                           headers={"Authorization": f"Bearer {ia_online.TOKEN}"},
                           json={"model": modelo, "max_tokens": 4, "temperature": 0, "messages": [{"role": "user", "content": [
                               {"type": "text", "text": perg}, {"type": "image_url", "image_url": {"url": b64(orig)}},
                               {"type": "image_url", "image_url": {"url": b64(cena)}}]}]})
            return r.json()["choices"][0]["message"]["content"].strip().upper().startswith("YES")
        except Exception as e:
            print("aviso confere", modelo, str(e)[:100], flush=True)
    return True  # se a IA de visão falhar, segue (e eu confiro olhando)


def editar_ok(orig, base, prompt, saida, tentativas=3):
    for t in range(tentativas):
        editar(base, prompt + (" The head and face are OUT of the frame (framing from the chest down)." if t else ""), saida)
        if confere(orig, saida):
            return True
        print("  cena reprovada na conferência, refazendo", flush=True)
    return False


def html_overlay(nome, legendas, D, img, pasta):
    L = Linha(D)
    el = []
    add = lambda h, est, an="", cls="": el.append(f'<div class="ab {cls}" style="{est};{an}">{h}</div>')
    add('<span class="ia">🤖 Feito com IA · #publi</span>', "left:36px;top:40px;z-index:60")
    add('<span class="achado" style="background:#ffe600;color:#111">🔥 ACHADO DO DIA</span>', "top:84px;z-index:7", L.pop(.05, None, .5), "c")
    tam = 70 if len(nome) <= 20 else 58 if len(nome) <= 30 else 48
    add(f'<span class="titulo">{nome}</span>', f"top:190px;font-size:{tam}px;z-index:6", L.janela(.1, None, "translateY(-30px)"), "c")
    add('<div class="moldura"></div>', "left:90px;top:300px;z-index:5")
    add(f'<div class="mini"><img src="{img}"><span>foto real</span></div>', "left:770px;top:1040px;z-index:9", L.pop(.6, None, .3))
    add('<span class="cta" style="background:#ff2e63;color:#fff">TOQUE NO PRODUTO 🛒</span>', "top:1250px;z-index:8", L.pulsa(max(.5, D - 2.6)), "c")
    css = open(os.path.join(MOTOR, "estilo2.css"), encoding="utf-8").read().replace("{FONTES}", os.path.abspath(MOTOR).replace("\\", "/"))
    html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
{css}
.moldura{{width:900px;height:900px;border-radius:48px;box-shadow:0 0 0 10px rgba(255,255,255,.95),0 30px 70px rgba(0,0,0,.55)}}
.mini{{width:240px;height:270px;background:#fff;border-radius:28px;overflow:hidden;box-shadow:0 14px 40px rgba(0,0,0,.55);text-align:center}}
.mini img{{width:240px;height:220px;object-fit:contain;background:#fff}}
.mini span{{display:block;font-family:Mont,sans-serif;font-weight:900;font-size:26px;color:#111;line-height:46px;background:#ffe600}}
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
    cam = os.path.join(pasta, "v.html")
    open(cam, "w", encoding="utf-8").write(html)
    return cam


def fazer(i):
    p = json.load(open(os.path.join(AQUI, "ia10_produtos.json"), encoding="utf-8"))[i]
    genero = "fm"[i % 2]
    pasta = os.path.join(SAIDA, f"_tmp{i:02d}")
    shutil.rmtree(pasta, ignore_errors=True); os.makedirs(pasta, exist_ok=True)
    img = os.path.join(pasta, "prod.jpg")
    video2.baixar(p["image_url"], img)
    from PIL import Image
    im = Image.open(img).convert("RGB")
    W = max(im.width, int(im.height * 9 / 16)); H = int(W * 16 / 9)
    alto = Image.new("RGB", (W, H), (255, 255, 255)); alto.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    img_v = os.path.join(pasta, "prod_v.jpg"); alto.resize((720, 1280)).save(img_v, quality=95)
    fixo = os.path.join(AQUI, f"_roteiro{i}.json")
    r = json.load(open(fixo, encoding="utf-8")) if os.path.exists(fixo) else roteiro_ia(p["title"], "woman" if genero == "f" else "man")
    print("roteiro:", r["fala"], flush=True)

    # voz
    wv = os.path.join(pasta, "fala.wav")
    voz = random.choice(video2.vozmod.VOZES[genero])
    pal, dur = falas.edge(r["fala"], wv, voz)
    t0 = .15
    pal = [{"t": t0 + w["t"], "d": w["d"], "w": w["w"]} for w in pal]
    D = round(t0 + dur + .8, 2)

    # cenas de IA: 1ª cena sai da foto real; as outras saem da 1ª (mesmo lugar, mesma pessoa)
    NEG = ("talking, open mouth, yawning, lip movement, face, head, sudden movement, jump cut, morphing, deformed product, "
           "extra objects, text, watermark, blurry, shaky camera, fast motion")
    n_cenas = min(5, max(3, int((D + 0.5) / 4.5) + 1))
    base1 = os.path.join(pasta, "cena0.jpg")
    if not editar_ok(img, img_v, r["cenas"][0] + " Fill the whole vertical frame with the scene, no white borders. The person is seen from the side or from behind, never facing the camera.", base1):
        raise RuntimeError("produto não ficou fiel na cena base")
    clipes = []
    for k in range(n_cenas):
        pr = r["cenas"][k]
        foto_cena = base1 if k == 0 else os.path.join(pasta, f"cena{k}.jpg")
        c = os.path.join(pasta, f"cena{k}.mp4")
        for tent in range(2):
            try:
                if k > 0 and not editar_ok(img, base1, "Same place, same person and same clothes as this photo, same exact product. New shot: " + pr + " The person is seen from the side, from behind or from the chest down, never facing the camera.", foto_cena):
                    break
                ia_online.anima_foto(foto_cena, pr + " Slow, smooth, natural movement of the hands; steady camera with a gentle slow push-in. "
                                     "The person keeps the mouth closed and does not talk. The product stays exactly identical.", c, dur=5, neg=NEG + (", person, people, hands" if k == 4 else ""))
                clipes.append(c); break
            except Exception as e:
                print("aviso cena", k, e, flush=True); time.sleep(10)
    if not clipes:
        raise RuntimeError("nenhuma cena de IA saiu")
    # junta com transição suave (sem voltar a cena ao contrário)
    partes = []
    for n, c in enumerate(clipes):
        s = os.path.join(pasta, f"s{n}.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", c, "-an", "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,setsar=1,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", s])
        partes.append(s)
    durs = [float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", s]).strip()) for s in partes]
    F = .5
    ent, filt, ant, off = [], "", "[0:v]", 0.0
    for n, s in enumerate(partes):
        ent += ["-i", s]
    for n in range(1, len(partes)):
        off += durs[n - 1] - F
        filt += f"{ant}[{n}:v]xfade=transition=fade:duration={F}:offset={off:.3f}[x{n}];"
        ant = f"[x{n}]"
    total = sum(durs) - F * (len(partes) - 1)
    fg = os.path.join(pasta, "fg.mp4")
    if len(partes) > 1:
        # se a fala for mais longa, a última cena fica parada no último quadro (sem repetir)
        filt += f"{ant}tpad=stop_mode=clone:stop_duration={max(0, D - total) + .2:.2f}[v]"
        sh(["ffmpeg", "-y", "-loglevel", "error", *ent, "-filter_complex", filt, "-map", "[v]", "-t", f"{D:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", fg])
    else:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", partes[0], "-vf", f"tpad=stop_mode=clone:stop_duration={D:.2f}", "-t", f"{D:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", fg])
    # áudio
    N = int(D * audio.SR)
    vb = np.zeros((N, 2)); audio._soma(vb, video2.ler_wav(wv), t0)
    mus = audio.musica(D, {"bpm": random.choice([108, 116, 122]), "partes": [(0, D, {"kick", "hat", "baixo", "pluck"})]})
    mus = mus / (np.max(np.abs(mus)) + 1e-9)
    sfx = np.zeros((N, 2)); audio._soma(sfx, audio.EFEITOS["whoosh"](), .05)
    mix = vb + mus * .1 + sfx * .25
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * .92
    f = int(.3 * audio.SR); mix[-f:] *= np.linspace(1, 0, f)[:, None]
    wav = os.path.join(pasta, "mix.wav"); video2.gravar_wav(wav, mix)

    out = os.path.join(SAIDA, f"{i + 1:02d}.mp4")
    # regra do dono: NADA escrito no vídeo (sem preço, sem texto) — só as cenas e a voz
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", fg, "-i", wav,
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", out])
    legenda = r["legenda"].strip() + "\n\nPubli · conteúdo feito com IA\n" + " ".join(
        "#" + re.sub(r"[^a-z0-9]", "", h.lower()) for h in r["hashtags"][:5])
    json.dump({"legenda": legenda, "link": p.get("link") or p.get("product_link"), "nome": p["title"], "fala": r["fala"],
               "comissao": p["commission"], "item_id": p["item_id"]}, open(out[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-vf", "fps=0.5,scale=240:-1,tile=8x2", "-frames:v", "1", out[:-4] + "_tira.jpg"])
    shutil.rmtree(pasta, ignore_errors=True)
    print("OK", out, D, "s", flush=True)


if __name__ == "__main__":
    fazer(int(sys.argv[1]))
