"""Daily short videos (reels) for social media: picks the sets with the biggest price
difference between shops on the newest scrape day and renders one video per set into
site/rolki/, with a ready caption, on a page that is hidden from search engines."""
import datetime as dt
import html
import os
import statistics
import tempfile
from collections import defaultdict

from . import catalog, pages
from .net import fetch
from .scrape import load_shops

COUNT = 3              # videos per day; one to post, the others as spares
MIN_SHARE = 0.15       # smaller differences do not make a story
SPIKE = 1.2            # an offer this much above its shop's recent median is a price spike, not a real price
SPIKE_DAYS = 14
REPEAT_DAYS = 14       # a set featured in a video is skipped for this many days
OUT_PATH = "rolki/"
HOOKS = ["Ten sam zestaw LEGO.", "Przepłacasz za LEGO?", "Zanim kupisz ten zestaw…"]
BASE_TAGS = ["#lego", "#klocki", "#promocje", "#legopolska"]


def daily_offers(prices: list[dict]) -> dict[str, dict[str, dict[str, float]]]:
    """day -> set -> shop -> PLN price, in-stock offers only."""
    days: dict = defaultdict(lambda: defaultdict(dict))
    for row in prices:
        if row["in_stock"] == "0" or not row["price_pln"]:
            continue
        days[row["date"]][row["set_num"]][row["shop"]] = float(row["price_pln"])
    return days


def is_spike(price: float, earlier: list[float]) -> bool:
    return bool(earlier) and price > SPIKE * statistics.median(earlier)


def day_candidates(days: dict, day: str) -> list[dict]:
    """Sets with at least two believable offers on `day`, biggest difference in złoty first."""
    since = (dt.date.fromisoformat(day) - dt.timedelta(days=SPIKE_DAYS)).isoformat()
    earlier_days = [d for d in days if since <= d < day]
    found = []
    for set_num, shops in days[day].items():
        offers = [(shop, price) for shop, price in shops.items()
                  if not is_spike(price, [days[d][set_num][shop] for d in earlier_days
                                          if shop in days[d].get(set_num, {})])]
        if len(offers) < 2:
            continue
        offers.sort(key=lambda o: (-o[1], o[0]))
        diff = offers[0][1] - offers[-1][1]
        share = diff / offers[0][1]
        if share >= MIN_SHARE:
            found.append({"set_num": set_num, "date": day, "offers": offers, "diff": diff, "pct": share * 100})
    found.sort(key=lambda c: (-c["diff"], c["set_num"]))
    return found


def daily_picks(prices: list[dict], count: int = COUNT) -> dict[str, list[dict]]:
    """day -> picked deals, for every scrape day. Picks of the previous REPEAT_DAYS days are
    skipped, so the choice for a day is the same whenever the site is rebuilt."""
    days = daily_offers(prices)
    picks: dict[str, list[dict]] = {}
    for day in sorted(days):
        since = (dt.date.fromisoformat(day) - dt.timedelta(days=REPEAT_DAYS)).isoformat()
        recent = {c["set_num"] for d, cs in picks.items() if since <= d < day for c in cs}
        picks[day] = [c for c in day_candidates(days, day) if c["set_num"] not in recent][:count]
    return picks


def theme_label(theme: str) -> str:
    return f"LEGO {theme}" if theme else "LEGO"


def hashtags(theme: str) -> str:
    tags = list(BASE_TAGS)
    slug = pages.slugify(theme).replace("-", "")
    if slug:
        tags.insert(1, f"#lego{slug}")
    return " ".join(tags + ["#prezent"])


