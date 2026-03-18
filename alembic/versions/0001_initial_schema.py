"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-08 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learners",
        sa.Column("learner_id", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("level_band", sa.String(length=32), nullable=False),
        sa.Column("native_language", sa.String(length=80), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("weak_topics", sa.JSON(), nullable=False),
        sa.Column("daily_goal_minutes", sa.Integer(), nullable=False),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("total_turns", sa.Integer(), nullable=False),
        sa.Column("last_active_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("learner_id"),
    )
    op.create_table(
        "lesson_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.String(length=120), nullable=False),
        sa.Column("course_id", sa.String(length=120), nullable=False),
        sa.Column("chapter_id", sa.String(length=120), nullable=False),
        sa.Column("lesson_id", sa.String(length=120), nullable=False),
        sa.Column("variant_id", sa.String(length=120), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("grammar_accuracy", sa.Float(), nullable=True),
        sa.Column("pronunciation_accuracy", sa.Float(), nullable=True),
        sa.Column("weak_topics", sa.JSON(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("exercise_results", sa.JSON(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.learner_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lesson_results_chapter_id"), "lesson_results", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_lesson_results_completed_at"), "lesson_results", ["completed_at"], unique=False)
    op.create_index(op.f("ix_lesson_results_course_id"), "lesson_results", ["course_id"], unique=False)
    op.create_index(op.f("ix_lesson_results_learner_id"), "lesson_results", ["learner_id"], unique=False)
    op.create_index(op.f("ix_lesson_results_lesson_id"), "lesson_results", ["lesson_id"], unique=False)
    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=120), nullable=False),
        sa.Column("learner_id", sa.String(length=120), nullable=False),
        sa.Column("course_id", sa.String(length=120), nullable=False),
        sa.Column("chapter_id", sa.String(length=120), nullable=False),
        sa.Column("lesson_id", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.learner_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_items_chapter_id"), "review_items", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_review_items_course_id"), "review_items", ["course_id"], unique=False)
    op.create_index(op.f("ix_review_items_due_on"), "review_items", ["due_on"], unique=False)
    op.create_index(op.f("ix_review_items_learner_id"), "review_items", ["learner_id"], unique=False)
    op.create_index(op.f("ix_review_items_lesson_id"), "review_items", ["lesson_id"], unique=False)
    op.create_index(op.f("ix_review_items_review_id"), "review_items", ["review_id"], unique=True)
    op.create_index(op.f("ix_review_items_status"), "review_items", ["status"], unique=False)
    op.create_index(op.f("ix_review_items_topic"), "review_items", ["topic"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_items_topic"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_status"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_review_id"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_lesson_id"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_learner_id"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_due_on"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_course_id"), table_name="review_items")
    op.drop_index(op.f("ix_review_items_chapter_id"), table_name="review_items")
    op.drop_table("review_items")
    op.drop_index(op.f("ix_lesson_results_lesson_id"), table_name="lesson_results")
    op.drop_index(op.f("ix_lesson_results_learner_id"), table_name="lesson_results")
    op.drop_index(op.f("ix_lesson_results_course_id"), table_name="lesson_results")
    op.drop_index(op.f("ix_lesson_results_completed_at"), table_name="lesson_results")
    op.drop_index(op.f("ix_lesson_results_chapter_id"), table_name="lesson_results")
    op.drop_table("lesson_results")
    op.drop_table("learners")
