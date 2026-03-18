from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from english_tech.curriculum.models import LessonPointer, LessonResult, LevelBand, NextLessonSelection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class ReviewItem(BaseModel):
    review_id: str = Field(min_length=1, max_length=120)
    lesson: LessonPointer
    topic: str = Field(min_length=1, max_length=120)
    due_on: date
    reason: str = Field(min_length=1, max_length=300)
    status: ReviewStatus = ReviewStatus.pending
    created_at: datetime = Field(default_factory=utc_now)


class LessonHistoryEntry(BaseModel):
    lesson: LessonPointer
    variant_id: str | None = Field(default=None, max_length=120)
    completed_at: datetime = Field(default_factory=utc_now)
    grammar_accuracy: float | None = Field(default=None, ge=0, le=1)
    pronunciation_accuracy: float | None = Field(default=None, ge=0, le=1)
    weak_topics: list[str] = Field(default_factory=list)
    summary_text: str | None = Field(default=None, max_length=3000)
    review_due_on: date | None = None
    turn_count: int = Field(default=0, ge=0)


class LearnerProfile(BaseModel):
    learner_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(default="Learner", min_length=1, max_length=120)
    level_band: LevelBand = LevelBand.beginner
    onboarding_completed: bool = False
    native_language: str = Field(default="unknown", min_length=2, max_length=80)
    goals: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    completed_lessons: list[str] = Field(default_factory=list)
    daily_goal_minutes: int = Field(default=10, ge=1, le=180)
    streak_days: int = Field(default=0, ge=0)
    total_turns: int = Field(default=0, ge=0)
    last_active_on: date | None = None
    lesson_history: list[LessonHistoryEntry] = Field(default_factory=list)
    review_queue: list[ReviewItem] = Field(default_factory=list)
    preferred_scenario: str = Field(default="General conversation", max_length=120)
    memory_notes: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    learner: LearnerProfile
    total_completed_lessons: int = 0
    weak_topics: list[str] = Field(default_factory=list)
    recent_results: list[LessonResult] = Field(default_factory=list)
    recent_history: list[LessonHistoryEntry] = Field(default_factory=list)
    review_queue: list[ReviewItem] = Field(default_factory=list)
    review_count_due: int = 0
    next_review_due_on: date | None = None
    recommended_next_lesson: NextLessonSelection | None = None
