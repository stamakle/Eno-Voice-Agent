from __future__ import annotations

from fastapi import Header, HTTPException, WebSocket, status

from english_tech.config import AUTH_REQUIRE_VERIFIED_EMAIL
from english_tech.auth.models import AuthUser
from english_tech.auth.service import AuthService


auth_service = AuthService()


def _extract_bearer_token(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing authorization header')
    scheme, _, token = value.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authorization header')
    return token.strip()


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _extract_bearer_token(authorization)
    return auth_service.authenticate_token(token)


def get_verified_user(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_current_user(authorization)
    if AUTH_REQUIRE_VERIFIED_EMAIL and not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Email verification is required')
    return user


def resolve_ws_user(websocket: WebSocket) -> AuthUser:
    token = websocket.query_params.get('token')
    if not token:
        header = websocket.headers.get('authorization')
        if header:
            token = _extract_bearer_token(header)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing websocket auth token')
    return auth_service.authenticate_token(token)


def resolve_ws_verified_user(websocket: WebSocket) -> AuthUser:
    user = resolve_ws_user(websocket)
    if AUTH_REQUIRE_VERIFIED_EMAIL and not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Email verification is required')
    return user
