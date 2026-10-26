import os
import sys

import csv
import json

from . import brickset, catalog, discover, scrape, site

USAGE = "Usage: python -m lego_prices [scrape | catalog | ages | site | discover | probe URL...]"


def notice(msg: str) -> None:
    print(f"::notice::{msg}" if os.environ.get("GITHUB_ACTIONS") == "true" else msg)


def catalog_set_nums() -> set[str]:
    return {s["set_num"] for s in catalog.load_catalog("data/sets.csv")}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scrape"
    if cmd == "scrape":
        sys.exit(scrape.main())
    elif cmd == "catalog":
        print(f"Saved {catalog.download_catalog('data/sets.csv')} sets")
    elif cmd == "ages":
        count = brickset.download("data/brickset.csv")
        print("BRICKSET_API_KEY not set, skipping ages" if count is None else f"Saved ages for {count} sets")
    elif cmd == "site":
        notice(f"Built site: {site.build()}")
    elif cmd == "discover":
        set_nums = catalog_set_nums()
        with open("data/shops.json", encoding="utf-8") as f:
            shops = [s for s in json.load(f)["shops"] if s.get("discover")]
        for shop in shops:
            rows, summary = discover.discover(shop, set_nums)
            if rows:  # keep the previous list when a shop's sitemap is temporarily unavailable
                discover.write_rows(f"data/discovered/{shop['id']}.csv", rows)
            notice(summary)
    elif cmd == "probe":
        set_nums = catalog_set_nums()
        results = [discover.probe(url, set_nums) for url in sys.argv[2:]]
        with open("data/probe_report.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0]))
            w.writeheader()
            w.writerows(results)
        for r in results:
            notice(f"{r['shop']}: {r['lego_urls']} LEGO URLs, {r['matched']} sets, sample: {r['sample_result']}")
    else:
        print(USAGE)
        sys.exit(2)
