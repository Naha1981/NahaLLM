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

Resilience controls include request timeout, retries per provider, circuit failure threshold, and circuit cooldown.

The current circuit breaker is intentionally process-local so NahaLLM can run cheaply on a free Render instance. Redis-backed shared state is a later upgrade when horizontal scaling requires it.

## Architecture principles

1. Apps depend only on NahaLLM, never directly on providers.
2. Provider keys stay server-side.
3. Routing is deterministic and observable before adding sophisticated optimisation.
4. Provider differences are isolated behind adapters.
5. Start on free infrastructure and free provider tiers; add paid providers only when required.
6. Keep OmniRoute/NaraRouter or any third-party router replaceable rather than a hard dependency.
7. Future multimodal capabilities, embeddings, tool calling, and provider-specific capabilities can be added without breaking the V1 interface.

## NahaLabs consumers

The gateway is intended to serve applications including Flavourly, CargoIQ, tutoring, SELLA, LeadMachine, and future NahaLabs systems.

## Status

V1 foundation under active development. Next major layer: persistent usage metering, per-app quotas/rate limits, Redis support, and an operator dashboard.
