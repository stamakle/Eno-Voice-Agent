from __future__ import annotations

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from english_tech.config import LEARNER_ROOT, RESULT_ROOT
from english_tech.curriculum.models import LessonResult
from english_tech import db
from english_tech.learners.models import LearnerProfile
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    db.ensure_database_connection()
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        command.upgrade(alembic_cfg, "head")
    elif tables.intersection({"learners", "lesson_results", "review_items"}):
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")

    learner_store = LearnerStore()
    result_store = LessonResultStore()

    learner_count = 0
    result_count = 0

    for path in sorted(LEARNER_ROOT.glob("*.json")):
        payload = load_json(path)
        profile = LearnerProfile.model_validate(payload)
        learner_store.save_profile(profile)
        learner_count += 1

    for path in sorted(RESULT_ROOT.glob("*.json")):
        payload = load_json(path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            result = LessonResult.model_validate(item)
            result_store.append_result(result)
            learner_store.apply_lesson_result(result.learner_id, result)
            result_count += 1

    print(
        json.dumps(
            {
                "status": "ok",
                "learners_migrated": learner_count,
                "results_migrated": result_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
