from scrapper_shared.config import Settings


def test_allowed_domains_set_is_deduplicated_and_normalized() -> None:
    settings = Settings(
        ALLOWED_DOMAINS=" https://www.Example.ro ,example.ro/path, http://shop.test.ro,shop.test.ro "
    )
    assert settings.allowed_domains_set == {"example.ro", "shop.test.ro"}


def test_search_provider_is_manual_only() -> None:
    settings = Settings()
    assert settings.search_provider == "manual"
