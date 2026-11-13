"""Trilha e efeitos sintetizados (originais, sem direitos de terceiros)."""
import wave
import numpy as np

SR = 44100
rng = np.random.default_rng(42)


def _t(d):
    return np.arange(int(d * SR)) / SR


def banda(x, lo, hi):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.clip(np.minimum((f - lo * .8) / (lo * .2 + 1e-9), (hi * 1.2 - f) / (hi * .2 + 1e-9)), 0, 1)
    return np.fft.irfft(X * m, n)


def norm(x, pico):
    m = np.max(np.abs(x)) + 1e-12
    return x / m * pico


def env_ad(n, ataque=.005, queda=6.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(ataque, 1e-4), 0, 1)
    return a * np.exp(-t * queda)


# ---------------- instrumentos ----------------
def kick(forte=1.0):
    t = _t(.38)
    f = 46 + 120 * np.exp(-t * 30)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    y += rng.standard_normal(len(t)) * np.exp(-t * 380) * .2
    return norm(y, .95 * forte)


def clap():
    t = _t(.28)
    n = banda(rng.standard_normal(len(t)), 900, 4200)
    e = np.exp(-t * 20) * .7
    for o in (0, .011, .022):
        i = int(o * SR)
        e[i:] += np.exp(-t[:len(t) - i] * 110) * .5
    return norm(n * e, .55)


def hat(aberto=False):
    t = _t(.22 if aberto else .06)
    n = banda(rng.standard_normal(len(t)), 7000, 15000)
    return norm(n * np.exp(-t * (16 if aberto else 75)), .3 if aberto else .26)


def baixo(f, d):
    t = _t(d)
    y = np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t) + .12 * np.sin(6 * np.pi * f * t)
    e = np.clip(t / .006, 0, 1) * (.55 + .45 * np.exp(-t * 9))
    r = int(.03 * SR)
    e[-r:] *= np.linspace(1, 0, r)
    return norm(y * e, .55)


def pad(freqs, d):
    t = _t(d)
    L = np.zeros_like(t)
    R = np.zeros_like(t)
    for f in freqs:
        for h in range(1, 6):
            L += np.sin(2 * np.pi * f * h * .997 * t) / h ** 1.3
            R += np.sin(2 * np.pi * f * h * 1.003 * t + .7) / h ** 1.3
    e = np.clip(t / .35, 0, 1) * np.clip((d - t) / .35, 0, 1)
    return np.stack([L * e, R * e], 1) / (len(freqs) * 2.2)


def pluck(f, d=.45):
    t = _t(d)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 9) + .3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 15) + .1 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 22)
    y *= np.clip(t / .003, 0, 1)
    return norm(y, .5)


# ---------------- efeitos ----------------
def sino(f, d=.6, queda=7):
    t = _t(d)
    y = np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) + .12 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 12)
    return y * np.exp(-t * queda) * np.clip(t / .002, 0, 1)


def ding(f=1318.5):
    a = sino(f, .7)
    b = sino(f * 1.335, .7)
    y = np.zeros(int(.82 * SR))
    y[:len(a)] += a
    i = int(.1 * SR)
    y[i:i + len(b)] += b
    return norm(y, .42)


def moeda():
    a, b = sino(1975, .5, 10), sino(2637, .7, 8)
    y = np.zeros(int(.8 * SR))
    y[:len(a)] += a
    i = int(.07 * SR)
    y[i:i + len(b)] += b
    return norm(y, .4)


def pop(f0=900):
    t = _t(.09)
    f = f0 * np.exp(-t * 25) + 180
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45), .5)


def tique():
    t = _t(.035)
    return norm(np.sin(2 * np.pi * 2300 * t) * np.exp(-t * 150), .25)


def _varre(d, f0, f1, ganho):
    n = int(d * SR)
    x = rng.standard_normal(n + 2048)
    y = np.zeros(n + 2048)
    tam, passo = 2048, 512
    w = np.hanning(tam)
    for i in range(0, n, passo):
        p = i / n
        fc = f0 * (f1 / f0) ** p
        seg = banda(x[i:i + tam] * w, fc * .6, fc * 1.6)
        y[i:i + tam] += seg * w
    y = y[:n]
    t = np.arange(n) / n
    return y * ganho(t)


