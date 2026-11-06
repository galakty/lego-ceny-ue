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
RETIRING_PATH = "wycofywane/"
MONTHS = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
          "październik", "listopad", "grudzień"]
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


def month_text(iso_date: str) -> str:
    """"2026-12-31" -> "grudzień 2026"."""
    d = dt.date.fromisoformat(iso_date)
    return f"{MONTHS[d.month - 1]} {d.year}"


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


def join_names(names: list[str]) -> str:
    """"A", "A i B", "A, B i C"."""
    return " i ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else "".join(names)


def quick_nav(root: str) -> str:
    """Buttons to the seasonal pages right under the header, on every page."""
    year = dt.date.today().year
    links = [(GIFT_FINDER_PATH, "✨", "Kreator prezentu"), (f"kalendarz-adwentowy-{year}/", "🎄", f"Kalendarze adwentowe {year}")] + [
        (f"prezent/do-{b}-zl/", "🎁", f"Prezent do {b} zł") for b in deals.GIFT_BUDGETS] + [
        (RETIRING_PATH, "⏳", "Wycofywane wkrótce")]
    items = "".join(f'<a class="quick-btn" href="{root}{href}"><span aria-hidden="true">{icon}</span> {e(label)}</a>'
                    for href, icon, label in links)
    return f'<nav class="quick" aria-label="Na skróty"><div class="wrap">{items}</div></nav>'


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
  <link rel="icon" href="{root}brick.png">
  <link rel="stylesheet" href="{root}style.css">{ld}
</head>
<body>
  <header class="top"><div class="wrap">
    <a class="brand" href="{root}"><img src="{root}brick.png" alt="" width="48" height="43">{SITE_NAME}</a>
    <a class="nav-link" href="{root}promocje/">Promocje dnia</a>
    <p class="tagline"><strong>Najtańsze LEGO w jednym miejscu.</strong> Codziennie porównujemy ceny w sklepach. Szukaj po wieku dziecka, liczbie klocków i serii.</p>
  </div></header>
  {quick_nav(root)}
  <main class="wrap page">
{body}
  </main>
  <footer class="wrap foot">
    Dane o zestawach: <a href="https://rebrickable.com">Rebrickable</a> i <a href="https://brickset.com">Brickset</a>.
    Kursy walut: NBP. LEGO® jest znakiem towarowym Grupy LEGO, która nie sponsoruje tej strony. {e(DISCLOSURE)}
    <a href="{root}o-stronie/">O stronie, kontakt i prywatność</a>
  </footer>
  <script data-goatcounter="https://klockownik.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <script src="{root}analytics.js"></script>
</body>
</html>
"""


def per_piece(cost: float | None, pieces: int) -> str:
    """Price per piece, e.g. "0,31 zł za klocek"; empty when either is unknown."""
    return f"{pln(cost / pieces)} za klocek" if cost is not None and pieces else ""


def is_30d_low(cost: float, low: float | None) -> bool:
    return low is not None and cost <= low + 0.005


def price_notes(s: dict, cost: float | None) -> str:
    """Small lines under a card's price: price per piece and how it compares with the 30-day low."""
    if cost is None:
        return ""
    notes = []
    if per_piece(cost, s["pieces"]):
        notes.append(f'<div class="meta">{per_piece(cost, s["pieces"])}</div>')
    low = s.get("low_30d")
    if is_30d_low(cost, low):
        notes.append('<div class="low30 best">Najtaniej od 30 dni</div>')
    elif low is not None:
        notes.append(f'<div class="low30">Najniżej w 30 dni: {pln(low)}</div>')
    return "".join(notes)


def card_list(root: str, sets: list[dict], notes: dict[str, tuple[float, str]] | None = None) -> str:
    """Set cards; notes maps a set number to (price to show, deal label)."""
    items = []
    for s in sets:
        cost, note = (notes or {}).get(s["num"], (best_cost(s), ""))
        meta = " · ".join(x for x in (s["num"], pieces_text(s["pieces"]), age_text(s)) if x)
        price = f'<div class="price">od {pln(cost)}</div>' if cost is not None else f'<div class="price check">{e(NO_PRICE_LABEL)}</div>'
        if note:
            price = f'<div class="deal">{e(note)}</div>{price}'
        price += price_notes(s, cost)
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


