"""Amazon Product Advertising API (Brasil).

A Amazon só libera a API depois de 3 vendas qualificadas em 180 dias como
associado. O link retornado já contém sua tag de afiliado. A comissão é
estimada pela tabela em config.yaml.
"""
import os

from ..models import Product


def available() -> bool:
    return all(os.getenv(k) for k in ("AMAZON_ACCESS_KEY", "AMAZON_SECRET_KEY", "AMAZON_PARTNER_TAG"))


_api = None


def _client():
    global _api
    if _api is None:
        from amazon_paapi import AmazonApi
        _api = AmazonApi(os.environ["AMAZON_ACCESS_KEY"], os.environ["AMAZON_SECRET_KEY"],
                         os.environ["AMAZON_PARTNER_TAG"], "BR", throttling=1.2)
    return _api


def search(query: str, limit: int, cfg: dict) -> list[Product]:
    res = _client().search_items(keywords=query, sort_by="Price:LowToHigh", item_count=min(limit, 10))
    rate = cfg["comissao_estimada"]["amazon"]
    out = []
    for it in res.items or []:
        try:
            listing = it.offers.listings[0]
            price = float(listing.price.amount)
        except (AttributeError, IndexError, TypeError):
            continue
        orig = getattr(getattr(listing, "saving_basis", None), "amount", None)
        try:
            image = it.images.primary.large.url
        except AttributeError:
            image = None
        out.append(Product(
            source="amazon",
            id=it.asin,
            title=it.item_info.title.display_value,
            price=price,
            original_price=float(orig) if orig else None,
            url=it.detail_page_url,
            commission_rate=rate,
            commission_is_estimate=True,
            image=image,
        ))
    return out
