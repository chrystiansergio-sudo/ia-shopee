"""Vozes do vídeo v2: Edge-TTS (grátis), voz clonada do dono (Chatterbox, MIT) e gravações reais do dono.
Todas devolvem: wav 44.1 kHz estéreo + lista de palavras com tempo (para a legenda)."""
import json
import os
import random
import re
import shutil
import subprocess

import voz
from peneira import RAIZ, env

GRAV = os.path.join(RAIZ, "gravacoes")
_whisper = None


def _modelo():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper


def palavras_whisper(wav):
    segs, _ = _modelo().transcribe(wav, language="pt", word_timestamps=True, vad_filter=False)
    out = []
    for s in segs:
        for w in (s.words or []):
            txt = w.word.strip()
            if txt:
                out.append({"t": float(w.start), "d": float(w.end - w.start), "w": txt})
    return out


def alinhar(texto, wav):
    """legenda com o TEXTO CERTO: usa o Whisper só para saber onde a fala começa e termina,
    e distribui as palavras do texto original nesse intervalo (pelo tamanho de cada palavra)."""
    ws = palavras_whisper(wav)
    total = duracao(wav)
    ini = ws[0]["t"] if ws else 0.05
    fim = (ws[-1]["t"] + ws[-1]["d"]) if ws else total - .05
    palavras = texto.split()
    pesos = [len(w) + 2 for w in palavras]
    soma = sum(pesos) or 1
    out, t = [], ini
    for w, pz in zip(palavras, pesos):
        d = (fim - ini) * pz / soma
        out.append({"t": t, "d": d * .9, "w": w})
        t += d
    return out


def duracao(wav):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                capture_output=True, text=True).stdout.strip())


def _para_wav(src, wav, extra=None):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src]
    if extra:
        cmd += ["-af", extra]
    subprocess.run(cmd + ["-ar", "44100", "-ac", "2", wav], check=True)


# ---------------------------------------------------------------- Edge-TTS
def edge(texto, wav, voz_nome):
    _, pal, dur = voz.falar(texto, wav, voz=voz_nome)
    return pal, dur


# ---------------------------------------------------------------- números por extenso (para a voz clonada)
def _extenso(n):
    from num2words import num2words
    return num2words(n, lang="pt_BR")


def por_extenso(t):
    def reais(m):
        i, c = int(m.group(1).replace(".", "")), int(m.group(2) or 0)
        s = f"{_extenso(i)} rea{'l' if i == 1 else 'is'}"
        return s + (f" e {_extenso(c)}" if c else "")
    t = re.sub(r"R\$\s*([\d.]+),(\d{2})", reais, t)
    t = re.sub(r"(\d+)%", lambda m: f"{_extenso(int(m.group(1)))} por cento", t)
    t = re.sub(r"(\d+),(\d)", lambda m: f"{_extenso(int(m.group(1)))} vírgula {_extenso(int(m.group(2)))}", t)
    t = re.sub(r"\d+", lambda m: _extenso(int(m.group(0))), t)
    return t


def clonada(texto, wav, tentativas=2):
    """voz do dono clonada (Chatterbox Multilingual no Hugging Face)"""
    env()
    from gradio_client import Client, handle_file
    amostra = os.path.join(GRAV, "amostra_voz.wav")
    c = Client("ResembleAI/Chatterbox-Multilingual-TTS", token=os.environ.get("HF_TOKEN"), verbose=False)
    ult = None
    for _ in range(tentativas):
        try:
            r = c.predict(text_input=por_extenso(texto), language_id="pt", audio_prompt_path_input=handle_file(amostra),
                          exaggeration_input=0.55, temperature_input=0.7, seed_num_input=random.randint(1, 9999), cfgw_input=0.5,
                          api_name="/generate_tts_audio")
            src = r if isinstance(r, str) else r[0]
            _para_wav(src, wav, "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm")
            return alinhar(texto, wav), duracao(wav)
        except Exception as e:
            ult = e
    raise RuntimeError(f"voz clonada falhou: {ult}")


# ---------------------------------------------------------------- gravações reais do dono
def gravacoes(tipo="gancho"):
    p = os.path.join(GRAV, "transcricoes.json")
    if not os.path.exists(p):
        return []
    return [g for g in json.load(open(p, encoding="utf-8")) if g.get("tipo") == tipo]


def gravacao(g, wav):
    src = os.path.join(RAIZ, g["arquivo"])
    ini, fim = max(0, g["ini"] - .05), g["fim"] + .15
    _para_wav(src, wav, f"atrim={ini}:{fim},asetpts=PTS-STARTPTS,loudnorm")
    return alinhar(g["texto"], wav), duracao(wav)
