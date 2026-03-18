# Architecture

## Product Shape
- Flutter mobile client
- FastAPI backend
- voice runtime for STT, tutor logic, and TTS
- curriculum agent for sequencing lessons
- learner profile and progress store

## Agents

### Curriculum Agent
Responsibilities:
- choose course and chapter progression
- adapt next lesson using weak topics and completion history
- decide when to review prior material
- prepare learner-specific lesson variants while keeping the course template deterministic
- cache generated lesson variants for reuse

### Tutor Agent
Responsibilities:
- run the active lesson
- ask questions and guide speaking exercises
- provide corrections and retry prompts
- generate end-of-lesson recap
- maintain retry-aware session state for each exercise

## Data Layers
- `data/curriculum/templates/*.json`
- `data/curriculum/generated/<learner_id>/*.json`
- `data/learners/*.json`
- `data/results/*.json`
- later: migrate learner data to SQLite or Postgres

## Runtime Flow
1. learner opens lesson in Flutter
2. backend loads learner profile and next lesson
3. tutor runtime builds lesson-aware prompt
4. learner speaks or types
5. backend processes STT, correction logic, and tutor response
6. TTS returns spoken reply
7. lesson result is persisted
