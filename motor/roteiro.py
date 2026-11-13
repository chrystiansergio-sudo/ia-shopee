"""Roteiro, legenda e hashtags a partir dos dados do produto (sem IA paga, sem tokens)."""
import random
import re

PARAR = {"kit", "pcs", "pç", "peças", "pecas", "unid", "un", "und", "unidades", "com", "para", "de", "do", "da",
         "e", "em", "até", "ate", "x", "a", "o", "novo", "nova", "original", "promoção", "oferta", "envio", "imediato", "pronta", "entrega"}


TIPOS = ("creme", "sérum", "serum", "esponja", "palmilha", "tênis", "tenis", "bolsa", "vestido", "brinco", "colar", "sandália",
         "sandalia", "batom", "paleta", "máscara", "mascara", "base", "corretivo", "pincel", "escova", "massageador", "joelheira",
         "corretor", "termômetro", "termometro", "oxímetro", "oximetro", "comedouro", "bebedouro", "cama", "coleira", "peitoral",
         "tapete", "organizador", "organizadora", "garrafa", "fone", "carregador", "cabo", "suporte", "luminária", "luminaria",
         "capa", "relógio", "relogio", "mochila", "carteira", "óculos", "oculos", "blusa", "saia", "cropped", "conjunto", "cílios", "cilios", "extensão", "extensões", "pente", "shampoo", "hidratante", "perfume", "kit")


def nome_curto(titulo, max_palavras=4):
    # começa no tipo do produto quando o título abre com marca/código ("Numudin No 9 NAD ... Creme Para Olhos")
    ws = titulo.split()
    primeira = ws[0].lower().strip(",.-") if ws else ""
    for i, w in enumerate(ws[:10]):
        if primeira in TIPOS and primeira != "kit":
            break
        if 0 < i and w.lower().strip(",.-") in TIPOS and w.lower() != "kit":
            titulo = " ".join(ws[i:])
            break
    t = re.sub(r"[\[\(\{【].*?[\]\)\}】]", " ", titulo)
    t = re.sub(r"\b\d+([/,.x-]\d+)*\s*(pcs|pç|unid|un|und|peças|pecas|cm|ml|l|g|kg|m|w|mah|x)?\b", " ", t, flags=re.I)
    t = re.sub(r"[^\wÀ-ÿ ]", " ", t)
    palavras = [p for p in t.split() if len(p) > 1]
    out = []
    for p in palavras:
        if p.lower() in PARAR and not out:
            continue
        out.append(p)
        if len(out) == max_palavras:
            break
    while out and out[-1].lower() in PARAR:
        out.pop()
    s = " ".join(out).lower() or "esse achadinho"
    return s[0].upper() + s[1:]


def reais(v):
    i, c = int(v), round((v - int(v)) * 100)
    return f"R$ {i},{c:02d}"


def vendas_txt(n):
    if n >= 1000:
        k = n // 1000
        return f"mais de {k} mil vendidos"
    return f"mais de {n // 100 * 100 or n} vendidos"


GANCHOS = {
    "achado": ["Gente, olha esse achadinho!", "Achei o achadinho do mês!", "Para tudo e olha isso!", "Que achado, gente!"],
    "nao_compre": ["Não compre antes de ver isso!", "Pare de pagar caro nisso!", "Ninguém te conta isso da Shopee!"],
    "preco": ["Você não vai acreditar nesse preço!", "Olha o preço disso, gente!", "Isso aqui tá quase de graça!"],
    "presente": ["Achei o presente perfeito!", "Quer um presente que todo mundo ama?", "Presente barato e que impressiona!"],
    "produto_fala": ["Oi! Me leva pra casa?", "Ei, você! Olha pra mim!", "Psiu! Tô em promoção!"],
}
CTAS = ["Toca no produto aqui embaixo antes que acabe!", "Clica no produto marcado e garante o seu!",
        "O link tá aqui no vídeo, corre!", "Toca no carrinho e aproveita o desconto!", "Corre que esse preço não dura!"]


NICHOS_OBJETO = {"casa e cozinha", "organizacao", "limpeza", "eletronicos", "carro", "ferramentas", "papelaria", "casa e decoracao"}
PALAVRAS_PESSOA = ("touca", "cabelo", "roupa", "pijama", "vestido", "blusa", "biquini", "maquiagem", "cilios", "unha", "skincare",
                   "serum", "legging", "short", "calça", "camiseta", "bone", "oculos", "meia", "academia")


def nicho_da_palavra(palavra):
    import json
    import os
    try:
        nichos = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "nichos.json"), encoding="utf-8"))
    except OSError:
        return ""
    return next((n for n, ws in nichos.items() if palavra in ws), "")


