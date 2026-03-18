from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
CURRICULUM_ROOT = DATA_ROOT / "curriculum"
TEMPLATE_ROOT = CURRICULUM_ROOT / "templates"
GENERATED_TEMPLATE_ROOT = CURRICULUM_ROOT / "generated"
LEARNER_ROOT = DATA_ROOT / "learners"
RESULT_ROOT = DATA_ROOT / "results"
TTS_ROOT = DATA_ROOT / "tts"
PIPER_ROOT = TTS_ROOT / "piper_runtime"
PIPER_BIN_DIR = PIPER_ROOT / "piper"
PIPER_BINARY_PATH = PIPER_BIN_DIR / "piper"
PIPER_RELEASE = os.getenv("ENGLISH_TECH_PIPER_RELEASE", "2023.11.14-2")
PIPER_ARCHIVE_URL = os.getenv(
    "ENGLISH_TECH_PIPER_ARCHIVE_URL",
    f"https://github.com/rhasspy/piper/releases/download/{PIPER_RELEASE}/piper_linux_x86_64.tar.gz",
)
PIPER_ARCHIVE_PATH = TTS_ROOT / f"piper_linux_x86_64_{PIPER_RELEASE}.tar.gz"
PIPER_VOICE_NAME = os.getenv("ENGLISH_TECH_TTS_VOICE", "en_US-lessac-medium")
PIPER_VOICE_DIR = TTS_ROOT / "voices" / PIPER_VOICE_NAME
PIPER_VOICE_MODEL_PATH = PIPER_VOICE_DIR / f"{PIPER_VOICE_NAME}.onnx"
PIPER_VOICE_CONFIG_PATH = PIPER_VOICE_DIR / f"{PIPER_VOICE_NAME}.onnx.json"
PIPER_VOICE_MODEL_URL = os.getenv(
    "ENGLISH_TECH_PIPER_VOICE_MODEL_URL",
    f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{PIPER_VOICE_NAME}.onnx?download=true",
)
PIPER_VOICE_CONFIG_URL = os.getenv(
    "ENGLISH_TECH_PIPER_VOICE_CONFIG_URL",
    f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{PIPER_VOICE_NAME}.onnx.json?download=true",
)
DEFAULT_SQLITE_PATH = DATA_ROOT / "english_tech.db"
APP_ENV = os.getenv("ENGLISH_TECH_ENV", "development").strip().lower()
PRODUCTION_MODE = APP_ENV in {"production", "prod"}
DATABASE_URL = os.getenv(
    "ENGLISH_TECH_DATABASE_URL",
    "postgresql+psycopg://english_tech:english_tech@127.0.0.1:5432/english_tech",
)
DATABASE_FALLBACK_URL = os.getenv(
    "ENGLISH_TECH_DATABASE_FALLBACK_URL",
    f"sqlite:///{DEFAULT_SQLITE_PATH}",
)
REQUIRE_POSTGRES_IN_PRODUCTION = os.getenv(
    "ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION",
    "true" if PRODUCTION_MODE else "false",
).lower() in {"1", "true", "yes", "on"}
DB_AUTO_CREATE = os.getenv("ENGLISH_TECH_DB_AUTO_CREATE", "false").lower() in {"1", "true", "yes", "on"}
AUTH_ACCESS_TTL_MINUTES = int(os.getenv("ENGLISH_TECH_AUTH_ACCESS_TTL_MINUTES", "720"))
AUTH_REFRESH_TTL_DAYS = int(os.getenv("ENGLISH_TECH_AUTH_REFRESH_TTL_DAYS", "30"))
AUTH_TOKEN_BYTES = int(os.getenv("ENGLISH_TECH_AUTH_TOKEN_BYTES", "32"))
AUTH_VERIFICATION_TTL_HOURS = int(os.getenv("ENGLISH_TECH_AUTH_VERIFICATION_TTL_HOURS", "24"))
AUTH_PASSWORD_RESET_TTL_MINUTES = int(os.getenv("ENGLISH_TECH_AUTH_PASSWORD_RESET_TTL_MINUTES", "30"))
AUTH_REQUIRE_VERIFIED_EMAIL = os.getenv(
    "ENGLISH_TECH_AUTH_REQUIRE_VERIFIED_EMAIL",
    "true" if PRODUCTION_MODE else "false",
).lower() in {"1", "true", "yes", "on"}
AUTH_DEBUG_TOKENS = os.getenv(
    "ENGLISH_TECH_AUTH_DEBUG_TOKENS",
    "false" if PRODUCTION_MODE else "true",
).lower() in {"1", "true", "yes", "on"}
AUTH_LOCK_THRESHOLD = int(os.getenv("ENGLISH_TECH_AUTH_LOCK_THRESHOLD", "5"))
AUTH_LOCK_MINUTES = int(os.getenv("ENGLISH_TECH_AUTH_LOCK_MINUTES", "15"))
GOOGLE_WEB_CLIENT_ID = os.getenv("ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID", "").strip()
GOOGLE_SERVER_CLIENT_ID = os.getenv("ENGLISH_TECH_GOOGLE_SERVER_CLIENT_ID", "").strip()
GOOGLE_ALLOWED_CLIENT_IDS = tuple(
    dict.fromkeys(
        client_id
        for client_id in [
            *[item.strip() for item in os.getenv("ENGLISH_TECH_GOOGLE_ALLOWED_CLIENT_IDS", "").split(",")],
            GOOGLE_WEB_CLIENT_ID,
            GOOGLE_SERVER_CLIENT_ID,
        ]
        if client_id
    )
)
GOOGLE_AUTH_ENABLED = bool(GOOGLE_ALLOWED_CLIENT_IDS)
APP_BASE_URL = os.getenv("ENGLISH_TECH_APP_BASE_URL", "http://127.0.0.1:8100")
AUTH_OUTBOX_ROOT = DATA_ROOT / "auth_outbox"
RATE_LIMIT_BACKEND = os.getenv("ENGLISH_TECH_RATE_LIMIT_BACKEND", "memory").strip().lower()
REDIS_URL = os.getenv("ENGLISH_TECH_REDIS_URL", "redis://127.0.0.1:6379/0")
AUTH_RATE_LIMIT_PER_MINUTE = int(os.getenv("ENGLISH_TECH_AUTH_RATE_LIMIT_PER_MINUTE", "20"))
AUDIO_RATE_LIMIT_PER_MINUTE = int(os.getenv("ENGLISH_TECH_AUDIO_RATE_LIMIT_PER_MINUTE", "60"))
COACH_WS_RATE_LIMIT_PER_MINUTE = int(os.getenv("ENGLISH_TECH_COACH_WS_RATE_LIMIT_PER_MINUTE", "120"))
LESSON_WS_RATE_LIMIT_PER_MINUTE = int(os.getenv("ENGLISH_TECH_LESSON_WS_RATE_LIMIT_PER_MINUTE", "240"))
LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE = int(
    os.getenv("ENGLISH_TECH_LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE", "900")
)
CORS_ORIGIN_REGEX = os.getenv(
    "ENGLISH_TECH_CORS_ORIGIN_REGEX",
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"(?:10(?:\.\d{1,3}){3})|"
    r"(?:192\.168(?:\.\d{1,3}){2})|"
    r"(?:172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})|"
    r"(?:[A-Za-z0-9-]+\.local)|"
    r"(?:[A-Za-z0-9-]+)"
    r")(?::\d+)?$",
)
DEFAULT_STT_DEVICE = "cuda" if shutil.which("nvidia-smi") else "cpu"
STT_MODEL_NAME = os.getenv("ENGLISH_TECH_STT_MODEL", "base.en")
STT_DEVICE = os.getenv("ENGLISH_TECH_STT_DEVICE", DEFAULT_STT_DEVICE)
STT_COMPUTE_TYPE = os.getenv(
    "ENGLISH_TECH_STT_COMPUTE_TYPE",
    "float16" if STT_DEVICE == "cuda" else "int8",
)
STT_LANGUAGE = os.getenv("ENGLISH_TECH_STT_LANGUAGE", "en")
TTS_RATE = os.getenv("ENGLISH_TECH_TTS_RATE", "+0%")
STREAM_AUDIO_CHUNK_BYTES = int(os.getenv("ENGLISH_TECH_STREAM_AUDIO_CHUNK_BYTES", "16384"))
STREAM_PARTIAL_AUDIO_BYTES = int(os.getenv("ENGLISH_TECH_STREAM_PARTIAL_AUDIO_BYTES", "16000"))
STREAM_PARTIAL_CHUNK_INTERVAL = int(os.getenv("ENGLISH_TECH_STREAM_PARTIAL_CHUNK_INTERVAL", "4"))
STREAM_TTS_SEGMENT_MAX_CHARS = int(os.getenv("ENGLISH_TECH_STREAM_TTS_SEGMENT_MAX_CHARS", "160"))
LLM_PROVIDER = os.getenv("ENGLISH_TECH_LLM_PROVIDER", "ollama").strip().lower()
LLM_BASE_URL = os.getenv("ENGLISH_TECH_LLM_BASE_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("ENGLISH_TECH_LLM_MODEL", "llama3.2:3b")
LLM_API_KEY = os.getenv("ENGLISH_TECH_LLM_API_KEY", "")
LLM_TIMEOUT_SECONDS = float(os.getenv("ENGLISH_TECH_LLM_TIMEOUT_SECONDS", "20"))

for path in (
    CURRICULUM_ROOT,
    TEMPLATE_ROOT,
    GENERATED_TEMPLATE_ROOT,
    LEARNER_ROOT,
    RESULT_ROOT,
    TTS_ROOT,
    PIPER_ROOT,
    PIPER_VOICE_DIR,
    AUTH_OUTBOX_ROOT,
):
    path.mkdir(parents=True, exist_ok=True)