def price_summary(s: dict, cost: float) -> str:
    """Box above the offers table: cheapest price now, per piece, and the 30-day low."""
    items = [f'<div><span class="meta">Najniższa cena teraz</span><strong>{pln(cost)}</strong></div>']
    if s["pieces"]:
        items.append(f'<div><span class="meta">Cena za klocek</span><strong>{pln(cost / s["pieces"])}</strong></div>')
    low = s.get("low_30d")
    if low is not None:
        label = " (to teraz)" if is_30d_low(cost, low) else ""
        items.append(f'<div><span class="meta">Najniższa cena z 30 dni{label}</span><strong>{pln(low)}</strong></div>')
    since = (dt.date.today() - dt.timedelta(days=deals.LOOKBACK_DAYS)).isoformat()
    first = s["history"][0][0] if s["history"] else None
    note = (f'<p class="meta">Ceny tego zestawu śledzimy od {date_text(first)}, więc najniższa cena obejmuje krótszy okres.</p>'
            if low is not None and first and first > since else "")
    return f'<div class="price-summary">{"".join(items)}</div>{note}'


CHART_DAYS = 180  # older prices make the line too dense on a phone


def date_text(iso_date: str) -> str:
    return f"{dt.date.fromisoformat(iso_date):%d.%m.%Y}"


def price_chart(history: list[list]) -> str:
    """Static SVG line of the lowest daily price, so the chart works without JavaScript and is crawlable.
    Days are placed by date, so days without a price leave a straight segment instead of squeezing the line."""
    if not history:
        return ""
    since = (dt.date.fromisoformat(history[-1][0]) - dt.timedelta(days=CHART_DAYS)).isoformat()
    points = [(dt.date.fromisoformat(d), p) for d, p in history if d >= since]
    if len(points) < 2:
        return ""
    w, h, pad = 600, 140, 6
    first, last = points[0][0], points[-1][0]
    days = (last - first).days or 1
    low, high = min(p for _, p in points), max(p for _, p in points)
    span = high - low or 1

    def xy(day, price):
        return pad + (day - first).days * (w - 2 * pad) / days, h - pad - (price - low) * (h - 2 * pad) / span

    # a step line: a price holds until the next scrape changes it
    coords = []
    for i, (day, price) in enumerate(points):
        x, y = xy(day, price)
        if i:
            coords.append((x, coords[-1][1]))
        coords.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"{coords[0][0]:.1f},{h} {line} {coords[-1][0]:.1f},{h}"
    flat = " (bez zmian)" if high == low else ""
    label = f"Wykres najniższej ceny od {date_text(first.isoformat())} do {date_text(last.isoformat())}: od {pln(low)} do {pln(high)}"
    return f"""<figure class="price-chart">
        <figcaption>Najniższa cena w czasie{flat}</figcaption>
        <div class="plot">
          <div class="y-axis"><span>{pln(high)}</span><span>{pln(low)}</span></div>
          <svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="{e(label)}">
            <polygon points="{area}" class="area"/>
            <polyline points="{line}" class="line" vector-effect="non-scaling-stroke"/>
          </svg>
          <div class="x-axis"><span>{date_text(first.isoformat())}</span><span>{date_text(last.isoformat())}</span></div>
        </div>
      </figure>"""


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
        offers = ('<div class="table-scroll"><table><thead><tr><th>Sklep</th><th>Kraj</th><th class="num">Cena</th>'
                  f'<th class="num">Dostawa do PL</th><th class="num">Razem</th></tr></thead><tbody>{rows}</tbody></table></div>'
                  f'<p class="meta">Ceny z {e(s["offers"][0]["date"])}. Aktualizujemy je codziennie.</p>')
        offers = price_summary(s, cost) + offers
    else:
        offers = ('<p class="meta">Nie mamy jeszcze ceny z porównywanych sklepów.'
                  + (' Sprawdź aktualną cenę:</p>' if affiliates else ' Dodajemy kolejne sklepy.</p>'))
    ref = f'<p class="meta">Cena katalogowa LEGO w Niemczech: {s["lego_de_eur"]:.2f} EUR</p>'.replace(".", ",") if s["lego_de_eur"] else ""
    if s.get("exit_date") and s["exit_date"] >= dt.date.today().isoformat():
        ref += (f'<p class="meta retiring">⏳ LEGO planuje wycofać ten zestaw: {month_text(s["exit_date"])}. '
                f'<a href="{root}{RETIRING_PATH}">Inne wycofywane zestawy</a></p>')

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
      {price_chart(s["history"])}
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
                 age: int | None = None, about: tuple[str, ...] = ()) -> str:
    """List page; `about` paragraphs go under the list, so the sets stay at the top and search engines get the text."""
    shown = ranked(sets, age)[:LIST_LIMIT]
    more = (f'<p><a class="more-link" href="{root}?{search_query}">Zobacz wszystkie ({len(sets)}) '
            f'w wyszukiwarce z filtrami</a></p>') if search_query else ""
    body = f"""{breadcrumbs(root, [(trail_label, None)])}
    <h1>{e(title)}</h1>
    <p class="lead">{e(intro)}</p>
    {more}
    {card_list(root, shown) if shown else '<p class="meta">Nie mamy jeszcze takich zestawów w katalogu.</p>'}
    {more if len(sets) > LIST_LIMIT else ""}
    {"".join(f'<p class="about">{e(p)}</p>' for p in about)}"""
    return layout(root, f"{title} – ceny i porównanie | {SITE_NAME}", intro, canonical, body)


