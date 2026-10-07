# NahaLLM

NahaLabs shared LLM gateway for AI-powered applications.

## Vision

NahaLLM gives every NahaLabs application one provider-independent, OpenAI-compatible AI interface. Applications never contain provider-specific API keys or routing logic.

```text
NahaLabs apps
     |
     v
 NahaLLM API
     |
     +--> authentication
     +--> routing policy
     +--> provider health / circuit breaker
     +--> retry + fallback
     +--> usage / metering foundation
     |
     +--> Gemini
     +--> Groq
     +--> Cerebras
     +--> Mistral
     +--> OpenRouter
     +--> FreeLLMAPI (optional fallback gateway)

NahaMedia (optional)
     |
     +--> image-to-video provider adapter
     +--> Spyce-compatible I2V endpoint
     +--> future replaceable providers
```

## V1 capabilities

- OpenAI-compatible `/v1/chat/completions`
- Server-side provider credentials only
- Model aliases: `fast`, `balanced`, `premium`, `economy`
- Deterministic free-first routing
- Per-provider retry and automatic fallback
- Process-local circuit breaker to temporarily skip unhealthy providers
- True upstream SSE streaming
- Health/readiness endpoints
- Authenticated provider status endpoint
- Request IDs for tracing
- Structured usage-oriented logging without prompt content by default
- Per-application API keys
- Replaceable provider adapters
- Tests for routing, fallback, authentication, and resilience

## API

```text
GET  /health
GET  /ready
GET  /v1/models
GET  /v1/providers
POST /v1/chat/completions
POST /v1/media/image-to-video
GET  /v1/media/jobs/{job_id}
```

Example:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <naha-app-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "fast",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

Streaming:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <naha-app-key>" \
  -H "Content-Type: application/json" \
  -N \
  -d '{
    "model": "fast",
    "messages": [{"role": "user", "content": "Write a short welcome message."}],
    "stream": true
  }'
```

## Configuration

Provider credentials are environment variables and must never be committed. See `.env.example`.

### Optional FreeLLMAPI fallback

NahaLLM can use a self-hosted FreeLLMAPI instance as the final fallback for every chat alias. FreeLLMAPI exposes an OpenAI-compatible `/v1/chat/completions` endpoint and supports router models such as `auto:fast`, `auto:balanced`, `auto:smart`, and `auto:cheap`. NahaLLM maps `fast`, `balanced`, `premium`, and `economy` to those strategies respectively. This keeps FreeLLMAPI behind the NahaLLM contract, so applications do not depend on it directly.

Set `FREELLMAPI_API_KEY` and `FREELLMAPI_BASE_URL` on the NahaLLM server. The default URL is `http://127.0.0.1:3001/v1`, which is suitable when both services run on the same machine. For a deployed NahaLLM instance, use a private/reachable FreeLLMAPI endpoint instead.

Resilience controls include request timeout, retries per provider, circuit failure threshold, and circuit cooldown.

The current circuit breaker is intentionally process-local so NahaLLM can run cheaply on a free Render instance. Redis-backed shared state is a later upgrade when horizontal scaling requires it.

## NahaMedia image-to-video

NahaLLM now exposes a provider-independent image-to-video contract behind a feature flag. The client submits a public image URL plus a motion prompt and receives a NahaMedia job ID. The job can then be polled until the provider returns a video URL.

The first adapter is Spyce-configurable rather than hard-coded to an undocumented endpoint. Set `NAHAMEDIA_ENABLED=true`, `SPYCE_API_KEY`, `SPYCE_I2V_SUBMIT_URL`, and `SPYCE_I2V_STATUS_URL_TEMPLATE` on the server. NahaLLM never logs the source image or prompt content by default.

Example:

```bash
curl http://localhost:8000/v1/media/image-to-video \\
  -H "Authorization: Bearer <naha-app-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "image_url": "https://example.com/product.jpg",
    "prompt": "Slow camera push-in with natural product movement",
    "duration_seconds": 6,
    "aspect_ratio": "16:9",
    "resolution": "720p"
  }'
```

Then poll:

```bash
curl http://localhost:8000/v1/media/jobs/<job-id> \\
  -H "Authorization: Bearer <naha-app-key>"
```

The media layer is intentionally separate from chat routing so LeadMachine, Flavourly and other NahaLabs apps can consume one stable interface while providers are replaced later.

## Architecture principles

1. Apps depend only on NahaLLM, never directly on providers.
2. Provider keys stay server-side.
3. Routing is deterministic and observable before adding sophisticated optimisation.
4. FreeLLMAPI is an optional fallback behind NahaLLM, never a direct application dependency.
5. Provider differences are isolated behind adapters.
6. Start on free infrastructure and free provider tiers; add paid providers only when required.
7. Keep OmniRoute/NaraRouter, FreeLLMAPI, or any third-party router replaceable rather than a hard dependency.
8. Future multimodal capabilities, embeddings, tool calling, and provider-specific capabilities can be added without breaking the V1 interface.

## NahaLabs consumers

The gateway is intended to serve applications including Flavourly, CargoIQ, tutoring, SELLA, LeadMachine, and future NahaLabs systems.

## Status

V1 foundation under active development. Next major layer: persistent usage metering, per-app quotas/rate limits, Redis support, and an operator dashboard.
