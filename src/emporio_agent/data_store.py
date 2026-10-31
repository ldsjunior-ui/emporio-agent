"""Camada de dados: carrega os CSVs uma vez e expõe consultas tipadas.

Decisões: stdlib `csv` (sem pandas) porque são ~65 produtos e 20 pedidos; o ganho de simplicidade
e de tempo de import supera qualquer vantagem de um DataFrame neste volume.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR

STATUS_PRODUTO = {
    "active": "ativo",
    "discontinued": "descontinuado",
    "coming_soon": "em breve (ainda não vendido)",
}
STATUS_PEDIDO = {
    "pending": "pendente (aguardando confirmação do pagamento)",
    "confirmed": "confirmado (em separação, ainda não despachado)",
    "shipped": "enviado (a caminho do cliente)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PAGAMENTO = {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto bancário"}


def normalize(text: str) -> str:
    """minúsculas, sem acento, só alfanumérico: base da busca tolerante a acento e caixa."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def stem(token: str) -> str:
    """Stemmer mínimo de plural pt-BR: violões→violao, guitarras→guitarra, baixos→baixo."""
    if token.endswith("oes") or token.endswith("aes"):
        return token[:-3] + "ao"
    if token.endswith("ais") and len(token) > 4:
        return token[:-3] + "al"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def tokens(text: str) -> list[str]:
    return [stem(t) for t in normalize(text).split()]


def payment_label(code: str) -> str:
    m = re.fullmatch(r"credit_(\d+)x", code)
    if m:
        return f"cartão de crédito em {m.group(1)}x"
    return PAGAMENTO.get(code, code)


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    price_brl: float
    category_id: int
    category: str
    description: str
    stock_quantity: int
    status: str
    specs: dict
    created_at: str
    search_tokens: frozenset = field(default_factory=frozenset, compare=False, repr=False)

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: float
    description: str
    is_active: bool


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: date
    status: str
    total_brl: float
    payment_method: str
    tracking_code: str
    estimated_delivery: date | None
    notes: str


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    phone: str
    email: str
    city: str


def _rows(name: str, data_dir: Path) -> list[dict]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        categories = {int(r["category_id"]): r for r in _rows("categories", data_dir)}
        self.categories = categories

        self.products: dict[int, Product] = {}
        for r in _rows("products", data_dir):
            cat = categories[int(r["category_id"])]["name"]
            specs = json.loads(r["specs"]) if r["specs"] else {}
            blob = " ".join([r["name"], cat, r["description"], " ".join(map(str, specs.values()))])
            self.products[int(r["product_id"])] = Product(
                product_id=int(r["product_id"]),
                name=r["name"],
                price_brl=float(r["price_brl"]),
                category_id=int(r["category_id"]),
                category=cat,
                description=r["description"],
                stock_quantity=int(r["stock_quantity"]),
                status=r["status"],
                specs=specs,
                created_at=r["created_at"],
                search_tokens=frozenset(tokens(blob)),
            )

        self.promotions = [
            Promotion(
                int(r["promotion_id"]), int(r["product_id"]), float(r["discount_percent"]),
                r["description"], r["is_active"] == "1",
            )
            for r in _rows("promotions", data_dir)
        ]
        self.customers = {
            int(r["customer_id"]): Customer(
                int(r["customer_id"]), r["name"], r["phone"], r["email"], r["city"]
            )
            for r in _rows("customers", data_dir)
        }
        self.orders = {
            int(r["order_id"]): Order(
                int(r["order_id"]), int(r["customer_id"]), date.fromisoformat(r["order_date"]),
                r["status"], float(r["total_brl"]), r["payment_method"], r["tracking_code"],
                _date(r["estimated_delivery"]), r["notes"],
            )
            for r in _rows("orders", data_dir)
        }
        self.order_items: dict[int, list[tuple[int, int]]] = {}
        for r in _rows("order_items", data_dir):
            self.order_items.setdefault(int(r["order_id"]), []).append(
                (int(r["product_id"]), int(r["quantity"]))
            )

    # --- promoções -----------------------------------------------------------------------
    def active_promotion(self, product_id: int) -> Promotion | None:
        """Só promoções com is_active=1 valem. Se houver mais de uma, vale a de maior desconto
        (promoções não são cumulativas, política §6.2)."""
        active = [p for p in self.promotions if p.product_id == product_id and p.is_active]
        return max(active, key=lambda p: p.discount_percent, default=None)

    # --- clientes ------------------------------------------------------------------------
    def verify_customer(self, order_id: int, contact: str) -> Customer | None:
        """Confere e-mail ou telefone informado contra o dono do pedido (LGPD, política §9)."""
        order = self.orders.get(order_id)
        if not order:
            return None
        customer = self.customers[order.customer_id]
        given = contact.strip().lower()
        digits = re.sub(r"\D", "", given)
        if given == customer.email.lower():
            return customer
        phone_digits = re.sub(r"\D", "", customer.phone)
        if len(digits) >= 8 and phone_digits.endswith(digits[-11:] if len(digits) >= 11 else digits):
            return customer
        return None


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()
