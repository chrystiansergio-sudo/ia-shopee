import sys, time, peneira, video, json
ps = peneira.escolher("teste", sys.argv[1] if len(sys.argv)>1 else "todos", int(sys.argv[2]) if len(sys.argv)>2 else 1)
estilos = sys.argv[3].split(",") if len(sys.argv)>3 else [None]*len(ps)
for i,p in enumerate(ps):
    t=time.time()
    info = video.fazer(p, "todos", f"../saida/teste_{i}.mp4", estilo=estilos[i % len(estilos)])
    print(f"ok {i} {time.time()-t:.0f}s", info["roteiro"]["estilo"], info["voz"], info["clipe"], info["duracao"])
    print(info["legenda"])
