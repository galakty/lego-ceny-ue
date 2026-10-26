"""LEGO set catalog from the free Rebrickable dumps (sets.csv.gz, themes.csv.gz)."""
import csv
import gzip
import io

from .net import fetch

SETS_URL = "https://cdn.rebrickable.com/media/downloads/sets.csv.gz"
THEMES_URL = "https://cdn.rebrickable.com/media/downloads/themes.csv.gz"
FIELDS = ["set_num", "name", "year", "num_parts", "theme", "img_url"]


def _rows(gz_bytes: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(gzip.decompress(gz_bytes).decode("utf-8"))))


def parse_themes(gz_bytes: bytes) -> dict[str, str]:
    """Maps theme id to its top-level theme name (e.g. a 'Ultimate Collector Series' subtheme -> 'Star Wars')."""
    rows = {r["id"]: r for r in _rows(gz_bytes)}

    def root(theme_id: str) -> str:
        seen = set()
        while rows[theme_id]["parent_id"] and theme_id not in seen:
            seen.add(theme_id)
            theme_id = rows[theme_id]["parent_id"]
        return rows[theme_id]["name"]

    return {theme_id: root(theme_id) for theme_id in rows}


def parse_sets(gz_bytes: bytes, themes: dict[str, str] | None = None, min_year: int = 2020) -> list[dict]:
    themes = themes or {}
    sets, seen = [], set()
    for row in _rows(gz_bytes):
        if int(row["year"]) < min_year or int(row["num_parts"]) == 0:
            continue
        set_num = row["set_num"].split("-")[0]
        if set_num in seen:  # keep only the first variant (e.g. 75313-1, not 75313-2)
            continue
        seen.add(set_num)
        sets.append({
            "set_num": set_num,
            "name": row["name"],
            "year": int(row["year"]),
            "num_parts": int(row["num_parts"]),
            "theme": themes.get(row.get("theme_id", ""), ""),
            "img_url": row["img_url"],
        })
    return sets


def download_catalog(path: str, min_year: int = 2020) -> int:
    sets = parse_sets(fetch(SETS_URL), parse_themes(fetch(THEMES_URL)), min_year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sets)
    return len(sets)


def load_catalog(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{**r, "year": int(r["year"]), "num_parts": int(r["num_parts"])} for r in csv.DictReader(f)]
