"""Mercado Livre — API de busca (site MLB).

O ML não tem API pública para gerar link de afiliado: o relatório traz o link
do produto e você gera o link de afiliado no painel/extensão do Programa de
Afiliados. A comissão é estimada pela tabela em config.yaml.

A busca exige um token OAuth. Crie um app em developers.mercadolivre.com.br,
faça o fluxo de autorização uma vez e coloque o refresh token em ML_REFRESH_TOKEN.
O ML troca o refresh token a cada uso; o novo fica salvo em data/ml_token.json.
"""
import json
import os
from pathlib import Path

import requests

from ..models import Product

# ATENÇÃO: o arquivo fica fora do repositório (.gitignore). Antes de ativar o ML no GitHub,
# será preciso guardar o refresh token renovado em outro lugar (ex.: cache do Actions).
TOKEN_FILE = Path("data/ml_token.json")
_access_token = None


def available() -> bool:
    return all(os.getenv(k) for k in ("ML_CLIENT_ID", "ML_CLIENT_SECRET")) and bool(
        TOKEN_FILE.exists() or os.getenv("ML_REFRESH_TOKEN"))


def _token() -> str:
    global _access_token
    if _access_token:
        return _access_token
    refresh = os.getenv("ML_REFRESH_TOKEN")
    if TOKEN_FILE.exists():
        refresh = json.loads(TOKEN_FILE.read_text()).get("refresh_token", refresh)
    r = requests.post("https://api.mercadolibre.com/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": os.environ["ML_CLIENT_ID"],
        "client_secret": os.environ["ML_CLIENT_SECRET"],
        "refresh_token": refresh,
    }, timeout=30)
    r.raise_for_status()
    tok = r.json()
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    _access_token = tok["access_token"]
    return _access_token


def search(query: str, limit: int, cfg: dict) -> list[Product]:
    r = requests.get(
        "https://api.mercadolibre.com/sites/MLB/search",
        params={"q": query, "sort": "price_asc", "limit": limit},
        headers={"Authorization": f"Bearer {_token()}"},
        timeout=30,
    )
    r.raise_for_status()
    rate = cfg["comissao_estimada"]["mercadolivre"]
    out = []
    for it in r.json().get("results", []):
        if it.get("condition") not in (None, "new"):
            continue
        # só vendedores nacionais: descarta compra internacional (CBT / envio do exterior)
        if "cbt_item" in (it.get("tags") or []) or it.get("international_delivery_mode") not in (None, "none"):
            continue
        out.append(Product(
            source="mercadolivre",
            id=it["id"],
            title=it["title"],
            price=float(it["price"]),
            original_price=it.get("original_price"),
            url=it["permalink"],
            commission_rate=rate,
            commission_is_estimate=True,
            image=it.get("thumbnail"),
            sales=it.get("sold_quantity"),
            shop=(it.get("seller") or {}).get("nickname"),
        ))
    return out
