"""Finds LEGO product pages in shops through their sitemaps.

Many shops put the set number in the product URL (e.g. .../klocki-lego-60510-city-...),
so walking the sitemap and matching URLs against the set catalog gives us product
pages without searching the shop. Respects robots.txt.
"""
import csv
import gzip
import os
import re
import urllib.robotparser
from urllib.parse import urljoin, urlparse

from .net import USER_AGENT, fetch
from .price_parser import extract_offer, page_title

LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
SET_NUM = re.compile(r"(?<![\d])(\d{4,6})(?![\d])")
MAX_SITEMAPS = 400
FIELDS = ["set_num", "shop", "url"]


def _text(data: bytes) -> str:
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def robots(base_url: str) -> tuple[urllib.robotparser.RobotFileParser, list[str]]:
    rp = urllib.robotparser.RobotFileParser()
    try:
        lines = _text(fetch(urljoin(base_url, "/robots.txt"))).splitlines()
    except Exception:
        lines = []
    rp.parse(lines)
    sitemaps = [line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("sitemap:")]
    return rp, sitemaps or [urljoin(base_url, "/sitemap.xml")]


def lego_urls(sitemap_urls: list[str], url_filter: str = "lego") -> tuple[list[str], int]:
    """Walks sitemap indexes breadth-first; returns URLs matching the url_filter regex (case-insensitive)
    and the number of sitemaps read."""
    pattern = re.compile(url_filter, re.I)
    queue, seen, found = list(sitemap_urls), set(), []
    while queue and len(seen) < MAX_SITEMAPS:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            body = _text(fetch(sm, timeout=60))
        except Exception:
            continue
        locs = LOC.findall(body)
        if "<sitemapindex" in body:
            queue += locs
        else:
            found += [u for u in locs if pattern.search(u)]
    return found, len(seen)


def match_sets(urls: list[str], set_nums: set[str]) -> dict[str, str]:
    """Maps set number to the first product URL that mentions it in its path."""
    matches: dict[str, str] = {}
    for url in urls:
        nums = [n for n in SET_NUM.findall(urlparse(url).path) if n in set_nums]
        if len(set(nums)) == 1 and nums[0] not in matches:  # skip bundles naming several sets
            matches[nums[0]] = url
    return matches


def discover(shop: dict, set_nums: set[str]) -> tuple[list[dict], str]:
    base = shop["discover"]["base_url"]
    rp, sitemaps = robots(base)
    urls, read = lego_urls(sitemaps, shop["discover"].get("url_filter", "lego"))
    urls = [u for u in urls if rp.can_fetch(USER_AGENT, u)]
    matches = match_sets(urls, set_nums)
    rows = [{"set_num": n, "shop": shop["id"], "url": u} for n, u in sorted(matches.items())]
    return rows, f"{shop['id']}: {read} sitemaps, {len(urls)} LEGO URLs, {len(rows)} matched sets"


def probe(base_url: str, set_nums: set[str]) -> dict:
    """One-off check whether a shop can be used: sitemap reachable, LEGO URLs found, a product page parses."""
    result = {"shop": base_url, "sitemaps": 0, "lego_urls": 0, "matched": 0, "sample": "", "sample_result": ""}
    try:
        rp, sitemaps = robots(base_url)
        urls, result["sitemaps"] = lego_urls(sitemaps)
        result["lego_urls"] = len(urls)
        matches = match_sets(urls, set_nums)
        result["matched"] = len(matches)
        if matches:
            url = next(iter(matches.values()))
            result["sample"] = url
            if not rp.can_fetch(USER_AGENT, url):
                result["sample_result"] = "disallowed by robots.txt"
            else:
                html = fetch(url).decode("utf-8", errors="replace")
                offer = extract_offer(html)
                result["sample_result"] = f"{offer.price} {offer.currency}" if offer else f"no price ({page_title(html)!r})"
    except Exception as e:
        result["sample_result"] = f"error: {e}"
    return result


def write_rows(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
