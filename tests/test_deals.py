import datetime as dt
import unittest

from lego_prices import deals, pages


def make_set(num, offers=(), lego_de_eur=None, history=()):
    return {"num": num, "name": f"Set {num}", "year": 2026, "pieces": 100, "theme": "City", "img": "",
            "age_min": None, "age_max": None, "lego_de_eur": lego_de_eur,
            "offers": [{"pln": p, "total": None, "in_stock": stock, "date": "2026-10-27"} for p, stock in offers],
            "history": [list(h) for h in history]}


def days(prices, start="2026-11-01"):
    """History with one price per day from `start`."""
    first = dt.date.fromisoformat(start)
    return [((first + dt.timedelta(days=i)).isoformat(), p) for i, p in enumerate(prices)]


class SuspiciousPriceTest(unittest.TestCase):
    def test_price_far_below_the_next_shop_is_ignored(self):
        s = make_set("71868", [(106.94, True), (269.0, None), (408.65, True)])
        self.assertEqual(deals.best_in_stock(s), 269.0)
        self.assertEqual(deals.best_in_stock(make_set("1", [(150, True), (269, True)])), 150)  # 44% off is a real deal
        self.assertEqual(deals.best_in_stock(make_set("1", [(20, True)])), 20)  # nothing to compare with

    def test_suspicious_price_is_no_price_drop(self):
        s = make_set("x", [(100, True), (300, True)], history=[("2026-10-26", 300), ("2026-10-27", 100)])
        self.assertEqual(deals.price_drops([s]), [])


class BlackFridayTest(unittest.TestCase):
    def test_date(self):
        self.assertEqual(deals.black_friday_date(2026), dt.date(2026, 11, 27))
        self.assertEqual(deals.black_friday_date(2025), dt.date(2025, 11, 28))
        self.assertEqual(deals.black_friday_date(2027), dt.date(2027, 11, 26))

    def test_real_deals_and_recently_cheaper(self):
        low = make_set("low", [(80, True)], history=days([100, 100, 95, 100, 100, 80]))      # new 30-day low, -20%
        flat = make_set("flat", [(100, True)], history=days([100] * 6))                     # lowest, but no discount
        listed = make_set("list", [(100, True)], lego_de_eur=50, history=days([100] * 6))   # 50% below list price
        up = make_set("up", [(130, True)], history=days([110, 100, 120, 120, 125, 130]))    # was 100 on 11-02
        short = make_set("short", [(50, True)], history=days([100, 50]))                    # too little history
        real, higher = deals.black_friday([low, flat, listed, up, short], 4.0)
        self.assertEqual([(s["num"], p, label) for s, p, label in real],
                         [("list", 100, "−50% vs cena LEGO"), ("low", 80, "−20% w 30 dni")])
        self.assertEqual([(s["num"], p, lo, day) for s, p, lo, day in higher], [("up", 130, 100, "2026-11-02")])


class DealsTest(unittest.TestCase):
    def test_best_in_stock_skips_sold_out(self):
        self.assertEqual(deals.best_in_stock(make_set("1", [(50, False), (80, None), (90, True)])), 80)
        self.assertIsNone(deals.best_in_stock(make_set("1", [(50, False)])))

    def test_lowest_recent_keeps_only_last_30_days(self):
        history = [["2026-09-20", 50.0], ["2026-10-10", 90.0], ["2026-10-25", 80.0], ["2026-11-02", 100.0]]
        self.assertEqual(deals.lowest_recent(history, "2026-11-02"), 80.0)
        self.assertIsNone(deals.lowest_recent(history[:1], "2026-11-02"))
        self.assertIsNone(deals.lowest_recent(history, None))

    def test_below_list_price(self):
        sets = [make_set("cheap", [(60, True)], lego_de_eur=25),   # list price 100 zł, 40% off
                make_set("small", [(95, True)], lego_de_eur=25),   # 5% off: not a deal
                make_set("nolist", [(10, True)])]
        found = deals.below_list_price(sets, 4.0)
        self.assertEqual([(s["num"], p, round(d, 2)) for s, p, d in found], [("cheap", 60, 0.4)])
        self.assertEqual(deals.below_list_price(sets, None), [])

    def test_price_drops(self):
        sets = [make_set("drop", [(150, True)], history=[("2026-10-20", 200), ("2026-10-25", 180), ("2026-10-27", 150)]),
                make_set("old", [(150, True)], history=[("2026-08-01", 300), ("2026-10-27", 150)]),       # outside the window
                make_set("stale", history=[("2026-10-20", 200), ("2026-10-26", 100)]),     # no price today
                make_set("rise", [(120, True)], history=[("2026-10-26", 100), ("2026-10-27", 120)])]
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


class RetiringTest(unittest.TestCase):
    today = dt.date(2026, 10, 30)

    def test_retiring_soonest_first_priced_first(self):
        dec_priced, dec_unpriced, jun = make_set("b", [(80, True)]), make_set("a"), make_set("c", [(50, True)])
        dec_priced["exit_date"] = dec_unpriced["exit_date"] = "2026-12-31"
        jun["exit_date"] = "2027-06-30"
        gone, far, unknown = make_set("gone"), make_set("far"), make_set("unknown")
        gone["exit_date"], far["exit_date"] = "2026-01-01", "2028-12-31"
        found = deals.retiring([jun, gone, dec_unpriced, far, unknown, dec_priced], self.today)
        self.assertEqual([(s["num"], p) for s, p in found], [("b", 80), ("a", None), ("c", 50)])

    def test_retiring_page(self):
        s = make_set("10305", [(60, True)], lego_de_eur=25)
        s["exit_date"] = "2026-12-31"
        page = pages.retiring_page([s], "https://example.org", 4.0, self.today)
        self.assertIn("Wycofanie: grudzień 2026", page)
        self.assertIn("−40% vs cena LEGO", page)
        self.assertIn('href="https://example.org/wycofywane/"', page)
        self.assertIn("Nie znamy jeszcze", pages.retiring_page([make_set("1")], "https://example.org", 4.0, self.today))


if __name__ == "__main__":
    unittest.main()


class PriceNotesTest(unittest.TestCase):
    def test_per_piece_and_30_day_low(self):
        s = make_set("1")  # 100 pieces
        s["low_30d"] = 80.0
        self.assertIn("0,90 zł za klocek", pages.price_notes(s, 90.0))
        self.assertIn("Najniżej w 30 dni: 80,00 zł", pages.price_notes(s, 90.0))
        self.assertIn("Najtaniej od 30 dni", pages.price_notes(s, 80.0))
        self.assertEqual(pages.price_notes(s, None), "")
