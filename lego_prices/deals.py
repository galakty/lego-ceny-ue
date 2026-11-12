"""Finds deals for the "Promocje" page: sets sold well below the LEGO list price,
and sets whose lowest price dropped compared with the previous weeks. Also the
sets LEGO retires soon, for the "Wycofywane wkrótce" page."""
import datetime as dt

MIN_DISCOUNT = 0.10  # smaller differences are noise, not a deal
LOOKBACK_DAYS = 30
LIMIT = 60


SUSPICIOUS_SHARE = 0.45  # an offer under this share of the next cheapest shop is most likely a data error


def plausible_prices(s: dict) -> list[float]:
    """PLN prices of the offers not marked as out of stock, without suspiciously low ones: a price
    under SUSPICIOUS_SHARE of the cheapest other shop is usually a wrong price in the shop's page or feed."""
    prices = sorted(o["pln"] for o in s["offers"] if o["in_stock"] is not False)
    while len(prices) > 1 and prices[0] < SUSPICIOUS_SHARE * prices[1]:
        prices.pop(0)
    return prices


def best_in_stock(s: dict) -> float | None:
    """Cheapest believable PLN price among offers not marked as out of stock."""
    prices = plausible_prices(s)
    return prices[0] if prices else None


def latest_price(s: dict, latest: str) -> float | None:
    """Today's lowest price from the history, when it is also the cheapest believable offer; None otherwise."""
    if not s["history"] or s["history"][-1][0] != latest:
        return None
    price, best = s["history"][-1][1], best_in_stock(s)
    return price if best is not None and abs(best - price) < 0.005 else None


def below_list_price(sets: list[dict], eur_rate: float | None) -> list[tuple[dict, float, float]]:
    """(set, price, discount) for sets cheaper than the LEGO list price in Germany, biggest discount first."""
    if not eur_rate:
        return []
    found = []
    for s in sets:
        price = best_in_stock(s)
        discount = list_price_discount(s, price, eur_rate)
        if discount is not None and discount >= MIN_DISCOUNT:
            found.append((s, price, discount))
    found.sort(key=lambda t: (-t[2], t[0]["num"]))
    return found[:LIMIT]


def lowest_recent(history: list[list], latest: str | None, days: int = LOOKBACK_DAYS) -> float | None:
    """Lowest daily price in the `days` days up to and including `latest` (the newest scrape date), or None."""
    if not latest:
        return None
    since = (dt.date.fromisoformat(latest) - dt.timedelta(days=days)).isoformat()
    recent = [p for d, p in history if since < d <= latest]
    return min(recent) if recent else None


def price_drops(sets: list[dict]) -> list[tuple[dict, float, float]]:
    """(set, price, drop) for sets whose lowest price on the latest day is below the
    highest daily lowest price of the previous LOOKBACK_DAYS, biggest drop first."""
    latest = max((s["history"][-1][0] for s in sets if s["history"]), default=None)
    if latest is None:
        return []
    since = (dt.date.fromisoformat(latest) - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    found = []
    for s in sets:
        price = latest_price(s, latest)
        if len(s["history"]) < 2 or price is None:
            continue
        before = [p for d, p in s["history"][:-1] if d >= since]
        if not before:
            continue
        drop = 1 - price / max(before)
        if drop >= MIN_DISCOUNT:
            found.append((s, price, drop))
    found.sort(key=lambda t: (-t[2], t[0]["num"]))
    return found[:LIMIT]


GIFT_BUDGETS = [50, 100, 200]  # PLN


def gifts(sets: list[dict], budget: float) -> list[tuple[dict, float]]:
    """(set, price) for sets in stock for at most the budget, most pieces for the money first."""
    found = [(s, p) for s in sets if (p := best_in_stock(s)) is not None and p <= budget]
    found.sort(key=lambda t: (-t[0]["pieces"], t[1], t[0]["num"]))
    return found


def advent_calendars(sets: list[dict], year: int) -> list[tuple[dict, float | None]]:
    """(set, lowest price or None) for this year's LEGO advent calendars, cheapest first, unpriced last."""
    found = [(s, best_in_stock(s)) for s in sets if s["year"] == year and "advent calendar" in s["name"].lower()]
    found.sort(key=lambda t: (t[1] is None, t[1] or 0, t[0]["num"]))
    return found


RETIRING_DAYS = 365  # Brickset rarely knows exit dates further ahead


def list_price_discount(s: dict, price: float | None, eur_rate: float | None) -> float | None:
    """Share below the LEGO list price in Germany, negative when dearer; None when either price is missing."""
    if price is None or not s["lego_de_eur"] or not eur_rate:
        return None
    return 1 - price / (s["lego_de_eur"] * eur_rate)


def retiring(sets: list[dict], today: dt.date) -> list[tuple[dict, float | None]]:
    """(set, lowest price or None) for sets LEGO retires within RETIRING_DAYS, soonest first,
    priced before unpriced on the same date."""
    until = (today + dt.timedelta(days=RETIRING_DAYS)).isoformat()
    found = [(s, best_in_stock(s)) for s in sets if s.get("exit_date") and today.isoformat() <= s["exit_date"] <= until]
    found.sort(key=lambda t: (t[0]["exit_date"], t[1] is None, t[0]["num"]))
    return found


def black_friday_date(year: int) -> dt.date:
    """The day after the fourth Thursday of November (US Thanksgiving)."""
    first = dt.date(year, 11, 1)
    thursday = first + dt.timedelta(days=(3 - first.weekday()) % 7 + 21)
    return thursday + dt.timedelta(days=1)


BF_MIN_HISTORY = 5     # days of earlier prices needed to judge a promotion
BF_REAL_MIN = 0.05     # a 30-day low counts as a deal when it is this much below the 30-day high or the list price
BF_HIGHER = 0.10       # "it was cheaper": today's price this much above the 30-day low


def black_friday(sets: list[dict], eur_rate: float | None) -> tuple[list[tuple[dict, float, str]], list[tuple[dict, float, float, str]]]:
    """Two lists for the Black Friday page:
    real deals as (set, price, label): today's price is the lowest of the past LOOKBACK_DAYS and clearly below the usual price;
    no bargains as (set, price, low, day of low): sets clearly cheaper in the past LOOKBACK_DAYS than today."""
    latest = max((s["history"][-1][0] for s in sets if s["history"]), default=None)
    if latest is None:
        return [], []
    since = (dt.date.fromisoformat(latest) - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    real, higher = [], []
    for s in sets:
        price = latest_price(s, latest)
        before = [(d, p) for d, p in s["history"][:-1] if d >= since]
        if price is None or len(before) < BF_MIN_HISTORY:
            continue
        low_day, low = min(before, key=lambda t: (t[1], t[0]))
        high = max(p for _, p in before)
        if price <= low + 0.005:
            drop = 1 - price / high
            vs_list = list_price_discount(s, price, eur_rate) or 0.0
            if max(drop, vs_list) >= BF_REAL_MIN:
                label = f"−{round(vs_list * 100)}% vs cena LEGO" if vs_list >= drop else f"−{round(drop * 100)}% w {LOOKBACK_DAYS} dni"
                real.append((s, price, label, max(drop, vs_list)))
        elif price >= low * (1 + BF_HIGHER):
            higher.append((s, price, low, low_day, 1 - low / price))
    real.sort(key=lambda t: (-t[3], t[0]["num"]))
    higher.sort(key=lambda t: (-t[4], t[0]["num"]))
    return [t[:3] for t in real[:LIMIT]], [t[:4] for t in higher[:LIMIT]]
