"""Testa: colocar o produto REAL numa cena (edição de imagem grátis) antes de animar."""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import ia_online, video2
from gradio_client import Client, handle_file
AQUI = os.path.dirname(os.path.abspath(__file__))
p = json.load(open(os.path.join(AQUI, "ia10_produtos.json"), encoding="utf-8"))[0]
img = os.path.join(AQUI, "_c_prod.jpg"); video2.baixar(p["image_url"], img)
PR = ("Place this exact mini food chopper on a bright modern kitchen counter with fresh garlic and vegetables around it; "
      "an adult woman's hand is pressing its top button. Keep the product exactly identical: same shape, colors, size and details. "
      "Realistic photo, vertical framing, no text.")
qual = sys.argv[1]
t = time.time()
if qual == "qwen":
    c = Client("Qwen/Qwen-Image-Edit", token=ia_online.TOKEN, verbose=False)
    r = c.predict(image=handle_file(img), prompt=PR, seed=7, randomize_seed=False, true_guidance_scale=4.0,
                  num_inference_steps=24, rewrite_prompt=False, api_name="/infer")
else:
    c = Client("black-forest-labs/FLUX.1-Kontext-Dev", token=ia_online.TOKEN, verbose=False)
    r = c.predict(input_image=handle_file(img), prompt=PR, seed=7, randomize_seed=False, guidance_scale=2.5, steps=24, api_name="/infer")
v = r[0]; v = v.get("path") if isinstance(v, dict) else v
shutil.copy(v, os.path.join(AQUI, f"_c_{qual}.png"))
print(qual, "ok", round(time.time() - t), "s")
