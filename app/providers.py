from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


@dataclass(frozen=True)
class Provider:
    name: str
    api_key: str
    base_url: str
    model: str


class ProviderError(Exception):
    def __init__(self, provider: str, status_code: int | None, detail: str):
        self.provider = provider
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def configured_providers(settings: Settings, alias: str) -> list[Provider]:
    candidates = {
        "fast": [
            Provider("groq", settings.groq_api_key, settings.groq_base_url, settings.groq_model_fast),
            Provider("cerebras", settings.cerebras_api_key, settings.cerebras_base_url, settings.cerebras_model_fast),
            Provider("gemini", settings.gemini_api_key, settings.gemini_base_url, settings.gemini_model_balanced),
        ],
        "balanced": [
            Provider("gemini", settings.gemini_api_key, settings.gemini_base_url, settings.gemini_model_balanced),
            Provider("groq", settings.groq_api_key, settings.groq_base_url, settings.groq_model_balanced),
            Provider("cerebras", settings.cerebras_api_key, settings.cerebras_base_url, settings.cerebras_model_balanced),
            Provider("mistral", settings.mistral_api_key, settings.mistral_base_url, settings.mistral_model_balanced),
        ],
        "premium": [
            Provider("gemini", settings.gemini_api_key, settings.gemini_base_url, settings.gemini_model_premium),
            Provider("openrouter", settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_model_premium),
        ],
        "economy": [
            Provider("groq", settings.groq_api_key, settings.groq_base_url, settings.groq_model_fast),
            Provider("cerebras", settings.cerebras_api_key, settings.cerebras_base_url, settings.cerebras_model_fast),
        ],
    }
    return [p for p in candidates.get(alias, []) if p.api_key and p.model]


def _upstream_payload(provider: Provider, payload: dict[str, Any]) -> dict[str, Any]:
    upstream_payload = dict(payload)
    upstream_payload["model"] = provider.model
    return upstream_payload


def _headers(provider: Provider) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }


async def chat_completion(
    provider: Provider,
    payload: dict[str, Any],
    settings: Settings,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=settings.nahallm_request_timeout_seconds) as client:
            return await client.post(
                provider.base_url.rstrip("/") + "/chat/completions",
                headers=_headers(provider),
                json=_upstream_payload(provider, payload),
            )
    except httpx.HTTPError as exc:
        raise ProviderError(provider.name, None, str(exc)) from exc


async def stream_chat_completion(
    provider: Provider,
    payload: dict[str, Any],
    settings: Settings,
) -> AsyncIterator[bytes]:
    client = httpx.AsyncClient(timeout=settings.nahallm_request_timeout_seconds)
    response: httpx.Response | None = None
    try:
        request = client.build_request(
            "POST",
            provider.base_url.rstrip("/") + "/chat/completions",
            headers=_headers(provider),
            json=_upstream_payload(provider, payload),
        )
        response = await client.send(request, stream=True)
        if response.status_code >= 400:
            detail = (await response.aread())[:1000].decode("utf-8", errors="replace")
            raise ProviderError(provider.name, response.status_code, detail)
        async for chunk in response.aiter_bytes():
            yield chunk
    except httpx.HTTPError as exc:
        raise ProviderError(provider.name, None, str(exc)) from exc
    finally:
        if response is not None:
            await response.aclose()
        await client.aclose()
