# English Tech

English Tech is a curriculum-driven English learning platform built around a FastAPI backend, a Flutter client, and a voice pipeline that turns learner speech into guided lesson feedback in real time.

The repository combines deterministic course templates with adaptive lesson orchestration, authenticated learner state, local STT/TTS services, and mobile/web clients for voice-first practice.

## Highlights

- Curriculum engine for `beginner`, `advanced`, and `proficiency` learning tracks.
- FastAPI backend with auth, learner profile, dashboard, lesson, coach, and audio APIs.
- Two realtime WebSocket flows:
  - `WS /api/coach/ws/coach` for onboarding, guidance, and lesson recommendation.
  - `WS /ws/lesson` for live lesson turns, partial transcription, correction, and completion.
- Local speech services using `faster-whisper` for STT and `Piper` for TTS.
- Postgres-first persistence with Alembic migrations and SQLite fallback for local development.
- Flutter client for Android, iOS, web, macOS, Linux, and Windows targets.
- CI coverage for backend compile/tests plus Flutter analyze/test.

## System Overview

```text
Flutter client
  -> HTTP APIs for auth, profile, dashboard, curriculum, and lesson metadata
  -> WebSockets for coach and live lesson sessions

FastAPI backend
  -> Curriculum agent for lesson selection and personalization
  -> Tutor runtime for retry-aware exercise flow
  -> Speech layer for STT and TTS
  -> SQLAlchemy + Alembic persistence for learners, auth, results, and review items
```

## Core Capabilities

- Learner authentication with access/refresh tokens and optional Google sign-in support.
- Curriculum sequencing with weak-topic prioritization and review-aware lesson selection.
- Lesson runtime with `teach -> respond -> correct -> retry -> summarize`.
- Coach runtime that can greet the learner, summarize progress, and open the next lesson.
- Local speech endpoints:
  - `POST /api/audio/stt`
  - `POST /api/audio/tts`
- Dashboard and profile APIs for progress tracking and learner settings.
- Metrics and rate limiting for both HTTP and WebSocket traffic.

## Repository Layout

```text
backend/                  FastAPI application package
backend/english_tech/
  api/routes/             HTTP and WebSocket routes
  coaching/               Coach orchestration
  curriculum/             Templates, runtime, grading, and agent logic
  learners/               Learner profile and result stores
  speech/                 STT/TTS integration
flutter_client/           Flutter application
data/curriculum/templates/Seed curriculum JSON templates
alembic/                  Database migrations
scripts/                  Bootstrap, migration, validation, and speech preload helpers
deploy/                   Production env example, Caddy config, and systemd units
docs/                     Architecture, API, deployment, and planning notes
tests/                    Backend test suite
```

## Backend Quick Start

### Prerequisites

