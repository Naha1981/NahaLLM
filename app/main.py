import hashlib
import json
import logging
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import get_settings
from .providers import ProviderError, chat_completion, configured_providers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nahallm")

app = FastAPI(title="NahaLLM", version="0.1.0")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "balanced"
    messages: list[dict[str, Any]] = Field(min_length=1)
    stream: bool = False


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
    return JSONResponse(
        status_code=200 if ready_state else 503,
        content={"status": "ready" if ready_state else "not_ready", "providers": providers},
    )


@app.get("/v1/models")
async def models(_: str = Depends(authenticate)) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": alias, "object": "model", "owned_by": "nahalabs"}
            for alias in ("fast", "balanced", "premium", "economy")
        ],
    }


@app.post("/v1/chat/completions")
async def completions(
    request: Request,
    body: ChatRequest,
    token: str = Depends(authenticate),
):
    settings = get_settings()
    if body.model not in {"fast", "balanced", "premium", "economy"}:
        raise HTTPException(status_code=400, detail="model must be one of: fast, balanced, premium, economy")

    payload = body.model_dump(exclude_none=True)
    started = time.perf_counter()
    request_id = "nah_" + uuid.uuid4().hex[:16]
    last_error: ProviderError | None = None

    for provider in configured_providers(settings, body.model):
        try:
            response = await chat_completion(provider, payload, settings)
            if response.status_code < 400:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                logger.info(
                    "request_id=%s app_key=%s alias=%s provider=%s status=%s latency_ms=%s",
                    request_id, public_key_id(token), body.model, provider.name, response.status_code, elapsed_ms,
                )
                if body.stream:
                    return StreamingResponse(
                        response.aiter_bytes(),
                        status_code=response.status_code,
                        media_type="text/event-stream",
                        headers={"X-NahaLLM-Request-ID": request_id},
                    )
                data = response.json()
                data["nahallm"] = {"request_id": request_id, "provider": provider.name, "alias": body.model}
                return JSONResponse(data, headers={"X-NahaLLM-Request-ID": request_id})

            detail = response.text[:1000]
            last_error = ProviderError(provider.name, response.status_code, detail)
            logger.warning("provider_failure request_id=%s provider=%s status=%s", request_id, provider.name, response.status_code)
        except ProviderError as exc:
            last_error = exc
            logger.warning("provider_error request_id=%s provider=%s", request_id, provider.name)

    if last_error:
        raise HTTPException(
            status_code=502 if last_error.status_code is None or last_error.status_code >= 500 else 429,
            detail={"message": "All configured NahaLLM providers failed", "provider": last_error.provider, "request_id": request_id},
        )
    raise HTTPException(status_code=503, detail="No provider is configured for this model alias")
