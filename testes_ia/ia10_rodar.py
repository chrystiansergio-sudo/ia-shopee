"""Faz e manda os vídeos do teste IA-10, um por um (de/até índice)."""
import os, subprocess, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
de, ate = int(sys.argv[1]), int(sys.argv[2])
env = dict(os.environ, PYTHONIOENCODING="utf-8")
for i in range(de, ate + 1):
    r = subprocess.run([sys.executable, os.path.join(AQUI, "ia10_fazer.py"), str(i)], cwd=AQUI, env=env, capture_output=True, text=True, encoding="utf-8")
    linhas = [l for l in (r.stdout + r.stderr).splitlines() if not l.startswith("  aviso busca")]
    print(f"== vídeo {i + 1}:", *linhas[-3:], sep="\n", flush=True)
    if r.returncode == 0:
        s = subprocess.run([sys.executable, os.path.join(AQUI, "ia10_enviar.py"), str(i + 1)], cwd=AQUI, env=env, capture_output=True, text=True, encoding="utf-8")
        print((s.stdout + s.stderr).strip()[-300:], flush=True)
