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
        self.assertFalse(pages.fits_age(make_set("duplo", 10, 2), 6))
        self.assertTrue(pages.fits_age(make_set("a", 10, 3), 6))

    def test_ranked_by_age_prefers_closest(self):
        sets = [make_set("duplo", 10, 3, year=2026), make_set("city", 10, 6, year=2024)]
        self.assertEqual([s["num"] for s in pages.ranked(sets, 6)], ["city", "duplo"])

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
        self.assertNotIn("og:image", page)  # the test set has no picture
        self.assertIn("Cena za klocek</span><strong>0,66 zł", page)
        self.assertNotIn("Najniższa cena z 30 dni", page)  # the test set has no history

    def test_set_page_preview_image(self):
        s = make_set("60510", 252)
        s["img"] = "https://cdn.example/60510.jpg"
        self.assertIn('<meta property="og:image" content="https://cdn.example/60510.jpg">', pages.set_page(s, [], "https://example.org"))

    def test_landing_pages(self):
        self.assertIn("Set 60510", self.read("wiek/6/index.html"))
        self.assertNotIn("Set 75313", self.read("wiek/6/index.html"))
        self.assertIn("Set 75313", self.read("wiek/dorosli/index.html"))
        self.assertIn("Set 75313", self.read("klocki/ponad-3000/index.html"))
        self.assertIn("?seria=Star+Wars", self.read("seria/star-wars/index.html"))

    def test_gift_finder_page(self):
        page = self.read("prezent/kreator/index.html")
        self.assertIn('<script src="../../gift.js" defer></script>', page)
        self.assertIn('data-value="minecraft"', page)
        self.assertIn('data-value="200" aria-pressed="true"', page)  # default budget
        self.assertIn("prezent/kreator/</loc>", self.read("sitemap.xml"))
        self.assertIn('href="../../prezent/kreator/"', self.read("zestaw/60510/index.html"))  # quick nav button

    def test_flowers_page_exists_and_is_in_sitemap(self):
        page = self.read("kwiaty-lego/index.html")
        self.assertIn("<h1>Kwiaty LEGO: bukiety, orchidee i bonsai</h1>", page)
        self.assertIn("Nie mamy jeszcze takich zestawów", page)  # the test sets are no flowers
        self.assertIn("kwiaty-lego/</loc>", self.read("sitemap.xml"))

    def test_index_and_sitemap(self):
        index = self.read("index.html")
        self.assertIn('href="https://example.org/x/"', index)
        self.assertIn('href="seria/star-wars/"', index)
        sitemap = self.read("sitemap.xml")
        self.assertIn("<loc>https://example.org/x/zestaw/75313/</loc>", sitemap)
        self.assertEqual(sitemap.count("<url>"), self.count)
        self.assertIn("Sitemap: https://example.org/x/sitemap.xml", self.read("robots.txt"))


if __name__ == "__main__":
    unittest.main()


class FlowerTest(unittest.TestCase):
    def test_is_flower(self):
        def named(name, theme="Icons"):
            return {"name": name, "theme": theme}
        for name in ("Flower Bouquet", "Orchid", "Mini Orchid", "Bonsai Tree", "Bouquet of Roses", "Tulip Bouquet",
                     "Cherry Blossoms", "Wildflower Bouquet", "Pretty Pink Flower Bouquet"):
            self.assertTrue(pages.is_flower(named(name)), name)
        self.assertTrue(pages.is_flower(named("Japanese Red Maple", "Botanicals")))
        for name, theme in (("Piranha Plant", "Super Mario"), ("Lotus Evija", "Speed Champions"),
                            ("Glinda, Elphaba & Nessarose at Shiz University", "Wicked"), ("Millennium Falcon", "Star Wars")):
            self.assertFalse(pages.is_flower(named(name, theme)), name)


class PriceChartTest(unittest.TestCase):
    def test_chart_places_days_by_date(self):
        svg = pages.price_chart([["2026-10-01", 200.0], ["2026-10-02", 100.0], ["2026-10-11", 150.0]])
        self.assertIn("<svg", svg)
        self.assertIn("01.10.2026", svg)
        self.assertIn("11.10.2026", svg)
        self.assertIn("200,00 zł", svg)
        self.assertIn("100,00 zł", svg)
        # step line: 6 + 1 day of 10 * 588 px = 64.8 px
        self.assertIn("64.8,6.0 64.8,134.0", svg)

    def test_no_chart_for_a_single_day(self):
        self.assertEqual(pages.price_chart([["2026-10-01", 200.0]]), "")
        self.assertEqual(pages.price_chart([]), "")


class AffiliateTest(unittest.TestCase):
    programs = {"amazon": {"name": "Amazon.pl", "search_url": "https://www.amazon.pl/s", "query_param": "k",
                           "params": {"tag": "klockownik-21"},
                           "disclosure": "Jako partner Amazon uzyskujemy przychody z kwalifikujących się zakupów."},
                "allegro": {"name": "Allegro", "search_url": "https://allegro.pl/listing", "query_param": "string",
                            "params": {"utm_medium": "afiliacja", "utm_campaign": "abc"}}}

    def test_search_link(self):
        from lego_prices.affiliates import search_links
        self.assertEqual(search_links("60510", self.programs), [
            ("Amazon.pl", "https://www.amazon.pl/s?k=LEGO+60510&tag=klockownik-21"),
            ("Allegro", "https://allegro.pl/listing?string=LEGO+60510&utm_medium=afiliacja&utm_campaign=abc"),
        ])

    def test_set_page_has_button_and_disclosure(self):
        out = tempfile.mkdtemp()
        try:
            with open(os.path.join(out, "index.html"), "w") as f:
                f.write("<!-- BROWSE --><!-- DISCLOSURE -->")
            pages.build([make_set("60510", 252, 5)], out, "https://example.org", self.programs)
            with open(os.path.join(out, "zestaw/60510/index.html"), encoding="utf-8") as f:
                page = f.read()
            self.assertIn('href="https://www.amazon.pl/s?k=LEGO+60510&amp;tag=klockownik-21" rel="sponsored nofollow noopener"', page)
            self.assertIn("Jako partner Amazon", page)
            self.assertIn("Sprawdź aktualną cenę:", page)
            with open(os.path.join(out, "wiek/6/index.html"), encoding="utf-8") as f:
                self.assertIn("Sprawdź cenę na Amazon.pl i Allegro →", f.read())
            with open(os.path.join(out, "index.html"), encoding="utf-8") as f:
                self.assertIn("Jako partner Amazon", f.read())
        finally:
            shutil.rmtree(out)
