import gzip
import urllib.request
import zlib

USER_AGENT = "Mozilla/5.0 (compatible; lego-prices/0.1; +https://github.com/galakty/lego-ceny-ue)"


def decode_body(body: bytes, encoding: str | None) -> bytes:
    """Undoes the Content-Encoding the server applied; shop pages of 1 MB shrink to about a fifth."""
    encoding = (encoding or "").strip().lower()
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:  # some servers send raw deflate without the zlib header
            return zlib.decompress(body, -zlib.MAX_WBITS)
    return body


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pl,en;q=0.8",
                                               "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return decode_body(resp.read(), resp.headers.get("Content-Encoding"))
