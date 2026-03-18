from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LevelBand(str, Enum):
    beginner = "beginner"
    advanced = "advanced"
    proficiency = "proficiency"


class ExerciseType(str, Enum):
    teach = "teach"
    repeat = "repeat"
    roleplay = "roleplay"
    grammar = "grammar"
    pronunciation = "pronunciation"
    conversation = "conversation"
    recap = "recap"


class ReviewRule(BaseModel):
    review_after_days: int = Field(ge=1)
    trigger: str = Field(min_length=1, max_length=200)


class Exercise(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=120)
    exercise_type: ExerciseType
    prompt: str = Field(min_length=1, max_length=2000)
    expected_answer: str | None = Field(default=None, max_length=2000)
    sample_answer: str | None = Field(default=None, max_length=2000)
    correction_focus: list[str] = Field(default_factory=list)
    min_response_words: int = Field(default=1, ge=1, le=200)
    max_attempts: int = Field(default=2, ge=1, le=5)


class Lesson(BaseModel):
    lesson_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=500)
    target_vocabulary: list[str] = Field(default_factory=list)
    target_grammar: list[str] = Field(default_factory=list)
    pronunciation_focus: list[str] = Field(default_factory=list)
    exercises: list[Exercise] = Field(min_length=1)
    success_criteria: list[str] = Field(default_factory=list)
    review_rule: ReviewRule


class Chapter(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    lessons: list[Lesson] = Field(min_length=1)


class CourseTemplate(BaseModel):
    course_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    level_band: LevelBand
    cefr_range: str = Field(min_length=2, max_length=20)
    chapters: list[Chapter] = Field(min_length=1)


class LessonPointer(BaseModel):
    course_id: str = Field(min_length=1, max_length=120)
    chapter_id: str = Field(min_length=1, max_length=120)
    lesson_id: str = Field(min_length=1, max_length=120)


class LessonVariant(BaseModel):
    variant_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    source_lesson: LessonPointer
    lesson: Lesson
    personalization_focus: list[str] = Field(default_factory=list)
    generated_from: str = Field(default="deterministic-template-agent", min_length=1, max_length=120)
    generated_at: datetime = Field(default_factory=utc_now)


class ExerciseFeedback(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=120)
    passed: bool = False
    should_advance: bool = False
    error_type: str = Field(default="clarity", min_length=1, max_length=120)
    original_text: str = Field(default="", max_length=2000)
    corrected_text: str | None = Field(default=None, max_length=2000)
    feedback_text: str = Field(min_length=1, max_length=3000)
    retry_prompt: str | None = Field(default=None, max_length=2000)
    focus: list[str] = Field(default_factory=list)
    attempt_number: int = Field(default=1, ge=1, le=10)


class ExerciseResult(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=120)
    exercise_type: ExerciseType
    attempts: int = Field(default=1, ge=1, le=10)
    completed: bool = False
    mastered: bool = False
    learner_response: str | None = Field(default=None, max_length=2000)
    feedback: ExerciseFeedback | None = None


class TutorTurn(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=4000)
    exercise_id: str | None = Field(default=None, max_length=120)
    created_at: datetime = Field(default_factory=utc_now)


class LessonResult(BaseModel):
    learner_id: str = Field(min_length=1, max_length=120)
    lesson: LessonPointer
    variant_id: str | None = Field(default=None, max_length=120)
    completed: bool = False
    grammar_accuracy: float | None = Field(default=None, ge=0, le=1)
    pronunciation_accuracy: float | None = Field(default=None, ge=0, le=1)
    weak_topics: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    summary_text: str | None = Field(default=None, max_length=3000)
    exercise_results: list[ExerciseResult] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    completed_at: datetime = Field(default_factory=utc_now)


class LessonCompletionRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=120)
    lesson: LessonPointer
    variant_id: str | None = Field(default=None, max_length=120)
    completed: bool = True
    grammar_accuracy: float | None = Field(default=None, ge=0, le=1)
    pronunciation_accuracy: float | None = Field(default=None, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    summary_text: str | None = Field(default=None, max_length=3000)
    exercise_results: list[ExerciseResult] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)


class TutorSessionSnapshot(BaseModel):
    session_id: str
    learner_id: str
    course_id: str
    chapter_id: str
    lesson_id: str
    lesson_title: str
    variant_id: str | None = None
    status: str
    current_exercise_id: str | None = None
    current_exercise_type: ExerciseType | None = None
    current_prompt: str | None = None
    current_attempt: int = 0
    current_max_attempts: int = 0
    pending_retry: bool = False
    completed_exercises: list[str] = Field(default_factory=list)
    completed_exercise_count: int = 0
    turn_count: int = 0
    personalization_focus: list[str] = Field(default_factory=list)
    lesson_summary: str | None = None


class NextLessonSelection(BaseModel):
    course_id: str
    chapter_id: str
    lesson_id: str
    reason: str
    review_mode: bool = False
