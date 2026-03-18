from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel, Field

from english_tech.curriculum.models import (
    Exercise,
    ExerciseType,
    Lesson,
    LessonPointer,
    LessonVariant,
    NextLessonSelection,
)
from english_tech.curriculum.store import CurriculumStore
from english_tech.learners.models import LearnerProfile, ReviewItem, ReviewStatus


class NextLessonRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=120)
    course_id: str = Field(min_length=1, max_length=120)
    completed_lessons: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    review_queue: list[ReviewItem] = Field(default_factory=list)
    learner_goals: list[str] = Field(default_factory=list)


class CurriculumAgent:
    """Deterministic curriculum agent with cached lesson variants.

    The course structure stays static. Personalization happens by preparing a
    learner-specific lesson variant inside the template boundaries.
    """

    def __init__(self, store: CurriculumStore):
        self.store = store

    def next_lesson(self, request: NextLessonRequest) -> Lesson | None:
        selection = self.select_next_lesson(request)
        if selection is None:
            return None
        return self.store.get_lesson(
            course_id=selection.course_id,
            chapter_id=selection.chapter_id,
            lesson_id=selection.lesson_id,
        )

    def select_next_lesson(self, request: NextLessonRequest) -> NextLessonSelection | None:
        course = self.store.get_course(request.course_id)
        if course is None:
            return None

        today = date.today()
        for review in sorted(request.review_queue, key=lambda item: (item.due_on, item.lesson.lesson_id, item.topic)):
            if review.status != ReviewStatus.pending:
                continue
            if review.lesson.course_id != request.course_id:
                continue
            if review.due_on > today:
                continue
            return self.describe_selection(
                course_id=review.lesson.course_id,
                chapter_id=review.lesson.chapter_id,
                lesson_id=review.lesson.lesson_id,
                reason=f"Scheduled review due for {review.topic}.",
                review_mode=True,
            )

        weak_topics = {item.lower() for item in request.weak_topics}
        learner_goals = {goal.lower() for goal in request.learner_goals}
        completed = set(request.completed_lessons)

        for chapter in course.chapters:
            for lesson in chapter.lessons:
                if lesson.lesson_id in completed:
                    continue
                lesson_topics = {
                    *map(str.lower, lesson.target_grammar),
                    *map(str.lower, lesson.pronunciation_focus),
                    *map(str.lower, lesson.target_vocabulary),
                }
                if weak_topics and weak_topics.intersection(lesson_topics):
                    return self.describe_selection(
                        course_id=course.course_id,
                        chapter_id=chapter.chapter_id,
                        lesson_id=lesson.lesson_id,
                        reason="Selected because it reinforces a stored weak topic.",
                    )
                if learner_goals and any(goal in lesson.goal.lower() or goal in lesson.title.lower() for goal in learner_goals):
                    return self.describe_selection(
                        course_id=course.course_id,
                        chapter_id=chapter.chapter_id,
                        lesson_id=lesson.lesson_id,
                        reason="Selected because it aligns with the learner goals.",
                    )

        for chapter in course.chapters:
            for lesson in chapter.lessons:
                if lesson.lesson_id not in completed:
                    return self.describe_selection(
                        course_id=course.course_id,
                        chapter_id=chapter.chapter_id,
                        lesson_id=lesson.lesson_id,
                        reason="Selected by deterministic curriculum order.",
                    )
        return None

    def describe_selection(
        self,
        course_id: str,
        chapter_id: str,
        lesson_id: str,
        *,
        reason: str,
        review_mode: bool = False,
    ) -> NextLessonSelection:
        return NextLessonSelection(
            course_id=course_id,
            chapter_id=chapter_id,
            lesson_id=lesson_id,
            reason=reason,
            review_mode=review_mode,
        )

    def prepare_lesson(
        self,
        learner: LearnerProfile,
        *,
        course_id: str,
        chapter_id: str,
        lesson_id: str,
    ) -> LessonVariant:
        lesson = self.store.get_lesson(course_id=course_id, chapter_id=chapter_id, lesson_id=lesson_id)
        chapter = self.store.get_chapter(course_id=course_id, chapter_id=chapter_id)
        if lesson is None or chapter is None:
            raise ValueError(f"Unknown lesson: {course_id}/{chapter_id}/{lesson_id}")

        personalization_focus = self._collect_personalization_focus(learner, lesson)
        variant_id = self._variant_id(
            learner_id=learner.learner_id,
            pointer=LessonPointer(course_id=course_id, chapter_id=chapter_id, lesson_id=lesson_id),
            focus=personalization_focus,
            goals=learner.goals,
        )
        cached = self.store.get_variant(learner.learner_id, variant_id)
        if cached is not None:
            return cached

        personalized_lesson = self._build_variant_lesson(
            lesson=lesson,
            chapter_title=chapter.title,
            learner=learner,
            personalization_focus=personalization_focus,
        )
        variant = LessonVariant(
            variant_id=variant_id,
            learner_id=learner.learner_id,
            source_lesson=LessonPointer(course_id=course_id, chapter_id=chapter_id, lesson_id=lesson_id),
            lesson=personalized_lesson,
            personalization_focus=personalization_focus,
        )
        self.store.save_variant(variant)
        return variant

    def _build_variant_lesson(
        self,
        *,
        lesson: Lesson,
        chapter_title: str,
        learner: LearnerProfile,
        personalization_focus: list[str],
    ) -> Lesson:
        intro_style = {
            "beginner": "Use short, clear answers.",
            "advanced": "Use complete explanations with detail.",
            "proficiency": "Aim for natural, precise English.",
        }[learner.level_band.value]
        exercises = [
            self._personalize_exercise(
                exercise=exercise,
                lesson=lesson,
                learner=learner,
                personalization_focus=personalization_focus,
            )
            for exercise in lesson.exercises
        ]

        if personalization_focus and not any(ex.exercise_type == ExerciseType.recap for ex in exercises):
            exercises.append(
                Exercise(
                    exercise_id=f"{lesson.lesson_id}_personal_recap",
                    exercise_type=ExerciseType.recap,
                    prompt=(
                        f"Ask {learner.display_name} to summarize the lesson from {chapter_title} in one short answer. "
                        f"Reinforce: {', '.join(personalization_focus)}."
                    ),
                    sample_answer=f"Today I practiced {lesson.title.lower()} and focused on {', '.join(personalization_focus)}.",
                    correction_focus=personalization_focus,
                    min_response_words=6,
                    max_attempts=2,
                )
            )

        success_criteria = list(dict.fromkeys([*lesson.success_criteria, intro_style]))
        if personalization_focus:
            success_criteria.append(f"Personal focus: {', '.join(personalization_focus)}")

        goal_suffix = f" Personal focus: {', '.join(personalization_focus)}." if personalization_focus else ""
        return lesson.model_copy(
            update={
                "goal": f"{lesson.goal} {intro_style}{goal_suffix}".strip(),
                "exercises": exercises,
                "success_criteria": success_criteria,
            }
        )

    def _personalize_exercise(
        self,
        *,
        exercise: Exercise,
        lesson: Lesson,
        learner: LearnerProfile,
        personalization_focus: list[str],
    ) -> Exercise:
        focus = list(dict.fromkeys([*exercise.correction_focus, *personalization_focus]))
        response_targets = {
            ExerciseType.teach: 3,
            ExerciseType.repeat: 5,
            ExerciseType.roleplay: 8,
            ExerciseType.grammar: 5,
            ExerciseType.pronunciation: 3,
            ExerciseType.conversation: 10,
            ExerciseType.recap: 6,
        }
        max_attempt_targets = {
            ExerciseType.teach: 1,
            ExerciseType.repeat: 3,
            ExerciseType.roleplay: 2,
            ExerciseType.grammar: 2,
            ExerciseType.pronunciation: 3,
            ExerciseType.conversation: 2,
            ExerciseType.recap: 2,
        }
        prompt_fragments = [exercise.prompt]
        if lesson.target_vocabulary:
            prompt_fragments.append(f"Use target vocabulary when possible: {', '.join(lesson.target_vocabulary[:3])}.")
        if personalization_focus:
            prompt_fragments.append(f"Pay extra attention to: {', '.join(personalization_focus)}.")
        if learner.goals:
            prompt_fragments.append(f"Keep the response aligned with the learner goals: {', '.join(learner.goals[:2])}.")

        sample_answer = exercise.sample_answer or self._sample_answer(exercise, learner)
        return exercise.model_copy(
            update={
                "prompt": " ".join(prompt_fragments),
                "sample_answer": sample_answer,
                "correction_focus": focus,
                "min_response_words": max(exercise.min_response_words, response_targets[exercise.exercise_type]),
                "max_attempts": max(exercise.max_attempts, max_attempt_targets[exercise.exercise_type]),
            }
        )

    def _collect_personalization_focus(self, learner: LearnerProfile, lesson: Lesson) -> list[str]:
        ordered = [*learner.weak_topics, *lesson.target_grammar, *lesson.pronunciation_focus]
        return list(dict.fromkeys([item for item in ordered if item]))[:4]

    def _sample_answer(self, exercise: Exercise, learner: LearnerProfile) -> str | None:
        if exercise.expected_answer is None:
            return None
        sample = exercise.expected_answer
        if "____" not in sample:
            return sample

        replacements = [learner.display_name, "your country", "your city"]
        for value in replacements:
            if "____" not in sample:
                break
            sample = sample.replace("____", value, 1)
        return sample.replace("____", "your answer")

    def _variant_id(
        self,
        *,
        learner_id: str,
        pointer: LessonPointer,
        focus: list[str],
        goals: list[str],
    ) -> str:
        digest = hashlib.sha1(
            "|".join(
                [
                    learner_id,
                    pointer.course_id,
                    pointer.chapter_id,
                    pointer.lesson_id,
                    ",".join(focus),
                    ",".join(goals),
                ]
            ).encode("utf-8")
        ).hexdigest()[:10]
        return f"{pointer.lesson_id}_{digest}"
