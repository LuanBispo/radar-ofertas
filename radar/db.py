"""Histórico em SQLite: detecta produtos novos e quedas de preço entre execuções."""
import datetime
import sqlite3
from pathlib import Path

from .models import Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    key TEXT PRIMARY KEY, source TEXT, title TEXT, category TEXT, url TEXT,
    first_seen TEXT, last_seen TEXT, last_price REAL, min_price REAL
);
CREATE TABLE IF NOT EXISTS prices (
    key TEXT, day TEXT, price REAL, PRIMARY KEY (key, day)
);
"""


class History:
    def __init__(self, path: str = "data/radar.db"):
        Path(path).parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.today = datetime.date.today().isoformat()
        # "primeira execução" = ainda não há nada de dias anteriores (vale também p/ reexecuções no 1º dia)
        self.first_run = self.conn.execute(
            "SELECT COUNT(*) FROM products WHERE first_seen < ?", (self.today,)).fetchone()[0] == 0

    def record(self, p: Product) -> None:
        row = self.conn.execute(
            "SELECT first_seen, last_price, last_seen FROM products WHERE key=?", (p.key,)).fetchone()
        if row is None:
            # na primeira execução tudo seria "novo"; não marcamos para não inundar o relatório
            p.is_new = not self.first_run
            self.conn.execute(
                "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)",
                (p.key, p.source, p.title, p.category, p.url, self.today, self.today, p.price, p.price))
        else:
            first_seen, last_price, last_seen = row
            p.is_new = first_seen == self.today and not self.first_run
            if last_seen != self.today:
                p.previous_price = last_price
            else:  # rodou mais de uma vez no mesmo dia: compara com o dia anterior
                prev = self.conn.execute(
                    "SELECT price FROM prices WHERE key=? AND day<? ORDER BY day DESC LIMIT 1",
                    (p.key, self.today)).fetchone()
                p.previous_price = prev[0] if prev else None
            self.conn.execute(
                "UPDATE products SET title=?, url=?, last_seen=?, last_price=?, min_price=MIN(min_price, ?) "
                "WHERE key=?", (p.title, p.url, self.today, p.price, p.price, p.key))
        self.conn.execute("INSERT OR REPLACE INTO prices VALUES (?,?,?)", (p.key, self.today, p.price))

    def is_all_time_low(self, p: Product) -> bool:
        row = self.conn.execute("SELECT MIN(price), COUNT(*) FROM prices WHERE key=?", (p.key,)).fetchone()
        return row[1] >= 3 and p.price <= row[0]

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
