# API Contract

## Health
- `GET /health`
- `GET /api/metrics`
  - requires `Authorization: Bearer <token>`
  - returns in-process request, websocket, and LLM counters

## Auth
- `POST /api/auth/register`
  - input:
    - `email`
    - `password`
    - `display_name`
  - output:
    - `token`
    - `user`
    - `expires_at`
- `POST /api/auth/login`
  - input:
    - `email`
    - `password`
- `POST /api/auth/refresh`
  - input:
    - `refresh_token`
  - output:
    - rotated `token`
    - rotated `refresh_token`
    - `user`
- `POST /api/auth/logout`
  - requires `Authorization: Bearer <token>`
- `GET /api/auth/me`
  - requires `Authorization: Bearer <token>`
  - returns current authenticated learner identity

## Coach
- `GET /api/coach/bootstrap`
  - requires `Authorization: Bearer <token>`
  - returns the backend-owned spoken greeting, spoken progress summary, spoken next step, classification, and recommended lesson
- `WS /api/coach/ws/coach?token=<bearer-token>`

Coach websocket client messages:
- `request_bootstrap`
- `audio_input_start`
- `audio_chunk`
- `audio_commit`
- `learner_text`
  - input: `text`

Coach websocket server events:
- `coach_session`
- `coach_bootstrap`
- `coach_reply`
- `coach_audio_start`
- `coach_audio_chunk`
- `coach_audio_complete`
- `stt_partial`
- `stt_result`
- `open_lesson`
- `error`

## Audio
- `POST /api/audio/stt`
  - multipart form upload
  - field: `audio`
  - optional field: `language`
  - accepts PCM WAV audio
  - output:
    - transcript text
    - detected language
    - duration seconds
    - word timings with probabilities
    - active inference device
- `POST /api/audio/tts`
  - JSON body:
    - `text`
    - optional `voice`
    - optional `rate`
  - output:
    - `audio/wav` response body generated locally by Piper

## Curriculum
- `GET /api/curriculum/templates`
  - list available course templates
- `GET /api/curriculum/templates/{course_id}`
  - return full course template
- `POST /api/curriculum/next-lesson`
  - input:
    - `learner_id`
    - `course_id`
    - `completed_lessons`
    - `weak_topics`
    - optional `review_queue`
    - optional `learner_goals`
  - output:
    - `selection`
    - `lesson`

## Lesson
- `GET /api/lesson/{course_id}/{chapter_id}/{lesson_id}`
  - requires `Authorization: Bearer <token>`
  - returns the personalized lesson variant for the authenticated learner
- `POST /api/lesson/complete`
  - requires `Authorization: Bearer <token>`
  - input:
    - `lesson.course_id`
    - `lesson.chapter_id`
    - `lesson.lesson_id`
    - optional `variant_id`
    - `completed`
    - optional `grammar_accuracy`
    - optional `pronunciation_accuracy`
    - optional `notes`
    - optional `weak_topics`
    - optional `summary_text`
    - optional `exercise_results`
    - optional `turn_count`
  - output:
    - persisted lesson result envelope
    - generated review items
    - learner progress summary

## Learner Profile
- `GET /api/profile/me`
  - requires `Authorization: Bearer <token>`
- `POST /api/profile/me`
  - requires `Authorization: Bearer <token>`

## Dashboard
- `GET /api/dashboard/me`
  - requires `Authorization: Bearer <token>`
  - output:
    - learner profile
    - total completed lessons
    - weak topics
    - recent lesson results
    - recent lesson history
    - pending review queue
    - due review count
    - next review due date
    - recommended next lesson

## Live Lesson WebSocket
- `WS /ws/lesson?token=<bearer-token>`

Client message types:
- `join_lesson`
  - input: `course_id`, `chapter_id`, `lesson_id`
- `request_state`
- `audio_input_start`
  - input: optional `sample_rate`
- `audio_chunk`
  - input: base64-encoded PCM16 bytes
- `audio_commit`
- `learner_text`
  - input: `text`
- `complete_lesson`
  - input: optional accuracy scores, notes, weak topics, summary text
  - accepted only after the lesson reaches `ready_for_completion`

Server event types:
- `session_state`
- `audio_input_ack`
- `stt_partial`
- `stt_result`
- `assistant_message`
- `assistant_audio_start`
- `assistant_audio_chunk`
- `assistant_audio_complete`
- `assistant_audio_error`
- `lesson_prompt`
- `correction`
- `assistant_summary`
- `lesson_ready_to_complete`
- `lesson_completed`
- `error`

## Persistence
- primary database URL: `ENGLISH_TECH_DATABASE_URL`
- local fallback database URL: `ENGLISH_TECH_DATABASE_FALLBACK_URL`
- `ENGLISH_TECH_ENV=production` + `ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION=true`
  - disables silent SQLite fallback and requires Postgres
- `ENGLISH_TECH_RATE_LIMIT_BACKEND=redis`
- `ENGLISH_TECH_REDIS_URL=redis://...`
  - enables Redis-backed shared rate limiting
- local default fallback storage: SQLite at `data/english_tech.db`
- schema migrations are managed by Alembic
- bootstrap:
  - `python -m alembic upgrade head`
- current SQLAlchemy models:
  - `learners`
  - `auth_users`
  - `auth_sessions`
  - `lesson_results`
  - `review_items`
- legacy JSON migration script:
  - `scripts/migrate_json_to_db.py`
