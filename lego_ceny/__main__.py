import sys

from . import catalog, scrape

USAGE = "Użycie: python -m lego_ceny [scrape | catalog]"

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scrape"
    if cmd == "scrape":
        sys.exit(scrape.main())
    elif cmd == "catalog":
        print(f"Zapisano {catalog.download_catalog('data/sets.csv')} zestawów")
    else:
        print(USAGE)
        sys.exit(2)
