"""Chama IAs grátis do Hugging Face (ZeroGPU) com a chave do .env (HF_TOKEN)."""
import os, re, shutil, subprocess, sys, time
import httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from peneira import env
env()
TOKEN = os.environ.get("HF_TOKEN")
from gradio_client import Client, handle_file

_urls = []
import gradio_client.client as _gc
_orig_dl = _gc.Endpoint._download_file
def _spy(self, x):
    if isinstance(x, dict) and x.get("url"):
        _urls.append(x["url"])
    return _orig_dl(self, x)
_gc.Endpoint._download_file = _spy


def baixar_hls(m3u8_local, saida, headers):
    """Os vídeos em 'streaming' chegam como playlist + pedaços .ts no servidor do Space."""
    url = next((u for u in reversed(_urls) if u.endswith("playlist.m3u8")), None)
    base = url.rsplit("/", 1)[0] if url else None
    segs = [l.strip() for l in open(m3u8_local, encoding="utf-8") if l.strip().endswith(".ts")]
    partes = []
    for i, s in enumerate(segs):
        dest = os.path.join(os.path.dirname(saida), f"_seg{i}.ts")
        r = httpx.get(f"{base}/{s}", headers=headers, timeout=120, follow_redirects=True)
        r.raise_for_status()
        open(dest, "wb").write(r.content); partes.append(dest)
    lista = os.path.join(os.path.dirname(saida), "_segs.txt")
    open(lista, "w").write("".join(f"file '{os.path.abspath(p)}'\n".replace("\\", "/") for p in partes))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", saida], check=True)
    for p in partes + [lista]: os.remove(p)
    return url


def pessoa_falando(imagem, audio16k, saida):
    c = Client("Soul-AILab/SoulX-FlashHead", token=TOKEN, verbose=False)
    t = time.time()
    r = c.predict(ckpt_dir="models/SoulX-FlashHead-1_3B", wav2vec_dir="models/wav2vec2-base-960h", model_type="pro",
                  cond_image=handle_file(imagem), audio_path=handle_file(audio16k), seed=9999, use_face_crop=False,
                  api_name="/run_inference_streaming")
    url = baixar_hls(r["video"], saida, {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})
    print("pessoa ok", round(time.time() - t), "s", url)


if __name__ == "__main__":
    print("token:", "sim" if TOKEN else "NÃO")


def imagem(prompt, saida, w=720, h=1280, seed=7):
    c = Client("black-forest-labs/FLUX.1-schnell", token=TOKEN, verbose=False)
    r = c.predict(prompt=prompt, seed=seed, randomize_seed=False, width=w, height=h, num_inference_steps=4, api_name="/infer")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", r[0], saida], check=True)


def anima_foto(img, prompt, saida, dur=3.5, neg="blurry, low quality, deformed, warped text, morphing, extra objects, watermark, shaky camera"):
    c = Client("Saravutw/WAN2.2_I2V_LIGHTNING_4-8step_custom", token=TOKEN, verbose=False)
    t = time.time()
    r = c.predict(input_image=handle_file(img), last_image=None, prompt=prompt, steps=6, negative_prompt=neg,
                  duration_seconds=dur, guidance_scale=1, guidance_scale_2=1, seed=42, randomize_seed=False, quality=6,
                  scheduler="UniPCMultistep", flow_shift=3.0, frame_multiplier=16, api_name="/generate_video")
    v = r[0] if isinstance(r, (list, tuple)) else r
    if isinstance(v, dict):
        v = v.get("video") or v.get("path")
    shutil.copy(v, saida)
    print("anima ok", round(time.time() - t), "s", saida)
