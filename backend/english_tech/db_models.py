from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from english_tech.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearnerRecord(Base):
    __tablename__ = "learners"

    learner_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Learner")
    level_band: Mapped[str] = mapped_column(String(32), default="beginner")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    native_language: Mapped[str] = mapped_column(String(80), default="unknown")
    goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    weak_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=10)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    last_active_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_scenario: Mapped[str] = mapped_column(String(120), default="General conversation")
    memory_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuthUserRecord(Base):
    __tablename__ = "auth_users"

    user_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(120), ForeignKey("learners.learner_id"), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    auth_provider: Mapped[str] = mapped_column(String(32), default="local")
    google_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_salt: Mapped[str] = mapped_column(String(255))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_reset_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), ForeignKey("auth_users.user_id"), index=True)
    learner_id: Mapped[str] = mapped_column(String(120), ForeignKey("learners.learner_id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class LessonResultRecord(Base):
    __tablename__ = "lesson_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(120), ForeignKey("learners.learner_id"), index=True)
    course_id: Mapped[str] = mapped_column(String(120), index=True)
    chapter_id: Mapped[str] = mapped_column(String(120), index=True)
    lesson_id: Mapped[str] = mapped_column(String(120), index=True)
    variant_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    grammar_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    pronunciation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    weak_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    exercise_results: Mapped[list[dict]] = mapped_column(JSON, default=list)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ReviewItemRecord(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    learner_id: Mapped[str] = mapped_column(String(120), ForeignKey("learners.learner_id"), index=True)
    course_id: Mapped[str] = mapped_column(String(120), index=True)
    chapter_id: Mapped[str] = mapped_column(String(120), index=True)
    lesson_id: Mapped[str] = mapped_column(String(120), index=True)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    due_on: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
