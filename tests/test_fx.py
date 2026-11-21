import json
import os
import tempfile
import unittest

from lego_prices.fx import load_rates

PAYLOAD = json.dumps([{"rates": [{"code": "EUR", "mid": 4.25}]}]).encode()


def failing(_url):
    raise OSError("HTTP Error 500: Internal Server Error")


class LoadRatesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.dir.name, "fx_rates.json")
        self.sleeps = []

    def tearDown(self):
        self.dir.cleanup()

    def load(self, fetch_fn):
        return load_rates(self.cache, attempts=3, wait=1, fetch_fn=fetch_fn, sleep=self.sleeps.append)

    def test_retries_after_server_error_and_saves_rates(self):
        answers = [failing, lambda _url: PAYLOAD]
        rates = self.load(lambda url: answers.pop(0)(url))
        self.assertEqual(rates["EUR"], 4.25)
        self.assertEqual(self.sleeps, [1])
        with open(self.cache, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["EUR"], 4.25)

    def test_uses_saved_rates_when_nbp_is_down(self):
        self.load(lambda _url: PAYLOAD)
        rates = self.load(failing)
        self.assertEqual(rates["EUR"], 4.25)
        self.assertEqual(len(self.sleeps), 2)

    def test_pln_only_without_saved_rates(self):
        self.assertEqual(self.load(failing), {"PLN": 1.0})


if __name__ == "__main__":
    unittest.main()