def estilos_possiveis(p):
    palavra = (p.get("palavra") or "").lower()
    titulo = p.get("title", "").lower()
    presente_ok = any(w in palavra for w in
                      ("bolsa", "relogio", "perfume", "fone", "smartwatch", "caixa de som", "skincare", "maquiagem", "luminaria", "oculos", "carteira"))
    # produto falante só em objetos (evita pôr boca em cima de pessoa da foto)
    fala_ok = nicho_da_palavra(palavra) in NICHOS_OBJETO and not any(w in titulo for w in PALAVRAS_PESSOA)
    return [e for e in GANCHOS if (e != "presente" or presente_ok) and (e != "produto_fala" or fala_ok)]


def montar(p, estilo=None, evitar=()):
    if not estilo:
        ops = estilos_possiveis(p)
        estilo = random.choice([e for e in ops if e not in evitar] or ops)
    nome = nome_curto(p["title"])
    preco = reais(p["price"])
    de = reais(p["original_price"]) if p.get("original_price") else None
    gancho = random.choice(GANCHOS[estilo])
    vend = vendas_txt(p["sold"])
    nota = f"{p['rating']:.1f}".replace(".", ",")
    if estilo == "produto_fala":
        corpo = [f"Eu sou {nome.lower()} e tô com {p['discount']}% de desconto!",
                 f"Já tenho {vend} e nota {nota} de 5.",
                 f"Hoje eu saio por só {preco}."]
    elif estilo == "nao_compre":
        corpo = [f"Esse {nome.lower()} tá com {p['discount']}% de desconto.",
                 f"Já são {vend}, nota {nota}.",
                 (f"De {de} por só {preco}!" if de else f"Por só {preco}!")]
    elif estilo == "presente":
        corpo = [f"{nome}, com {p['discount']}% de desconto.",
                 f"Nota {nota} e {vend}.",
                 f"Sai por só {preco}."]
    else:
        corpo = [f"{nome} com {p['discount']}% de desconto!",
                 f"Já tem {vend} e nota {nota}.",
                 (f"De {de} por apenas {preco}!" if de else f"Apenas {preco}!")]
    cta = random.choice(CTAS)
    falas = [gancho] + corpo + [cta]
    return {"estilo": estilo, "nome": nome, "falas": falas, "preco": preco, "de": de}


TAGS_BASE = ["#achadinhos", "#shopee", "#achadinhosdashopee", "#promoção", "#oferta", "#comprinhas"]


def legenda(p, r, nicho):
    tag_nicho = "#" + re.sub(r"[^a-z0-9]", "", (p.get("palavra") or nicho or "").lower().replace(" ", ""))[:25]
    tags = TAGS_BASE[:] + ([tag_nicho] if len(tag_nicho) > 2 else [])
    random.shuffle(tags)
    emoji = random.choice(["🔥", "😱", "🛒", "💥", "✨"])
    linhas = [f"{emoji} {r['nome']} com {p['discount']}% OFF!",
              (f"De {r['de']} por {r['preco']}" if r["de"] else f"Por {r['preco']}") + f" • ⭐ {p['rating']:.1f}",
              "👇 Toque no produto marcado no vídeo",
              " ".join(tags[:7])]
    return "\n".join(linhas)


if __name__ == "__main__":
    ex = {"title": "Kit 5 Suporte Organizador de Vassoura Rodo Mop Utensílios", "price": 14.59, "original_price": 39.43,
          "discount": 63, "sold": 2882, "rating": 4.7, "palavra": "rodo"}
    for e in GANCHOS:
        r = montar(ex, e)
        print(e, "|", " ".join(r["falas"]))
    print()
    print(legenda(ex, r, "limpeza"))


# ======================================================================= roteiro v2
BENEFICIOS = {
    "casa e cozinha": ["Deixa a cozinha muito mais prática.", "Facilita demais o dia a dia na cozinha.", "Aquele item que faz falta e ninguém lembra de comprar."],
    "organizacao": ["Deixa tudo organizado e no lugar.", "Ganha espaço e acaba com a bagunça.", "Organização bonita e sem gastar muito."],
    "limpeza": ["Deixa a limpeza muito mais rápida.", "Economiza tempo na faxina.", "Limpeza fácil, sem esforço."],
    "maquiagem": ["Make bonita gastando pouco.", "Acabamento lindo no dia a dia.", "Item que não pode faltar na necessaire."],
    "saude": ["Cuida do seu bem-estar no dia a dia.", "Alívio e conforto gastando pouco.", "Ótimo pra ter em casa."],
    "beleza": ["Ótimo pra sua rotina de cuidados.", "Um mimo que vale cada centavo.", "Fica lindo no dia a dia."],
    "moda": ["Combina com tudo.", "Estilo bonito por um preço baixo.", "Aquele item que eleva qualquer look."],
    "eletronicos": ["Muito útil no dia a dia.", "Tecnologia boa sem pesar no bolso.", "Praticidade que você vai usar todo dia."],
    "pet": ["Seu pet merece esse conforto.", "Facilita a rotina com o seu pet.", "Quem tem pet sabe como isso ajuda."],
    "fitness": ["Ótimo pra treinar em casa.", "Ajuda a manter o foco no treino.", "Treino mais completo gastando pouco."],
    "casa e decoracao": ["Deixa a casa mais aconchegante.", "Muda a cara do ambiente.", "Decoração bonita sem gastar muito."],
    "carro": ["Deixa o carro mais prático e organizado.", "Item que todo motorista precisa.", "Mais conforto no seu carro."],
    "ferramentas": ["Resolve aquele reparo em casa.", "Ferramenta que faz falta na hora certa.", "Prática e fácil de usar."],
    "bebe e infantil": ["Facilita a rotina com as crianças.", "Prático pro dia a dia da família."],
    "papelaria": ["Deixa os estudos mais organizados.", "Perfeito pra escola ou trabalho."],
    "viagem": ["Viagem muito mais organizada.", "Item indispensável na mala."],
}
GANCHOS_TTS = ["Gente, olha esse achadinho!", "Para tudo e olha isso!", "Que achado, gente!", "Você não vai acreditar nesse preço!",
               "Olha o que eu achei na Shopee!", "Isso aqui tá barato demais!", "Não compre antes de ver isso!", "Olha que coisa mais útil!"]
