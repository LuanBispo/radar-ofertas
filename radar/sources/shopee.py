"""Shopee Affiliate Open API (Brasil).

Credenciais: painel affiliate.shopee.com.br > Open API (AppID e Secret).
Retorna comissão real por produto e `offerLink`, que já é o seu link de afiliado.
"""
import hashlib
import json
import os
import time

import requests

from ..models import Product

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

QUERY = """
query($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
    nodes {
      itemId productName price priceMin priceMax priceDiscountRate
      commissionRate sales ratingStar imageUrl shopName offerLink productLink
    }
  }
}
"""

SORT_PRICE_ASC = 4


def available() -> bool:
    return bool(os.getenv("SHOPEE_APP_ID") and os.getenv("SHOPEE_SECRET"))


def _headers(payload: str) -> dict:
    app_id, secret = os.environ["SHOPEE_APP_ID"], os.environ["SHOPEE_SECRET"]
    ts = str(int(time.time()))
    sig = hashlib.sha256(f"{app_id}{ts}{payload}{secret}".encode()).hexdigest()
    return {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={sig}",
    }


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def search(query: str, limit: int, cfg: dict) -> list[Product]:
    body = {"query": QUERY, "variables": {"keyword": query, "sortType": SORT_PRICE_ASC, "page": 1, "limit": limit}}
    payload = json.dumps(body, separators=(",", ":"))
    r = requests.post(ENDPOINT, data=payload, headers=_headers(payload), timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])

    out = []
    for n in data["data"]["productOfferV2"]["nodes"]:
        price = _float(n.get("priceMin")) or _float(n.get("price"))
        if not price:
            continue
        disc = _float(n.get("priceDiscountRate")) or 0  # inteiro em %, ex.: 25
        out.append(Product(
            source="shopee",
            id=str(n["itemId"]),
            title=n["productName"],
            price=price,
            original_price=round(price / (1 - disc / 100), 2) if 0 < disc < 100 else None,
            url=n.get("offerLink") or n.get("productLink"),
            commission_rate=_float(n.get("commissionRate")) or 0.0,
            image=n.get("imageUrl"),
            sales=n.get("sales"),
            rating=_float(n.get("ratingStar")),
            shop=n.get("shopName"),
        ))
    return out