- Python `3.10+`
- [`uv`](https://docs.astral.sh/uv/) or a comparable Python environment tool
- Optional:
  - Postgres for shared/local multi-service development
  - Redis for shared rate limiting
  - Ollama or another OpenAI-compatible endpoint for semantic feedback

### Install and run

```bash
cd /home/aseda/Desktop/english_tech
uv venv --python 3.10 .uv-venv
uv pip install --python .uv-venv/bin/python -e .
PYTHONPATH=backend .uv-venv/bin/python -m alembic upgrade head
PYTHONPATH=backend .uv-venv/bin/uvicorn english_tech.main:app --host 127.0.0.1 --port 8091 --reload
```

The backend prefers `ENGLISH_TECH_DATABASE_URL`, which defaults to local Postgres. In development, if that connection fails, it falls back to SQLite at `data/english_tech.db`.

### Optional local bootstrap helpers

Migrate legacy JSON learner/result data into the active database:

```bash
PYTHONPATH=backend .uv-venv/bin/python scripts/migrate_json_to_db.py
```

Preload local Piper runtime assets before the first TTS request:

```bash
PYTHONPATH=backend .uv-venv/bin/python scripts/preload_speech_assets.py
```

Run the backend against local Postgres and Redis with the checked-in helper script:

```bash
./scripts/local_services/run_backend_with_local_stack.sh
```

## Flutter Client

The Flutter app lives in [`flutter_client/`](flutter_client) and is already scaffolded for mobile, desktop, and web targets.

### Default targets

- API: `http://10.0.2.2:8091`
- Coach WebSocket: `ws://10.0.2.2:8091/api/coach/ws/coach`
- Lesson WebSocket: `ws://10.0.2.2:8091/ws/lesson`

### Run locally

```bash
cd /home/aseda/Desktop/english_tech/flutter_client
flutter pub get
flutter run \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://<host>:8091 \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://<host>:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://<host>:8091/ws/lesson
```

Example Chrome configuration used in local development:

```bash
cd /home/aseda/Desktop/english_tech/flutter_client
flutter run -d chrome \
  --web-hostname 127.0.0.1 \
  --web-port 8100 \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://127.0.0.1:8091 \
  --dart-define=ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID=<google-web-client-id> \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://127.0.0.1:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://127.0.0.1:8091/ws/lesson
```

## Important Configuration

| Variable | Purpose |
| --- | --- |
| `ENGLISH_TECH_ENV` | `development` or `production`; production disables permissive fallbacks. |
| `ENGLISH_TECH_DATABASE_URL` | Primary database connection string. |
| `ENGLISH_TECH_DATABASE_FALLBACK_URL` | SQLite fallback used in development if Postgres is unavailable. |
| `ENGLISH_TECH_DB_AUTO_CREATE` | Auto-run Alembic migrations on startup. Useful for local bootstrapping. |
| `ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION` | Forces Postgres in production mode. |
| `ENGLISH_TECH_RATE_LIMIT_BACKEND` | `memory` or `redis`. |
| `ENGLISH_TECH_REDIS_URL` | Redis URL for shared rate limiting. |
| `ENGLISH_TECH_STT_MODEL` | `faster-whisper` model name, default `base.en`. |
| `ENGLISH_TECH_STT_DEVICE` | STT device selection, default `cuda` when available, otherwise `cpu`. |
| `ENGLISH_TECH_TTS_VOICE` | Piper voice model, default `en_US-lessac-medium`. |
| `ENGLISH_TECH_TTS_RATE` | Speech rate override for generated TTS audio. |
| `ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID` | Google OAuth client for Flutter web sign-in. |
| `ENGLISH_TECH_GOOGLE_ALLOWED_CLIENT_IDS` | Comma-separated client IDs accepted by the backend. |
| `ENGLISH_TECH_LLM_PROVIDER` | `ollama`, `openai_compat`, or `none`. |
| `ENGLISH_TECH_LLM_BASE_URL` | Base URL for the configured LLM endpoint. |
| `ENGLISH_TECH_LLM_MODEL` | Model name used for semantic lesson evaluation. |

See [`deploy/.env.production.example`](deploy/.env.production.example) for a production-oriented baseline.

## API Summary

Key HTTP routes:

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

For message-level details, see [`docs/api_contract.md`](docs/api_contract.md).

## Testing and CI

Backend:

```bash
cd /home/aseda/Desktop/english_tech
PYTHONPATH=backend python -m unittest discover -s tests -p 'test_*.py'
```

Flutter:

```bash
cd /home/aseda/Desktop/english_tech/flutter_client
flutter pub get
flutter analyze --no-fatal-infos
flutter test
```

GitHub Actions runs both paths from [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Deployment Notes

- [`Dockerfile`](Dockerfile) builds the backend image.
- [`deploy/Caddyfile`](deploy/Caddyfile) provides a reverse-proxy example.
- [`deploy/systemd-user/`](deploy/systemd-user) contains user-level service units.
- [`docs/production_deployment.md`](docs/production_deployment.md) documents the current production expectations.

Production mode expects Postgres and is designed to work with Redis-backed rate limiting. A full application Compose stack is not currently checked in; the existing [`docker-compose.yml`](docker-compose.yml) is limited to a Neo4j service.

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/api_contract.md`](docs/api_contract.md)
- [`docs/curriculum_strategy.md`](docs/curriculum_strategy.md)
- [`docs/flutter_integration.md`](docs/flutter_integration.md)
- [`docs/implementation_phase_plan.md`](docs/implementation_phase_plan.md)
- [`docs/production_deployment.md`](docs/production_deployment.md)
- [`docs/voice_first_refactor.md`](docs/voice_first_refactor.md)