# Pages for popular searches that no single theme or filter covers (e.g. "lego kwiaty").
# Set names come from Rebrickable, so the words are English.
FLOWER_WORDS = re.compile(
    r"\b(flowers?|bouquets?|orchids?|roses?|tulips?|bonsai|succulents?|blossoms?|sunflowers?|wildflowers?|"
    r"poinsettias?|chrysanthemums?|lil(y|ies)|dais(y|ies)|peon(y|ies)|lavender|snake plant|bird of paradise|lotus flowers?)\b", re.I)
NOT_FLOWER_THEMES = {"Super Mario", "Speed Champions"}  # Piranha Plant, Lotus cars


def is_flower(s: dict) -> bool:
    return "botanical" in s["theme"].lower() or (s["theme"] not in NOT_FLOWER_THEMES and bool(FLOWER_WORDS.search(s["name"])))


FLOWERS_PATH = "kwiaty-lego/"
FLOWERS_TITLE = "Kwiaty LEGO: bukiety, orchidee i bonsai"
FLOWERS_INTRO = ("Kwiaty z klocków LEGO: bukiety, orchidee, tulipany, róże i drzewka bonsai z serii LEGO Botanicals i Icons. "
                 "Porównaj ceny w sklepach i kup kwiaty, które nigdy nie zwiędną.")
FLOWERS_ABOUT = (
    "Kwiaty LEGO to jeden z najpopularniejszych prezentów z klocków dla dorosłych: na Dzień Kobiet, Dzień Matki, walentynki "
    "albo zamiast zwykłego bukietu. Po złożeniu stoją w wazonie jak prawdziwe, a składanie zajmuje od jednego wieczoru do kilku dni.",
    "Najmniejsze zestawy, jak pojedyncze kwiatki czy mała orchidea, kosztują kilkadziesiąt złotych. Duże bukiety i bonsai "
    "to zwykle 150–300 zł, ale w promocjach bywają dużo tańsze. Ceny sprawdzamy codziennie, więc łatwo złapiesz najniższą.",
)
ARCHITECTURE_INTRO = ("LEGO Architecture: panoramy miast i słynne budowle z klocków, od Paryża i Nowego Jorku po Tadż Mahal. "
                      "Wszystkie zestawy z cenami z polskich sklepów, aktualizowanymi codziennie.")
ARCHITECTURE_ABOUT = (
    "Seria LEGO Architecture jest dla dorosłych i starszych dzieci, zwykle od 12 lub 18 lat. Zestawy Skyline to panoramy miast "
    "z najbardziej znanymi budynkami, a większe modele odwzorowują pojedyncze zabytki z dużą liczbą detali.",
    "To dobry prezent dla miłośników podróży: model miasta, w którym ktoś był, wygląda świetnie na półce lub biurku. "
    "Na stronie każdego zestawu znajdziesz liczbę klocków, cenę za klocek i historię najniższej ceny.",
)
ADULTS_INTRO = ("LEGO dla dorosłych: zestawy 16+ i 18+, czyli duże modele kolekcjonerskie z serii Icons, Architecture, Technic, "
                "Botanicals i Star Wars. Porównaj ceny i sprawdź, gdzie kupisz najtaniej.")
