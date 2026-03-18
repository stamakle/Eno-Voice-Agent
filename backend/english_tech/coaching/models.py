from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from english_tech.curriculum.models import NextLessonSelection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CoachClassification(BaseModel):
    level_band: str = Field(min_length=1, max_length=64)
    level_label: str = Field(min_length=1, max_length=64)
    standing: str = Field(min_length=1, max_length=64)
    pass_status: str = Field(min_length=1, max_length=64)
    strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    improvement_focus: list[str] = Field(default_factory=list)


class CoachBootstrap(BaseModel):
    learner_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    level_band: str = Field(min_length=1, max_length=64)
    level_label: str = Field(min_length=1, max_length=64)
    needs_onboarding: bool = False
    has_resume_lesson: bool = False
    total_completed_lessons: int = Field(default=0, ge=0)
    review_count_due: int = Field(default=0, ge=0)
    weak_topics: list[str] = Field(default_factory=list)
    recommended_next_lesson: NextLessonSelection | None = None
    recommended_lesson_title: str | None = Field(default=None, max_length=200)
    spoken_greeting: str = Field(min_length=1, max_length=2000)
    spoken_progress_summary: str = Field(min_length=1, max_length=2000)
    spoken_next_step: str = Field(min_length=1, max_length=2000)
    spoken_resume_offer: str | None = Field(default=None, max_length=2000)
    classification: CoachClassification
    preferred_scenario: str = Field(default="General conversation", max_length=120)
    memory_notes: list[str] = Field(default_factory=list)


class CoachTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class CoachConversationTurn(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=4000)
    created_at: datetime = Field(default_factory=utc_now)


class CoachSessionSnapshot(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    turn_count: int = Field(default=0, ge=0)
    connected_at: datetime = Field(default_factory=utc_now)
    last_action: str = Field(default="none", min_length=1, max_length=64)


class SemanticCoachDecision(BaseModel):
    reply: str = Field(min_length=1, max_length=4000)
    intent: str = Field(min_length=1, max_length=64)
    selected_level: str | None = Field(default=None, max_length=64)
    extracted_memory: list[str] = Field(default_factory=list)


class CoachTurnResponse(BaseModel):
    handled: bool = True
    spoken_reply: str = Field(min_length=1, max_length=4000)
    action: str = Field(default="none", min_length=1, max_length=64)
    lesson_to_open: NextLessonSelection | None = None
    bootstrap: CoachBootstrap
