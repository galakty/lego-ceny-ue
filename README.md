# lego-ceny-ue

Live at https://klockownik.pl (GitHub Pages with a custom domain; DNS at Hostido).

LEGO price comparison across EU shops. For each set it shows the price in PLN **including shipping to Poland**. The site itself is aimed at Polish users, so its UI text will be in Polish; code and docs are in English.

## How it works

1. `data/products.csv` lists (set number, shop, product page URL) pairs.
2. `python -m lego_prices scrape` fetches each page and reads the price. Most shops embed schema.org product data (JSON-LD), so one parser covers many shops.
3. Prices are converted to PLN at the National Bank of Poland mid rate, and shipping to Poland from `data/shops.json` is added.
4. Results are appended to `data/prices.csv`, one row per set, shop and day.
5. GitHub Actions runs this daily at 05:00 UTC and commits the history (`.github/workflows/scrape.yml`).

## Adding a set

Add a row to `data/products.csv`:

```
75313,mediamarkt-pl,https://mediamarkt.pl/pl/product/...
```

The shop must exist in `data/shops.json`. Set `shipping_to_pl` to the shipping cost to Poland in the shop's currency. While it is `null`, the site shows only the price, without a total.

To earn on clicks to a shop's offers, set `affiliate_link` on the shop to the deeplink template from its affiliate network, with `{url}` where the URL-encoded product URL goes (or `{url_b64}` for the Base64-encoded URL that webePartners uses) (e.g. `"https://www.awin1.com/cread.php?awinmid=<mid>&awinaffid=3135303&ued={url}"`). Offer links on the site then go through the network and are marked `rel="sponsored"`.

## Set catalog and ages

- `python -m lego_prices catalog` downloads all sets since 2020 (name, year, piece count, theme, image) from the free [Rebrickable](https://rebrickable.com/downloads/) dumps into `data/sets.csv`.
- `python -m lego_prices ages` downloads recommended ages and the LEGO.com Germany list price from the [Brickset API](https://brickset.com/article/52664/api-version-3-documentation) into `data/brickset.csv`. It needs a free API key in `BRICKSET_API_KEY`; without one it is skipped and the age filter has no data.

Both files are generated on every site build and are not committed.

## Site

`python -m lego_prices site` builds a static site into `site/`: the template from `lego_prices/site_template/` plus `site/data/sets.json`. Search and filters (piece count ranges, child's age, theme, sets with prices only) run in the browser, and the current filters are kept in the URL (e.g. `?wiek=6&od=500`), so filtered views can be shared.

Besides the interactive search, the build writes plain HTML pages that search engines can index (`lego_prices/pages.py`): one per set (`zestaw/<number>/`), per child's age (`wiek/<age>/`, `wiek/dorosli/`), per piece count range (`klocki/<range>/`) and per theme (`seria/<theme>/`), a daily deals page (`promocje/`, see `lego_prices/deals.py`: sets at least 10% below the LEGO Germany list price converted at the NBP rate, and sets whose lowest price dropped 10% or more versus the previous 30 days), seasonal pages (`kalendarz-adwentowy-<year>/` and `prezent/do-<budget>-zl/` for 50, 100 and 200 zł, cheapest offer in stock), plus `sitemap.xml` and `robots.txt`. Set `SITE_URL` when the site moves to its own domain.

`.github/workflows/pages.yml` builds and deploys the site to GitHub Pages on every push to `main` and after each daily scrape.

Setup, once:
1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → New repository secret: `BRICKSET_API_KEY`.

## Affiliate links

`data/affiliates.json` lists affiliate programs. Every set page and the set popup in the search get a "Sprawdź na <shop>" button that searches the shop for the set number with our affiliate parameters (Amazon.pl tag `klockownik-21`, Allegro Share UTM campaign). Links use `rel="sponsored nofollow"` and the footer shows the required disclosure.

## Tests

```
python -m unittest discover -s tests -v
```

## Shops that block scraping

Tested on 2026-10-23 from GitHub Actions runners:
- **LEGO.com, Proshop, MediaMarkt.at**: HTTP 403.
- **Amazon**: either a captcha or a page with USD prices, because GitHub runners are in the US. Reliable EUR/PLN prices need the official affiliate API.
- **MediaMarkt.pl** and **Neonet** work via JSON-LD, with products found from their sitemaps (`discover` workflow).
- **Empik**: sitemap lists LEGO products, but product pages return 403.
- **x-kom** (403), **al.to** (429); **Media Expert, Smyk, Euro, Carrefour, Komputronik** have no LEGO products in their sitemaps.

Blocked URLs are kept in `data/products_blocked.csv` so we can come back to them once an API is available.

Debugging: run the workflow manually with the `debug` option and the fetched pages are pushed to the `debug-html` branch (with embedded Google API keys redacted). Delete the branch when done. The status of the last run is in `data/last_run.csv`.

## TODO

- Fill in shipping costs to Poland in `data/shops.json`.
- Get EU prices through affiliate APIs and product feeds (Amazon, Awin and similar).
