import hashlib
import logging
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .circuit_breaker import CircuitBreaker
from .config import get_settings
from .providers import ProviderError, chat_completion, close_http_client, configured_providers, stream_chat_completion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nahallm")

app = FastAPI(title="NahaLLM", version="0.3.0")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "balanced"
    messages: list[dict[str, Any]] = Field(min_length=1)
    stream: bool = False


breaker = CircuitBreaker()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_http_client()


def authenticate(authorization: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not settings.api_keys:
        raise HTTPException(status_code=503, detail="NahaLLM is not configured with an API key")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:].strip()
    if token not in settings.api_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token


def public_key_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def configured_breaker(settings):
    global breaker
    if breaker.failure_threshold != max(1, settings.nahallm_circuit_failure_threshold) or breaker.cooldown_seconds != max(0.0, settings.nahallm_circuit_cooldown_seconds):
        breaker = CircuitBreaker(settings.nahallm_circuit_failure_threshold, settings.nahallm_circuit_cooldown_seconds)
    return breaker


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "nahallm"}


@app.get("/ready")
async def ready() -> JSONResponse:
    settings = get_settings()
    providers = {
        "groq": bool(settings.groq_api_key),
        "cerebras": bool(settings.cerebras_api_key),
        "gemini": bool(settings.gemini_api_key),
        "mistral": bool(settings.mistral_api_key),
        "openrouter": bool(settings.openrouter_api_key and settings.openrouter_model_premium),
    }
    ready_state = any(providers.values()) and bool(settings.api_keys)
    return JSONResponse(status_code=200 if ready_state else 503, content={"status": "ready" if ready_state else "not_ready", "providers": providers})


@app.get("/v1/models")
async def models(_: str = Depends(authenticate)) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": alias, "object": "model", "owned_by": "nahalabs"} for alias in ("fast", "balanced", "premium", "economy")],
    }


@app.get("/v1/providers")
async def provider_status(_: str = Depends(authenticate)) -> dict[str, Any]:
    settings = get_settings()
    configured = {p.name for alias in ("fast", "balanced", "premium", "economy") for p in configured_providers(settings, alias)}
    return {"providers": sorted(configured), "circuits": configured_breaker(settings).snapshot()}


@app.post("/v1/chat/completions")
async def completions(body: ChatRequest, token: str = Depends(authenticate)):
    settings = get_settings()
    aliases = {"fast", "balanced", "premium", "economy"}
    if body.model not in aliases:
        raise HTTPException(status_code=400, detail="model must be one of: fast, balanced, premium, economy")

    payload = body.model_dump(exclude_none=True)
    started = time.perf_counter()
    request_id = "nah_" + uuid.uuid4().hex[:16]
    cb = configured_breaker(settings)
    last_error: ProviderError | None = None

    for provider in configured_providers(settings, body.model):
        if not cb.allow(provider.name):
            logger.info("provider_skipped request_id=%s provider=%s reason=circuit_open", request_id, provider.name)
            continue
        attempts = max(0, settings.nahallm_max_retries_per_provider) + 1
        for attempt in range(attempts):
            try:
                if body.stream:
                    async def stream():
                        try:
                            async for chunk in stream_chat_completion(provider, payload, settings):
                                yield chunk
                            cb.record_success(provider.name)
                        except ProviderError:
                            cb.record_failure(provider.name)
                            raise
                    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-NahaLLM-Request-ID": request_id, "Cache-Control": "no-cache"})

                response = await chat_completion(provider, payload, settings)
                if response.status_code < 400:
                    cb.record_success(provider.name)
                    elapsed_ms = round((time.perf_counter() - started) * 1000)
                    logger.info("request_id=%s app_key=%s alias=%s provider=%s status=%s latency_ms=%s", request_id, public_key_id(token), body.model, provider.name, response.status_code, elapsed_ms)
                    data = response.json()
                    data["nahallm"] = {"request_id": request_id, "provider": provider.name, "alias": body.model}
                    return JSONResponse(data, headers={"X-NahaLLM-Request-ID": request_id})

                last_error = ProviderError(provider.name, response.status_code, response.text[:1000])
                if response.status_code == 429 or response.status_code >= 500:
                    cb.record_failure(provider.name)
                    if attempt + 1 < attempts:
                        continue
                break
            except ProviderError as exc:
                last_error = exc
                cb.record_failure(provider.name)
                if attempt + 1 < attempts:
                    continue
                break

    if last_error:
        status = 502 if last_error.status_code is None or last_error.status_code >= 500 else 429
        raise HTTPException(status_code=status, detail={"message": "All configured NahaLLM providers failed", "request_id": request_id})
    raise HTTPException(status_code=503, detail="No provider is configured or currently available for this model alias")
