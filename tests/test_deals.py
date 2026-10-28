import unittest

from lego_prices import deals, pages


def make_set(num, offers=(), lego_de_eur=None, history=()):
    return {"num": num, "name": f"Set {num}", "year": 2026, "pieces": 100, "theme": "City", "img": "",
            "age_min": None, "age_max": None, "lego_de_eur": lego_de_eur,
            "offers": [{"pln": p, "total": None, "in_stock": stock, "date": "2026-10-27"} for p, stock in offers],
            "history": [list(h) for h in history]}


class DealsTest(unittest.TestCase):
    def test_best_in_stock_skips_sold_out(self):
        self.assertEqual(deals.best_in_stock(make_set("1", [(50, False), (80, None), (90, True)])), 80)
        self.assertIsNone(deals.best_in_stock(make_set("1", [(50, False)])))

    def test_below_list_price(self):
        sets = [make_set("cheap", [(60, True)], lego_de_eur=25),   # list price 100 zł, 40% off
                make_set("small", [(95, True)], lego_de_eur=25),   # 5% off: not a deal
                make_set("nolist", [(10, True)])]
        found = deals.below_list_price(sets, 4.0)
        self.assertEqual([(s["num"], p, round(d, 2)) for s, p, d in found], [("cheap", 60, 0.4)])
        self.assertEqual(deals.below_list_price(sets, None), [])

    def test_price_drops(self):
        sets = [make_set("drop", history=[("2026-10-20", 200), ("2026-10-25", 180), ("2026-10-27", 150)]),
                make_set("old", history=[("2026-08-01", 300), ("2026-10-27", 150)]),       # outside the window
                make_set("stale", history=[("2026-10-20", 200), ("2026-10-26", 100)]),     # no price today
                make_set("rise", history=[("2026-10-26", 100), ("2026-10-27", 120)])]
        found = deals.price_drops(sets)
        self.assertEqual([(s["num"], p, round(d, 2)) for s, p, d in found], [("drop", 150, 0.25)])

    def test_deals_page(self):
        sets = [make_set("60510", [(60, True)], lego_de_eur=25)]
        page = pages.deals_page(sets, "https://example.org", 4.0)
        self.assertIn("−40% vs cena LEGO", page)
        self.assertIn("od 60,00 zł", page)
        self.assertIn('href="https://example.org/promocje/"', page)
        self.assertIn("nie znaleźliśmy", pages.deals_page(sets, "https://example.org", None))


class SeasonalTest(unittest.TestCase):
    def test_gifts_within_budget_most_pieces_first(self):
        small, big, pricey = make_set("small", [(40, True)]), make_set("big", [(95, True)]), make_set("pricey", [(150, True)])
        big["pieces"] = 500
        sold_out = make_set("gone", [(30, False)])
        self.assertEqual([s["num"] for s, _ in deals.gifts([small, big, pricey, sold_out], 100)], ["big", "small"])

    def test_advent_calendars(self):
        cal = make_set("60510", [(85, True)])
        cal["name"] = "City Advent Calendar 2026"
        unpriced = make_set("76318")
        unpriced["name"] = "Harry Potter Advent Calendar 2026"
        old = make_set("60436", [(50, True)])
        old["name"], old["year"] = "City Advent Calendar 2024", 2024
        found = deals.advent_calendars([unpriced, old, cal, make_set("1")], 2026)
        self.assertEqual([(s["num"], p) for s, p in found], [("60510", 85), ("76318", None)])

    def test_seasonal_pages(self):
        cal = make_set("60510", [(85, True)])
        cal["name"] = "City Advent Calendar 2026"
        out = pages.seasonal_pages([cal], "https://example.org", 2026)
        self.assertIn("od 85,00 zł", out["kalendarz-adwentowy-2026/"])
        self.assertIn("City Advent Calendar 2026", out["prezent/do-100-zl/"])
        self.assertIn("Dziś nie mamy zestawów w tej cenie.", out["prezent/do-50-zl/"])


if __name__ == "__main__":
    unittest.main()
