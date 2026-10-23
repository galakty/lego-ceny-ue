"""Kursy walut z API Narodowego Banku Polskiego (tabela A, kurs średni)."""
import json

from .net import fetch

NBP_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"


def parse_nbp(payload: bytes) -> dict[str, float]:
    table = json.loads(payload)[0]
    rates = {r["code"]: float(r["mid"]) for r in table["rates"]}
    rates["PLN"] = 1.0
    return rates


def load_rates() -> dict[str, float]:
    return parse_nbp(fetch(NBP_URL))


def to_pln(amount: float, currency: str, rates: dict[str, float]) -> float:
    return round(amount * rates[currency.upper()], 2)
