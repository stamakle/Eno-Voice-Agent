# Flutter Integration

## Recommendation
Use Flutter as the learner-facing mobile app and keep the backend responsible for curriculum orchestration and voice intelligence.

## Flutter Responsibilities
- authentication
- learner onboarding
- lesson picker
- microphone capture
- audio playback
- progress dashboard
- notifications and reminders

## Backend Responsibilities
- course and lesson retrieval
- next-lesson selection
- learner state persistence
- voice lesson websocket runtime
- STT, tutor logic, and TTS orchestration

## Transport
- HTTP for profile, curriculum, lesson metadata, and dashboard
- WebSocket for live voice sessions

## Current Scaffold
- Manual client scaffold lives in `flutter_client/`
- Implemented screens:
  - `HomeScreen` for health, dashboard, reviews-due summary, and recommended lesson launch
  - `LessonScreen` for `/ws/lesson` session flow, retries, and lesson summary
- Implemented services:
  - `ApiClient` for HTTP endpoints
  - `LessonSocket` for websocket messages

## Current Backend Target
- Android emulator HTTP: `http://10.0.2.2:8091`
- Android emulator WebSocket: `ws://10.0.2.2:8091/ws/lesson`

For physical devices, update `flutter_client/lib/config/app_config.dart` to point at the reachable backend host.
