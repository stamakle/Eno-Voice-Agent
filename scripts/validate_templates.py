from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from english_tech.curriculum.store import CurriculumStore  # noqa: E402


if __name__ == "__main__":
    store = CurriculumStore()
    courses = store.list_courses()
    print(f"validated {len(courses)} course templates")
    for course in courses:
        print(f"- {course.course_id}: {len(course.chapters)} chapters")
