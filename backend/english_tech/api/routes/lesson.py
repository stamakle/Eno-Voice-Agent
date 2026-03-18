from fastapi import APIRouter, Depends, HTTPException

from english_tech.auth.deps import get_verified_user
from english_tech.curriculum.agent import CurriculumAgent
from english_tech.curriculum.models import LessonCompletionRequest, LessonResult
from english_tech.curriculum.runtime import build_lesson_summary, build_review_items, derive_weak_topics
from english_tech.curriculum.store import CurriculumStore
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore

router = APIRouter()
store = CurriculumStore()
agent = CurriculumAgent(store=store)
result_store = LessonResultStore()
learner_store = LearnerStore()


@router.get("/{course_id}/{chapter_id}/{lesson_id}")
def get_lesson(
    course_id: str,
    chapter_id: str,
    lesson_id: str,
    user=Depends(get_verified_user),
):
    lesson = store.get_lesson(course_id=course_id, chapter_id=chapter_id, lesson_id=lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    profile = learner_store.get_or_create_profile(user.learner_id)
    variant = agent.prepare_lesson(
        profile,
        course_id=course_id,
        chapter_id=chapter_id,
        lesson_id=lesson_id,
    )
    return variant.model_dump(mode="json")


@router.post("/complete")
def complete_lesson(request: LessonCompletionRequest, user=Depends(get_verified_user)):
    lesson = store.get_lesson(
        course_id=request.lesson.course_id,
        chapter_id=request.lesson.chapter_id,
        lesson_id=request.lesson.lesson_id,
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    learner_id = user.learner_id
    
    from datetime import datetime, timezone
    all_results = result_store.list_results(learner_id)
    recent_completion = next(
        (r for r in reversed(all_results) 
         if r.lesson.lesson_id == request.lesson.lesson_id 
         and r.completed 
         and (datetime.now(timezone.utc) - r.completed_at).total_seconds() < 10),
        None
    )
    
    if recent_completion:
        profile = learner_store.get_or_create_profile(learner_id)
        return {
            "status": "saved",
            "result": recent_completion.model_dump(mode="json"),
            "review_items": [],
            "learner": {
                "completed_lessons": profile.completed_lessons,
                "weak_topics": profile.weak_topics,
                "review_count_due": len(learner_store.due_reviews(learner_id)),
            },
        }

    weak_topics = request.weak_topics or derive_weak_topics(lesson, request.exercise_results)
    summary_text = request.summary_text or build_lesson_summary(lesson, request.exercise_results)
    result = LessonResult(
        learner_id=learner_id,
        lesson=request.lesson,
        variant_id=request.variant_id,
        completed=request.completed,
        grammar_accuracy=request.grammar_accuracy,
        pronunciation_accuracy=request.pronunciation_accuracy,
        weak_topics=weak_topics,
        notes=request.notes,
        summary_text=summary_text,
        exercise_results=request.exercise_results,
        turn_count=request.turn_count,
    )
    result_store.append_result(result)

    review_items = []
    if request.completed:
        review_items = build_review_items(
            lesson_pointer=request.lesson,
            lesson=lesson,
            weak_topics=weak_topics,
            completed_at=result.completed_at,
        )
    profile = learner_store.apply_lesson_result(learner_id, result, review_items=review_items)

    return {
        "status": "saved",
        "result": result.model_dump(mode="json"),
        "review_items": [item.model_dump(mode="json") for item in review_items],
        "learner": {
            "completed_lessons": profile.completed_lessons,
            "weak_topics": profile.weak_topics,
            "review_count_due": len(learner_store.due_reviews(learner_id)),
        },
    }
