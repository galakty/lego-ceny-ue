import csv
import gzip
import json
import os
import tempfile
import unittest

from lego_prices import brickset, site
from lego_prices.catalog import parse_sets, parse_themes
from lego_prices.fx import parse_nbp, to_pln
from lego_prices.price_parser import Offer, _parse_price, extract_offer, page_title
from lego_prices.scrape import build_row, save_rows

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class PriceParserTest(unittest.TestCase):
    def test_jsonld_graph(self):
        self.assertEqual(extract_offer(read("jsonld_product.html")), Offer(749.99, "EUR", True))

    def test_jsonld_nested_in_buyaction(self):
        self.assertEqual(extract_offer(read("buyaction.html")), Offer(164.86, "PLN", True))

    def test_meta_fallback(self):
        self.assertEqual(extract_offer(read("meta_only.html")), Offer(3199.99, "PLN", None))

    def test_amazon_html(self):
        self.assertEqual(extract_offer(read("amazon.html")), Offer(29.99, "EUR", True))

    def test_page_title(self):
        self.assertEqual(page_title(read("amazon.html")), "LEGO City 60510 : Amazon.de: Spielzeug")

    def test_no_price(self):
        self.assertIsNone(extract_offer("<html><body>nothing</body></html>"))

    def test_number_formats(self):
        self.assertEqual(_parse_price("1.299,99 €"), 1299.99)
        self.assertEqual(_parse_price("1,299.99"), 1299.99)
        self.assertEqual(_parse_price("1299,99"), 1299.99)
        self.assertEqual(_parse_price(42), 42.0)


class FxTest(unittest.TestCase):
    def test_parse_nbp(self):
        payload = json.dumps([{"rates": [{"code": "EUR", "mid": 4.25}]}]).encode()
        rates = parse_nbp(payload)
        self.assertEqual(to_pln(100, "eur", rates), 425.0)
        self.assertEqual(rates["PLN"], 1.0)


class CatalogTest(unittest.TestCase):
    def test_filters_old_and_empty(self):
        text = ("set_num,name,year,theme_id,num_parts,img_url\n"
                "75313-1,AT-AT,2021,158,6785,https://img/75313.jpg\n"
                "6000-1,Old,1990,1,100,\n"
                "123-1,Gear,2022,1,0,\n")
        sets = parse_sets(gzip.compress(text.encode()), min_year=2020)
        self.assertEqual([s["set_num"] for s in sets], ["75313"])


class ThemesTest(unittest.TestCase):
    def test_subtheme_maps_to_root_and_variants_dedupe(self):
        themes_csv = "id,name,parent_id\n158,Star Wars,\n171,Ultimate Collector Series,158\n"
        themes = parse_themes(gzip.compress(themes_csv.encode()))
        self.assertEqual(themes["171"], "Star Wars")
        sets_csv = ("set_num,name,year,theme_id,num_parts,img_url\n"
                    "75313-1,AT-AT,2021,171,6785,i\n75313-2,AT-AT,2021,171,6785,i\n")
        sets = parse_sets(gzip.compress(sets_csv.encode()), themes)
        self.assertEqual([(s["set_num"], s["theme"]) for s in sets], [("75313", "Star Wars")])


class BricksetTest(unittest.TestCase):
    def test_parse(self):
        payload = json.dumps({"status": "success", "matches": 2, "sets": [
            {"number": "60510", "numberVariant": 1, "ageRange": {"min": 5}, "LEGOCom": {"DE": {"retailPrice": 34.99}}},
            {"number": "60510", "numberVariant": 2, "ageRange": {"min": 9}},
        ]}).encode()
        rows, matches = brickset.parse_sets(payload)
        self.assertEqual(matches, 2)
        self.assertEqual(rows, [{"set_num": "60510", "age_min": 5, "age_max": "", "lego_de_eur": 34.99}])

    def test_error_raises(self):
        with self.assertRaises(RuntimeError):
            brickset.parse_sets(json.dumps({"status": "error", "message": "API limit exceeded"}).encode())


