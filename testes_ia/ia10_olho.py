"""IA que OLHA a foto (grátis no Hugging Face): diz se a foto é limpa (só o produto, sem texto/selos/montagem)."""
import base64, os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
import httpx, ia_online

PERG = ("Look at this e-commerce product photo. Answer with ONE word: CLEAN if it shows only the product (and maybe a plain "
        "background or a single real setting) with NO added text, NO numbers, NO badges, NO arrows, NO collage of several panels. "
        "Otherwise answer TEXT.")


def foto_ok(url_ou_arq):
    if os.path.exists(url_ou_arq):
        b = open(url_ou_arq, "rb").read()
    else:
        b = urllib.request.urlopen(urllib.request.Request(url_ou_arq, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
    data = "data:image/jpeg;base64," + base64.b64encode(b).decode()
    for modelo in ["Qwen/Qwen2.5-VL-72B-Instruct", "Qwen/Qwen2.5-VL-32B-Instruct", "meta-llama/Llama-4-Scout-17B-16E-Instruct"]:
        try:
            r = httpx.post("https://router.huggingface.co/v1/chat/completions", timeout=90,
                           headers={"Authorization": f"Bearer {ia_online.TOKEN}"},
                           json={"model": modelo, "max_tokens": 5, "temperature": 0,
                                 "messages": [{"role": "user", "content": [{"type": "text", "text": PERG},
                                                                           {"type": "image_url", "image_url": {"url": data}}]}]})
            txt = r.json()["choices"][0]["message"]["content"].strip().upper()
            return txt.startswith("CLEAN"), modelo
        except Exception as e:
            print("aviso olho", modelo, str(e)[:120])
    raise RuntimeError("nenhuma IA de visão respondeu")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(a[-40:], foto_ok(a))
