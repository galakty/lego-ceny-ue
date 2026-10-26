"""Fetches current prices for the (set, shop) pairs in data/products.csv
and appends them to the history in data/prices.csv."""
import csv
import datetime as dt
import glob
import json
import os
import sys
import time

from .fx import load_rates, to_pln
from .net import fetch
from .price_parser import extract_offer, page_title

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def warn(msg: str) -> None:
    # In GitHub Actions, warnings become run annotations, visible without opening the logs.
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
    """Appends rows; a rerun on the same day replaces that day's entries."""
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
    """Status of the last run for each set-shop pair, for quick diagnosis."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["set_num", "shop", "status", "detail"])
        w.writeheader()
        w.writerows(report)


def load_products(data_dir: str) -> list[dict]:
    """Hand-picked products.csv plus the per-shop lists found by `discover`; the first URL per (set, shop) wins."""
    paths = [os.path.join(data_dir, "products.csv")] + sorted(glob.glob(os.path.join(data_dir, "discovered", "*.csv")))
    products, seen = [], set()
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for p in csv.DictReader(f):
                if (p["set_num"], p["shop"]) not in seen:
                    seen.add((p["set_num"], p["shop"]))
                    products.append(p)
    return products


def main(data_dir: str = "data", delay: float = 2.0) -> int:
    shops = load_shops(os.path.join(data_dir, "shops.json"))
    rates = load_rates()
    today = dt.date.today().isoformat()
    rows, failures, report = [], 0, []
    products = load_products(data_dir)
    for p in products:
        shop = shops.get(p["shop"])
        if not shop:
            warn(f"unknown shop {p['shop']}")
            report.append({**_key(p), "status": "error", "detail": "unknown shop"})
            failures += 1
            continue
        try:
            html = fetch(p["url"]).decode("utf-8", errors="replace")
            offer = extract_offer(html)
        except Exception as e:  # network error, block, 404
            warn(f"{p['set_num']} @ {p['shop']}: {e}")
            report.append({**_key(p), "status": "error", "detail": str(e)})
            failures += 1
            continue
        debug_dir = os.environ.get("DEBUG_HTML_DIR")
        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            with open(os.path.join(debug_dir, f"{p['set_num']}_{p['shop']}.html"), "w", encoding="utf-8") as f:
                f.write(html)
        if offer is None:
            detail = f"price not found (page: {page_title(html)!r}, {len(html)} chars)"
            warn(f"{p['set_num']} @ {p['shop']}: {detail}")
            report.append({**_key(p), "status": "no_price", "detail": detail})
            failures += 1
            continue
        rows.append(build_row(today, p["set_num"], shop, p["url"], offer, rates))
        msg = f"{p['set_num']} @ {p['shop']}: {offer.price} {offer.currency}"
        report.append({**_key(p), "status": "ok", "detail": f"{offer.price} {offer.currency}"})
        print(f"::notice::{msg}" if IN_ACTIONS else f"  {msg}")
        time.sleep(delay)
    save_rows(os.path.join(data_dir, "prices.csv"), rows)
    save_report(os.path.join(data_dir, "last_run.csv"), report)
    summary = f"Saved {len(rows)} prices, failures: {failures}"
    print(f"::notice::{summary}" if IN_ACTIONS else summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
