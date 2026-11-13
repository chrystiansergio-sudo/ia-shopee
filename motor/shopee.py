"""Cliente mínimo da Shopee Affiliate Open API (Brasil).

Credenciais (AppID + Secret) são liberadas no painel de afiliado:
https://affiliate.shopee.com.br  ->  Open API.

Os links retornados em `offerLink` / `shortLink` JÁ são links de afiliado
da sua conta (as comissões caem para você).
"""
import hashlib
import json
import os
import time
import urllib.request
import urllib.error

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"


class ShopeeError(Exception):
    pass


def _q(value):
    """Escapa um valor para ser embutido na query GraphQL."""
    return json.dumps(value, ensure_ascii=False)


def _call(app_id, secret, query):
    if not app_id or not secret:
        raise ShopeeError("SHOPEE_APP_ID / SHOPEE_SECRET não configurados no .env")
    payload = json.dumps({"query": query}, separators=(",", ":"), ensure_ascii=False)
    ts = str(int(time.time()))
    signature = hashlib.sha256((app_id + ts + payload + secret).encode("utf-8")).hexdigest()
    req = urllib.request.Request(
        ENDPOINT,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={signature}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ShopeeError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
    except urllib.error.URLError as e:
        raise ShopeeError(f"Falha de conexão: {e.reason}") from e
    if data.get("errors"):
        err = data["errors"][0]
        code = (err.get("extensions") or {}).get("code", "")
        raise ShopeeError(f"{code} {err.get('message', err)}".strip())
    return data.get("data") or {}


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def search(app_id, secret, keyword, sort=2, limit=30, page=1):
    """Busca ofertas por palavra-chave.

    sort: 1=relevância, 2=mais vendidos, 3=maior preço, 4=menor preço, 5=maior comissão
    Retorna lista de dicts normalizados (já com link de afiliado).
    """
    if os.environ.get("SHOPEE_SIMULADO") == "1":
        return [{"item_id": f"sim-{keyword}-{page}-{i}", "title": f"Oferta simulada {keyword} {page}-{i}",
                 "price": 49.9, "original_price": 99.8, "discount": 50, "link": f"https://s.shopee.com.br/sim{page}{i}",
                 "image_url": "", "shop": "Loja Simulada", "rating": 4.9, "sold": 1000, "commission": 0.1}
                for i in range(5)]
    query = (
        "{ productOfferV2(keyword: %s, sortType: %d, page: %d, limit: %d) {"
        " nodes { itemId productName price priceMin priceDiscountRate imageUrl"
        " offerLink productLink commissionRate sales ratingStar shopName }"
        " pageInfo { page limit hasNextPage } } }"
    ) % (_q(keyword), int(sort), int(page), int(limit))
    data = _call(app_id, secret, query)
    nodes = ((data.get("productOfferV2") or {}).get("nodes")) or []
    out = []
    for n in nodes:
        price = _f(n.get("priceMin") or n.get("price"))
        disc = int(_f(n.get("priceDiscountRate")))
        original = round(price / (1 - disc / 100), 2) if 0 < disc < 100 else None
        out.append({
            "item_id": "" if n.get("itemId") is None else str(n.get("itemId")),
            "title": (n.get("productName") or "").strip(),
            "price": price,
            "original_price": original,
            "discount": disc,
            "link": n.get("offerLink") or "",
            "product_link": n.get("productLink") or "",
            "image_url": n.get("imageUrl") or "",
            "shop": n.get("shopName") or "",
            "rating": _f(n.get("ratingStar")),
            "sold": int(_f(n.get("sales"))),
            "commission": _f(n.get("commissionRate")),
        })
    return out


def short_link(app_id, secret, origin_url, sub_id="whatsapp"):
    """Converte qualquer link de produto da Shopee em link de afiliado seu."""
    query = 'mutation { generateShortLink(input: { originUrl: %s, subIds: [%s] }) { shortLink } }' % (
        _q(origin_url), _q(sub_id))
    data = _call(app_id, secret, query)
    link = (data.get("generateShortLink") or {}).get("shortLink")
    if not link:
        raise ShopeeError("A Shopee não retornou shortLink")
    return link
