# Eno-Voice-Agent

Eno Voice Agent is a voice-first English learning platform built around a FastAPI backend, a Flutter client, and a realtime speech loop for coaching, lessons, and learner progress tracking.

This repository combines curriculum orchestration, authenticated learner state, local STT/TTS services, and mobile/web clients into a single stack for spoken English practice.

Note: the product-facing name can be `Eno Voice Agent`, while the current Python package and import path remain `english_tech`.

## Overview

- Voice-first English coaching and lesson delivery.
- Curriculum-driven progression across `beginner`, `advanced`, and `proficiency` tracks.
- Realtime coach and lesson WebSocket runtimes.
- Postgres-first persistence with Alembic migrations and SQLite fallback for local development.
- Flutter client for mobile, desktop, and web.
- Production-oriented scaffolding for deployment, rate limiting, and reverse proxying.

## Architecture

```text
Flutter client
  -> HTTP APIs for auth, profile, curriculum, lesson metadata, dashboard, and audio
  -> WebSockets for coach and live lesson sessions

FastAPI backend
  -> Coach orchestration for onboarding and lesson guidance
  -> Curriculum agent for lesson sequencing and personalization
  -> Tutor runtime for retries, correction, and summaries
  -> Speech services for STT and TTS
  -> SQLAlchemy + Alembic persistence for learners, auth, sessions, and lesson results
```

## Core Features

- Email/password auth with access and refresh tokens.
- Optional Google sign-in support for Flutter web and compatible clients.
- Curriculum sequencing with weak-topic prioritization and review-aware lesson selection.
- Lesson runtime with `teach -> respond -> correct -> retry -> summarize`.
- Coach runtime that can greet the learner, summarize progress, and recommend or open the next lesson.
- Local speech stack:
  - `faster-whisper` for speech-to-text
  - `Piper` for text-to-speech
- Dashboard, learner profile, lesson history, and review queue support.
- HTTP and WebSocket rate limiting with optional Redis-backed shared state.
- CI coverage for backend and Flutter validation.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Speech: faster-whisper, Piper
- Client: Flutter
- Database: Postgres with SQLite development fallback
- Rate limiting: in-memory or Redis
- LLM integration: Ollama or OpenAI-compatible endpoints for semantic evaluation

## Quick Start

### Prerequisites