class SiteTest(unittest.TestCase):
    shops = {"a": {"name": "Shop A", "country": "PL", "ships_to_pl": True},
             "b": {"name": "Shop B", "country": "DE", "ships_to_pl": True}}

    def price(self, date, shop, pln, total=""):
        return {"date": date, "set_num": "60510", "shop": shop, "price": str(pln), "currency": "PLN",
                "in_stock": "1", "price_pln": str(pln), "shipping_pln": "", "total_pln": str(total), "url": "u"}

    def test_latest_offer_per_shop_sorted(self):
        prices = [self.price("2026-10-24", "a", 170), self.price("2026-10-25", "a", 165),
                  self.price("2026-10-25", "b", 150, 160)]
        offers = site.latest_offers(prices, self.shops)["60510"]
        self.assertEqual([(o["shop"], o["pln"]) for o in offers], [("Shop B", 150.0), ("Shop A", 165.0)])

    def test_history_is_daily_minimum(self):
        prices = [self.price("2026-10-25", "a", 165), self.price("2026-10-25", "b", 150),
                  self.price("2026-10-24", "a", 170)]
        self.assertEqual(site.price_history(prices)["60510"], [["2026-10-24", 170.0], ["2026-10-25", 150.0]])

    def test_build_sets_merges_ages(self):
        sets = [{"set_num": "60510", "name": "Advent", "year": 2026, "num_parts": 252, "theme": "City", "img_url": ""}]
        ages = {"60510": {"set_num": "60510", "age_min": "5", "age_max": "", "lego_de_eur": "34.99"}}
        out = site.build_sets(sets, ages, {}, {})[0]
        self.assertEqual((out["age_min"], out["age_max"], out["lego_de_eur"], out["offers"]), (5, None, 34.99, []))


class ScrapeTest(unittest.TestCase):
    rates = {"EUR": 4.0, "PLN": 1.0}
    shop = {"id": "amazon-de", "currency": "EUR", "ships_to_pl": True,
            "shipping_to_pl": 5.0, "free_shipping_from": 50.0}

    def test_total_includes_shipping(self):
        row = build_row("2026-10-23", "40000", self.shop, "u", Offer(10.0, "EUR", True), self.rates)
        self.assertEqual((row["price_pln"], row["shipping_pln"], row["total_pln"]), (40.0, 20.0, 60.0))

    def test_free_shipping_threshold(self):
        row = build_row("2026-10-23", "75313", self.shop, "u", Offer(700.0, "EUR", True), self.rates)
        self.assertEqual(row["total_pln"], 2800.0)

    def test_unknown_shipping_leaves_total_empty(self):
        shop = dict(self.shop, shipping_to_pl=None)
        row = build_row("2026-10-23", "75313", shop, "u", Offer(700.0, "EUR", True), self.rates)
        self.assertEqual(row["total_pln"], "")

    def test_same_day_rerun_replaces(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prices.csv")
            r1 = build_row("2026-10-23", "75313", self.shop, "u", Offer(700.0, "EUR", True), self.rates)
            r2 = build_row("2026-10-23", "75313", self.shop, "u", Offer(650.0, "EUR", True), self.rates)
            save_rows(path, [r1])
            save_rows(path, [r2])
            with open(path, newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["price"] for r in rows], ["650.0"])


class ShopLinkTest(unittest.TestCase):
    def test_plain_and_affiliate_links(self):
        url = "https://www.neonet.pl/zabawki/lego-60510.html?x=1"
        self.assertEqual(site.shop_link(url, {}), url)
        shop = {"affiliate_link": "https://net.example/click?id=7&url={url}"}
        self.assertEqual(site.shop_link(url, shop),
                         "https://net.example/click?id=7&url=https%3A%2F%2Fwww.neonet.pl%2Fzabawki%2Flego-60510.html%3Fx%3D1")


if __name__ == "__main__":
    unittest.main()
