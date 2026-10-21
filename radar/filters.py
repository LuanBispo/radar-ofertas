"""Mantém só produtos de tecnologia com comissão e qualidade mínimas."""
import unicodedata

from .models import Product

STOPWORDS = {"para", "com", "sem", "inteligente", "completo", "infantil", "portatil", "bancada"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def reason_to_reject(p: Product, f: dict) -> str | None:
    if not p.url:
        return "sem link"
    # lojas internacionais da Shopee costumam ter o nome entre colchetes no início: "[loja] Produto..."
    if p.title.lstrip().startswith("[") and "]" in p.title[:30]:
        return "vendedor do exterior (provável)"
    title = _norm(p.title)
    # tecnologia = contém um termo da lista OU uma palavra significativa da própria busca
    query_words = [w for w in _norm(p.query).split() if len(w) >= 4 and w not in STOPWORDS]
    if not any(_norm(t) in title for t in f["exigir_termos"]) and not any(w in title for w in query_words):
        return "fora do nicho"
    if any(_norm(t) in title for t in f["excluir_termos"]):
        return "termo excluído"
    if p.commission_rate < f["comissao_minima"]:
        return "comissão baixa"
    if not (f["preco_min_brl"] <= p.price <= f["preco_max_brl"]):
        return "preço fora da faixa"
    if p.sales is not None and p.sales < f["vendas_minimas"]:
        return "poucas vendas"
    # Shopee devolve nota 0 quando o produto não tem avaliações: também é descartado.
    # (A busca do Mercado Livre e da Amazon não informa nota; nesses casos o filtro não se aplica.)
    if p.rating is not None and p.rating < f["avaliacao_minima"]:
        return "avaliação baixa ou sem avaliações"
    return None


def dedupe(products: list[Product]) -> list[Product]:
    seen: dict[str, Product] = {}
    for p in products:
        if p.key not in seen or p.price < seen[p.key].price:
            seen[p.key] = p
    return list(seen.values())