ADULTS_ABOUT = (
    "Zestawy LEGO dla dorosłych mają zwykle więcej klocków, bardziej złożoną budowę i projekt, który ma dobrze wyglądać "
    "na półce: samochody, budynki, kwiaty, statki kosmiczne i modele z filmów.",
    "To popularny prezent na urodziny i święta dla osób, które wracają do klocków po latach. Duże zestawy często tanieją "
    "w promocjach, dlatego przy każdym pokazujemy najniższą cenę z ostatnich 30 dni.",
)
THEME_COPY = {"Architecture": (ARCHITECTURE_INTRO, ARCHITECTURE_ABOUT)}  # theme -> (intro, about) for popular searches


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
            f'<p><strong>Okazje:</strong> <a href="promocje/">Promocje dnia</a> <a href="{GIFT_FINDER_PATH}">Kreator prezentu</a> '
            f'<a href="kalendarz-adwentowy-{dt.date.today().year}/">Kalendarze adwentowe {dt.date.today().year}</a> '
            + " ".join(f'<a href="prezent/do-{b}-zl/">Prezent do {b} zł</a>' for b in deals.GIFT_BUDGETS)
            + f' <a href="{RETIRING_PATH}">Wycofywane wkrótce</a></p>'
            f'<p><strong>Popularne:</strong> <a href="{FLOWERS_PATH}">Kwiaty LEGO</a> <a href="seria/architecture/">LEGO Architecture</a> '
            f'<a href="wiek/dorosli/">LEGO dla dorosłych</a></p>'
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


GIFT_FINDER_PATH = "prezent/kreator/"
GIFT_AGES = [(str(a), f"{a} {plural(a, 'rok', 'lata', 'lat')}") for a in range(2, 15)] + [("18", "Nastolatek lub dorosły")]
GIFT_FINDER_BUDGETS = [50, 100, 150, 200, 300, 500]
GIFT_INTERESTS = [  # (value used by gift.js, label)
    ("auta", "🚗 Auta"), ("zwierzeta", "🐶 Zwierzęta"), ("minecraft", "⛏️ Minecraft"), ("kosmos", "🚀 Kosmos i Star Wars"),
    ("superbohaterowie", "🦸 Superbohaterowie"), ("disney", "👑 Disney i księżniczki"), ("dinozaury", "🦖 Dinozaury"),
    ("miasto", "🏙️ Miasto i budowle"), ("harrypotter", "🪄 Harry Potter"), ("ninjago", "🥷 Ninjago"),
    ("gry", "🎮 Mario i gry"), ("technika", "⚙️ Technika i roboty"), ("kwiaty", "🌷 Kwiaty"),
]


GIFT_FAQ = [  # (question, answer); shown on the page and as FAQPage structured data for search engines
    ("Jak działa kreator prezentu LEGO?",
     "Wybierasz wiek dziecka, budżet i zainteresowania, a kreator od razu pokazuje 5 pasujących zestawów LEGO. "
     "Najpierw te z największą liczbą klocków w Twoim budżecie, każdy z najtańszym sklepem, w którym jest dostępny."),
    ("Skąd są ceny?",
     "Ceny zestawów sprawdzamy codziennie w sklepach w Polsce i w innych krajach UE i przeliczamy na złote. "
     "Pokazujemy tylko oferty dostępne w sprzedaży."),
    ("Jaki zestaw LEGO wybrać na prezent dla dziecka?",
     "Zacznij od wieku podanego na pudełku: dla 2–5 lat najlepsze są duże klocki DUPLO, od 4–5 lat proste zestawy "
     "LEGO City, Friends i Disney, a od 7–9 lat Technic, Star Wars, Ninjago czy Minecraft. Potem wybierz to, co dziecko lubi."),
    ("Jaki prezent LEGO dla dorosłego?",
     "Dorośli najczęściej wybierają zestawy 18+: kwiaty LEGO, budowle z serii Architecture, samochody Technic i Icons. "
     "W kreatorze wybierz wiek „Nastolatek lub dorosły”."),
]


