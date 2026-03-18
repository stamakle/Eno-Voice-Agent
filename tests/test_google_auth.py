from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, select

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

TEST_DIR = tempfile.mkdtemp(prefix="english_tech_google_auth_")
TEST_DB = Path(TEST_DIR) / "google_auth.db"
os.environ["ENGLISH_TECH_ENV"] = "development"
os.environ["ENGLISH_TECH_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ENGLISH_TECH_DATABASE_FALLBACK_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ENGLISH_TECH_DB_AUTO_CREATE"] = "true"
os.environ["ENGLISH_TECH_LLM_PROVIDER"] = "none"
os.environ["ENGLISH_TECH_GOOGLE_ALLOWED_CLIENT_IDS"] = (
    "test-web-client.apps.googleusercontent.com"
)

from english_tech.auth.service import AuthService
from english_tech.db import init_db, session_scope
from english_tech.db_models import AuthSessionRecord, AuthUserRecord, LearnerRecord


class GoogleAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        with session_scope() as session:
            session.execute(delete(AuthSessionRecord))
            session.execute(delete(AuthUserRecord))
            session.execute(delete(LearnerRecord))
        self.service = AuthService()

    def _claims(
        self,
        *,
        sub: str,
        email: str,
        name: str = "Google User",
    ) -> dict[str, object]:
        return {
            "sub": sub,
            "email": email,
            "email_verified": True,
            "name": name,
            "aud": "test-web-client.apps.googleusercontent.com",
            "iss": "https://accounts.google.com",
        }

    def test_google_login_creates_verified_google_user(self) -> None:
        self.service._verify_google_id_token = lambda token: self._claims(
            sub="google-sub-1",
            email="new.google.user@gmail.com",
            name="New Google User",
        )

        auth_session = self.service.login_with_google(id_token="google-token")

        self.assertEqual(auth_session.user.email, "new.google.user@gmail.com")
        self.assertEqual(auth_session.user.display_name, "New Google User")
        self.assertFalse(auth_session.email_verification_required)

        with session_scope() as session:
            user = session.scalar(
                select(AuthUserRecord).where(
                    AuthUserRecord.email == "new.google.user@gmail.com"
                )
            )
            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.auth_provider, "google")
            self.assertEqual(user.google_subject, "google-sub-1")
            self.assertIsNotNone(user.email_verified_at)

    def test_google_login_links_existing_local_account(self) -> None:
        local_session = self.service.register(
            email="linked.user@gmail.com",
            password="supersecret1",
            display_name="Linked Local User",
        )
        self.service._verify_google_id_token = lambda token: self._claims(
            sub="google-sub-2",
            email="linked.user@gmail.com",
            name="Linked Google User",
        )

        google_session = self.service.login_with_google(id_token="google-token")

        self.assertEqual(google_session.user.user_id, local_session.user.user_id)
        with session_scope() as session:
            user = session.scalar(
                select(AuthUserRecord).where(
                    AuthUserRecord.email == "linked.user@gmail.com"
                )
            )
            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.auth_provider, "local")
            self.assertEqual(user.google_subject, "google-sub-2")
            self.assertIsNotNone(user.email_verified_at)

    def test_password_login_is_blocked_for_google_only_accounts(self) -> None:
        self.service._verify_google_id_token = lambda token: self._claims(
            sub="google-sub-3",
            email="google.only@gmail.com",
        )
        self.service.login_with_google(id_token="google-token")

        with self.assertRaises(HTTPException) as context:
            self.service.login(
                email="google.only@gmail.com",
                password="supersecret1",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Continue with Google", str(context.exception.detail))


if __name__ == "__main__":
    unittest.main()
