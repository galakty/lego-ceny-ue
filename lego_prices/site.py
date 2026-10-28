"""Builds the static site: copies the template and writes site/data/sets.json
from the catalog, Brickset ages and the price history."""
import csv
import json
import os
import shutil
from collections import defaultdict
import base64
from urllib.parse import quote

from . import affiliates, brickset, catalog, deals, fx, pages
from .scrape import load_shops

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "site_template")


def _num(value: str) -> float | None:
    return float(value) if value not in ("", None) else None


def load_prices(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def shop_link(url: str, shop: dict) -> str:
    """Product URL wrapped in the shop's affiliate deeplink, when the shop has one.
    {url} is the URL-encoded product URL, {url_b64} the Base64 one (webePartners)."""
    template = shop.get("affiliate_link")
    if not template:
        return url
    b64 = base64.b64encode(url.encode()).decode()
    return template.replace("{url}", quote(url, safe="")).replace("{url_b64}", quote(b64, safe=""))


def latest_offers(prices: list[dict], shops: dict[str, dict]) -> dict[str, list[dict]]:
    """Newest price per (set, shop), cheapest first by total cost (or price when shipping is unknown).
    Shops whose newest offer is sold out are left out."""
    newest: dict[tuple[str, str], dict] = {}
    for row in prices:
        key = (row["set_num"], row["shop"])
        if key not in newest or row["date"] > newest[key]["date"]:
            newest[key] = row
    offers = defaultdict(list)
    for (set_num, shop_id), row in newest.items():
        if row["in_stock"] == "0":  # a sold-out offer is no real price, so it never shows or counts as cheapest
            continue
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
            "url": shop_link(row["url"], shop),
            "sponsored": bool(shop.get("affiliate_link")),
            "date": row["date"],
        })
    for lst in offers.values():
        lst.sort(key=lambda o: o["total"] if o["total"] is not None else o["pln"])
    return offers


def price_history(prices: list[dict]) -> dict[str, list[list]]:
    """Lowest PLN price per set and day, across shops, counting only offers not marked as sold out."""
    best: dict[str, dict[str, float]] = defaultdict(dict)
    for row in prices:
        if row["in_stock"] == "0":
            continue
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


def stats(payload: list[dict], page_count: int) -> str:
    with_age = sum(s["age_min"] is not None for s in payload)
    with_offers = sum(bool(s["offers"]) for s in payload)
    return f"{len(payload)} sets, {with_age} with age, {with_offers} with prices, {page_count} pages in sitemap"


def build(data_dir: str = "data", out_dir: str = "site") -> str:
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
    programs = affiliates.load(os.path.join(data_dir, "affiliates.json"))
    with open(os.path.join(out_dir, "config.js"), "w", encoding="utf-8") as f:
        # the browser search builds the same affiliate links as the static pages
        config = [{k: a[k] for k in ("name", "search_url", "query_param", "params")} for a in programs.values()]
        f.write(f"window.AFFILIATES = {json.dumps(config, ensure_ascii=False)};\n")
    try:
        eur_rate = fx.load_rates()["EUR"]
    except Exception as exc:  # the deals page then skips the list price comparison
        print(f"No EUR rate from NBP: {exc}")
        eur_rate = None
    # shops that had a price in the history, named on the about page
    priced_shops = sorted({shops[r["shop"]]["name"] for r in prices if r["shop"] in shops})
    page_count = pages.build(payload, out_dir, os.environ.get("SITE_URL", pages.DEFAULT_SITE_URL), programs, eur_rate,
                             priced_shops)
    found = f"deals: {len(deals.below_list_price(payload, eur_rate))} below list price, {len(deals.price_drops(payload))} price drops"
    return f"{stats(payload, page_count)}; {found}"
