from __future__ import annotations

from english_tech.coaching.models import CoachClassification
from english_tech.curriculum.models import LevelBand, LessonResult
from english_tech.learners.models import LearnerProfile


def level_label(level_band: LevelBand | str) -> str:
    value = level_band.value if isinstance(level_band, LevelBand) else str(level_band)
    return {
        "beginner": "beginner",
        "advanced": "advanced",
        "proficiency": "fluent",
    }.get(value, value)


def classify_learner(profile: LearnerProfile, results: list[LessonResult]) -> CoachClassification:
    latest = results[-1] if results else None
    weak_areas = list(dict.fromkeys([*profile.weak_topics, *([] if latest is None else latest.weak_topics)]))[:3]

    strengths: list[str] = []
    if len(profile.completed_lessons) >= 3:
        strengths.append("lesson consistency")
    if latest and latest.completed:
        strengths.append("lesson completion")
    if latest and (latest.grammar_accuracy or 0) >= 0.85:
        strengths.append("grammar control")
    if latest and (latest.pronunciation_accuracy or 0) >= 0.85:
        strengths.append("pronunciation accuracy")
    if not strengths:
        strengths.append("willingness to practice")

    improvement_focus = weak_areas[:]
    if latest and latest.grammar_accuracy is not None and latest.grammar_accuracy < 0.7:
        improvement_focus.append("grammar accuracy")
    if latest and latest.pronunciation_accuracy is not None and latest.pronunciation_accuracy < 0.7:
        improvement_focus.append("pronunciation clarity")
    if not improvement_focus:
        improvement_focus.append("longer spoken answers")
    improvement_focus = list(dict.fromkeys(improvement_focus))[:3]

    if latest is None:
        pass_status = "not_assessed"
    elif latest.completed and not latest.weak_topics and (latest.grammar_accuracy or 0) >= 0.85 and (latest.pronunciation_accuracy or 0) >= 0.85:
        pass_status = "passed_clean"
    elif latest.completed:
        pass_status = "passed_with_review"
    else:
        pass_status = "needs_retry"

    if len(profile.completed_lessons) == 0:
        standing = "starting_out"
    elif pass_status == "passed_clean" and len(weak_areas) <= 1:
        standing = "ready_to_advance"
    elif len(weak_areas) >= 3:
        standing = "needs_targeted_review"
    else:
        standing = "on_track"

    return CoachClassification(
        level_band=profile.level_band.value,
        level_label=level_label(profile.level_band),
        standing=standing,
        pass_status=pass_status,
        strengths=strengths,
        weak_areas=weak_areas,
        improvement_focus=improvement_focus,
    )
