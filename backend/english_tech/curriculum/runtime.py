from __future__ import annotations

import re
from datetime import timedelta
from difflib import SequenceMatcher

from english_tech.curriculum.models import Exercise, ExerciseFeedback, ExerciseResult, Lesson, LessonPointer
from english_tech.learners.models import LearnerProfile, ReviewItem


_WORD_RE = re.compile(r"[a-zA-Z']+")


def build_lesson_system_prompt(lesson: Lesson, learner: LearnerProfile, personalization_focus: list[str] | None = None) -> str:
    vocab = ", ".join(lesson.target_vocabulary) or "none"
    grammar = ", ".join(lesson.target_grammar) or "none"
    pronunciation = ", ".join(lesson.pronunciation_focus) or "none"
    success = "; ".join(lesson.success_criteria) or "complete the exercises"
    goals = ", ".join(learner.goals) or "general spoken English"
    focus = ", ".join(personalization_focus or []) or "none"
    return (
        "You are Ama, an English coach running a structured lesson. "
        f"Learner level: {learner.level_band.value}. "
        f"Learner goals: {goals}. "
        f"Lesson title: {lesson.title}. Goal: {lesson.goal}. "
        f"Target vocabulary: {vocab}. Target grammar: {grammar}. "
        f"Pronunciation focus: {pronunciation}. Personal focus: {focus}. "
        f"Success criteria: {success}. "
        "Teach briefly, ask the learner to respond, correct clearly, request a retry when needed, and finish with a recap."
    )


def build_lesson_intro(lesson: Lesson, learner: LearnerProfile) -> str:
    return (
        f"Welcome {learner.display_name}. Today we are working on {lesson.title}. "
        f"Goal: {lesson.goal} "
        "I will guide you through each exercise, give corrections, and recap the lesson at the end."
    )


def build_retry_prompt(exercise: Exercise, feedback: ExerciseFeedback) -> str:
    sample = feedback.corrected_text or exercise.sample_answer or exercise.expected_answer
    sample_text = f" Model answer: {sample}." if sample else ""
    return f"Try the same exercise again and focus on {', '.join(feedback.focus)}.{sample_text}"