def gift_finder_page(site_url: str) -> str:
    """Form for the gift finder; gift.js picks the sets in the browser from data/sets.json.

    The picks need JavaScript, so the page also carries plain text, links and an FAQ that search engines can read.
    """
    root = "../../"
    title = "Kreator prezentu LEGO"
    intro = ("Wybierz wiek dziecka, budżet i to, co lubi. Pokażemy 5 zestawów LEGO z największą liczbą klocków "
             "w tej cenie, z najtańszym sklepem i ceną sprawdzaną codziennie.")
    description = ("Kreator prezentu LEGO: podaj wiek, budżet i zainteresowania, a dobierzemy 5 zestawów z najlepszą ceną. "
                   "Pomysł na prezent na urodziny, Mikołajki i święta.")
    ages = "".join(f'<option value="{v}">{e(label)}</option>' for v, label in GIFT_AGES)
    budgets = "".join(f'<button type="button" data-value="{b}" aria-pressed="{str(b == 200).lower()}">do {b} zł</button>'
                      for b in GIFT_FINDER_BUDGETS) + '<button type="button" data-value="" aria-pressed="false">bez limitu</button>'
    interests = "".join(f'<button type="button" data-value="{v}" aria-pressed="false">{e(label)}</button>' for v, label in GIFT_INTERESTS)
    age_links = " · ".join(f'<a href="{root}wiek/{a}/">{e(age_title(a))}</a>' for a in AGES)
    budget_links = " · ".join(f'<a href="{root}prezent/do-{b}-zl/">LEGO na prezent do {b} zł</a>' for b in deals.GIFT_BUDGETS)
    faq = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in GIFT_FAQ)
    body = f"""{breadcrumbs(root, [(title, None)])}
    <h1>🎁 {e(title)}</h1>
    <p class="lead">{e(intro)}</p>
    <form class="gift-form" onsubmit="return false">
      <label class="field"><strong>Wiek</strong>
        <select id="g-age"><option value="">Dowolny</option>{ages}</select></label>
      <div class="field"><strong>Budżet</strong><div class="chips" id="g-budget">{budgets}</div></div>
      <div class="field"><strong>Co lubi?</strong> <span class="meta">Możesz zaznaczyć kilka albo nic.</span>
        <div class="chips" id="g-interests">{interests}</div></div>
    </form>
    <p class="meta" id="g-count" aria-live="polite">Wczytuję zestawy…</p>
    <ol class="gift-list" id="g-list"></ol>
    <button type="button" class="more" id="g-more" hidden>Pokaż kolejne 5</button>
    <noscript><p>Kreator działa z włączonym JavaScriptem. Bez niego zobacz <a href="{root}prezent/do-100-zl/">LEGO do 100 zł</a>.</p></noscript>
    <section class="about">
      <h2>Pomysł na prezent z LEGO w minutę</h2>
      <p>Nie wiesz, jaki zestaw LEGO kupić na urodziny, Mikołajki albo pod choinkę? Kreator prezentu LEGO dobiera zestawy
        do wieku dziecka, budżetu i tego, co lubi: aut, dinozaurów, Minecrafta, Star Wars, księżniczek Disneya czy Harry'ego Pottera.
        Wszystkie ceny porównujemy codziennie w sklepach, więc od razu widzisz, gdzie kupisz najtaniej.</p>
      <p><strong>Prezent według wieku:</strong> {age_links} · <a href="{root}wiek/dorosli/">LEGO dla dorosłych</a></p>
      <p><strong>Prezent według budżetu:</strong> {budget_links}</p>
      <p><strong>Na święta:</strong> <a href="{root}kalendarz-adwentowy-{dt.date.today().year}/">Kalendarze adwentowe LEGO</a> ·
        <a href="{root}kwiaty-lego/">Kwiaty LEGO</a> · <a href="{root}promocje/">Promocje dnia</a></p>
      <h2>Najczęstsze pytania</h2>
      {faq}
    </section>
    <script src="{root}gift.js" defer></script>"""
    jsonld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in GIFT_FAQ]}
    return layout(root, f"{title} – dobierz zestaw do wieku i budżetu | {SITE_NAME}", description,
                  f"{site_url}/{GIFT_FINDER_PATH}", body, jsonld=jsonld)


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


