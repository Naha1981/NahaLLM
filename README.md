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
     +--> routing policy
     +--> provider health
     +--> fallback
     +--> usage / metering
     |
     +--> Gemini
     +--> Groq
     +--> Cerebras
     +--> Mistral
     +--> NVIDIA
     +--> OpenRouter
```

## V1 goals

- OpenAI-compatible `/v1/chat/completions` interface
- Server-side provider credentials only
- Model aliases: `fast`, `balanced`, `premium`, `economy`
- Free-first provider routing
- Automatic fallback on transient, provider, and rate-limit failures
- Streaming responses
- Health/readiness endpoints
- Structured usage logging without storing sensitive prompt content by default
- Per-application API keys and usage metadata
- Replaceable provider adapters
- Tests for routing, fallback, authentication, and provider failures

## Architecture principles

1. Apps depend only on NahaLLM, never directly on providers.
2. Provider keys stay server-side.
3. Routing is deterministic and observable before adding sophisticated optimisation.
4. Provider differences are isolated behind adapters.
5. Start on free infrastructure and free provider tiers; add paid providers only when required.
6. Keep OmniRoute/NaraRouter or any third-party router replaceable rather than a hard dependency.
7. Design for future multimodal capabilities, embeddings, and tool calling without blocking V1 text chat.

## Planned API

```text
GET  /health
GET  /ready
GET  /v1/models
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

## NahaLabs consumers

The gateway is intended to serve applications including Flavourly, CargoIQ, tutoring, SELLA, LeadMachine, and future NahaLabs systems.

## Status

V1 foundation under active development.
