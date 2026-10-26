import os
import shutil
import tempfile
import unittest

from lego_prices import pages


def make_set(num, pieces, age_min=None, age_max=None, theme="City", year=2026, offers=None):
    return {"num": num, "name": f"Set {num}", "year": year, "pieces": pieces, "theme": theme, "img": "",
            "age_min": age_min, "age_max": age_max, "lego_de_eur": None, "offers": offers or [], "history": []}


OFFER = {"shop": "MediaMarkt.pl", "country": "PL", "ships_to_pl": True, "price": 165.82, "currency": "PLN",
         "pln": 165.82, "shipping": None, "total": None, "in_stock": True, "url": "https://example.com/p", "date": "2026-10-26"}


class HelpersTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(pages.slugify("Harry Potter"), "harry-potter")
        self.assertEqual(pages.slugify("Łódź & Żółć"), "lodz-zolc")

    def test_pln(self):
        self.assertEqual(pages.pln(1234.5), "1 234,50 zł")

    def test_pieces_text(self):
        self.assertEqual([pages.pieces_text(n) for n in (1, 3, 12, 22, 252)],
                         ["1 klocek", "3 klocki", "12 klocków", "22 klocki", "252 klocki"])

    def test_fits_age(self):
        self.assertTrue(pages.fits_age(make_set("a", 10, 5), 6))
        self.assertFalse(pages.fits_age(make_set("a", 10, 7), 6))
        self.assertFalse(pages.fits_age(make_set("a", 10, 2, 5), 6))
        self.assertFalse(pages.fits_age(make_set("a", 10), 6))

    def test_ranked_puts_priced_first(self):
        sets = [make_set("old", 10, year=2020), make_set("priced", 10, year=2021, offers=[OFFER]), make_set("new", 10, year=2026)]
        self.assertEqual([s["num"] for s in pages.ranked(sets)], ["priced", "new", "old"])


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        with open(os.path.join(self.out, "index.html"), "w") as f:
            f.write('<link rel="canonical" href="{{SITE_URL}}/"><!-- BROWSE -->')
        self.sets = [make_set("60510", 252, 5, offers=[OFFER]), make_set("75313", 6785, 18, theme="Star Wars")]
        self.count = pages.build(self.sets, self.out, "https://example.org/x/")

    def tearDown(self):
        shutil.rmtree(self.out)

    def read(self, rel):
        with open(os.path.join(self.out, rel), encoding="utf-8") as f:
            return f.read()

    def test_set_page(self):
        page = self.read("zestaw/60510/index.html")
        self.assertIn("<title>LEGO 60510 Set 60510 – cena od 165,82 zł, 252 klocki</title>", page)
        self.assertIn('<link rel="canonical" href="https://example.org/x/zestaw/60510/">', page)
        self.assertIn('"@type": "AggregateOffer"', page)

    def test_landing_pages(self):
        self.assertIn("Set 60510", self.read("wiek/6/index.html"))
        self.assertNotIn("Set 75313", self.read("wiek/6/index.html"))
        self.assertIn("Set 75313", self.read("wiek/dorosli/index.html"))
        self.assertIn("Set 75313", self.read("klocki/ponad-3000/index.html"))
        self.assertIn("?seria=Star+Wars", self.read("seria/star-wars/index.html"))

    def test_index_and_sitemap(self):
        index = self.read("index.html")
        self.assertIn('href="https://example.org/x/"', index)
        self.assertIn('href="seria/star-wars/"', index)
        sitemap = self.read("sitemap.xml")
        self.assertIn("<loc>https://example.org/x/zestaw/75313/</loc>", sitemap)
        self.assertEqual(sitemap.count("<url>"), self.count)


if __name__ == "__main__":
    unittest.main()
