from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from english_tech.curriculum.models import LessonPointer, LessonResult
from english_tech.db import ensure_database_connection, session_scope
from english_tech.db_models import LearnerRecord, LessonResultRecord, ReviewItemRecord
from english_tech.learners.models import (
    LearnerProfile,
    LessonHistoryEntry,
    ReviewItem,
    ReviewStatus,
)


class LearnerStore:
    def __init__(self):
        ensure_database_connection()

    def get_or_create_profile(self, learner_id: str) -> LearnerProfile:
        with session_scope() as session:
            learner = session.get(LearnerRecord, learner_id)
            if learner is None:
                learner = LearnerRecord(learner_id=learner_id)
                session.add(learner)
                session.flush()
            return self._build_profile(session, learner)

    def save_profile(self, profile: LearnerProfile) -> None:
        with session_scope() as session:
            learner = session.get(LearnerRecord, profile.learner_id)
            if learner is None:
                learner = LearnerRecord(learner_id=profile.learner_id)
                session.add(learner)
            learner.display_name = profile.display_name
            learner.level_band = profile.level_band.value
            learner.onboarding_completed = profile.onboarding_completed
            learner.native_language = profile.native_language
            learner.goals = list(profile.goals)
            learner.weak_topics = list(profile.weak_topics)
            learner.daily_goal_minutes = profile.daily_goal_minutes
            learner.streak_days = profile.streak_days
            learner.total_turns = profile.total_turns
            learner.last_active_on = profile.last_active_on
            learner.preferred_scenario = profile.preferred_scenario
            learner.memory_notes = list(profile.memory_notes)

    def add_completed_lesson(self, learner_id: str, lesson_id: str) -> LearnerProfile:
        del lesson_id
        return self.get_or_create_profile(learner_id)

    def merge_weak_topics(self, learner_id: str, weak_topics: list[str]) -> LearnerProfile:
        with session_scope() as session:
            learner = self._get_or_create_record(session, learner_id)
            learner.weak_topics = self._merge_topics(list(learner.weak_topics or []), weak_topics)
            return self._build_profile(session, learner)

    def record_session_turns(self, learner_id: str, turns: int, *, on_date: date | None = None) -> LearnerProfile:
        with session_scope() as session:
            learner = self._get_or_create_record(session, learner_id)
            self._touch_activity(learner, on_date=on_date)
            learner.total_turns += max(turns, 0)
            return self._build_profile(session, learner)

    def due_reviews(self, learner_id: str, *, on_date: date | None = None) -> list[ReviewItem]:
        today = on_date or date.today()
        with session_scope() as session:
            rows = session.scalars(
                select(ReviewItemRecord)
                .where(ReviewItemRecord.learner_id == learner_id)
                .where(ReviewItemRecord.status == ReviewStatus.pending.value)
                .where(ReviewItemRecord.due_on <= today)
                .order_by(ReviewItemRecord.due_on, ReviewItemRecord.topic, ReviewItemRecord.lesson_id)
            ).all()
            return [self._review_to_model(row) for row in rows]

    def apply_lesson_result(
        self,
        learner_id: str,
        result: LessonResult,
        *,
        review_items: list[ReviewItem] | None = None,
    ) -> LearnerProfile:
        with session_scope() as session:
            learner = self._get_or_create_record(session, learner_id)
            self._touch_activity(learner, on_date=result.completed_at.date())
            learner.total_turns += result.turn_count
            learner.weak_topics = self._merge_topics(list(learner.weak_topics or []), result.weak_topics)
            self._complete_due_reviews_for_lesson(session, learner_id, result.lesson.lesson_id, on_date=result.completed_at.date())
            if review_items:
                self._merge_review_items(session, learner_id, review_items)
            return self._build_profile(session, learner)

    def _get_or_create_record(self, session, learner_id: str) -> LearnerRecord:
        learner = session.get(LearnerRecord, learner_id)
        if learner is None:
            learner = LearnerRecord(learner_id=learner_id)
            session.add(learner)
            session.flush()
        return learner

    def _build_profile(self, session, learner: LearnerRecord) -> LearnerProfile:
        result_rows = session.scalars(
            select(LessonResultRecord)
            .where(LessonResultRecord.learner_id == learner.learner_id)
            .order_by(LessonResultRecord.completed_at)
        ).all()
        review_rows = session.scalars(
            select(ReviewItemRecord)
            .where(ReviewItemRecord.learner_id == learner.learner_id)
            .order_by(ReviewItemRecord.due_on, ReviewItemRecord.topic)
        ).all()

        completed_lessons: list[str] = []
        lesson_history: list[LessonHistoryEntry] = []
        for row in result_rows:
            if row.completed and row.lesson_id not in completed_lessons:
                completed_lessons.append(row.lesson_id)
            review_due_on = self._review_due_on_for_lesson(review_rows, row.lesson_id)
            lesson_history.append(
                LessonHistoryEntry(
                    lesson=LessonPointer(
                        course_id=row.course_id,
                        chapter_id=row.chapter_id,
                        lesson_id=row.lesson_id,
                    ),
                    variant_id=row.variant_id,
                    completed_at=row.completed_at,
                    grammar_accuracy=row.grammar_accuracy,
                    pronunciation_accuracy=row.pronunciation_accuracy,
                    weak_topics=list(row.weak_topics or []),
                    summary_text=row.summary_text,
                    review_due_on=review_due_on,
                    turn_count=row.turn_count,
                )
            )

        return LearnerProfile(
            learner_id=learner.learner_id,
            display_name=learner.display_name,
            level_band=learner.level_band,
            onboarding_completed=learner.onboarding_completed,
            native_language=learner.native_language,
            goals=list(learner.goals or []),
            weak_topics=list(learner.weak_topics or []),
            completed_lessons=completed_lessons,
            daily_goal_minutes=learner.daily_goal_minutes,
            streak_days=learner.streak_days,
            total_turns=learner.total_turns,
            last_active_on=learner.last_active_on,
            preferred_scenario=learner.preferred_scenario,
            memory_notes=list(learner.memory_notes or []),
            lesson_history=lesson_history,
            review_queue=[self._review_to_model(row) for row in review_rows],
        )

    def _review_due_on_for_lesson(self, rows: list[ReviewItemRecord], lesson_id: str):
        matching = [row.due_on for row in rows if row.lesson_id == lesson_id]
        return min(matching) if matching else None

    def _review_to_model(self, row: ReviewItemRecord) -> ReviewItem:
        return ReviewItem(
            review_id=row.review_id,
            lesson=LessonPointer(
                course_id=row.course_id,
                chapter_id=row.chapter_id,
                lesson_id=row.lesson_id,
            ),
            topic=row.topic,
            due_on=row.due_on,
            reason=row.reason,
            status=ReviewStatus(row.status),
            created_at=row.created_at,
        )

    def _touch_activity(self, learner: LearnerRecord, *, on_date: date | None = None) -> None:
        today = on_date or date.today()
        if learner.last_active_on is None:
            learner.streak_days = 1
        elif learner.last_active_on == today:
            return
        elif learner.last_active_on == today - timedelta(days=1):
            learner.streak_days += 1
        else:
            learner.streak_days = 1
        learner.last_active_on = today

    def _complete_due_reviews_for_lesson(self, session, learner_id: str, lesson_id: str, *, on_date: date) -> None:
        rows = session.scalars(
            select(ReviewItemRecord)
            .where(ReviewItemRecord.learner_id == learner_id)
            .where(ReviewItemRecord.lesson_id == lesson_id)
            .where(ReviewItemRecord.status == ReviewStatus.pending.value)
        ).all()
        for row in rows:
            if row.due_on <= on_date:
                row.status = ReviewStatus.completed.value

    def _merge_review_items(self, session, learner_id: str, review_items: list[ReviewItem]) -> None:
        for item in review_items:
            row = session.scalar(select(ReviewItemRecord).where(ReviewItemRecord.review_id == item.review_id))
            if row is None:
                session.add(
                    ReviewItemRecord(
                        review_id=item.review_id,
                        learner_id=learner_id,
                        course_id=item.lesson.course_id,
                        chapter_id=item.lesson.chapter_id,
                        lesson_id=item.lesson.lesson_id,
                        topic=item.topic,
                        due_on=item.due_on,
                        reason=item.reason,
                        status=item.status.value,
                        created_at=item.created_at,
                    )
                )
                continue
            if item.due_on < row.due_on:
                row.due_on = item.due_on
                row.reason = item.reason
                row.status = item.status.value

    def _merge_topics(self, existing: list[str], incoming: list[str]) -> list[str]:
        return list(dict.fromkeys([*existing, *[item for item in incoming if item]]))
