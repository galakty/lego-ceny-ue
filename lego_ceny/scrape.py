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
from .price_parser import extract_offer, page_title

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def warn(msg: str) -> None:
    # W GitHub Actions ostrzeżenia trafiają do adnotacji przebiegu, widocznych bez otwierania logów.
    print(f"::warning::{msg}" if IN_ACTIONS else f"! {msg}", file=sys.stdout if IN_ACTIONS else sys.stderr)


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


def _key(p: dict) -> dict:
    return {"set_num": p["set_num"], "shop": p["shop"]}


def save_report(path: str, report: list[dict]) -> None:
    """Stan ostatniego przebiegu dla każdej pary zestaw-sklep, do szybkiej diagnozy."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["set_num", "shop", "status", "detail"])
        w.writeheader()
        w.writerows(report)


def main(data_dir: str = "data", delay: float = 3.0) -> int:
    shops = load_shops(os.path.join(data_dir, "shops.json"))
    rates = load_rates()
    today = dt.date.today().isoformat()
    rows, failures, report = [], 0, []
    with open(os.path.join(data_dir, "products.csv"), newline="", encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    for p in products:
        shop = shops.get(p["shop"])
        if not shop:
            warn(f"nieznany sklep {p['shop']}")
            report.append({**_key(p), "status": "blad", "detail": "nieznany sklep"})
            failures += 1
            continue
        try:
            html = fetch(p["url"]).decode("utf-8", errors="replace")
            offer = extract_offer(html)
        except Exception as e:  # sieć, blokada, 404
            warn(f"{p['set_num']} @ {p['shop']}: {e}")
            report.append({**_key(p), "status": "blad", "detail": str(e)})
            failures += 1
            continue
        if offer is None:
            detail = f"nie znaleziono ceny (strona: {page_title(html)!r}, {len(html)} znaków)"
            warn(f"{p['set_num']} @ {p['shop']}: {detail}")
            report.append({**_key(p), "status": "brak ceny", "detail": detail})
            failures += 1
            continue
        rows.append(build_row(today, p["set_num"], shop, p["url"], offer, rates))
        msg = f"{p['set_num']} @ {p['shop']}: {offer.price} {offer.currency}"
        report.append({**_key(p), "status": "ok", "detail": f"{offer.price} {offer.currency}"})
        print(f"::notice::{msg}" if IN_ACTIONS else f"  {msg}")
        time.sleep(delay)
    save_rows(os.path.join(data_dir, "prices.csv"), rows)
    save_report(os.path.join(data_dir, "last_run.csv"), report)
    summary = f"Zapisano {len(rows)} cen, błędów: {failures}"
    print(f"::notice::{summary}" if IN_ACTIONS else summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