def retiring_page(sets: list[dict], site_url: str, eur_rate: float | None, today: dt.date) -> str:
    """Sets LEGO retires soon, grouped by the month they go, with the discount from the list price."""
    root = "../"
    found = deals.retiring(sets, today)[:LIST_LIMIT]
    by_month: dict[str, list[tuple[dict, float | None]]] = {}
    for s, price in found:
        by_month.setdefault(month_text(s["exit_date"]), []).append((s, price))
    sections = []
    for month, items in by_month.items():
        notes = {}
        for s, price in items:
            discount = deals.list_price_discount(s, price, eur_rate)
            notes[s["num"]] = (price, f"−{percent(discount)} vs cena LEGO" if discount and discount >= deals.MIN_DISCOUNT else "")
        sections.append(f'<h2>Wycofanie: {e(month)}</h2>{card_list(root, [s for s, _ in items], notes)}')
    if not sections:
        sections.append('<p class="meta">Nie znamy jeszcze zestawów wycofywanych w najbliższych miesiącach.</p>')
    intro = ("Zestawy LEGO, które producent wkrótce przestanie sprzedawać, od najszybciej wycofywanych. "
             "Po wycofaniu ceny popularnych zestawów często rosną, więc to ostatnia okazja, by kupić je w zwykłej cenie.")
    body = f"""{breadcrumbs(root, [("Wycofywane wkrótce", None)])}
    <h1>LEGO wycofywane wkrótce</h1>
    <p class="lead">{e(intro)}</p>
    <p class="meta">Planowane daty wycofania pochodzą z <a href="https://brickset.com">Brickset</a> i mogą się zmienić.
    Ceny z polskich sklepów aktualizujemy codziennie. To nie jest porada inwestycyjna: nie gwarantujemy, że zestaw zyska na wartości.</p>
    {"".join(sections)}"""
    image = next((s["img"] for s, _ in found if s["img"]), "")
    return layout(root, f"LEGO wycofywane w {today.year} i {today.year + 1} – ostatnia szansa | {SITE_NAME}", intro,
                  f"{site_url}/{RETIRING_PATH}", body, image=image)


CONTACT_EMAIL = "kontakt.klockownik@gmail.com"


def about_page(site_url: str, shops: list[str], affiliates: dict) -> str:
    root = "../"
    programs = [a["name"] for a in affiliates.values()]
    body = f"""{breadcrumbs(root, [("O stronie", None)])}
    <article class="about">
    <h1>O stronie Klockownik</h1>
    <p class="lead">Klockownik to darmowa porównywarka cen zestawów LEGO. Codziennie sprawdzamy ceny w sklepach i pokazujemy,
    gdzie dany zestaw jest najtańszy, razem z historią ceny.</p>
    <h2>Skąd bierzemy ceny</h2>
    <p>Ceny pobieramy automatycznie raz dziennie ze stron sklepów{": " + e(join_names(shops)) if shops else ""}.
    Oferty niedostępne w sklepie nie są pokazywane. Ceny w sklepie mogą zmienić się w ciągu dnia, więc przed zakupem
    zawsze sprawdź cenę na stronie sklepu. Dane o zestawach (liczba klocków, wiek, seria) pochodzą z
    <a href="https://rebrickable.com">Rebrickable</a> i <a href="https://brickset.com">Brickset</a>.</p>
    <h2>Jak zarabiamy</h2>
    <p>Część linków do sklepów to linki partnerskie{" (" + e(join_names(programs + ["webePartners"])) + ")" if programs else ""}.
    Jeśli po kliknięciu coś kupisz, sklep może zapłacić nam niewielką prowizję. Ty nie płacisz więcej, a kolejność ofert
    zależy wyłącznie od ceny. {e(DISCLOSURE)}</p>
    <h2>Prywatność i cookies</h2>
    <p>Klockownik nie zbiera danych osobowych i nie używa własnych plików cookies. Odwiedziny liczymy anonimowo narzędziem
    <a href="https://www.goatcounter.com">GoatCounter</a>, które nie używa cookies i nie śledzi użytkowników.
    Po kliknięciu w link do sklepu lub partnera (np. Amazon, Allegro) obowiązuje polityka prywatności tego serwisu,
    który może zapisać własne pliki cookies, aby przypisać zakup do naszego polecenia.</p>
    <h2>Kontakt</h2>
    <p>Pytania, błędy w cenach, propozycje współpracy: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>
    <p class="meta">LEGO® jest znakiem towarowym Grupy LEGO, która nie sponsoruje, nie autoryzuje ani nie popiera tej strony.</p>
    </article>"""
    intro = "Czym jest Klockownik, skąd bierzemy ceny LEGO, jak zarabiamy, prywatność i kontakt."
    return layout(root, f"O stronie, kontakt i prywatność | {SITE_NAME}", intro, f"{site_url}/o-stronie/", body)


