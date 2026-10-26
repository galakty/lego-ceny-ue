"""Extracts price and availability from a product page.

Most shops embed product data as JSON-LD (schema.org Product/Offer),
so one parser works for many shops. As a fallback we read the
product:price:amount / og:price:amount meta tags.
"""
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class Offer:
    price: float
    currency: str
    in_stock: bool | None


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.jsonld: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_jsonld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []
        elif tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False


def _parse_price(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d,.]", "", str(value))
    if not s:
        return None
    # "1.299,99" -> 1299.99 ; "1,299.99" -> 1299.99 ; "1299,99" -> 1299.99
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _walk(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "offers", "mainEntity", "itemOffered", "object"):
            if key in node:
                yield from _walk(node[key])


def _offer_from_jsonld(blocks: list[str]) -> Offer | None:
    for raw in blocks:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            types = node.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if not any(t in ("Offer", "AggregateOffer") for t in types):
                continue
            price = _parse_price(node.get("price", node.get("lowPrice")))
            currency = node.get("priceCurrency")
            if price is None or not currency:
                continue
            availability = str(node.get("availability", ""))
            in_stock = None
            if availability:
                in_stock = "InStock" in availability or "LimitedAvailability" in availability
            return Offer(price, currency.upper(), in_stock)
    return None


_AMAZON_PRICE = re.compile(r'id="(?:corePrice_feature_div|corePriceDisplay_desktop_feature_div|apex_desktop)".*?<span class="a-offscreen">([^<]+)</span>', re.S)
_CURRENCY_SIGNS = {"€": "EUR", "zł": "PLN", "kr": "SEK", "£": "GBP"}


def _amazon_offer(html: str) -> Offer | None:
    m = _AMAZON_PRICE.search(html)
    if not m:
        return None
    text = m.group(1).replace("\xa0", " ")
    currency = next((code for sign, code in _CURRENCY_SIGNS.items() if sign in text), None)
    price = _parse_price(text)
    if price is None or currency is None:
        return None
    in_stock = None
    if 'id="availability"' in html:
        in_stock = 'id="add-to-cart-button"' in html
    return Offer(price, currency, in_stock)


def page_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:80] if m else ""


def extract_offer(html: str) -> Offer | None:
    c = _Collector()
    c.feed(html)
    offer = _offer_from_jsonld(c.jsonld) or _amazon_offer(html)
    if offer:
        return offer
    for prefix in ("product:price", "og:price"):
        price = _parse_price(c.meta.get(f"{prefix}:amount"))
        currency = c.meta.get(f"{prefix}:currency")
        if price is not None and currency:
            return Offer(price, currency.upper(), None)
    return None
