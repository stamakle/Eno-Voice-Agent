from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from english_tech.curriculum.models import (
    Exercise,
    ExerciseFeedback,
    ExerciseResult,
    Lesson,
    TutorSessionSnapshot,
    TutorTurn,
)


@dataclass
class TutorSessionState:
    learner_id: str
    course_id: str
    chapter_id: str
    lesson: Lesson
    variant_id: str | None = None
    personalization_focus: list[str] = field(default_factory=list)
    system_prompt: str = ""
    session_id: str = field(default_factory=lambda: uuid4().hex)
    current_exercise_index: int = 0
    completed_exercises: list[str] = field(default_factory=list)
    turn_count: int = 0
    status: str = "active"
    attempt_counts: dict[str, int] = field(default_factory=dict)
    pending_retry: bool = False
    lesson_summary: str | None = None
    transcript: list[TutorTurn] = field(default_factory=list)
    exercise_results: dict[str, ExerciseResult] = field(default_factory=dict)

    def current_exercise(self) -> Exercise | None:
        if self.current_exercise_index >= len(self.lesson.exercises):
            return None
        return self.lesson.exercises[self.current_exercise_index]

    def current_attempt(self) -> int:
        exercise = self.current_exercise()
        if exercise is None:
            return 0
        return self.attempt_counts.get(exercise.exercise_id, 0)

    def register_attempt(self) -> int:
        exercise = self.current_exercise()
        if exercise is None:
            return 0
        attempt = self.attempt_counts.get(exercise.exercise_id, 0) + 1
        self.attempt_counts[exercise.exercise_id] = attempt
        return attempt

    def add_turn(self, role: str, message: str) -> None:
        exercise = self.current_exercise()
        self.transcript.append(
            TutorTurn(role=role, message=message, exercise_id=exercise.exercise_id if exercise else None)
        )

    def record_feedback(self, feedback: ExerciseFeedback, learner_text: str) -> ExerciseResult | None:
        exercise = self.current_exercise()
        if exercise is None:
            return None

        result = ExerciseResult(
            exercise_id=exercise.exercise_id,
            exercise_type=exercise.exercise_type,
            attempts=self.attempt_counts.get(exercise.exercise_id, feedback.attempt_number),
            completed=feedback.should_advance,
            mastered=feedback.passed,
            learner_response=learner_text,
            feedback=feedback,
        )
        self.exercise_results[exercise.exercise_id] = result
        self.pending_retry = not feedback.should_advance

        if feedback.should_advance:
            if exercise.exercise_id not in self.completed_exercises:
                self.completed_exercises.append(exercise.exercise_id)
            self.current_exercise_index += 1
            self.pending_retry = False
            if self.current_exercise_index >= len(self.lesson.exercises):
                self.status = "ready_for_completion"
            else:
                self.status = "active"
        else:
            self.status = "retrying"
        return result

    def ordered_exercise_results(self) -> list[ExerciseResult]:
        results: list[ExerciseResult] = []
        for exercise in self.lesson.exercises:
            result = self.exercise_results.get(exercise.exercise_id)
            if result is not None:
                results.append(result)
        return results

    def snapshot(self) -> TutorSessionSnapshot:
        exercise = self.current_exercise()
        return TutorSessionSnapshot(
            session_id=self.session_id,
            learner_id=self.learner_id,
            course_id=self.course_id,
            chapter_id=self.chapter_id,
            lesson_id=self.lesson.lesson_id,
            lesson_title=self.lesson.title,
            variant_id=self.variant_id,
            status=self.status,
            current_exercise_id=exercise.exercise_id if exercise else None,
            current_exercise_type=exercise.exercise_type if exercise else None,
            current_prompt=exercise.prompt if exercise else None,
            current_attempt=self.current_attempt(),
            current_max_attempts=exercise.max_attempts if exercise else 0,
            pending_retry=self.pending_retry,
            completed_exercises=self.completed_exercises,
            completed_exercise_count=len(self.completed_exercises),
            turn_count=self.turn_count,
            personalization_focus=self.personalization_focus,
            lesson_summary=self.lesson_summary,
        )
