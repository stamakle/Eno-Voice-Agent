from fastapi import APIRouter, Depends, Header, Path, Request

from english_tech.auth.deps import auth_service, get_current_user
from english_tech.auth.models import (
    GoogleLoginRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from english_tech.config import AUTH_RATE_LIMIT_PER_MINUTE
from english_tech.security.rate_limit import enforce_http_rate_limit

router = APIRouter()


def _request_meta(http_request: Request) -> dict[str, str | None]:
    return {
        'ip_address': http_request.client.host if http_request.client else None,
        'user_agent': http_request.headers.get('user-agent'),
    }


@router.post('/register')
def register(request: RegisterRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_register',
        key_material=request.email.strip().lower(),
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.register(
        email=request.email,
        password=request.password,
        display_name=request.display_name,
        **_request_meta(http_request),
    ).model_dump(mode='json')


@router.post('/login')
def login(request: LoginRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_login',
        key_material=request.email.strip().lower(),
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.login(
        email=request.email,
        password=request.password,
        **_request_meta(http_request),
    ).model_dump(mode='json')


@router.post('/google')
def login_with_google(request: GoogleLoginRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_google_login',
        key_material=request.id_token[-24:],
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.login_with_google(
        id_token=request.id_token,
        **_request_meta(http_request),
    ).model_dump(mode='json')


@router.post('/refresh')
def refresh(request: RefreshTokenRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_refresh',
        key_material=request.refresh_token[-16:],
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.refresh(request.refresh_token, **_request_meta(http_request)).model_dump(mode='json')


@router.post('/logout')
def logout(authorization: str | None = Header(default=None)):
    if authorization:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() == 'bearer' and token:
            auth_service.revoke(token.strip())
    return {'status': 'logged_out'}


@router.get('/me')
def me(user=Depends(get_current_user)):
    return user.model_dump(mode='json')


@router.post('/verify-email')
def verify_email(request: VerifyEmailRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_verify_email',
        key_material=request.token[-16:],
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.verify_email(token=request.token).model_dump(mode='json')


@router.post('/resend-verification')
def resend_verification(request: ResendVerificationRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_resend_verification',
        key_material=request.email.strip().lower(),
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.resend_verification(email=request.email).model_dump(mode='json')


@router.post('/password-reset/request')
def request_password_reset(request: PasswordResetRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_password_reset_request',
        key_material=request.email.strip().lower(),
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.request_password_reset(email=request.email).model_dump(mode='json')


@router.post('/password-reset/confirm')
def confirm_password_reset(request: PasswordResetConfirmRequest, http_request: Request):
    enforce_http_rate_limit(
        http_request,
        category='auth_password_reset_confirm',
        key_material=request.token[-16:],
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return auth_service.reset_password(token=request.token, new_password=request.new_password).model_dump(mode='json')


@router.get('/sessions')
def list_sessions(user=Depends(get_current_user), authorization: str | None = Header(default=None)):
    token = None
    if authorization:
        scheme, _, candidate = authorization.partition(' ')
        if scheme.lower() == 'bearer' and candidate:
            token = candidate.strip()
    return [
        item.model_dump(mode='json')
        for item in auth_service.list_sessions(user_id=user.user_id, current_token=token)
    ]


@router.delete('/sessions/{session_id}')
def revoke_session(session_id: str = Path(min_length=1, max_length=120), user=Depends(get_current_user)):
    auth_service.revoke_session(user_id=user.user_id, session_id=session_id)
    return {'status': 'revoked', 'session_id': session_id}
