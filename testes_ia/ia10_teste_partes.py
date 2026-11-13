"""Testa as 2 peças grátis: texto (HF router) e cena de IA (Wan 2.2 ZeroGPU) com o 1º produto."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import ia_online, video2
import httpx
AQUI = os.path.dirname(os.path.abspath(__file__))
p = json.load(open(os.path.join(AQUI, "ia10_produtos.json"), encoding="utf-8"))[0]
modo = sys.argv[1]
if modo == "texto":
    for m in ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"]:
        try:
            r = httpx.post("https://router.huggingface.co/v1/chat/completions", timeout=90,
                           headers={"Authorization": f"Bearer {ia_online.TOKEN}"},
                           json={"model": m, "max_tokens": 200, "messages": [{"role": "user", "content": "Diga oi em português em 5 palavras."}]})
            print(m, r.status_code, r.text[:300])
        except Exception as e:
            print(m, "erro", e)
else:
    img = os.path.join(AQUI, "_ia10_img.jpg")
    video2.baixar(p["image_url"], img)
    t = time.time()
    ia_online.anima_foto(img, "a child happily rides this electric drift trike in a sunny park, smooth camera tracking, the trike keeps exactly the same design and colors",
                         os.path.join(AQUI, "_ia10_cena.mp4"), dur=4)
    print("tempo", round(time.time() - t))
