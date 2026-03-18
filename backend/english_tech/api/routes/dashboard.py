from fastapi import APIRouter, Depends

from english_tech.auth.deps import get_verified_user
from english_tech.curriculum.agent import CurriculumAgent, NextLessonRequest
from english_tech.curriculum.store import CurriculumStore
from english_tech.learners.models import DashboardSummary, ReviewStatus
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore

router = APIRouter()
store = CurriculumStore()
agent = CurriculumAgent(store=store)
learner_store = LearnerStore()
result_store = LessonResultStore()


@router.get("/me")
def dashboard(user=Depends(get_verified_user)):
    learner_id = user.learner_id
    profile = learner_store.get_or_create_profile(learner_id)
    results = result_store.list_results(learner_id)
    selection = agent.select_next_lesson(
        NextLessonRequest(
            learner_id=learner_id,
            course_id=profile.level_band.value,
            completed_lessons=profile.completed_lessons,
            weak_topics=profile.weak_topics,
            review_queue=profile.review_queue,
            learner_goals=profile.goals,
        )
    )

    pending_reviews = sorted(
        [item for item in profile.review_queue if item.status == ReviewStatus.pending],
        key=lambda item: (item.due_on, item.topic, item.lesson.lesson_id),
    )
    due_reviews = learner_store.due_reviews(learner_id)
    next_review_due_on = pending_reviews[0].due_on if pending_reviews else None

    summary = DashboardSummary(
        learner=profile,
        total_completed_lessons=len(profile.completed_lessons),
        weak_topics=profile.weak_topics,
        recent_results=results[-5:],
        recent_history=profile.lesson_history[-5:],
        review_queue=pending_reviews[:10],
        review_count_due=len(due_reviews),
        next_review_due_on=next_review_due_on,
        recommended_next_lesson=selection,
    )
    return summary.model_dump(mode="json")