GANCHOS_PET = ["Quem tem pet precisa ver isso!", "Olha esse achado pro seu pet!", "Seu cachorro vai adorar isso!", "Achadinho pra quem ama pet!"]
CTAS_TTS = ["Toca no produto aqui embaixo antes que acabe!", "Clica no produto marcado e garante o seu!",
            "Toca no carrinho e aproveita o desconto!", "Corre que esse preço não dura!"]


def nicho_de(p, nicho):
    return nicho_da_palavra((p.get("palavra") or "").lower()) or nicho


ABRE_PRECO = ["Achado! Só {preco}!", "Olha esse achado: só {preco}!", "Achadinho por só {preco}!", "Só {preco}, gente!"]


def montar2(p, formato, nicho):
    """Falas em ordem: PREÇO primeiro (abre), gancho, 2 de corpo e chamada final.
    Regra do dono: o preço é sempre a primeira coisa falada e mostrada."""
    n = nicho_de(p, nicho)
    nome = nome_curto(p["title"])
    preco = reais(p["price"])
    de = reais(p["original_price"]) if p.get("original_price") else None
    nota = f"{p['rating']:.1f}".replace(".", ",")
    vend = vendas_txt(p["sold"])
    benef = random.choice(BENEFICIOS.get(n, ["Muito útil no dia a dia."]))
    abre = random.choice(ABRE_PRECO).format(preco=preco) + f" {nome} com {p['discount']}% de desconto."
    corpo = [f"{benef} Nota {nota} e {vend}.",
             (f"Antes custava {de}, agora sai por {preco}!" if de else f"Tá saindo por só {preco}!")]
    if formato == "cachorro":
        gancho = random.choice(GANCHOS_PET)
    else:
        gancho = random.choice(GANCHOS_TTS)
    return {"nome": nome, "preco": preco, "de": de, "nicho": n, "abre": abre, "gancho": gancho, "corpo": corpo,
            "cta": random.choice(CTAS_TTS), "economia": (reais(p["original_price"] - p["price"]) if de else None)}


ELOGIOS = ["Qualidade que surpreende pelo preço.", "Bonito, prático e funciona de verdade.", "Um daqueles achados que vale cada centavo.",
           "Material caprichado e fácil de usar.", "Quem compra não se arrepende.", "Simples, útil e muito bem feito."]


def _tag(txt):
    import unicodedata
    t = unicodedata.normalize("NFKD", (txt or "").lower()).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]", "", t)[:25]
    return "#" + t if len(t) > 2 else ""


def legenda2(p, r, formato):
    """Regra do dono: nome do produto + texto dizendo que é bom + só 5 hashtags no fim
    (sem vendas/nota/preço; poucas hashtags para não arriscar a conta)."""
    emoji = random.choice(["🔥", "✨", "🛒", "💥", "😍"])
    ws = [w for w in r["nome"].split() if w.lower() not in PARAR]
    benef = random.sample(BENEFICIOS.get(r["nicho"], ["Muito útil no dia a dia."]), k=min(2, len(BENEFICIOS.get(r["nicho"], [1]))))
    tags = []
    tipo = _tag(ws[0]) if ws and ws[0].lower() in TIPOS else ""  # "#porta" sozinho não serve; "#creme" serve
    for t in [_tag("".join(ws[:2])) if len(ws) > 1 else "", tipo, _tag(r["nicho"]),
              "#achadinhosdashopee", "#shopee", "#achadinhos", "#oferta"]:
        if t and t not in tags:
            tags.append(t)
    linhas = [f"{emoji} {r['nome']}", "", " ".join(benef) + " " + random.choice(ELOGIOS),
              "👇 Toque no produto marcado no vídeo", "", "Publi · conteúdo feito com IA", " ".join(tags[:5])]
    return "\n".join(linhas)
