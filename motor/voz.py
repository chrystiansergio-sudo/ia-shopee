"""Voz grátis (Edge-TTS pt-BR) com o tempo de cada palavra, para a legenda sincronizada."""
import asyncio
import random
import subprocess

import edge_tts

VOZES = {"f": ["pt-BR-FranciscaNeural", "pt-BR-ThalitaMultilingualNeural"], "m": ["pt-BR-AntonioNeural"]}


async def _falar(texto, voz, mp3, rate):
    com = edge_tts.Communicate(texto, voz, rate=rate, boundary="WordBoundary")
    palavras = []
    with open(mp3, "wb") as f:
        async for c in com.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                palavras.append({"t": c["offset"] / 1e7, "d": c["duration"] / 1e7, "w": c["text"]})
    return palavras


def falar(texto, wav, genero=None, voz=None, rate="+12%"):
    """Gera `wav` e devolve (voz, lista de palavras com tempo, duração)."""
    voz = voz or random.choice(VOZES[genero or random.choice("fm")])
    mp3 = wav[:-4] + ".mp3"
    for tent in range(3):
        try:
            palavras = asyncio.run(_falar(texto, voz, mp3, rate))
            break
        except Exception as e:  # rede instável: tenta de novo
            print("  aviso voz", e)
            if tent == 2:
                raise
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "44100", "-ac", "2", wav], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                               capture_output=True, text=True).stdout.strip())
    return voz, palavras, dur


if __name__ == "__main__":
    v, p, d = falar("Gente, olha esse achadinho! De R$ 39,43 por apenas R$ 14,59! Corre!", "../saida/teste_voz.wav", "f")
    print(v, round(d, 2), "s")
    for x in p:
        print(round(x["t"], 2), x["w"])
