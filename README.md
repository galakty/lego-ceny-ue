# lego-ceny-ue

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

## Set catalog

`python -m lego_prices catalog` downloads all sets since 2020 from the free [Rebrickable](https://rebrickable.com/downloads/) dump into `data/sets.csv`.

## Tests

```
python -m unittest discover -s tests -v
```

## Shops that block scraping

Tested on 2026-10-23 from GitHub Actions runners:
- **LEGO.com, Proshop, MediaMarkt.at**: HTTP 403.
- **Amazon**: either a captcha or a page with USD prices, because GitHub runners are in the US. Reliable EUR/PLN prices need the official affiliate API.
- **MediaMarkt.pl** works via JSON-LD.

Blocked URLs are kept in `data/products_blocked.csv` so we can come back to them once an API is available.

Debugging: run the workflow manually with the `debug` option and the fetched pages are pushed to the `debug-html` branch. The status of the last run is in `data/last_run.csv`.

## TODO

- Fill in shipping costs to Poland in `data/shops.json`.
- Get EU prices through affiliate APIs and product feeds (Amazon, Awin and similar).
- Step 3: static site on GitHub Pages.
