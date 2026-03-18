from __future__ import annotations

from english_tech.coaching.models import CoachBootstrap, CoachClassification


def _name_fragment(display_name: str) -> str:
    return "" if display_name == "Learner" else f", {display_name}"


def build_spoken_greeting(*, display_name: str, level_label: str, needs_onboarding: bool, has_resume_lesson: bool, recommended_title: str | None) -> str:
    if needs_onboarding:
        return (
            f"Hello{_name_fragment(display_name)}. I am Aura, your English coach. "
            "Tell me your level by saying beginner, advanced, or fluent."
        )
    if has_resume_lesson and recommended_title:
        return (
            f"Welcome back{_name_fragment(display_name)}. You are currently working at the {level_label} level. "
            f"I can continue your lesson, {recommended_title}, if you are ready."
        )
    return (
        f"Welcome back{_name_fragment(display_name)}. You are working at the {level_label} level. "
        "I am ready to guide your next lesson."
    )


def build_progress_summary(classification: CoachClassification, *, total_completed_lessons: int, review_count_due: int) -> str:
    weak_text = " and ".join(classification.weak_areas[:2]) if classification.weak_areas else "no major weak areas yet"
    return (
        f"You have completed {total_completed_lessons} lessons. "
        f"Right now you are {classification.standing.replace('_', ' ')}. "
        f"Your strongest area is {classification.strengths[0]}. "
        f"Your main gap is {weak_text}. "
        f"You have {review_count_due} reviews due."
    )


def build_next_step(*, bootstrap: CoachBootstrap) -> str:
    if bootstrap.needs_onboarding:
        return "Say beginner, advanced, or fluent, and I will place you in the right track."
    if bootstrap.has_resume_lesson and bootstrap.recommended_lesson_title:
        return f"Say continue if you want to resume {bootstrap.recommended_lesson_title}, or ask how you can improve first."
    if bootstrap.recommended_lesson_title:
        return f"Say start lesson when you want to begin {bootstrap.recommended_lesson_title}."
    return "Ask me how you are doing, or tell me to start your next lesson."


def build_resume_offer(recommended_title: str | None) -> str | None:
    if not recommended_title:
        return None
    return f"Do you want to continue {recommended_title}?"


def build_improvement_reply(classification: CoachClassification) -> str:
    focus = ", ".join(classification.improvement_focus[:3])
    return f"Your main improvement focus is {focus}. Keep your answers a little longer and more precise."
