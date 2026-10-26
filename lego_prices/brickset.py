"""Recommended ages and LEGO.com reference prices from the Brickset API v3.

Needs a free API key (https://brickset.com/tools/webservices/requestkey)
in the BRICKSET_API_KEY environment variable. Only getSets calls count
towards the daily limit; one call returns up to 500 sets, so a full
refresh for 2020+ takes a few dozen calls.
"""
import csv
import datetime as dt
import json
import os
import urllib.parse

from .net import fetch

API_URL = "https://brickset.com/api/v3.asmx/getSets"
PAGE_SIZE = 500
FIELDS = ["set_num", "age_min", "age_max", "lego_de_eur"]


def parse_sets(payload: bytes) -> tuple[list[dict], int]:
    data = json.loads(payload)
    if data.get("status") != "success":
        raise RuntimeError(f"Brickset error: {data.get('message', data)}")
    rows = []
    for s in data.get("sets", []):
        if s.get("numberVariant", 1) != 1:
            continue
        age = s.get("ageRange") or {}
        lego_de = (s.get("LEGOCom") or {}).get("DE") or {}
        rows.append({
            "set_num": s["number"],
            "age_min": age.get("min") or "",
            "age_max": age.get("max") or "",
            "lego_de_eur": lego_de.get("retailPrice") or "",
        })
    return rows, int(data.get("matches", 0))


def fetch_year(api_key: str, year: int) -> list[dict]:
    rows, page = [], 1
    while True:
        params = json.dumps({"year": str(year), "pageSize": PAGE_SIZE, "pageNumber": page})
        query = urllib.parse.urlencode({"apiKey": api_key, "userHash": "", "params": params})
        batch, matches = parse_sets(fetch(f"{API_URL}?{query}"))
        rows += batch
        if page * PAGE_SIZE >= matches or not batch:
            return rows
        page += 1


def download(path: str, min_year: int = 2020) -> int | None:
    """Returns the number of sets saved, or None when no API key is configured."""
    api_key = os.environ.get("BRICKSET_API_KEY")
    if not api_key:
        return None
    rows = []
    for year in range(min_year, dt.date.today().year + 2):  # next year's sets are announced early
        rows += fetch_year(api_key, year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def load(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["set_num"]: r for r in csv.DictReader(f)}
