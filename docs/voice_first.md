# Voice-First

## Goal
Make `english_tech` a voice-first coaching product where the backend owns progress narration,
classification, onboarding, and next-step guidance. The dashboard remains available as a support API,
but it is no longer the primary learner-facing UI.

## Phase 1 Scope
Phase 1 moves bootstrap and high-level coach decisions out of Flutter and into the backend.
It does not replace the lesson websocket or add an LLM yet.

## Target Module Structure

### Backend
```text
backend/english_tech/
  api/
    routes/
      audio.py
      coach.py              # NEW voice-first bootstrap and coach turn routes
      curriculum.py
      dashboard.py          # support/admin API only
      health.py
      lesson.py
      live_lesson.py        # lesson websocket runtime
      profile.py            # support/admin API only
      web.py                # support/debug HTML templates
  coaching/
    __init__.py
    analysis.py            # derives learner classification and improvement focus
    messages.py            # spoken coach strings built from analysis
    models.py              # coach bootstrap/turn response schemas
    orchestrator.py        # backend-owned coach flow and next-step decisions
  curriculum/
    agent.py
    models.py
    runtime.py
    session.py
    store.py
  learners/
    models.py
    results.py
    store.py
  config.py
  db.py
  db_models.py
  main.py
```

### Flutter
```text
flutter_client/lib/
  config/
    app_config.dart
  models/
    api_models.dart        # extended with coach bootstrap / coach turn models
  screens/
    coach_screen.dart      # primary public learner screen
    lesson_screen.dart
    main_shell.dart        # collapsed to minimal voice-first shell
    onboarding_screen.dart # deprecated for public flow, kept only as fallback
    discover_screen.dart   # hidden support surface
    progress_screen.dart   # hidden support surface
    profile_screen.dart    # hidden support/settings surface
  services/
    api_client.dart        # bootstrap and coach turn APIs
    lesson_socket.dart
    speech_client.dart
  state/
    app_state.dart         # bootstraps from backend coach state, not dashboard
  main.dart
```

## Public UX Shape After Phase 1
- App boots directly into the coach surface.
- Backend returns:
  - spoken greeting
  - current classification
  - progress summary
  - improvement focus
  - whether onboarding is needed
  - whether a lesson can be resumed
  - recommended next lesson
- Flutter records speech, transcribes it, sends transcript to backend coach route, and renders the returned spoken reply.
- Dashboard and profile data still exist, but they are no longer the visible product center.

## Follow-on Phases

### Phase 2
- Move coach turn handling from HTTP to a dedicated `WS /ws/coach`
- Persist richer onboarding state
- Add auth and remove `demo` learner assumptions

### Phase 3
- Replace deterministic coach turn heuristics with LLM-backed semantic coaching
- Keep deterministic curriculum templates as constraints

### Phase 4
- Streaming STT/TTS, barge-in, and continuous listening
- Production deployment hardening