- Python `3.10+`
- [`uv`](https://docs.astral.sh/uv/)
- Optional for fuller local development:
  - Postgres
  - Redis
  - Flutter SDK
  - Ollama or another OpenAI-compatible endpoint

### Start the backend

```bash
git clone <your-repo-url>
cd english_tech
uv venv --python 3.10 .uv-venv
uv pip install --python .uv-venv/bin/python -e .
PYTHONPATH=backend .uv-venv/bin/python -m alembic upgrade head
PYTHONPATH=backend .uv-venv/bin/uvicorn english_tech.main:app --host 127.0.0.1 --port 8091 --reload
```

Then open:

- API health: `http://127.0.0.1:8091/health`
- OpenAPI docs: `http://127.0.0.1:8091/docs`

### Database behavior

The app prefers `ENGLISH_TECH_DATABASE_URL`, which defaults to local Postgres. In development, if that connection is unavailable, the app can fall back to SQLite at `data/english_tech.db`.

For production, set:

```bash
ENGLISH_TECH_ENV=production
ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION=true
```

## Optional Local Helpers

Migrate legacy JSON learner and result files into the active database:

```bash
PYTHONPATH=backend .uv-venv/bin/python scripts/migrate_json_to_db.py
```

Preload Piper assets before the first TTS request:

```bash
PYTHONPATH=backend .uv-venv/bin/python scripts/preload_speech_assets.py
```

Run against local Postgres and Redis with the included helper:

```bash
./scripts/local_services/run_backend_with_local_stack.sh
```

## Flutter Client

The Flutter app lives in [`flutter_client/`](flutter_client) and is configured for Android, iOS, macOS, Linux, Windows, and web.

Default runtime targets:

- API: `http://10.0.2.2:8091`
- Coach WebSocket: `ws://10.0.2.2:8091/api/coach/ws/coach`
- Lesson WebSocket: `ws://10.0.2.2:8091/ws/lesson`

Run locally:

```bash
cd flutter_client
flutter pub get
flutter run \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://<host>:8091 \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://<host>:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://<host>:8091/ws/lesson
```

Example web run:

```bash
cd flutter_client
flutter run -d chrome \
  --web-hostname 127.0.0.1 \
  --web-port 8100 \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://127.0.0.1:8091 \
  --dart-define=ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID=<google-web-client-id> \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://127.0.0.1:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://127.0.0.1:8091/ws/lesson
```

## Configuration

### Core environment variables

| Variable | Purpose |
| --- | --- |
| `ENGLISH_TECH_ENV` | `development` or `production`. |
| `ENGLISH_TECH_DATABASE_URL` | Primary database connection string. |
| `ENGLISH_TECH_DATABASE_FALLBACK_URL` | SQLite fallback used in development. |
| `ENGLISH_TECH_DB_AUTO_CREATE` | Auto-runs migrations at startup. Useful for bootstrap only. |
| `ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION` | Enforces Postgres when running in production mode. |
| `ENGLISH_TECH_RATE_LIMIT_BACKEND` | `memory` or `redis`. |
| `ENGLISH_TECH_REDIS_URL` | Redis connection string. |

### Speech and model settings

| Variable | Purpose |
| --- | --- |
| `ENGLISH_TECH_STT_MODEL` | Whisper model name, default `base.en`. |
| `ENGLISH_TECH_STT_DEVICE` | `cpu` or `cuda`. |
| `ENGLISH_TECH_STT_COMPUTE_TYPE` | Whisper compute mode. |
| `ENGLISH_TECH_TTS_VOICE` | Piper voice model name. |
| `ENGLISH_TECH_TTS_RATE` | Speech rate override. |
| `ENGLISH_TECH_LLM_PROVIDER` | `ollama`, `openai_compat`, or `none`. |
| `ENGLISH_TECH_LLM_BASE_URL` | Base URL for the model provider. |
| `ENGLISH_TECH_LLM_MODEL` | Model name for semantic lesson evaluation. |

### Auth and client settings

| Variable | Purpose |
| --- | --- |
| `ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID` | Google OAuth client for Flutter web sign-in. |
| `ENGLISH_TECH_GOOGLE_SERVER_CLIENT_ID` | Optional server/native client ID. |
| `ENGLISH_TECH_GOOGLE_ALLOWED_CLIENT_IDS` | Comma-separated allowed Google client IDs. |
| `ENGLISH_TECH_APP_BASE_URL` | Public client base URL used in auth flows. |
| `ENGLISH_TECH_CORS_ORIGIN_REGEX` | Allowed browser origins. |

Production defaults and examples live in [`deploy/.env.production.example`](deploy/.env.production.example).

## API Summary

Important HTTP routes:

- `GET /health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`
- `GET /api/coach/bootstrap`
- `GET /api/curriculum/templates`
- `POST /api/curriculum/next-lesson`
- `GET /api/lesson/{course_id}/{chapter_id}/{lesson_id}`
- `POST /api/lesson/complete`
- `GET /api/dashboard/me`
- `GET /api/profile/me`
- `POST /api/profile/me`
- `POST /api/audio/stt`
- `POST /api/audio/tts`
- `GET /api/metrics`

Realtime routes:

- `WS /api/coach/ws/coach?token=<bearer-token>`
- `WS /ws/lesson?token=<bearer-token>`

For request/response and event details, see [`docs/api_contract.md`](docs/api_contract.md).

## Development and Testing

Backend tests:

```bash
PYTHONPATH=backend python -m unittest discover -s tests -p 'test_*.py'
```

Flutter validation:

```bash
cd flutter_client
flutter pub get
flutter analyze --no-fatal-infos
flutter test
```

CI is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Production Notes

This repository includes production-oriented pieces, not just a prototype:

- [Dockerfile](Dockerfile) for backend image builds
- [deploy/.env.production.example](deploy/.env.production.example) for production configuration
- [deploy/Caddyfile](deploy/Caddyfile) for reverse proxy setup
- [deploy/systemd-user/](deploy/systemd-user) for user-level service definitions
- authenticated metrics and configurable rate limiting
- Postgres enforcement in production mode

Important caveat: [`docker-compose.yml`](docker-compose.yml) is not a full application stack today. It currently contains only a Neo4j service, so production deployment should follow the documented environment and service setup instead of relying on Compose alone.

## Repository Layout

```text
backend/                    FastAPI application package
backend/english_tech/
  api/routes/               HTTP and WebSocket routes
  coaching/                 Coach orchestration
  curriculum/               Templates, runtime, grading, and agent logic
  learners/                 Learner profile and result persistence
  speech/                   STT/TTS integration
flutter_client/             Flutter application
alembic/                    Database migrations
data/curriculum/templates/  Seed curriculum templates
scripts/                    Bootstrap, validation, migration, and local service helpers
deploy/                     Deployment config, env examples, and service units
docs/                       Architecture, API, and deployment docs
tests/                      Backend test suite
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/api_contract.md`](docs/api_contract.md)
- [`docs/curriculum_strategy.md`](docs/curriculum_strategy.md)
- [`docs/flutter_integration.md`](docs/flutter_integration.md)
- [`docs/implementation_phase_plan.md`](docs/implementation_phase_plan.md)
- [`docs/production_deployment.md`](docs/production_deployment.md)
- [`docs/voice_first_refactor.md`](docs/voice_first_refactor.md)
