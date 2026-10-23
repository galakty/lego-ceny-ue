import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; lego-ceny-ue/0.1; +https://github.com/galakty/lego-ceny-ue)"


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pl,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()
