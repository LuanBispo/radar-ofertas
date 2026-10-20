"""Mantém só produtos de tecnologia com comissão e qualidade mínimas."""
import unicodedata

from .models import Product


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def reason_to_reject(p: Product, f: dict) -> str | None:
    if not p.url:
        return "sem link"
    title = _norm(p.title)
    if not any(_norm(t) in title for t in f["exigir_termos"]):
        return "fora do nicho"
    if any(_norm(t) in title for t in f["excluir_termos"]):
        return "termo excluído"
    if p.commission_rate < f["comissao_minima"]:
        return "comissão baixa"
    if not (f["preco_min_brl"] <= p.price <= f["preco_max_brl"]):
        return "preço fora da faixa"
    if p.sales is not None and p.sales < f["vendas_minimas"]:
        return "poucas vendas"
    if p.rating and p.rating < f["avaliacao_minima"]:
        return "avaliação baixa"
    return None


def dedupe(products: list[Product]) -> list[Product]:
    seen: dict[str, Product] = {}
    for p in products:
        if p.key not in seen or p.price < seen[p.key].price:
            seen[p.key] = p
    return list(seen.values())
