# Implementation Phase Plan

## Phase 0: Refactor Foundation
- keep transport, voice, and session orchestration separate from curriculum logic
- create `curriculum`, `learners`, and `api` modules
- keep lesson state outside the websocket handler

## Phase 1: Curriculum Schema
- status: implemented
- implemented models now cover:
  - `CourseTemplate`, `Chapter`, `Lesson`, `Exercise`, `ReviewRule`
  - `LessonVariant`, `ExerciseFeedback`, `ExerciseResult`, `TutorSessionSnapshot`
  - `LearnerProfile`, `ReviewItem`, `LessonHistoryEntry`, `LessonResult`
- curriculum and learner JSON are validated through Pydantic before runtime use

## Phase 2: Static Curriculum Templates
- status: implemented
- deterministic templates ship for `beginner`, `advanced`, and `proficiency`
- template structure remains fixed; runtime personalization does not modify the base course files

## Phase 3: Curriculum Agent
- status: implemented
- next lesson selection now prioritizes:
  - due review items
  - weak-topic reinforcement
  - learner-goal alignment
  - deterministic course order
- learner-specific lesson variants are generated inside template boundaries and cached on disk under `data/curriculum/generated/`

## Phase 4: Lesson Runtime
- status: implemented
- the websocket lesson runtime now:
  - builds a lesson-aware tutor prompt
  - tracks retry counts per exercise
  - emits structured correction feedback
  - repeats the current exercise when a retry is needed
  - emits an end-of-lesson summary before completion

## Phase 5: Learner Profile And Progress
- status: implemented
- learner storage now tracks:
  - level band
  - goals
  - weak topics
  - completed lessons
  - streaks
  - total turns
  - lesson history
  - pending and completed review items
- review items are scheduled from each completed lesson using the lesson review rule

## Phase 6: Correction Engine
- return structured correction output
- show learner text, corrected text, error type, and retry guidance
- support grammar, vocabulary, fluency, and pronunciation categories

## Phase 7: Pronunciation MVP
- start with repeat-after-me and expected phrase comparison
- add targeted retry prompts
- postpone full phoneme scoring until the core tutor loop is stable

## Phase 8: Dashboard And Review
- expose progress metrics, review queue, and recent lessons
- track pronunciation retries, grammar accuracy, and speaking frequency

## Phase 9: Flutter Integration
- keep the backend as lesson orchestration and inference control
- use HTTP for profile, curriculum, and dashboard
- use WebSocket for live lesson sessions
