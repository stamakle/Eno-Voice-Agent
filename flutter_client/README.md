# english_tech_flutter

This is the generated Flutter client scaffold for the `english_tech` backend.

## Default backend target

The current scaffold expects the backend at:
- `http://10.0.2.2:8091` for Android emulator
- `ws://10.0.2.2:8091/api/coach/ws/coach`
- `ws://10.0.2.2:8091/ws/lesson`

Override those defaults at runtime with:

```bash
flutter run \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://<host>:8091 \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://<host>:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://<host>:8091/ws/lesson
```

For a physical device on the same LAN, replace `<host>` with the machine IP or DNS name that serves the backend.

Chrome target used on this machine:

```bash
flutter run -d chrome \
  --web-hostname 127.0.0.1 \
  --web-port 8100 \
  --dart-define=ENGLISH_TECH_API_BASE_URL=http://127.0.0.1:8091 \
  --dart-define=ENGLISH_TECH_COACH_WS_URL=ws://127.0.0.1:8091/api/coach/ws/coach \
  --dart-define=ENGLISH_TECH_LESSON_WS_URL=ws://127.0.0.1:8091/ws/lesson
```

## Current scaffold coverage

- `AuthScreen`
  - register/login
  - refresh-token backed session restore
- `CoachScreen`
  - authenticated coach websocket
  - backend-owned onboarding and progress guidance
  - streaming microphone PCM into the coach websocket
  - partial transcript updates during coach turns
  - streamed coach audio playback from websocket frames
- `LessonScreen`
  - `join_lesson`
  - streaming `audio_input_start` / `audio_chunk` / `audio_commit`
  - `stt_partial` live transcript updates
  - fallback `learner_text`
  - live tutor state updates
  - retry-aware lesson prompts
  - `assistant_summary`
  - `complete_lesson` once the lesson reaches `ready_for_completion`
  - microphone PCM streaming via `record`
  - playback interruption when the learner starts talking again
  - streamed assistant audio frames over the lesson websocket

## Local commands

```bash
cd /home/aseda/Desktop/english_tech/flutter_client
flutter pub get
flutter analyze
flutter test
```
