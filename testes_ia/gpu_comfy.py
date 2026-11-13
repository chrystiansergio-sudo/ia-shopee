"""Usa o ComfyUI rodando na placa da RunPod: (1) Qwen-Image-Edit-2509 coloca o produto REAL numa cena;
(2) Wan 2.2 I2V 14B (com LoRA lightx2v 4 passos) anima a cena. Sem limite diário."""
import json, os, random, time, uuid
import httpx

URL = os.environ.get("COMFY_URL", "https://966cz780do6fjx-8188.proxy.runpod.net")
cli = httpx.Client(timeout=120, follow_redirects=True)


def subir(arq):
    with open(arq, "rb") as f:
        r = cli.post(f"{URL}/upload/image", files={"image": (f"{uuid.uuid4().hex[:8]}_{os.path.basename(arq)}", f, "image/png")},
                     data={"overwrite": "true"})
    r.raise_for_status()
    return r.json()["name"]


def rodar(wf, saida, tipo):
    pid = cli.post(f"{URL}/prompt", json={"prompt": wf, "client_id": "iashopee"}).json()
    if "prompt_id" not in pid:
        raise RuntimeError(f"ComfyUI recusou: {str(pid)[:600]}")
    pid = pid["prompt_id"]
    t = time.time()
    while True:
        time.sleep(3)
        h = cli.get(f"{URL}/history/{pid}").json()
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(f"erro no ComfyUI: {str(st)[:800]}")
            if tipo == "clipe":  # quadros -> mp4 16 fps
                import subprocess, tempfile
                d = tempfile.mkdtemp()
                ims = [o for no in h[pid]["outputs"].values() for o in no.get("images", [])]
                for i, o in enumerate(ims):
                    r = cli.get(f"{URL}/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
                    open(os.path.join(d, f"{i:04d}.png"), "wb").write(r.content)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "16", "-i", os.path.join(d, "%04d.png"),
                                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", saida], check=True)
                import shutil; shutil.rmtree(d, ignore_errors=True)
                print(f"  {tipo} ok {time.time() - t:.0f}s ({len(ims)} quadros)", flush=True)
                return saida
            for no in h[pid]["outputs"].values():
                for k in ("images", "videos", "gifs"):
                    for o in no.get(k, []):
                        r = cli.get(f"{URL}/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
                        open(saida, "wb").write(r.content)
                        print(f"  {tipo} ok {time.time() - t:.0f}s", flush=True)
                        return saida
            raise RuntimeError("sem saída")
        if time.time() - t > 900:
            raise RuntimeError("demorou demais")


def editar(imagens, prompt, saida, w=720, h=1280, lora=None, seed=None):
    """imagens: 1 a 3 fotos (ex.: produto real, apresentadora). Saída 720x1280."""
    seed = seed or random.randint(1, 2 ** 31)
    nomes = [subir(a) for a in imagens]
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    }
    ins_p = {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0]}
    ins_n = {"clip": ["2", 0], "prompt": "", "vae": ["3", 0]}
    for i, n in enumerate(nomes, 1):
        wf[f"L{i}"] = {"class_type": "LoadImage", "inputs": {"image": n}}
        wf[f"S{i}"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [f"L{i}", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 16}}
        ins_p[f"image{i}"] = [f"S{i}", 0]
        ins_n[f"image{i}"] = [f"S{i}", 0]
    modelo = ["1", 0]
    passos, cfg = 20, 2.5
    if lora:
        wf["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
        modelo, passos, cfg = ["4", 0], 4, 1.0
    wf.update({
        "5": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": modelo, "shift": 3.0}},
        "6": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": ins_p},
        "7": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": ins_n},
        "8": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": seed, "steps": passos, "cfg": cfg, "sampler_name": "euler",
                                                   "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0], "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "cena"}},
    })
    return rodar(wf, saida, "cena")


NEG_WAN = ("talking, open mouth, yawning, lip movement, speaking, sudden movement, jump cut, scene change, morphing, deformed, "
           "extra objects, text, watermark, blurry, shaky camera, fast motion, low quality")


def animar(img, prompt, saida, w=480, h=832, frames=81, neg=NEG_WAN, seed=None):
    seed = seed or random.randint(1, 2 ** 31)
    nome = subir(img)
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "strength_model": 1.0}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "strength_model": 1.0}},
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 5.0}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": 5.0}},
        "7": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": prompt}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["7", 0], "text": neg}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": nome}},
        "12": {"class_type": "WanImageToVideo", "inputs": {"positive": ["8", 0], "negative": ["9", 0], "vae": ["10", 0], "start_image": ["11", 0],
                                                           "width": w, "height": h, "length": frames, "batch_size": 1}},
        "13": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["5", 0], "add_noise": "enable", "noise_seed": seed, "steps": 4, "cfg": 1.0,
                                                            "sampler_name": "euler", "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1],
                                                            "latent_image": ["12", 2], "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable"}},
        "14": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["6", 0], "add_noise": "disable", "noise_seed": seed, "steps": 4, "cfg": 1.0,
                                                            "sampler_name": "euler", "scheduler": "simple", "positive": ["12", 0], "negative": ["12", 1],
                                                            "latent_image": ["13", 0], "start_at_step": 2, "end_at_step": 10000, "return_with_leftover_noise": "disable"}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["10", 0]}},
        "16": {"class_type": "SaveImage", "inputs": {"images": ["15", 0], "filename_prefix": "quadros/q"}},
    }
    return rodar(wf, saida, "clipe")