def write(out_dir: str, rel: str, content: str) -> None:
    path = os.path.join(out_dir, rel, "index.html") if rel.endswith("/") or rel == "" else os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build(sets: list[dict], out_dir: str, site_url: str = DEFAULT_SITE_URL, affiliates: dict | None = None,
          eur_rate: float | None = None, shops: list[str] | None = None) -> int:
    global DISCLOSURE, NO_PRICE_LABEL
    affiliates = affiliates or {}
    DISCLOSURE = " ".join(a.get("disclosure", "") for a in affiliates.values()).strip()
    names = [a["name"] for a in affiliates.values()]
    NO_PRICE_LABEL = f"Sprawdź cenę na {join_names(names)} →" if names else "Brak cen"
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
        "../../", "LEGO dla dorosłych", ADULTS_INTRO, adults, urlencode({"wiek": 18}), f"{site_url}/wiek/dorosli/", "Dla dorosłych",
        about=ADULTS_ABOUT))
    urls.append("wiek/dorosli/")
    write(out_dir, FLOWERS_PATH, landing_page("../", FLOWERS_TITLE, FLOWERS_INTRO, [s for s in sets if is_flower(s)], "",
                                              f"{site_url}/{FLOWERS_PATH}", "Kwiaty LEGO", about=FLOWERS_ABOUT))
    urls.append(FLOWERS_PATH)

    for slug, title, lo, hi in PIECE_RANGES:
        rel = f"klocki/{slug}/"
        query = urlencode({k: v for k, v in (("od", lo), ("do", hi)) if v is not None})
        write(out_dir, rel, landing_page("../../", title, f"{title}: zestawy posortowane od tych z najlepszą ceną. Porównaj ceny w Polsce i UE.",
                                         [s for s in sets if in_range(s, lo, hi)], query, f"{site_url}/{rel}", title))
        urls.append(rel)

    write(out_dir, "promocje/", deals_page(sets, site_url, eur_rate))
    urls.append("promocje/")
    write(out_dir, RETIRING_PATH, retiring_page(sets, site_url, eur_rate, dt.date.today()))
    urls.append(RETIRING_PATH)
    write(out_dir, "o-stronie/", about_page(site_url, shops or [], affiliates))
    urls.append("o-stronie/")
    write(out_dir, GIFT_FINDER_PATH, gift_finder_page(site_url))
    urls.append(GIFT_FINDER_PATH)
    for rel, content in seasonal_pages(sets, site_url, dt.date.today().year).items():
        write(out_dir, rel, content)
        urls.append(rel)

    themes = sorted(((name, slugify(name)) for name in by_theme if name), key=lambda t: t[0].lower())
    for name, slug in themes:
        rel = f"seria/{slug}/"
        intro, about = THEME_COPY.get(name, (f"Wszystkie zestawy LEGO {name} od 2020 roku z cenami, liczbą klocków i wiekiem.", ()))
        write(out_dir, rel, landing_page("../../", f"LEGO {name}", intro, by_theme[name], urlencode({"seria": name}),
                                         f"{site_url}/{rel}", name, about=about))
        urls.append(rel)

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, encoding="utf-8") as f:
        index = f.read()
    index = (index.replace("<!-- BROWSE -->", browse_nav(themes)).replace("<!-- QUICKNAV -->", quick_nav("")).replace("{{SITE_URL}}", site_url)
             .replace("<!-- DISCLOSURE -->", e(DISCLOSURE)))
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index)

    today = dt.date.today().isoformat()
    sitemap = "".join(f"<url><loc>{e(site_url)}/{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    write(out_dir, "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n")
    write(out_dir, "sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>\n')
    return len(urls)
