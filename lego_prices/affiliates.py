"""Affiliate search links (e.g. Amazon), configured in data/affiliates.json."""
import json
import os
from urllib.parse import urlencode


def load(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def search_links(set_num: str, affiliates: dict[str, dict]) -> list[tuple[str, str]]:
    """(shop name, URL) pairs: a search for the set number, tagged with our affiliate ID."""
    return [(a["name"], f"{a['search_url']}?{urlencode({'k': f'LEGO {set_num}', 'tag': a['tag']})}")
            for a in affiliates.values()]
