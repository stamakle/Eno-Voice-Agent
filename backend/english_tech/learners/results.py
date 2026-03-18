from __future__ import annotations

from sqlalchemy import select

from english_tech.curriculum.models import ExerciseResult, LessonPointer, LessonResult
from english_tech.db import ensure_database_connection, session_scope
from english_tech.db_models import LearnerRecord, LessonResultRecord


class LessonResultStore:
    def __init__(self):
        ensure_database_connection()

    def list_results(self, learner_id: str) -> list[LessonResult]:
        with session_scope() as session:
            rows = session.scalars(
                select(LessonResultRecord)
                .where(LessonResultRecord.learner_id == learner_id)
                .order_by(LessonResultRecord.completed_at)
            ).all()
            return [self._to_model(row) for row in rows]

    def append_result(self, result: LessonResult) -> None:
        with session_scope() as session:
            learner = session.get(LearnerRecord, result.learner_id)
            if learner is None:
                learner = LearnerRecord(learner_id=result.learner_id)
                session.add(learner)
                session.flush()
            session.add(
                LessonResultRecord(
                    learner_id=result.learner_id,
                    course_id=result.lesson.course_id,
                    chapter_id=result.lesson.chapter_id,
                    lesson_id=result.lesson.lesson_id,
                    variant_id=result.variant_id,
                    completed=result.completed,
                    grammar_accuracy=result.grammar_accuracy,
                    pronunciation_accuracy=result.pronunciation_accuracy,
                    weak_topics=result.weak_topics,
                    notes=result.notes,
                    summary_text=result.summary_text,
                    exercise_results=[item.model_dump(mode="json") for item in result.exercise_results],
                    turn_count=result.turn_count,
                    completed_at=result.completed_at,
                )
            )

    def _to_model(self, row: LessonResultRecord) -> LessonResult:
        return LessonResult(
            learner_id=row.learner_id,
            lesson=LessonPointer(
                course_id=row.course_id,
                chapter_id=row.chapter_id,
                lesson_id=row.lesson_id,
            ),
            variant_id=row.variant_id,
            completed=row.completed,
            grammar_accuracy=row.grammar_accuracy,
            pronunciation_accuracy=row.pronunciation_accuracy,
            weak_topics=list(row.weak_topics or []),
            notes=list(row.notes or []),
            summary_text=row.summary_text,
            exercise_results=[ExerciseResult.model_validate(item) for item in (row.exercise_results or [])],
            turn_count=row.turn_count,
            completed_at=row.completed_at,
        )
