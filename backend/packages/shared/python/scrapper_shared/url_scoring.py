import re
from urllib.parse import urlparse

import tldextract

PREFERRED_KEYWORDS = [
    "gradina",
    "garden",
    "flori",
    "horti",
    "plante",
    "construct",
    "diy",
    "magazin",
    "shop",
    "market",
]

EXCLUDED_HINTS = ["forum", "pdf", "blog", "wikipedia", "manual"]


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    if not host:
        return ""
    extracted = tldextract.extract(host)
    if extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return host


def score_url(url: str, title: str = "", snippet: str = "") -> float:
    blob = f"{url} {title} {snippet}".lower()
    score = 0.0

    domain = domain_from_url(url)
    if domain.endswith(".ro"):
        score += 3

    if any(word in blob for word in PREFERRED_KEYWORDS):
        score += 2

    if re.search(r"/(produs|product|p|item|catalog)", blob):
        score += 1.5

    if any(bad in blob for bad in EXCLUDED_HINTS):
        score -= 3

    if "?" in url and "sort" in url:
        score -= 1

    return score


def is_probably_relevant(url: str, title: str = "", snippet: str = "") -> bool:
    return score_url(url, title, snippet) >= 1.0
