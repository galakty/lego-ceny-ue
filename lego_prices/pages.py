"""Static, crawlable pages for search engines: one page per set, plus landing
pages per child's age, per theme and per piece count range, and a sitemap.

The interactive search on the home page is rendered in the browser, which search
engines index poorly, so every set and every common search also gets a plain HTML page.
"""
import datetime as dt
import html
import json
import os
import re
import unicodedata
from urllib.parse import urlencode

from . import deals
from .affiliates import search_links

DEFAULT_SITE_URL = "https://klockownik.pl"
SITE_NAME = "Klockownik"
LIST_LIMIT = 120  # sets per landing page; the full list is one click away in the search
AGES = range(2, 15)
PIECE_RANGES = [  # (slug, title, min, max)
    ("do-250", "LEGO do 250 klocków", None, 250),
    ("250-500", "LEGO od 250 do 500 klocków", 250, 500),
    ("500-1000", "LEGO od 500 do 1000 klocków", 500, 1000),
    ("ponad-1000", "LEGO powyżej 1000 klocków", 1000, None),
    ("ponad-2000", "LEGO powyżej 2000 klocków", 2000, None),
    ("ponad-3000", "LEGO powyżej 3000 klocków", 3000, None),
]

e = html.escape


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def pln(value: float) -> str:
    whole, frac = f"{value:,.2f}".split(".")
    return f"{whole.replace(',', ' ')},{frac} zł"


