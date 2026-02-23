from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class ExtractedProduct:
    product_name: str
    price: Decimal | None
    currency: str | None
    size_text: str | None
    location_text: str | None
    canonical_url: str | None
    extraction_method: str
