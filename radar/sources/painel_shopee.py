"""Ofertas reais da Shopee coletadas no painel de afiliados (enquanto a Open API não é liberada).

O arquivo data/shopee_painel.json é gerado a partir de "Oferta > Oferta de produto"
no painel affiliate.shopee.com.br, logado na conta de afiliado. Cada link é o
link de afiliado oficial (long_link) do painel, com o seu ID de afiliado.

Quando a Open API for liberada, desligue esta fonte no config.yaml
(fontes.painel_shopee: false) e ligue fontes.shopee.
"""
import json
from pathlib import Path

from ..models import Product

FILE = Path("data/shopee_painel.json")
_cache = None


def available() -> bool:
    return FILE.exists()


def _load() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = json.loads(FILE.read_text(encoding="utf-8"))["produtos"]
    return _cache


def search(query: str, limit: int, cfg: dict) -> list[Product]:
    return [Product(
        source="shopee",
        id=d["id"],
        title=d["title"],
        price=d["price"],
        original_price=d.get("original_price"),
        url=d["url"],
        commission_rate=d["commission_rate"],
        image=d.get("image"),
        sales=d.get("sales"),
        rating=d.get("rating"),
        shop=d.get("shop"),
    ) for d in _load() if d.get("query") == query]
