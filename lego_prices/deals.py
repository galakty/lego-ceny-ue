"""Finds deals for the "Promocje" page: sets sold well below the LEGO list price,
and sets whose lowest price dropped compared with the previous weeks. Also the
sets LEGO retires soon, for the "Wycofywane wkrótce" page."""
import datetime as dt

MIN_DISCOUNT = 0.10  # smaller differences are noise, not a deal
LOOKBACK_DAYS = 30
LIMIT = 60


def best_in_stock(s: dict) -> float | None:
    """Cheapest PLN price among offers not marked as out of stock."""
    prices = [o["pln"] for o in s["offers"] if o["in_stock"] is not False]
    return min(prices) if prices else None


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


def price_drops(sets: list[dict]) -> list[tuple[dict, float, float]]:
    """(set, price, drop) for sets whose lowest price on the latest day is below the
    highest daily lowest price of the previous LOOKBACK_DAYS, biggest drop first."""
    latest = max((s["history"][-1][0] for s in sets if s["history"]), default=None)
    if latest is None:
        return []
    since = (dt.date.fromisoformat(latest) - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    found = []
    for s in sets:
        if len(s["history"]) < 2 or s["history"][-1][0] != latest:
            continue
        price = s["history"][-1][1]
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