def whoosh(d=.45, sobe=True):
    y = _varre(d, 350 if sobe else 5000, 5000 if sobe else 350, lambda p: np.sin(np.pi * p) ** 1.5)
    return norm(y, .38)


def riser(d=1.2):
    y = _varre(d, 300, 7000, lambda p: p ** 2)
    t = _t(d)
    f = 160 * (6 ** (t / d))
    y = norm(y, 1) + .25 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / d) ** 2
    return norm(y, .32)


def boom():
    t = _t(1.7)
    f = 36 + 75 * np.exp(-t * 8)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    y += banda(rng.standard_normal(len(t)), 40, 400) * np.exp(-t * 5) * .5
    return norm(y, .95)


def impacto():
    k = kick()
    t = _t(len(k) / SR)
    n = banda(rng.standard_normal(len(t)), 250, 3000) * np.exp(-t * 16)
    return norm(k + norm(n, .45), .9)


def carimbo():
    t = _t(.26)
    f = 70 + 140 * np.exp(-t * 40)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)
    y += banda(rng.standard_normal(len(t)), 150, 1800) * np.exp(-t * 32) * .7
    return norm(y, .8)


EFEITOS = {"ding": ding, "moeda": moeda, "pop": pop, "tique": tique, "whoosh": whoosh, "riser": riser,
           "boom": boom, "impacto": impacto, "carimbo": carimbo}

# Lá menor: Am - F - C - G
ACORDES = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
RAIZES = [110.0, 87.31, 130.81, 98.0]


def _soma(buf, x, t):
    i = int(round(t * SR))
    if i >= len(buf):
        return
    x = x[:len(buf) - i]
    if x.ndim == 1:
        buf[i:i + len(x)] += x[:, None]
    else:
        buf[i:i + len(x)] += x


def musica(T, cfg):
    """cfg: bpm, partes=[(t0, t1, {'kick','clap','hat','ohat','baixo','pad','pluck'})]"""
    bpm = cfg.get("bpm", 120)
    b = 60 / bpm
    N = int(T * SR)
    out = np.zeros((N, 2))
    partes = cfg.get("partes", [])

    def ativo(t, inst):
        return any(t0 <= t < t1 and inst in s for t0, t1, s in partes)

    nb = int(T / b) + 1
    for i in range(nb):
        tb = i * b
        ac = (i // 4) % 4
        if ativo(tb, "kick"):
            _soma(out, kick() * .9, tb)
        if ativo(tb, "clap") and i % 4 in (1, 3):
            _soma(out, clap() * .8, tb)
        if ativo(tb, "hat"):
            _soma(out, hat() * .8, tb)
            _soma(out, hat() * .55, tb + b / 2)
        if ativo(tb, "ohat"):
            _soma(out, hat(True) * .5, tb + b / 2)
        if ativo(tb, "baixo"):
            r = RAIZES[ac]
            _soma(out, baixo(r, b / 2 * .9) * .8, tb)
            _soma(out, baixo(r * (2 if i % 2 else 1), b / 2 * .9) * .7, tb + b / 2)
        if ativo(tb, "pluck"):
            notas = ACORDES[ac]
            seq = [notas[0] * 2, notas[1] * 2, notas[2] * 2, notas[1] * 2]
            _soma(out, pluck(seq[i % 4]) * .55, tb)
            _soma(out, pluck(seq[(i + 2) % 4] * (2 if i % 2 else 1)) * .35, tb + b / 2)
        if i % 4 == 0 and ativo(tb, "pad"):
            _soma(out, pad(ACORDES[ac], 4 * b + .3) * .9, tb)
    return out


def gerar(caminho, T, cfg, sons):
    N = int(T * SR)
    mus = musica(T, cfg) if cfg else np.zeros((N, 2))
    sfx = np.zeros((N, 2))
    for t, tipo, kw in sons:
        _soma(sfx, EFEITOS[tipo](**kw), t)
    mix = mus * cfg.get("vol", .5) + sfx * .85
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix = norm(mix, .89)
    f = int(.3 * SR)
    mix[-f:] *= np.linspace(1, 0, f)[:, None]
    mix[:int(.004 * SR)] *= np.linspace(0, 1, int(.004 * SR))[:, None]
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(caminho, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    rms = 20 * np.log10(np.sqrt(np.mean(mix ** 2)) + 1e-12)
    print(f"audio {caminho.split(chr(92))[-1]}: rms {rms:.1f} dBFS")
