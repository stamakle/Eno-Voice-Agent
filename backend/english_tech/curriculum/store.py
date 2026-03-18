from __future__ import annotations

import json
from pathlib import Path

from english_tech.config import GENERATED_TEMPLATE_ROOT, TEMPLATE_ROOT
from english_tech.curriculum.models import Chapter, CourseTemplate, Lesson, LessonVariant


class CurriculumStore:
    def __init__(
        self,
        template_root: Path = TEMPLATE_ROOT,
        generated_root: Path = GENERATED_TEMPLATE_ROOT,
    ):
        self.template_root = template_root
        self.generated_root = generated_root
        self.generated_root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, CourseTemplate] = {}

    def _load_course(self, path: Path) -> CourseTemplate:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CourseTemplate.model_validate(payload)

    def list_courses(self) -> list[CourseTemplate]:
        courses: list[CourseTemplate] = []
        for path in sorted(self.template_root.glob("*.json")):
            course = self.get_course(path.stem)
            if course is not None:
                courses.append(course)
        return courses

    def get_course(self, course_id: str) -> CourseTemplate | None:
        if course_id in self._cache:
            return self._cache[course_id]

        path = self.template_root / f"{course_id}.json"
        if not path.exists():
            return None

        course = self._load_course(path)
        self._cache[course_id] = course
        return course

    def get_chapter(self, *, course_id: str, chapter_id: str) -> Chapter | None:
        course = self.get_course(course_id)
        if course is None:
            return None
        for chapter in course.chapters:
            if chapter.chapter_id == chapter_id:
                return chapter
        return None

    def get_lesson(self, *, course_id: str, chapter_id: str, lesson_id: str) -> Lesson | None:
        chapter = self.get_chapter(course_id=course_id, chapter_id=chapter_id)
        if chapter is None:
            return None

        for lesson in chapter.lessons:
            if lesson.lesson_id == lesson_id:
                return lesson
        return None

    def locate_lesson(self, *, course_id: str, lesson_id: str) -> tuple[str, Lesson] | None:
        course = self.get_course(course_id)
        if course is None:
            return None

        for chapter in course.chapters:
            for lesson in chapter.lessons:
                if lesson.lesson_id == lesson_id:
                    return chapter.chapter_id, lesson
        return None

    def get_variant(self, learner_id: str, variant_id: str) -> LessonVariant | None:
        path = self._variant_path(learner_id, variant_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return LessonVariant.model_validate(payload)

    def save_variant(self, variant: LessonVariant) -> None:
        learner_root = self.generated_root / variant.learner_id
        learner_root.mkdir(parents=True, exist_ok=True)
        path = self._variant_path(variant.learner_id, variant.variant_id)
        path.write_text(
            json.dumps(variant.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def _variant_path(self, learner_id: str, variant_id: str) -> Path:
        return self.generated_root / learner_id / f"{variant_id}.json"
