"""Pobiera aktualne ceny dla par (zestaw, sklep) z data/products.csv
i dopisuje je do historii w data/prices.csv."""
import csv
import datetime as dt
import json
import os
import sys
import time

from .fx import load_rates, to_pln
from .net import fetch
from .price_parser import extract_offer

FIELDS = ["date", "set_num", "shop", "price", "currency", "in_stock",
          "price_pln", "shipping_pln", "total_pln", "url"]


def load_shops(path: str) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        return {s["id"]: s for s in json.load(f)["shops"]}


def shipping_pln(shop: dict, price: float, rates: dict[str, float]) -> float | None:
    if shop["shipping_to_pl"] is None:
        return None
    free_from = shop.get("free_shipping_from")
    cost = 0.0 if free_from is not None and price >= free_from else shop["shipping_to_pl"]
    return to_pln(cost, shop["currency"], rates)


def build_row(date: str, set_num: str, shop: dict, url: str, offer, rates) -> dict:
    price_pln = to_pln(offer.price, offer.currency, rates)
    ship = shipping_pln(shop, offer.price, rates) if shop["ships_to_pl"] else None
    total = round(price_pln + ship, 2) if ship is not None else None
    return {
        "date": date, "set_num": set_num, "shop": shop["id"],
        "price": offer.price, "currency": offer.currency,
        "in_stock": "" if offer.in_stock is None else int(offer.in_stock),
        "price_pln": price_pln,
        "shipping_pln": "" if ship is None else ship,
        "total_pln": "" if total is None else total,
        "url": url,
    }


def save_rows(path: str, rows: list[dict]) -> None:
    """Dopisuje wiersze; ponowne uruchomienie tego samego dnia nadpisuje wpisy z tego dnia."""
    existing = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    new_keys = {(r["date"], r["set_num"], r["shop"]) for r in rows}
    kept = [r for r in existing if (r["date"], r["set_num"], r["shop"]) not in new_keys]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(kept + rows)


def main(data_dir: str = "data", delay: float = 3.0) -> int:
    shops = load_shops(os.path.join(data_dir, "shops.json"))
    rates = load_rates()
    today = dt.date.today().isoformat()
    rows, failures = [], 0
    with open(os.path.join(data_dir, "products.csv"), newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    for p in products:
        shop = shops.get(p["shop"])
        if not shop:
            print(f"! nieznany sklep {p['shop']}", file=sys.stderr)
            failures += 1
            continue
        try:
            offer = extract_offer(fetch(p["url"]).decode("utf-8", errors="replace"))
        except Exception as e:  # sieć, blokada, 404
            print(f"! {p['set_num']} @ {p['shop']}: {e}", file=sys.stderr)
            failures += 1
            continue
        if offer is None:
            print(f"! {p['set_num']} @ {p['shop']}: nie znaleziono ceny", file=sys.stderr)
            failures += 1
            continue
        rows.append(build_row(today, p["set_num"], shop, p["url"], offer, rates))
        print(f"  {p['set_num']} @ {p['shop']}: {offer.price} {offer.currency}")
        time.sleep(delay)
    save_rows(os.path.join(data_dir, "prices.csv"), rows)
    print(f"Zapisano {len(rows)} cen, błędów: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
