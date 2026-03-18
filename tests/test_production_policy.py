from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ProductionDatabasePolicyTests(unittest.TestCase):
    def test_production_requires_postgres(self) -> None:
        db_path = Path(tempfile.mkdtemp(prefix='english_tech_prod_policy_')) / 'policy.db'
        env = os.environ.copy()
        env.update(
            {
                'PYTHONPATH': str(REPO_ROOT / 'backend'),
                'ENGLISH_TECH_ENV': 'production',
                'ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION': 'true',
                'ENGLISH_TECH_DATABASE_URL': f'sqlite:///{db_path}',
                'ENGLISH_TECH_DATABASE_FALLBACK_URL': f'sqlite:///{db_path}',
            }
        )
        code = (
            'from english_tech.db import ensure_database_connection\n'
            'ensure_database_connection()\n'
        )
        completed = subprocess.run(
            [sys.executable, '-c', code],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertNotEqual(completed.returncode, 0)
        combined = f'{completed.stdout}\n{completed.stderr}'
        self.assertIn('Production mode requires ENGLISH_TECH_DATABASE_URL to point to Postgres', combined)


if __name__ == '__main__':
    unittest.main()
