"""Exchange rates from the National Bank of Poland API (table A, mid rate)."""
import json
import os
import time

from .net import fetch

NBP_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"
CACHE_FILE = os.path.join("data", "fx_rates.json")


def parse_nbp(payload: bytes) -> dict[str, float]:
    table = json.loads(payload)[0]
    rates = {r["code"]: float(r["mid"]) for r in table["rates"]}
    rates["PLN"] = 1.0
    return rates


def load_rates(cache_file: str = CACHE_FILE, attempts: int = 4, wait: float = 15.0,
               fetch_fn=fetch, sleep=time.sleep) -> dict[str, float]:
    """Fetches today's rates, retrying because the NBP API sometimes answers 500 for a while.

    Every good answer is saved to `cache_file`; if NBP stays down, the last saved rates are used,
    so one bad morning at the bank does not cost a whole day of prices. Without saved rates
only PLN is known.
    """
    error = None
    for attempt in range(attempts):
        try:
            rates = parse_nbp(fetch_fn(NBP_URL))
        except Exception as exc:  # HTTP errors, timeouts, malformed JSON
            error = exc
            print(f"NBP rates attempt {attempt + 1}/{attempts} failed: {exc}")
            if attempt + 1 < attempts:
                sleep(wait * (attempt + 1))
            continue
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(rates, f, indent=0, sort_keys=True)
        except OSError as exc:
            print(f"could not save {cache_file}: {exc}")
        return rates
    try:
        with open(cache_file, encoding="utf-8") as f:
            rates = json.load(f)
    except (OSError, ValueError):
        # all shops price in PLN today; foreign offers are then reported per product instead of failing the run
        print(f"::warning::NBP rates unavailable ({error}) and no saved rates; only PLN prices today")
        return {"PLN": 1.0}
    print(f"::warning::NBP rates unavailable ({error}); using saved rates from {cache_file}")
    return rates


def to_pln(amount: float, currency: str, rates: dict[str, float]) -> float:
    return round(amount * rates[currency.upper()], 2)
