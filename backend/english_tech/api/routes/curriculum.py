from fastapi import APIRouter, HTTPException

from english_tech.curriculum.agent import CurriculumAgent, NextLessonRequest
from english_tech.curriculum.store import CurriculumStore

router = APIRouter()
store = CurriculumStore()
agent = CurriculumAgent(store=store)


@router.get("/templates")
def list_templates() -> list[dict[str, str]]:
    return [
        {
            "course_id": course.course_id,
            "title": course.title,
            "level_band": course.level_band.value,
            "cefr_range": course.cefr_range,
        }
        for course in store.list_courses()
    ]


@router.get("/templates/{course_id}")
def get_template(course_id: str):
    course = store.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Unknown course: {course_id}")
    return course.model_dump(mode="json")


@router.post("/next-lesson")
def next_lesson(request: NextLessonRequest):
    selection = agent.select_next_lesson(request)
    if selection is None:
        raise HTTPException(status_code=404, detail="No lesson matched the request")
    lesson = store.get_lesson(
        course_id=selection.course_id,
        chapter_id=selection.chapter_id,
        lesson_id=selection.lesson_id,
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Selected lesson could not be loaded")
    return {
        "selection": selection.model_dump(mode="json"),
        "lesson": lesson.model_dump(mode="json"),
    }
