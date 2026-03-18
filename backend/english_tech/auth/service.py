from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import or_, select

from english_tech.auth.email_outbox import AuthEmailOutbox
from english_tech.auth.models import AuthMessageResponse, AuthSession, AuthSessionSummary, AuthUser
from english_tech.config import (
    AUTH_ACCESS_TTL_MINUTES,
    AUTH_DEBUG_TOKENS,
    AUTH_LOCK_MINUTES,
    AUTH_LOCK_THRESHOLD,
    AUTH_PASSWORD_RESET_TTL_MINUTES,
    AUTH_REFRESH_TTL_DAYS,
    AUTH_REQUIRE_VERIFIED_EMAIL,
    AUTH_TOKEN_BYTES,
    AUTH_VERIFICATION_TTL_HOURS,
    GOOGLE_ALLOWED_CLIENT_IDS,
    GOOGLE_AUTH_ENABLED,
)
from english_tech.db import ensure_database_connection, session_scope
from english_tech.db_models import AuthSessionRecord, AuthUserRecord, LearnerRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self) -> None:
        ensure_database_connection()
        self._outbox = AuthEmailOutbox()
        self._google_request = google_requests.Request()

    def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        with session_scope() as session:
            existing = session.scalar(select(AuthUserRecord).where(AuthUserRecord.email == normalized_email))
            if existing is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email is already registered')

            user, learner = self._create_user(
                session,
                email=normalized_email,
                display_name=display_name,
                password=password,
                auth_provider='local',
            )

            verification_token = self._issue_verification_token(session, user, learner)
            auth_session = self._issue_session(
                session,
                user,
                learner,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            auth_session.email_verification_required = AUTH_REQUIRE_VERIFIED_EMAIL and not auth_session.user.email_verified
            auth_session.debug_email_verification_token = verification_token if AUTH_DEBUG_TOKENS else None
            return auth_session

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        with session_scope() as session:
            user = session.scalar(select(AuthUserRecord).where(AuthUserRecord.email == normalized_email))
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')
            if user.auth_provider == 'google':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='This account uses Google sign-in. Continue with Google instead.',
                )
            if self._is_locked(user):
                raise HTTPException(status_code=status.HTTP_423_LOCKED, detail='Account is temporarily locked')
            if not self._verify_password(password, user.password_hash, user.password_salt):
                self._register_failed_login(user)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')
            learner = session.get(LearnerRecord, user.learner_id)
            if learner is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Learner record is missing')
            user.failed_login_attempts = 0
            user.locked_until = None
            auth_session = self._issue_session(
                session,
                user,
                learner,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            auth_session.email_verification_required = AUTH_REQUIRE_VERIFIED_EMAIL and not auth_session.user.email_verified
            return auth_session

    def login_with_google(
        self,
        *,
        id_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        claims = self._verify_google_id_token(id_token)
        google_subject = str(claims.get('sub') or '').strip()
        normalized_email = str(claims.get('email') or '').strip().lower()
        email_verified = claims.get('email_verified') in {True, 'true', 'True', 1, '1'}

        if not google_subject or not normalized_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Google account payload is missing a verified email identity',
            )
        if not email_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Google account email must be verified before sign-in',
            )

        self._validate_email(normalized_email)
        display_name = self._google_display_name(claims, normalized_email)
        now = utc_now()

        with session_scope() as session:
            user = session.scalar(
                select(AuthUserRecord).where(AuthUserRecord.google_subject == google_subject)
            )

            if user is None:
                user = session.scalar(select(AuthUserRecord).where(AuthUserRecord.email == normalized_email))
                if user is not None and user.google_subject and user.google_subject != google_subject:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail='This email is already linked to another Google account',
                    )
            elif user.email != normalized_email:
                conflicting = session.scalar(
                    select(AuthUserRecord)
                    .where(AuthUserRecord.email == normalized_email)
                    .where(AuthUserRecord.user_id != user.user_id)
                )
                if conflicting is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail='Google account email conflicts with an existing user',
                    )
                user.email = normalized_email

            if user is None:
                user, learner = self._create_user(
                    session,
                    email=normalized_email,
                    display_name=display_name,
                    password=None,
                    auth_provider='google',
                    google_subject=google_subject,
                    email_verified_at=now,
                )
            else:
                learner = session.get(LearnerRecord, user.learner_id)
                if learner is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail='Learner record is missing',
                    )
                user.google_subject = google_subject
                user.email_verified_at = user.email_verified_at or now
                user.failed_login_attempts = 0
                user.locked_until = None
                if (
                    display_name
                    and learner.display_name.strip().lower() in {'', 'learner'}
                ):
                    learner.display_name = display_name

            auth_session = self._issue_session(
                session,
                user,
                learner,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            auth_session.email_verification_required = False
            return auth_session

    def refresh(self, refresh_token: str, *, ip_address: str | None = None, user_agent: str | None = None) -> AuthSession:
        token_hash = self._hash_token(refresh_token)
        now = utc_now()
        with session_scope() as session:
            row = session.scalar(
                select(AuthSessionRecord)
                .where(AuthSessionRecord.refresh_token_hash == token_hash)
                .where(AuthSessionRecord.revoked_at.is_(None))
            )
            if row is None or self._coerce_datetime(row.refresh_expires_at) <= now:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired refresh token')
            user = session.get(AuthUserRecord, row.user_id)
            learner = session.get(LearnerRecord, row.learner_id)
            if user is None or learner is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session')
            auth_session = self._issue_session(
                session,
                user,
                learner,
                replace_row=row,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            auth_session.email_verification_required = AUTH_REQUIRE_VERIFIED_EMAIL and not auth_session.user.email_verified
            return auth_session

    def authenticate_token(self, token: str) -> AuthUser:
        token_hash = self._hash_token(token)
        now = utc_now()
        with session_scope() as session:
            row = session.scalar(
                select(AuthSessionRecord)
                .where(AuthSessionRecord.token_hash == token_hash)
                .where(AuthSessionRecord.revoked_at.is_(None))
            )
            if row is None or self._coerce_datetime(row.expires_at) <= now:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token')
            user = session.get(AuthUserRecord, row.user_id)
            learner = session.get(LearnerRecord, row.learner_id)
            if user is None or learner is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session')
            row.last_used_at = now
            return self._auth_user(user, learner)

    def revoke(self, token: str) -> None:
        token_hash = self._hash_token(token)
        with session_scope() as session:
            row = session.scalar(
                select(AuthSessionRecord).where(
                    or_(
                        AuthSessionRecord.token_hash == token_hash,
                        AuthSessionRecord.refresh_token_hash == token_hash,
                    )
                )
            )
            if row is not None:
                row.revoked_at = utc_now()

    def list_sessions(self, *, user_id: str, current_token: str | None = None) -> list[AuthSessionSummary]:
        current_hash = self._hash_token(current_token) if current_token else None
        with session_scope() as session:
            rows = list(
                session.scalars(
                    select(AuthSessionRecord)
                    .where(AuthSessionRecord.user_id == user_id)
                    .order_by(AuthSessionRecord.created_at.desc())
                )
            )
            return [
                AuthSessionSummary(
                    session_id=row.session_id,
                    created_at=self._coerce_datetime(row.created_at),
                    last_used_at=self._coerce_datetime(row.last_used_at),
                    expires_at=self._coerce_datetime(row.expires_at),
                    refresh_expires_at=self._coerce_datetime(row.refresh_expires_at),
                    revoked_at=self._coerce_datetime(row.revoked_at) if row.revoked_at else None,
                    ip_address=row.ip_address,
                    user_agent=row.user_agent,
                    current=bool(current_hash and row.token_hash == current_hash),
                )
                for row in rows
            ]

    def revoke_session(self, *, user_id: str, session_id: str) -> None:
        with session_scope() as session:
            row = session.scalar(
                select(AuthSessionRecord)
                .where(AuthSessionRecord.session_id == session_id)
                .where(AuthSessionRecord.user_id == user_id)
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Session not found')
            row.revoked_at = utc_now()

    def request_password_reset(self, *, email: str) -> AuthMessageResponse:
        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        with session_scope() as session:
            user = session.scalar(select(AuthUserRecord).where(AuthUserRecord.email == normalized_email))
            if user is None:
                return AuthMessageResponse(message='If that account exists, a password reset email has been queued.')
            learner = session.get(LearnerRecord, user.learner_id)
            display_name = learner.display_name if learner is not None else 'Learner'
            reset_token = self._issue_password_reset_token(session, user, display_name=display_name)
            return AuthMessageResponse(
                message='If that account exists, a password reset email has been queued.',
                debug_token=reset_token if AUTH_DEBUG_TOKENS else None,
            )

    def reset_password(self, *, token: str, new_password: str) -> AuthMessageResponse:
        token_hash = self._hash_token(token)
        now = utc_now()
        with session_scope() as session:
            user = session.scalar(
                select(AuthUserRecord)
                .where(AuthUserRecord.password_reset_token_hash == token_hash)
            )
            if user is None or self._coerce_datetime(user.password_reset_expires_at) <= now:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired password reset token')
            salt = secrets.token_bytes(16)
            user.password_salt = base64.b64encode(salt).decode('ascii')
            user.password_hash = self._hash_password(new_password, salt)
            user.password_reset_token_hash = None
            user.password_reset_sent_at = None
            user.password_reset_expires_at = None
            user.failed_login_attempts = 0
            user.locked_until = None
            for session_row in session.scalars(select(AuthSessionRecord).where(AuthSessionRecord.user_id == user.user_id)):
                session_row.revoked_at = now
            return AuthMessageResponse(message='Password updated. Sign in again with your new password.')

    def resend_verification(self, *, email: str) -> AuthMessageResponse:
        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        with session_scope() as session:
            user = session.scalar(select(AuthUserRecord).where(AuthUserRecord.email == normalized_email))
            if user is None:
                return AuthMessageResponse(message='If that account exists, a verification email has been queued.')
            learner = session.get(LearnerRecord, user.learner_id)
            if learner is None:
                return AuthMessageResponse(message='If that account exists, a verification email has been queued.')
            if user.email_verified_at is not None:
                return AuthMessageResponse(message='Email is already verified.')
            verification_token = self._issue_verification_token(session, user, learner)
            return AuthMessageResponse(
                message='If that account exists, a verification email has been queued.',
                debug_token=verification_token if AUTH_DEBUG_TOKENS else None,
            )

    def verify_email(self, *, token: str) -> AuthMessageResponse:
        token_hash = self._hash_token(token)
        now = utc_now()
        with session_scope() as session:
            user = session.scalar(
                select(AuthUserRecord)
                .where(AuthUserRecord.verification_token_hash == token_hash)
            )
            if user is None or self._coerce_datetime(user.verification_expires_at) <= now:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired verification token')
            user.email_verified_at = now
            user.verification_token_hash = None
            user.verification_sent_at = None
            user.verification_expires_at = None
            return AuthMessageResponse(message='Email verified successfully.')

    def _issue_session(
        self,
        session,
        user: AuthUserRecord,
        learner: LearnerRecord,
        *,
        replace_row: AuthSessionRecord | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        access_token = secrets.token_urlsafe(AUTH_TOKEN_BYTES)
        refresh_token = secrets.token_urlsafe(AUTH_TOKEN_BYTES)
        now = utc_now()
        expires_at = now + timedelta(minutes=AUTH_ACCESS_TTL_MINUTES)
        refresh_expires_at = now + timedelta(days=AUTH_REFRESH_TTL_DAYS)

        if replace_row is None:
            token_row = AuthSessionRecord(
                session_id=f'session_{uuid4().hex[:16]}',
                user_id=user.user_id,
                learner_id=learner.learner_id,
                token_hash=self._hash_token(access_token),
                refresh_token_hash=self._hash_token(refresh_token),
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
                refresh_expires_at=refresh_expires_at,
                revoked_at=None,
                ip_address=ip_address,
                user_agent=(user_agent or '')[:500] or None,
            )
            session.add(token_row)
        else:
            replace_row.token_hash = self._hash_token(access_token)
            replace_row.refresh_token_hash = self._hash_token(refresh_token)
            replace_row.last_used_at = now
            replace_row.expires_at = expires_at
            replace_row.refresh_expires_at = refresh_expires_at
            replace_row.revoked_at = None
            replace_row.ip_address = ip_address
            replace_row.user_agent = (user_agent or '')[:500] or None

        return AuthSession(
            token=access_token,
            refresh_token=refresh_token,
            user=self._auth_user(user, learner),
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            email_verification_required=AUTH_REQUIRE_VERIFIED_EMAIL and user.email_verified_at is None,
        )

    def _issue_verification_token(self, session, user: AuthUserRecord, learner: LearnerRecord) -> str:
        token = secrets.token_urlsafe(AUTH_TOKEN_BYTES)
        now = utc_now()
        user.verification_token_hash = self._hash_token(token)
        user.verification_sent_at = now
        user.verification_expires_at = now + timedelta(hours=AUTH_VERIFICATION_TTL_HOURS)
        self._outbox.write_verification_email(email=user.email, display_name=learner.display_name, token=token)
        return token

    def _issue_password_reset_token(self, session, user: AuthUserRecord, *, display_name: str) -> str:
        token = secrets.token_urlsafe(AUTH_TOKEN_BYTES)
        now = utc_now()
        user.password_reset_token_hash = self._hash_token(token)
        user.password_reset_sent_at = now
        user.password_reset_expires_at = now + timedelta(minutes=AUTH_PASSWORD_RESET_TTL_MINUTES)
        self._outbox.write_password_reset_email(email=user.email, display_name=display_name, token=token)
        return token

    def _auth_user(self, user: AuthUserRecord, learner: LearnerRecord) -> AuthUser:
        return AuthUser(
            user_id=user.user_id,
            learner_id=learner.learner_id,
            email=user.email,
            display_name=learner.display_name,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
        )

    def _is_locked(self, user: AuthUserRecord) -> bool:
        return user.locked_until is not None and self._coerce_datetime(user.locked_until) > utc_now()

    def _register_failed_login(self, user: AuthUserRecord) -> None:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= AUTH_LOCK_THRESHOLD:
            user.locked_until = utc_now() + timedelta(minutes=AUTH_LOCK_MINUTES)
            user.failed_login_attempts = 0

    def _create_user(
        self,
        session,
        *,
        email: str,
        display_name: str,
        password: str | None,
        auth_provider: str,
        google_subject: str | None = None,
        email_verified_at: datetime | None = None,
    ) -> tuple[AuthUserRecord, LearnerRecord]:
        learner_id = f'learner_{uuid4().hex[:16]}'
        user_id = f'user_{uuid4().hex[:16]}'
        password_salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password or secrets.token_urlsafe(32), password_salt)

        learner = LearnerRecord(
            learner_id=learner_id,
            display_name=display_name.strip() or 'Learner',
        )
        user = AuthUserRecord(
            user_id=user_id,
            learner_id=learner_id,
            email=email,
            auth_provider=auth_provider,
            google_subject=google_subject,
            password_hash=password_hash,
            password_salt=base64.b64encode(password_salt).decode('ascii'),
            email_verified_at=email_verified_at,
            created_at=utc_now(),
            failed_login_attempts=0,
        )
        session.add(learner)
        session.flush()
        session.add(user)
        session.flush()
        return user, learner

    def _hash_password(self, password: str, salt: bytes) -> str:
        derived = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=64)
        return base64.b64encode(derived).decode('ascii')

    def _validate_email(self, email: str) -> None:
        if '@' not in email or email.startswith('@') or email.endswith('@'):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid email address')

    def _verify_password(self, password: str, expected_hash: str, encoded_salt: str) -> bool:
        salt = base64.b64decode(encoded_salt.encode('ascii'))
        candidate = self._hash_password(password, salt)
        return secrets.compare_digest(candidate, expected_hash)

    def _verify_google_id_token(self, token: str) -> dict[str, object]:
        if not GOOGLE_AUTH_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Google sign-in is not configured on the server',
            )
        try:
            claims = google_id_token.verify_oauth2_token(
                token,
                self._google_request,
                audience=None,
            )
        except (ValueError, GoogleAuthError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid Google identity token',
            ) from exc

        audience = str(claims.get('aud') or '')
        issuer = str(claims.get('iss') or '')
        if audience not in GOOGLE_ALLOWED_CLIENT_IDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Google identity token audience is not allowed',
            )
        if issuer not in {'accounts.google.com', 'https://accounts.google.com'}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid Google identity token issuer',
            )
        return claims

    def _google_display_name(self, claims: dict[str, object], email: str) -> str:
        claim_name = str(claims.get('name') or '').strip()
        if claim_name:
            return claim_name[:120]
        local_part = email.split('@', 1)[0].replace('.', ' ').replace('_', ' ').strip()
        return local_part.title()[:120] or 'Learner'

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def _coerce_datetime(self, value: datetime | None) -> datetime:
        if value is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
