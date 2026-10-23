import csv
import gzip
import json
import os
import tempfile
import unittest

from lego_ceny.catalog import parse_sets
from lego_ceny.fx import parse_nbp, to_pln
from lego_ceny.price_parser import Offer, _parse_price, extract_offer
from lego_ceny.scrape import build_row, save_rows

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class PriceParserTest(unittest.TestCase):
    def test_jsonld_graph(self):
        self.assertEqual(extract_offer(read("jsonld_product.html")), Offer(749.99, "EUR", True))

    def test_meta_fallback(self):
        self.assertEqual(extract_offer(read("meta_only.html")), Offer(3199.99, "PLN", None))

    def test_no_price(self):
        self.assertIsNone(extract_offer("<html><body>brak</body></html>"))

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


if __name__ == "__main__":
    unittest.main()
