import sys

from . import brickset, catalog, scrape, site

USAGE = "Usage: python -m lego_prices [scrape | catalog | ages | site]"

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
        print(f"Built site with {site.build()} sets")
    else:
        print(USAGE)
        sys.exit(2)
