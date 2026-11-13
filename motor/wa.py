"""Conversa com o bot de WhatsApp próprio do IA Shopee (pasta whatsapp/, porta 3101)."""
import json
import os
import urllib.request

URL = os.environ.get("IA_WA_URL", "http://127.0.0.1:3101")


def _post(caminho, dados, timeout=180):
    req = urllib.request.Request(URL + caminho, data=json.dumps(dados).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def status(sessao):
    with urllib.request.urlopen(f"{URL}/status?sessao={sessao}", timeout=10) as r:
        return json.loads(r.read())


def texto(sessao, numero, msg):
    return _post("/texto", {"sessao": sessao, "para": numero, "texto": msg})


def video(sessao, numero, arquivo, legenda=""):
    return _post("/video", {"sessao": sessao, "para": numero, "arquivo": os.path.abspath(arquivo), "legenda": legenda})
