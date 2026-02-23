import re
import unicodedata
from decimal import Decimal, InvalidOperation

PRICE_PATTERN = re.compile(
    r"(\d{1,3}(?:[\.,\s]\d{3})*(?:[\.,]\d{1,2})?)\s*(?:lei|ron|lei\.|r\.?o\.?n\.?)+",
    re.IGNORECASE,
)
SIZE_PATTERN = re.compile(r"(\d+(?:[\.,]\d+)?)\s*(cm|mm|m|l|ml|kg|g|buc|set|m2|m\^2)", re.IGNORECASE)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-zA-Z0-9\s]", " ", ascii_text)
    return " ".join(ascii_text.lower().split())


def normalize_product_name(value: str) -> str:
    return normalize_text(value)[:500]


def parse_price(raw: str | None) -> tuple[Decimal | None, str | None]:
    if not raw:
        return None, None

    text = raw.strip().replace("\xa0", " ")
    currency = "RON" if re.search(r"\b(ron|lei)\b", text, re.IGNORECASE) else None
    match = PRICE_PATTERN.search(text)
    if not match:
        fallback = re.search(r"\d+(?:[\.,]\d{1,2})?", text)
        if not fallback:
            return None, currency
        token = fallback.group(0)
    else:
        token = match.group(1)

    token = token.replace(" ", "")
    if token.count(",") == 1 and token.count(".") == 0:
        token = token.replace(",", ".")
    elif token.count(".") > 1 and token.count(",") == 0:
        token = token.replace(".", "")
    elif token.count(".") >= 1 and token.count(",") == 1:
        token = token.replace(".", "").replace(",", ".")
    else:
        token = token.replace(",", "")

    try:
        return Decimal(token), currency
    except InvalidOperation:
        return None, currency


def extract_size(text: str | None) -> str | None:
    if not text:
        return None
    match = SIZE_PATTERN.search(text)
    if match:
        value = match.group(1).replace(",", ".")
        unit = match.group(2).lower()
        return f"{value} {unit}"
    return None
