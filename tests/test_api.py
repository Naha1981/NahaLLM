import os

os.environ["NAHALLM_API_KEYS"] = "test-key"
os.environ["GROQ_API_KEY"] = "test-provider-key"

from fastapi.testclient import TestClient

from app.main import app
from app.providers import Provider


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authentication_required():
    response = client.get("/v1/models")
    assert response.status_code == 401


def test_models_require_auth():
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {"fast", "balanced", "premium", "economy"}


def test_alias_routing_is_deterministic():
    from app.config import get_settings
    from app.providers import configured_providers

    providers = configured_providers(get_settings(), "fast")
    assert providers
    assert providers[0].name == "groq"


def test_invalid_alias():
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "unknown", "messages":[{"role":"user","content":"hi"}]},
    )
    assert response.status_code == 400


def test_provider_fallback(monkeypatch):
    from app.main import get_settings

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
            }

        @property
        def text(self):
            return ""

    calls = []

    async def fake_completion(provider, payload, settings):
        calls.append(provider.name)
        if len(calls) == 1:
            from app.providers import ProviderError
            raise ProviderError(provider.name, 429, "rate limited")
        return FakeResponse()

    monkeypatch.setattr("app.main.chat_completion", fake_completion)
    monkeypatch.setattr(
        "app.main.configured_providers",
        lambda settings, alias: [
            Provider("first", "key", "http://first", "model"),
            Provider("second", "key", "http://second", "model"),
        ],
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "fast", "messages":[{"role":"user","content":"hi"}]},
    )
    assert response.status_code == 200
    assert calls == ["first", "second"]
