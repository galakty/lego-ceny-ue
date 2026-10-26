"""LEGO set catalog from the free Rebrickable dump (sets.csv.gz)."""
import csv
import gzip
import io

from .net import fetch

SETS_URL = "https://cdn.rebrickable.com/media/downloads/sets.csv.gz"


def parse_sets(gz_bytes: bytes, min_year: int = 2020) -> list[dict]:
    text = gzip.decompress(gz_bytes).decode("utf-8")
    sets = []
    for row in csv.DictReader(io.StringIO(text)):
        if int(row["year"]) < min_year or int(row["num_parts"]) == 0:
            continue
        sets.append({
            "set_num": row["set_num"].split("-")[0],
            "name": row["name"],
            "year": int(row["year"]),
            "num_parts": int(row["num_parts"]),
            "img_url": row["img_url"],
        })
    return sets


def download_catalog(path: str, min_year: int = 2020) -> int:
    sets = parse_sets(fetch(SETS_URL), min_year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["set_num", "name", "year", "num_parts", "img_url"])
        writer.writeheader()
        writer.writerows(sets)
    return len(sets)
