from app.config import Settings
from app.providers import configured_providers


def test_freellmapi_is_last_fallback_and_maps_aliases():
    settings = Settings(
        nahallm_api_keys="test-key",
        freellmapi_api_key="freellmapi-key",
        freellmapi_base_url="http://freellmapi.test/v1",
    )

    expected = {
        "fast": "auto:fast",
        "balanced": "auto:balanced",
        "premium": "auto:smart",
        "economy": "auto:cheap",
    }

    for alias, model in expected.items():
        providers = configured_providers(settings, alias)
        assert providers[-1].name == "freellmapi"
        assert providers[-1].base_url == "http://freellmapi.test/v1"
        assert providers[-1].api_key == "freellmapi-key"
        assert providers[-1].model == model


def test_freellmapi_is_disabled_without_key():
    settings = Settings(
        nahallm_api_keys="test-key",
        freellmapi_api_key="",
    )

    providers = configured_providers(settings, "fast")
    assert all(provider.name != "freellmapi" for provider in providers)
