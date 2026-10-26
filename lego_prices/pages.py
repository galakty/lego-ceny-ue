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

DEFAULT_SITE_URL = "https://galakty.github.io/lego-ceny-ue"
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


def ranked(sets: list[dict]) -> list[dict]:
    """Sets with prices first, then newest."""
    return sorted(sets, key=lambda s: (best_cost(s) is None, -s["year"], s["num"]))


def set_path(s: dict) -> str:
    return f"zestaw/{s['num']}/"


def layout(root: str, title: str, description: str, canonical: str, body: str, jsonld: dict | None = None) -> str:
    ld = f'\n  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
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
  <link rel="stylesheet" href="{root}style.css">{ld}
</head>
<body>
  <header class="top"><div class="wrap">
    <a class="brand" href="{root}">{SITE_NAME}</a>
    <p class="tagline">Ceny LEGO w Polsce i UE. Szukaj po liczbie klocków, wieku dziecka i serii.</p>
  </div></header>
  <main class="wrap page">
{body}
  </main>
  <footer class="wrap foot">
    Dane o zestawach: <a href="https://rebrickable.com">Rebrickable</a> i <a href="https://brickset.com">Brickset</a>.
    Kursy walut: NBP. LEGO® jest znakiem towarowym Grupy LEGO, która nie sponsoruje tej strony.
  </footer>
</body>
</html>
"""


def card_list(root: str, sets: list[dict]) -> str:
    items = []
    for s in sets:
        cost = best_cost(s)
        meta = " · ".join(x for x in (s["num"], pieces_text(s["pieces"]), age_text(s)) if x)
        price = f'<div class="price">od {pln(cost)}</div>' if cost is not None else '<div class="price none">Brak cen</div>'
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


def set_page(s: dict, related: list[dict], site_url: str) -> str:
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
            f'<tr{" class=best" if i == 0 else ""}><td><a href="{e(o["url"])}" rel="nofollow noopener" target="_blank">{e(o["shop"])}</a></td>'
            f'<td>{e(o["country"])}</td><td class="num">{pln(o["pln"])}</td>'
            f'<td class="num">{pln(o["shipping"]) if o["shipping"] is not None else ("nie wysyła do PL" if o["ships_to_pl"] is False else "?")}</td>'
            f'<td class="num">{pln(o["total"]) if o["total"] is not None else "–"}</td></tr>'
            for i, o in enumerate(s["offers"]))
        offers = ('<table><thead><tr><th>Sklep</th><th>Kraj</th><th class="num">Cena</th>'
                  f'<th class="num">Dostawa do PL</th><th class="num">Razem</th></tr></thead><tbody>{rows}</tbody></table>'
                  f'<p class="meta">Ceny z {e(s["offers"][0]["date"])}. Aktualizujemy je codziennie.</p>')
    else:
        offers = '<p class="meta">Nie mamy jeszcze cen dla tego zestawu. Dodajemy kolejne sklepy.</p>'
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
    return layout(root, title, description, url, body, product)


def landing_page(root: str, title: str, intro: str, sets: list[dict], search_query: str, canonical: str, trail_label: str) -> str:
    shown = ranked(sets)[:LIST_LIMIT]
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
            f'<p><strong>Wiek dziecka:</strong> {ages}</p><p><strong>Liczba klocków:</strong> {pieces}</p>'
            f'<p><strong>Serie:</strong> {series}</p></nav>')


def write(out_dir: str, rel: str, content: str) -> None:
    path = os.path.join(out_dir, rel, "index.html") if rel.endswith("/") or rel == "" else os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build(sets: list[dict], out_dir: str, site_url: str = DEFAULT_SITE_URL) -> int:
    site_url = site_url.rstrip("/")
    urls = [""]
    by_theme: dict[str, list[dict]] = {}
    for s in sets:
        by_theme.setdefault(s["theme"], []).append(s)

    for s in sets:
        write(out_dir, set_path(s), set_page(s, related_sets(s, by_theme), site_url))
        urls.append(set_path(s))

    for age in AGES:
        rel = f"wiek/{age}/"
        matching = [s for s in sets if fits_age(s, age)]
        intro = (f"Zestawy LEGO odpowiednie dla dziecka w wieku {age} {plural(age, 'roku', 'lat', 'lat')} według zaleceń producenta. "
                 f"Porównaj ceny w Polsce i UE i wybierz prezent dla {age}-latka.")
        write(out_dir, rel, landing_page("../../", age_title(age), intro, matching, urlencode({"wiek": age}), f"{site_url}/{rel}", f"Wiek {age} {plural(age, 'rok', 'lata', 'lat')}"))
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

    themes = sorted(((name, slugify(name)) for name in by_theme if name), key=lambda t: t[0].lower())
    for name, slug in themes:
        rel = f"seria/{slug}/"
        write(out_dir, rel, landing_page("../../", f"LEGO {name}", f"Wszystkie zestawy LEGO {name} od 2020 roku z cenami, liczbą klocków i wiekiem.",
                                         by_theme[name], urlencode({"seria": name}), f"{site_url}/{rel}", name))
        urls.append(rel)

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, encoding="utf-8") as f:
        index = f.read()
    index = index.replace("<!-- BROWSE -->", browse_nav(themes)).replace("{{SITE_URL}}", site_url)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index)

    today = dt.date.today().isoformat()
    sitemap = "".join(f"<url><loc>{e(site_url)}/{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    write(out_dir, "sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>\n')
    return len(urls)