def evaluate_exercise_response(
    lesson: Lesson,
    exercise: Exercise,
    learner_text: str,
    *,
    attempt_number: int,
) -> ExerciseFeedback:
    del lesson

    clean_text = " ".join(learner_text.split())
    focus = exercise.correction_focus or ["clarity"]
    normalized = _normalize(clean_text)
    min_words = max(exercise.min_response_words, 1)
    word_count = len(_WORD_RE.findall(clean_text))
    corrected_text = exercise.sample_answer or exercise.expected_answer

    if not clean_text:
        return _failed_feedback(
            exercise=exercise,
            focus=focus,
            attempt_number=attempt_number,
            error_type="missing_response",
            original_text=clean_text,
            corrected_text=corrected_text,
            feedback_text="I did not receive a spoken answer. Give one short spoken response.",
        )

    if word_count < min_words:
        return _failed_feedback(
            exercise=exercise,
            focus=focus,
            attempt_number=attempt_number,
            error_type="short_response",
            original_text=clean_text,
            corrected_text=corrected_text,
            feedback_text=f"Your answer is too short for this exercise. Aim for at least {min_words} words.",
        )

    if exercise.expected_answer and "____" not in exercise.expected_answer:
        similarity = SequenceMatcher(None, normalized, _normalize(exercise.expected_answer)).ratio()
        if similarity < 0.68:
            return _failed_feedback(
                exercise=exercise,
                focus=focus,
                attempt_number=attempt_number,
                error_type="model_answer_mismatch",
                original_text=clean_text,
                corrected_text=corrected_text,
                feedback_text="Your answer is understandable, but it does not match the target model closely enough.",
            )

    if exercise.expected_answer and "____" in exercise.expected_answer:
        anchors = _template_keywords(exercise.expected_answer)
        matched = sum(1 for token in anchors if token in normalized)
        required_matches = min(len(anchors), max(2, len(anchors) // 2)) if anchors else 0
        if anchors and matched < required_matches:
            return _failed_feedback(
                exercise=exercise,
                focus=focus,
                attempt_number=attempt_number,
                error_type="pattern_missing",
                original_text=clean_text,
                corrected_text=corrected_text,
                feedback_text="Your answer needs to follow the target sentence pattern more closely.",
            )

    feedback_text = f"Good work. Keep using {', '.join(focus)} in the next answer."
    return ExerciseFeedback(
        exercise_id=exercise.exercise_id,
        passed=True,
        should_advance=True,
        error_type="success",
        original_text=clean_text,
        corrected_text=None,
        feedback_text=feedback_text,
        retry_prompt=None,
        focus=focus,
        attempt_number=attempt_number,
    )


def derive_weak_topics(lesson: Lesson, exercise_results: list[ExerciseResult]) -> list[str]:
    weak_topics: list[str] = []
    for result in exercise_results:
        if result.mastered and result.attempts <= 1:
            continue
        if result.feedback is not None:
            weak_topics.extend(result.feedback.focus)
    if not weak_topics:
        weak_topics.extend(lesson.target_grammar[:1])
    return list(dict.fromkeys(weak_topics))[:5]


def build_lesson_summary(lesson: Lesson, exercise_results: list[ExerciseResult]) -> str:
    total = len(lesson.exercises)
    mastered = sum(1 for result in exercise_results if result.mastered)
    retried = sum(1 for result in exercise_results if result.attempts > 1)
    weak_topics = derive_weak_topics(lesson, exercise_results)
    summary = f"Lesson complete: {mastered} of {total} exercises were completed successfully."
    if retried:
        summary += f" {retried} exercise(s) needed an extra attempt."
    if weak_topics:
        summary += f" Keep reviewing: {', '.join(weak_topics)}."
    if lesson.success_criteria:
        summary += f" Success target: {lesson.success_criteria[0]}"
    return summary


def build_review_items(
    *,
    lesson_pointer: LessonPointer,
    lesson: Lesson,
    result: ExerciseResult | None = None,
    weak_topics: list[str],
    completed_at,
) -> list[ReviewItem]:
    del result

    due_on = completed_at.date() + timedelta(days=lesson.review_rule.review_after_days)
    topics = weak_topics or lesson.target_grammar or lesson.pronunciation_focus or lesson.target_vocabulary[:1]
    review_items: list[ReviewItem] = []
    for topic in list(dict.fromkeys(topics))[:3]:
        review_items.append(
            ReviewItem(
                review_id=f"{lesson_pointer.lesson_id}_{topic.lower().replace(' ', '_')}_{due_on.isoformat()}",
                lesson=lesson_pointer,
                topic=topic,
                due_on=due_on,
                reason=lesson.review_rule.trigger,
            )
        )
    return review_items


def _failed_feedback(
    *,
    exercise: Exercise,
    focus: list[str],
    attempt_number: int,
    error_type: str,
    original_text: str,
    corrected_text: str | None,
    feedback_text: str,
) -> ExerciseFeedback:
    should_advance = attempt_number >= exercise.max_attempts
    retry_prompt = None if should_advance else build_retry_prompt(
        exercise,
        ExerciseFeedback(
            exercise_id=exercise.exercise_id,
            passed=False,
            should_advance=False,
            error_type=error_type,
            original_text=original_text,
            corrected_text=corrected_text,
            feedback_text=feedback_text,
            retry_prompt=None,
            focus=focus,
            attempt_number=attempt_number,
        ),
    )
    if should_advance:
        feedback_text = f"{feedback_text} We will move on, but keep focusing on {', '.join(focus)}."
    return ExerciseFeedback(
        exercise_id=exercise.exercise_id,
        passed=False,
        should_advance=should_advance,
        error_type=error_type,
        original_text=original_text,
        corrected_text=corrected_text,
        feedback_text=feedback_text,
        retry_prompt=retry_prompt,
        focus=focus,
        attempt_number=attempt_number,
    )


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def _template_keywords(text: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall(text.lower())
        if token != "____"
    }
