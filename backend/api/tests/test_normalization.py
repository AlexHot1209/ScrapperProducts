from scrapper_shared.normalization import extract_size, normalize_text, parse_price


def test_normalize_text_removes_diacritics() -> None:
    assert normalize_text("Trandafir cățărător mare") == "trandafir catarator mare"


def test_parse_price_ron() -> None:
    amount, currency = parse_price("1.299,99 lei")
    assert str(amount) == "1299.99"
    assert currency == "RON"


def test_extract_size() -> None:
    assert extract_size("Ghiveci plastic 30 cm premium") == "30 cm"
