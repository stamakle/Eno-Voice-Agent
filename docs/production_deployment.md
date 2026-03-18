# Production Deployment

## Required services
- FastAPI application container
- Postgres
- Redis if `ENGLISH_TECH_RATE_LIMIT_BACKEND=redis`
- optional external or local Ollama/OpenAI-compatible LLM endpoint

## Environment
- see [deploy/.env.production.example](/home/aseda/Desktop/english_tech/deploy/.env.production.example)
- `ENGLISH_TECH_ENV=production`
- `ENGLISH_TECH_DATABASE_URL=postgresql+psycopg://...`
- `ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION=true`
- `ENGLISH_TECH_RATE_LIMIT_BACKEND=redis`
- `ENGLISH_TECH_REDIS_URL=redis://...`
- `ENGLISH_TECH_LLM_PROVIDER=ollama|openai_compat|none`
- `ENGLISH_TECH_LLM_BASE_URL=...`
- `ENGLISH_TECH_LLM_MODEL=...`

## Launch flow
1. Run `python -m alembic upgrade head`
2. Start Postgres and Redis
3. Start the API container
4. Put Caddy or another TLS proxy in front of the API
5. Verify `GET /health`
6. Verify `GET /api/metrics` with an authenticated account

## Current production notes
- Lesson audio is transported over websocket as PCM input and chunked WAV output.
- STT partials are emitted during lesson recording.
- Piper audio is still synthesized fully before chunk transport begins.
- In production, the app now fails closed if Postgres is not configured.
- Redis-backed rate limiting is optional but recommended for multi-instance deployment.