def date_note(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return f"Ceny z {d.day}.{d.month}.{d.year}, mogą się zmienić."


def video_deal(pick: dict, s: dict, shop_names: dict[str, str], index: int) -> dict:
    """The dict video.render() takes."""
    return {
        "set_num": pick["set_num"],
        "theme": theme_label(s.get("theme", "")),
        "name": s.get("name", pick["set_num"]),
        "offers": [(shop_names.get(shop, shop), price) for shop, price in pick["offers"]],
        "diff": pick["diff"],
        "pct": pick["pct"],
        "note": date_note(pick["date"]),
        "hook": HOOKS[index % len(HOOKS)],
    }


def caption(deal: dict, s: dict) -> str:
    lines = [f"{deal['theme']} {deal['name']} ({deal['set_num']}): "
             f"różnica w cenie aż {deal['diff']:.0f} zł 😳"]
    lines += [f"{shop}: {pages.pln(price)}" for shop, price in deal["offers"]]
    lines += ["Zanim kupisz, sprawdź ceny na klockownik.pl (link w bio)", deal["note"], "", hashtags(s.get("theme", ""))]
    return "\n".join(lines)


def reels_page(day: str, items: list[tuple[str, str, str]]) -> str:
    """items: (video file name, title, caption)."""
    cards = "".join(
        f'<section class="reel"><h2>{html.escape(title)}</h2>'
        f'<video src="{name}" controls playsinline preload="metadata" width="270"></video>'
        f'<p><a class="btn" href="{name}" download>Pobierz film</a></p>'
        f'<textarea readonly rows="9">{html.escape(text)}</textarea></section>'
        for name, title, text in items) or "<p>Dziś brak okazji z dużą różnicą cen.</p>"
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Rolki na dziś</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0 auto;max-width:640px;padding:16px;background:#f7f7f5;color:#1d1d1b}}
.reel{{background:#fff;border:1px solid #e3e3de;border-radius:12px;padding:16px;margin:16px 0}}
video{{display:block;max-width:100%;border-radius:8px;background:#000}}
textarea{{width:100%;box-sizing:border-box;font:inherit;font-size:14px}}
.btn{{display:inline-block;background:#ffcf00;color:#1d1d1b;padding:10px 16px;border-radius:8px;font-weight:700;text-decoration:none}}
</style></head><body>
<h1>Rolki na dziś</h1>
<p>Okazje z cen z dnia {html.escape(day)}. Pobierz film, dodaj muzykę w aplikacji i skopiuj opis.</p>
{cards}
</body></html>
"""


def build(data_dir: str = "data", out_dir: str = "site", count: int = COUNT) -> str:
    from . import video  # needs Pillow and ffmpeg, which only this step installs
    from .site import load_prices

    prices = load_prices(os.path.join(data_dir, "prices.csv"))
    picks = daily_picks(prices, count)
    if not picks:
        return "No prices, no reels"
    day = max(picks)
    sets = {s["set_num"]: s for s in catalog.load_catalog(os.path.join(data_dir, "sets.csv"))}
    shop_names = {k: v.get("name", k) for k, v in load_shops(os.path.join(data_dir, "shops.json")).items()}
    logo = os.path.join(os.path.dirname(__file__), "site_template", "logo.png")
    target = os.path.join(out_dir, OUT_PATH)
    os.makedirs(target, exist_ok=True)
    items = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, pick in enumerate(picks[day]):
            s = sets.get(pick["set_num"], {})
            deal = video_deal(pick, s, shop_names, i)
            photo = None
            if s.get("img_url"):
                try:
                    photo = os.path.join(tmp, f"{pick['set_num']}.jpg")
                    with open(photo, "wb") as f:
                        f.write(fetch(s["img_url"]))
                except Exception as exc:  # the video then shows the logo brick
                    print(f"No photo for {pick['set_num']}: {exc}")
                    photo = None
            name = f"{day}-{pick['set_num']}.mp4"
            video.render(deal, logo, os.path.join(target, name), photo)
            items.append((name, f"{deal['theme']} {deal['name']} ({deal['set_num']})", caption(deal, s)))
    with open(os.path.join(target, "index.html"), "w", encoding="utf-8") as f:
        f.write(reels_page(day, items))
    return f"{len(items)} reels for {day}: " + ", ".join(p["set_num"] for p in picks[day])
