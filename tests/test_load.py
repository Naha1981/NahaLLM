import asyncio

import httpx
import pytest

from app.main import app
from app.providers import Provider


@pytest.mark.asyncio
async def test_fifty_concurrent_chat_requests(monkeypatch):
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "id": "chatcmpl-load",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            }

    async def fake_completion(provider, payload, settings):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.03)
        async with lock:
            active -= 1
        return FakeResponse()

    monkeypatch.setattr("app.main.chat_completion", fake_completion)
    monkeypatch.setattr(
        "app.main.configured_providers",
        lambda settings, alias: [Provider("test-provider", "key", "http://test", "model")],
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    json={"model": "fast", "messages": [{"role": "user", "content": f"business-{i}"}]},
                )
                for i in range(50)
            ]
        )

    assert all(response.status_code == 200 for response in responses)
    assert len({response.headers["X-NahaLLM-Request-ID"] for response in responses}) == 50
    assert max_active == 50
