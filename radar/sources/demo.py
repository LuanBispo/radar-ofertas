"""Fonte fictícia para testar o sistema sem credenciais (fontes.demo: true)."""
import datetime
import random
import zlib

from ..models import Product


def available() -> bool:
    return True


def search(query: str, limit: int, cfg: dict) -> list[Product]:
    day = datetime.date.today().toordinal()
    out = []
    for i in range(6):
        rnd = random.Random(f"{query}-{i}")
        base = rnd.uniform(15, 300)
        # o preço oscila por dia e alguns itens só "aparecem" em certos dias -> testa novidades/quedas
        if (day + i) % 4 == 0:
            continue
        price = round(base * random.Random(f"{query}-{i}-{day}").uniform(0.8, 1.05), 2)
        out.append(Product(
            source="demo", id=f"{zlib.crc32(query.encode())}-{i}",
            title=f"{query.capitalize()} · produto de exemplo {i + 1}",
            price=price, original_price=round(base * 1.3, 2),
            url=f"https://exemplo.com/{query.replace(' ', '-')}/{i}",
            commission_rate=rnd.choice([0.03, 0.06, 0.08, 0.12]),
            sales=rnd.randint(0, 3000), rating=round(rnd.uniform(4.0, 5.0), 1),
        ))
    return out
