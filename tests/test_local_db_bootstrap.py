from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class LocalDatabaseBootstrapTests(unittest.TestCase):
    def test_init_db_upgrades_legacy_sqlite_schema_before_registration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="english_tech_bootstrap_") as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite3"
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(REPO_ROOT / "backend"),
                    "ENGLISH_TECH_ENV": "development",
                    "ENGLISH_TECH_DATABASE_URL": f"sqlite:///{db_path}",
                    "ENGLISH_TECH_DATABASE_FALLBACK_URL": f"sqlite:///{db_path}",
                    "ENGLISH_TECH_DB_AUTO_CREATE": "true",
                    "ENGLISH_TECH_LLM_PROVIDER": "none",
                }
            )

            legacy_upgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "0005_auth_recovery_verify"],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(
                legacy_upgrade.returncode,
                0,
                msg=f"{legacy_upgrade.stdout}\n{legacy_upgrade.stderr}",
            )

            with sqlite3.connect(db_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(learners)")
                }
            self.assertNotIn("preferred_scenario", columns)
            self.assertNotIn("memory_notes", columns)

            bootstrap = subprocess.run(
                [sys.executable, "-c", "from english_tech.db import init_db; init_db()"],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(bootstrap.returncode, 0, msg=f"{bootstrap.stdout}\n{bootstrap.stderr}")

            with sqlite3.connect(db_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(learners)")
                }
            self.assertIn("preferred_scenario", columns)
            self.assertIn("memory_notes", columns)

            register = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from english_tech.auth.service import AuthService\n"
                        "service = AuthService()\n"
                        "session = service.register(\n"
                        "    email='bootstrap@example.com',\n"
                        "    password='supersecret1',\n"
                        "    display_name='Bootstrap User',\n"
                        ")\n"
                        "assert session.user.email == 'bootstrap@example.com'\n"
                    ),
                ],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(register.returncode, 0, msg=f"{register.stdout}\n{register.stderr}")


if __name__ == "__main__":
    unittest.main()
