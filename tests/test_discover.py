import os
import tempfile
import unittest

from lego_prices import discover, scrape


class MatchSetsTest(unittest.TestCase):
    def test_matches_set_number_in_path(self):
        urls = [
            "https://mediamarkt.pl/pl/product/_klocki-lego-60510-city-kalendarz-adwentowy-2026-252-el-5-lat-178410969.html",
            "https://mediamarkt.pl/pl/product/_klocki-lego-zestaw-60510-i-60511-123.html",  # bundle: two sets
            "https://mediamarkt.pl/pl/product/_lego-torba-999999-1.html",  # not a catalog set
        ]
        self.assertEqual(discover.match_sets(urls, {"60510", "60511"}), {"60510": urls[0]})

    def test_product_id_not_mistaken_for_set(self):
        url = "https://shop.example/lego-star-wars-75313-at-at/178410969"
        self.assertEqual(discover.match_sets([url], {"75313", "1784"}), {"75313": url})


class LoadProductsTest(unittest.TestCase):
    def test_merges_manual_and_discovered(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "discovered"))
            with open(os.path.join(d, "products.csv"), "w") as f:
                f.write("set_num,shop,url\n60510,mm,manual\n")
            with open(os.path.join(d, "discovered", "mm.csv"), "w") as f:
                f.write("set_num,shop,url\n60510,mm,found\n75313,mm,found2\n")
            self.assertEqual([p["url"] for p in scrape.load_products(d)], ["manual", "found2"])


if __name__ == "__main__":
    unittest.main()
