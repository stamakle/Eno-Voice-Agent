from fastapi import APIRouter

from english_tech.config import (
    APP_ENV,
    AUTH_REQUIRE_VERIFIED_EMAIL,
    GOOGLE_AUTH_ENABLED,
    LLM_MODEL,
    LLM_PROVIDER,
    PIPER_VOICE_NAME,
    PRODUCTION_MODE,
    REQUIRE_POSTGRES_IN_PRODUCTION,
    STT_MODEL_NAME,
)
from english_tech import db
from english_tech.security.rate_limit import rate_limiter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "english_tech",
        "database": db.ACTIVE_DATABASE_URL.split(":", 1)[0],
        "stt_model": STT_MODEL_NAME,
        "tts_voice": PIPER_VOICE_NAME,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "env": APP_ENV,
        "production_mode": str(PRODUCTION_MODE).lower(),
        "postgres_required": str(REQUIRE_POSTGRES_IN_PRODUCTION).lower(),
        "auth_requires_verified_email": str(AUTH_REQUIRE_VERIFIED_EMAIL).lower(),
        "google_auth_enabled": str(GOOGLE_AUTH_ENABLED).lower(),
        "rate_limit_backend": rate_limiter.backend_name,
    }
