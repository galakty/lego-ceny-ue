import sys

from . import catalog, scrape

USAGE = "Usage: python -m lego_prices [scrape | catalog]"

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scrape"
    if cmd == "scrape":
        sys.exit(scrape.main())
    elif cmd == "catalog":
        print(f"Saved {catalog.download_catalog('data/sets.csv')} sets")
    else:
        print(USAGE)
        sys.exit(2)
