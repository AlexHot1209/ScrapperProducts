from __future__ import annotations

from abc import ABC, abstractmethod

from scrapper_shared.scraping.types import ExtractedProduct


class SiteAdapter(ABC):
    domains: set[str] = set()

    @classmethod
    def matches(cls, domain: str) -> bool:
        return domain in cls.domains

    @abstractmethod
    def extract(self, html: str, source_url: str) -> ExtractedProduct | None:
        raise NotImplementedError