def plural(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def pieces_text(n: int) -> str:
    return f"{n} {plural(n, 'klocek', 'klocki', 'klocków')}"


def age_text(s: dict) -> str:
    if s["age_min"] is None:
        return ""
    return f"{s['age_min']}–{s['age_max']} lat" if s["age_max"] else f"{s['age_min']}+"


def age_title(age: int) -> str:
    return f"LEGO dla {age}-latka"


def best_cost(s: dict) -> float | None:
    if not s["offers"]:
        return None
    o = s["offers"][0]
    return o["total"] if o["total"] is not None else o["pln"]


AGE_SPAN = 3  # a "2+" Duplo set is technically fine for a 6-year-old, but not what a parent is looking for


def fits_age(s: dict, age: int) -> bool:
    return (s["age_min"] is not None and age - AGE_SPAN <= s["age_min"] <= age
            and (s["age_max"] is None or s["age_max"] >= age))


def in_range(s: dict, lo: int | None, hi: int | None) -> bool:
    return (lo is None or s["pieces"] >= lo) and (hi is None or s["pieces"] <= hi)


def ranked(sets: list[dict], age: int | None = None) -> list[dict]:
    """Sets with prices first, then (on age pages) those aimed closest to the age, then newest."""
    return sorted(sets, key=lambda s: (best_cost(s) is None, age - s["age_min"] if age is not None else 0, -s["year"], s["num"]))


def set_path(s: dict) -> str:
    return f"zestaw/{s['num']}/"


DISCLOSURE = ""  # set by build() from data/affiliates.json
NO_PRICE_LABEL = "Brak cen"  # build() points to the affiliate searches instead, when there are any


def layout(root: str, title: str, description: str, canonical: str, body: str, jsonld: dict | None = None,
           image: str = "") -> str:
    ld = f'\n  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    # the preview picture Facebook and messengers show when the link is shared
    og_image = (f'\n  <meta property="og:image" content="{e(image)}">\n  <meta name="twitter:card" content="summary_large_image">'
                if image else "")
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <link rel="canonical" href="{e(canonical)}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{e(canonical)}">
  <meta property="og:type" content="website">{og_image}
  <link rel="stylesheet" href="{root}style.css">{ld}
</head>
<body>
  <header class="top"><div class="wrap">
    <a class="brand" href="{root}">{SITE_NAME}</a>
    <a class="nav-link" href="{root}promocje/">Promocje dnia</a>
    <p class="tagline">Ceny LEGO w Polsce i UE. Szukaj po liczbie klocków, wieku dziecka i serii.</p>
  </div></header>
  <main class="wrap page">
{body}
  </main>
  <footer class="wrap foot">
    Dane o zestawach: <a href="https://rebrickable.com">Rebrickable</a> i <a href="https://brickset.com">Brickset</a>.
    Kursy walut: NBP. LEGO® jest znakiem towarowym Grupy LEGO, która nie sponsoruje tej strony. {e(DISCLOSURE)}
  </footer>
  <script data-goatcounter="https://klockownik.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <script src="{root}analytics.js"></script>
</body>
</html>
"""


def card_list(root: str, sets: list[dict], notes: dict[str, tuple[float, str]] | None = None) -> str:
    """Set cards; notes maps a set number to (price to show, deal label)."""
    items = []
    for s in sets:
        cost, note = (notes or {}).get(s["num"], (best_cost(s), ""))
        meta = " · ".join(x for x in (s["num"], pieces_text(s["pieces"]), age_text(s)) if x)
        price = f'<div class="price">od {pln(cost)}</div>' if cost is not None else f'<div class="price check">{e(NO_PRICE_LABEL)}</div>'
        if note:
            price = f'<div class="deal">{e(note)}</div>{price}'
        img = f'<img src="{e(s["img"])}" alt="" loading="lazy">' if s["img"] else ""
        items.append(
            f'<li><a class="card" href="{root}{set_path(s)}"><div class="img">{img}</div>'
            f'<div class="body"><h2>{e(s["name"])}</h2><div class="meta">{e(meta)}</div>'
            f'<div class="meta">{e(" · ".join(str(x) for x in (s["theme"], s["year"]) if x))}</div>{price}</div></a></li>')
    return f'<ul class="grid">{"".join(items)}</ul>'


def breadcrumbs(root: str, trail: list[tuple[str, str | None]]) -> str:
    parts = [f'<a href="{root}">Start</a>'] + [
        f'<a href="{root}{href}">{e(label)}</a>' if href else f"<span>{e(label)}</span>" for label, href in trail]
    return f'<nav class="crumbs" aria-label="Okruszki">{" › ".join(parts)}</nav>'


def affiliate_buttons(s: dict, affiliates: dict) -> str:
    links = "".join(f'<a class="shop-btn" href="{e(url)}" rel="sponsored nofollow noopener" target="_blank">Sprawdź na {e(name)}</a>'
                    for name, url in search_links(s["num"], affiliates))
    return f'<p class="shop-links">{links}</p>' if links else ""


def set_page(s: dict, related: list[dict], site_url: str, affiliates: dict | None = None) -> str:
    root = "../../"
    url = f"{site_url}/{set_path(s)}"
    facts = [f"Numer {s['num']}", pieces_text(s["pieces"]), age_text(s) and f"wiek {age_text(s)}", s["theme"], str(s["year"])]
    cost = best_cost(s)
    title = f"LEGO {s['num']} {s['name']} – {'cena od ' + pln(cost) if cost is not None else 'ceny'}, {pieces_text(s['pieces'])}"
    description = (f"LEGO {s['num']} {s['name']} ({s['theme']}, {s['year']}): {pieces_text(s['pieces'])}"
                   + (f", dla dzieci {age_text(s)}" if age_text(s) else "")
                   + ". Porównaj ceny w Polsce i UE razem z dostawą do Polski.")

    if s["offers"]:
        rows = "".join(
            f'<tr{" class=best" if i == 0 else ""}><td><a href="{e(o["url"])}" rel="{"sponsored " if o.get("sponsored") else ""}nofollow noopener" target="_blank">{e(o["shop"])}</a></td>'
            f'<td>{e(o["country"])}</td><td class="num">{pln(o["pln"])}</td>'
            f'<td class="num">{pln(o["shipping"]) if o["shipping"] is not None else ("nie wysyła do PL" if o["ships_to_pl"] is False else "?")}</td>'
            f'<td class="num">{pln(o["total"]) if o["total"] is not None else "–"}</td></tr>'
            for i, o in enumerate(s["offers"]))
        offers = ('<table><thead><tr><th>Sklep</th><th>Kraj</th><th class="num">Cena</th>'
                  f'<th class="num">Dostawa do PL</th><th class="num">Razem</th></tr></thead><tbody>{rows}</tbody></table>'
                  f'<p class="meta">Ceny z {e(s["offers"][0]["date"])}. Aktualizujemy je codziennie.</p>')
    else:
        offers = ('<p class="meta">Nie mamy jeszcze ceny z porównywanych sklepów.'
                  + (' Sprawdź aktualną cenę:</p>' if affiliates else ' Dodajemy kolejne sklepy.</p>'))
    ref = f'<p class="meta">Cena katalogowa LEGO w Niemczech: {s["lego_de_eur"]:.2f} EUR</p>'.replace(".", ",") if s["lego_de_eur"] else ""

    trail = [(s["theme"], f"seria/{slugify(s['theme'])}/")] if s["theme"] else []
    body = f"""{breadcrumbs(root, trail + [(s['name'], None)])}
    <article class="set">
      <div class="set-head">
        {f'<img src="{e(s["img"])}" alt="LEGO {e(s["num"])} {e(s["name"])}">' if s["img"] else ""}
        <div>
          <h1>LEGO {e(s['num'])} {e(s['name'])}</h1>
          <p class="meta">{e(" · ".join(f for f in facts if f))}</p>
          {ref}
        </div>
      </div>
      <h2>Ceny</h2>
      {offers}
      {affiliate_buttons(s, affiliates or {})}
    </article>
    {f'<h2>Podobne zestawy</h2>{card_list(root, related)}' if related else ""}"""

    product = {"@context": "https://schema.org", "@type": "Product", "name": f"LEGO {s['num']} {s['name']}",
               "sku": s["num"], "brand": {"@type": "Brand", "name": "LEGO"}, "url": url}
    if s["img"]:
        product["image"] = s["img"]
    if s["offers"]:
        prices = [o["pln"] for o in s["offers"]]
        product["offers"] = {"@type": "AggregateOffer", "priceCurrency": "PLN", "lowPrice": min(prices),
                             "highPrice": max(prices), "offerCount": len(prices)}
    return layout(root, title, description, url, body, product, s["img"])


def landing_page(root: str, title: str, intro: str, sets: list[dict], search_query: str, canonical: str, trail_label: str,
                 age: int | None = None) -> str:
    shown = ranked(sets, age)[:LIST_LIMIT]
    more = (f'<p><a class="more-link" href="{root}?{search_query}">Zobacz wszystkie ({len(sets)}) '
            f'w wyszukiwarce z filtrami</a></p>') if search_query else ""
    body = f"""{breadcrumbs(root, [(trail_label, None)])}
    <h1>{e(title)}</h1>
    <p class="lead">{e(intro)}</p>
    {more}
    {card_list(root, shown)}
    {more if len(sets) > LIST_LIMIT else ""}"""
    return layout(root, f"{title} – ceny i porównanie | {SITE_NAME}", intro, canonical, body)


def related_sets(s: dict, by_theme: dict[str, list[dict]], limit: int = 8) -> list[dict]:
    pool = [o for o in by_theme.get(s["theme"], []) if o["num"] != s["num"]]
    pool.sort(key=lambda o: (abs(o["pieces"] - s["pieces"]), -o["year"]))
    return pool[:limit]


def browse_nav(themes: list[tuple[str, str]]) -> str:
    """Links from the home page to all landing pages, so crawlers can find them."""
    ages = " ".join(f'<a href="wiek/{a}/">{a} {plural(a, "rok", "lata", "lat")}</a>' for a in AGES) + ' <a href="wiek/dorosli/">dorośli</a>'
    pieces = " ".join(f'<a href="klocki/{slug}/">{e(t.replace("LEGO ", ""))}</a>' for slug, t, _, _ in PIECE_RANGES)
    series = " ".join(f'<a href="seria/{slug}/">{e(name)}</a>' for name, slug in themes)
    return (f'<nav class="browse wrap" aria-label="Przeglądaj"><h2>Przeglądaj</h2>'
            f'<p><strong>Okazje:</strong> <a href="promocje/">Promocje dnia</a> '
            f'<a href="kalendarz-adwentowy-{dt.date.today().year}/">Kalendarze adwentowe {dt.date.today().year}</a> '
            + " ".join(f'<a href="prezent/do-{b}-zl/">Prezent do {b} zł</a>' for b in deals.GIFT_BUDGETS) + '</p>'
            f'<p><strong>Wiek dziecka:</strong> {ages}</p><p><strong>Liczba klocków:</strong> {pieces}</p>'
            f'<p><strong>Serie:</strong> {series}</p></nav>')


def percent(share: float) -> str:
    return f"{round(share * 100)}%"


def deals_page(sets: list[dict], site_url: str, eur_rate: float | None) -> str:
    root = "../"
    below = deals.below_list_price(sets, eur_rate)
    drops = deals.price_drops(sets)
    sections = []
    if below:
        notes = {s["num"]: (price, f"−{percent(d)} vs cena LEGO") for s, price, d in below}
        sections.append(f"""<h2>Najtaniej względem ceny katalogowej</h2>
    <p class="meta">Porównujemy najniższą cenę w dostępnych sklepach z ceną katalogową LEGO w Niemczech, przeliczoną po kursie NBP.</p>
    {card_list(root, [s for s, _, _ in below], notes)}""")
    if drops:
        notes = {s["num"]: (price, f"−{percent(d)} w {deals.LOOKBACK_DAYS} dni") for s, price, d in drops}
        sections.append(f"""<h2>Największe spadki cen</h2>
    <p class="meta">Najniższa dzisiejsza cena w porównaniu z najwyższą ceną z ostatnich {deals.LOOKBACK_DAYS} dni.</p>
    {card_list(root, [s for s, _, _ in drops], notes)}""")
    if not sections:
        sections.append('<p class="meta">Dziś nie znaleźliśmy wyraźnych promocji. Sprawdź jutro, ceny aktualizujemy codziennie.</p>')
    dates = [o["date"] for s in sets for o in s["offers"]]
    updated = f" Ceny z {max(dates)}." if dates else ""
    intro = (f"Zestawy LEGO, które dziś kosztują wyraźnie mniej niż zwykle: co najmniej {percent(deals.MIN_DISCOUNT)} "
             f"poniżej ceny katalogowej albo poniżej ceny z ostatnich tygodni.{updated}")
    body = f"""{breadcrumbs(root, [("Promocje dnia", None)])}
    <h1>Promocje LEGO dnia</h1>
    <p class="lead">{e(intro)}</p>
    {"".join(sections)}"""
    image = next((s["img"] for s, _, _ in below + drops if s["img"]), "")
    return layout(root, f"Promocje LEGO – dzisiejsze okazje cenowe | {SITE_NAME}", intro, f"{site_url}/promocje/", body, image=image)


def priced_list_page(title: str, intro: str, items: list[tuple[dict, float | None]], canonical: str, empty: str) -> str:
    """A landing page whose cards show the given prices (the cheapest offer in stock) instead of the best cost."""
    root = "../../"
    notes = {s["num"]: (price, "") for s, price in items}
    cards = card_list(root, [s for s, _ in items[:LIST_LIMIT]], notes) if items else f'<p class="meta">{e(empty)}</p>'
    body = f"""{breadcrumbs(root, [(title, None)])}
    <h1>{e(title)}</h1>
    <p class="lead">{e(intro)}</p>
    {cards}"""
    image = next((s["img"] for s, _ in items if s["img"]), "")
    return layout(root, f"{title} – ceny i porównanie | {SITE_NAME}", intro, canonical, body, image=image)


def seasonal_pages(sets: list[dict], site_url: str, year: int) -> dict[str, str]:
    """Pages for the gift season: advent calendars and gifts within a budget. Maps path to HTML."""
    out = {}
    rel = f"kalendarz-adwentowy-{year}/"
    out[rel] = priced_list_page(
        f"Kalendarze adwentowe LEGO {year}",
        f"Wszystkie kalendarze adwentowe LEGO na {year} rok, od najtańszego. Ceny z polskich sklepów aktualizujemy codziennie, "
        "więc łatwo złapiesz promocję przed grudniem.",
        deals.advent_calendars(sets, year), f"{site_url}/{rel}", "Nie mamy jeszcze kalendarzy na ten rok.")
    for budget in deals.GIFT_BUDGETS:
        rel = f"prezent/do-{budget}-zl/"
        out[rel] = priced_list_page(
            f"LEGO na prezent do {budget} zł",
            f"Zestawy LEGO dostępne dziś za {budget} zł lub mniej, od tych z największą liczbą klocków. "
            "Ceny z polskich sklepów, aktualizowane codziennie. Wiek dziecka sprawdzisz na karcie zestawu.",
            deals.gifts(sets, budget), f"{site_url}/{rel}", "Dziś nie mamy zestawów w tej cenie.")
    return out


def write(out_dir: str, rel: str, content: str) -> None:
    path = os.path.join(out_dir, rel, "index.html") if rel.endswith("/") or rel == "" else os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build(sets: list[dict], out_dir: str, site_url: str = DEFAULT_SITE_URL, affiliates: dict | None = None,
          eur_rate: float | None = None) -> int:
    global DISCLOSURE, NO_PRICE_LABEL
    affiliates = affiliates or {}
    DISCLOSURE = " ".join(a.get("disclosure", "") for a in affiliates.values()).strip()
    names = [a["name"] for a in affiliates.values()]
    NO_PRICE_LABEL = f"Sprawdź cenę na {' i '.join(names)} →" if names else "Brak cen"
    site_url = site_url.rstrip("/")
    urls = [""]
    by_theme: dict[str, list[dict]] = {}
    for s in sets:
        by_theme.setdefault(s["theme"], []).append(s)

    for s in sets:
        write(out_dir, set_path(s), set_page(s, related_sets(s, by_theme), site_url, affiliates))
        urls.append(set_path(s))

    for age in AGES:
        rel = f"wiek/{age}/"
        matching = [s for s in sets if fits_age(s, age)]
        intro = (f"Zestawy LEGO odpowiednie dla dziecka w wieku {age} {plural(age, 'roku', 'lat', 'lat')} według zaleceń producenta. "
                 f"Porównaj ceny w Polsce i UE i wybierz prezent dla {age}-latka.")
        write(out_dir, rel, landing_page("../../", age_title(age), intro, matching, urlencode({"wiek": age}), f"{site_url}/{rel}", f"Wiek {age} {plural(age, 'rok', 'lata', 'lat')}", age))
        urls.append(rel)
    adults = [s for s in sets if s["age_min"] is not None and s["age_min"] >= 16]
    write(out_dir, "wiek/dorosli/", landing_page(
        "../../", "LEGO dla dorosłych", "Zestawy LEGO dla dorosłych (16+ i 18+): duże modele kolekcjonerskie, Icons, Architecture i Technic.",
        adults, urlencode({"wiek": 18}), f"{site_url}/wiek/dorosli/", "Dla dorosłych"))
    urls.append("wiek/dorosli/")

    for slug, title, lo, hi in PIECE_RANGES:
        rel = f"klocki/{slug}/"
        query = urlencode({k: v for k, v in (("od", lo), ("do", hi)) if v is not None})
        write(out_dir, rel, landing_page("../../", title, f"{title}: zestawy posortowane od tych z najlepszą ceną. Porównaj ceny w Polsce i UE.",
                                         [s for s in sets if in_range(s, lo, hi)], query, f"{site_url}/{rel}", title))
        urls.append(rel)

    write(out_dir, "promocje/", deals_page(sets, site_url, eur_rate))
    urls.append("promocje/")
    for rel, content in seasonal_pages(sets, site_url, dt.date.today().year).items():
        write(out_dir, rel, content)
        urls.append(rel)

    themes = sorted(((name, slugify(name)) for name in by_theme if name), key=lambda t: t[0].lower())
    for name, slug in themes:
        rel = f"seria/{slug}/"
        write(out_dir, rel, landing_page("../../", f"LEGO {name}", f"Wszystkie zestawy LEGO {name} od 2020 roku z cenami, liczbą klocków i wiekiem.",
                                         by_theme[name], urlencode({"seria": name}), f"{site_url}/{rel}", name))
        urls.append(rel)

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, encoding="utf-8") as f:
        index = f.read()
    index = (index.replace("<!-- BROWSE -->", browse_nav(themes)).replace("{{SITE_URL}}", site_url)
             .replace("<!-- DISCLOSURE -->", e(DISCLOSURE)))
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index)

    today = dt.date.today().isoformat()
    sitemap = "".join(f"<url><loc>{e(site_url)}/{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    write(out_dir, "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n")
    write(out_dir, "sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>\n')
    return len(urls)
