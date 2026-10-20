from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    source: str                 # shopee | mercadolivre | amazon | demo
    id: str
    title: str
    price: float                # BRL
    url: str                    # link de afiliado quando a API fornece; senão, link do produto
    commission_rate: float      # 0.07 = 7%
    commission_is_estimate: bool = False
    original_price: Optional[float] = None
    image: Optional[str] = None
    sales: Optional[int] = None
    rating: Optional[float] = None
    shop: Optional[str] = None
    category: str = ""
    query: str = ""
    # preenchidos pelo banco
    is_new: bool = field(default=False)
    previous_price: Optional[float] = field(default=None)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    @property
    def commission_value(self) -> float:
        return round(self.price * self.commission_rate, 2)

    @property
    def discount(self) -> Optional[float]:
        if self.original_price and self.original_price > self.price:
            return 1 - self.price / self.original_price
        return None

    @property
    def price_drop(self) -> Optional[float]:
        if self.previous_price and self.previous_price > self.price:
            return 1 - self.price / self.previous_price
        return None
