import unittest

from lego_prices import reels


def row(date, set_num, shop, price, in_stock="1"):
    return {"date": date, "set_num": set_num, "shop": shop, "price_pln": str(price), "in_stock": in_stock}


class ReelsTest(unittest.TestCase):
    def test_picks_biggest_difference_and_skips_small_ones(self):
        prices = [row("2026-11-01", "big", "a", 1000), row("2026-11-01", "big", "b", 700),
                  row("2026-11-01", "small", "a", 100), row("2026-11-01", "small", "b", 95),
                  row("2026-11-01", "one", "a", 500)]
        picks = reels.daily_picks(prices)["2026-11-01"]
        self.assertEqual([p["set_num"] for p in picks], ["big"])
        self.assertEqual(picks[0]["offers"], [("a", 1000.0), ("b", 700.0)])
        self.assertAlmostEqual(picks[0]["diff"], 300)
        self.assertAlmostEqual(picks[0]["pct"], 30)

    def test_sold_out_offers_do_not_count(self):
        prices = [row("2026-11-01", "x", "a", 1000, "0"), row("2026-11-01", "x", "b", 700)]
        self.assertEqual(reels.daily_picks(prices)["2026-11-01"], [])

    def test_price_spike_is_ignored(self):
        prices = [row(f"2026-11-0{d}", "x", "a", 800) for d in range(1, 4)]
        prices += [row(f"2026-11-0{d}", "x", "b", 600) for d in range(1, 5)]
        prices.append(row("2026-11-04", "x", "a", 1200))  # 50% jump overnight
        self.assertEqual(reels.daily_picks(prices, count=5)["2026-11-04"], [])

    def test_suspiciously_low_price_is_ignored(self):
        prices = [row("2026-11-01", "x", "a", 408.65), row("2026-11-01", "x", "b", 269), row("2026-11-01", "x", "c", 106.94)]
        picks = reels.daily_picks(prices)["2026-11-01"]
        self.assertEqual(picks[0]["offers"], [("a", 408.65), ("b", 269.0)])

    def test_set_is_not_repeated_within_two_weeks(self):
        prices = []
        for d in ("2026-11-01", "2026-11-02", "2026-11-20"):
            prices += [row(d, "x", "a", 1000), row(d, "x", "b", 700), row(d, "y", "a", 500), row(d, "y", "b", 300)]
        picks = reels.daily_picks(prices, count=1)
        self.assertEqual([p["set_num"] for p in picks["2026-11-01"]], ["x"])
        self.assertEqual([p["set_num"] for p in picks["2026-11-02"]], ["y"])
        self.assertEqual([p["set_num"] for p in picks["2026-11-20"]], ["x"])

    def test_caption(self):
        pick = {"set_num": "42215", "date": "2026-11-04", "offers": [("mm", 1979.16), ("neo", 1309.9)],
                "diff": 669.26, "pct": 33.8}
        s = {"name": "Volvo EC500 Hybrid Excavator", "theme": "Technic"}
        deal = reels.video_deal(pick, s, {"mm": "MediaMarkt.pl", "neo": "Neonet"}, 0)
        text = reels.caption(deal, s)
        self.assertIn("LEGO Technic Volvo EC500 Hybrid Excavator (42215): różnica w cenie aż 669 zł", text)
        self.assertIn("Neonet: 1 309,90 zł", text)
        self.assertIn("Ceny z 4.11.2026", text)
        self.assertIn("#legotechnic", text)

    def test_black_friday_reels_point_to_the_black_friday_page(self):
        s = {"name": "Volvo EC500 Hybrid Excavator", "theme": "Technic"}
        pick = {"set_num": "42215", "date": "2026-11-24", "offers": [("mm", 1979.16), ("neo", 1309.9)], "diff": 669.26, "pct": 33.8}
        deal = reels.video_deal(pick, s, {}, 0)
        self.assertEqual(deal["cta_url"], "klockownik.pl/black-friday")
        self.assertEqual(deal["hook"], reels.BF_HOOKS[0])
        text = reels.caption(deal, s)
        self.assertTrue(text.startswith("🖤 Black Friday: LEGO Technic"))
        self.assertIn("klockownik.pl/black-friday (link w bio)", text)
        self.assertIn("#blackfriday", text)
        self.assertIn("https://klockownik.pl/black-friday/", reels.reels_page("2026-11-24", []))
        pick["date"] = "2026-12-10"
        deal = reels.video_deal(pick, s, {}, 0)
        self.assertEqual(deal["cta_url"], "klockownik.pl")
        text = reels.caption(deal, s)
        self.assertNotIn("Black Friday", text)
        self.assertIn("Zanim kupisz, sprawdź ceny na klockownik.pl", text)
        self.assertNotIn("black-friday", reels.reels_page("2026-12-10", []))


if __name__ == "__main__":
    unittest.main()
