from pathlib import Path

from scrapper_shared.scraping.extract import extract_product


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_extract_product_from_jsonld() -> None:
    html = (FIXTURE_DIR / "product_jsonld.html").read_text(encoding="utf-8")
    result = extract_product(html, "https://example.ro/produs/trandafir-catarator")
    assert result is not None
    assert result.product_name == "Trandafir catarator Rosu"
    assert str(result.price) == "49.90"
    assert result.currency == "RON"
    assert result.size_text is not None
    assert "3 l" in result.size_text.lower()
    assert result.extraction_method == "jsonld"


def test_extract_product_from_opengraph_fallback() -> None:
    html = (FIXTURE_DIR / "product_heuristic.html").read_text(encoding="utf-8")
    result = extract_product(html, "https://example.ro/produs/pamant-50l")
    assert result is not None
    assert "Pamant" in result.product_name
    assert result.currency == "RON"
