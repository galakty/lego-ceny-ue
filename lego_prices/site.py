"""Builds the static site: copies the template and writes site/data/sets.json
from the catalog, Brickset ages and the price history."""
import csv
import json
import os
import shutil
from collections import defaultdict

from . import brickset, catalog
from .scrape import load_shops

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "site_template")


def _num(value: str) -> float | None:
    return float(value) if value not in ("", None) else None


def load_prices(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_offers(prices: list[dict], shops: dict[str, dict]) -> dict[str, list[dict]]:
    """Newest price per (set, shop), cheapest first by total cost (or price when shipping is unknown)."""
    newest: dict[tuple[str, str], dict] = {}
    for row in prices:
        key = (row["set_num"], row["shop"])
        if key not in newest or row["date"] > newest[key]["date"]:
            newest[key] = row
    offers = defaultdict(list)
    for (set_num, shop_id), row in newest.items():
        shop = shops.get(shop_id, {})
        offers[set_num].append({
            "shop": shop.get("name", shop_id),
            "country": shop.get("country", ""),
            "ships_to_pl": shop.get("ships_to_pl"),
            "price": float(row["price"]),
            "currency": row["currency"],
            "pln": float(row["price_pln"]),
            "shipping": _num(row["shipping_pln"]),
            "total": _num(row["total_pln"]),
            "in_stock": None if row["in_stock"] == "" else row["in_stock"] == "1",
            "url": row["url"],
            "date": row["date"],
        })
    for lst in offers.values():
        lst.sort(key=lambda o: o["total"] if o["total"] is not None else o["pln"])
    return offers


def price_history(prices: list[dict]) -> dict[str, list[list]]:
    """Lowest PLN price per set and day, across shops."""
    best: dict[str, dict[str, float]] = defaultdict(dict)
    for row in prices:
        pln = float(row["price_pln"])
        day = best[row["set_num"]]
        day[row["date"]] = min(pln, day.get(row["date"], pln))
    return {s: sorted([d, p] for d, p in days.items()) for s, days in best.items()}


def build_sets(sets: list[dict], ages: dict[str, dict], offers, history) -> list[dict]:
    out = []
    for s in sets:
        age = ages.get(s["set_num"], {})
        out.append({
            "num": s["set_num"],
            "name": s["name"],
            "year": s["year"],
            "pieces": s["num_parts"],
            "theme": s["theme"],
            "img": s["img_url"],
            "age_min": int(age["age_min"]) if age.get("age_min") else None,
            "age_max": int(age["age_max"]) if age.get("age_max") else None,
            "lego_de_eur": _num(age.get("lego_de_eur", "")),
            "offers": offers.get(s["set_num"], []),
            "history": history.get(s["set_num"], []),
        })
    return out


def build(data_dir: str = "data", out_dir: str = "site") -> int:
    sets = catalog.load_catalog(os.path.join(data_dir, "sets.csv"))
    ages = brickset.load(os.path.join(data_dir, "brickset.csv"))
    prices = load_prices(os.path.join(data_dir, "prices.csv"))
    shops = load_shops(os.path.join(data_dir, "shops.json"))
    payload = build_sets(sets, ages, latest_offers(prices, shops), price_history(prices))

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(TEMPLATE_DIR, out_dir)
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    with open(os.path.join(out_dir, "data", "sets.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return len(payload)
