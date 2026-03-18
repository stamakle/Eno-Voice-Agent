from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from english_tech.config import (
    DATABASE_FALLBACK_URL,
    DATABASE_URL,
    PRODUCTION_MODE,
    REQUIRE_POSTGRES_IN_PRODUCTION,
)


class Base(DeclarativeBase):
    pass


def _connect_args_for(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


def _build_engine(url: str):
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=_connect_args_for(url))


engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
ACTIVE_DATABASE_URL = DATABASE_URL


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql")


def _validate_database_policy() -> None:
    if REQUIRE_POSTGRES_IN_PRODUCTION and PRODUCTION_MODE and not _is_postgres_url(DATABASE_URL):
        raise RuntimeError("Production mode requires ENGLISH_TECH_DATABASE_URL to point to Postgres.")


def ensure_database_connection() -> str:
    global engine, SessionLocal, ACTIVE_DATABASE_URL

    _validate_database_policy()

    if ACTIVE_DATABASE_URL != DATABASE_URL:
        engine = _build_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
        ACTIVE_DATABASE_URL = DATABASE_URL

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ACTIVE_DATABASE_URL
    except Exception:
        if PRODUCTION_MODE and REQUIRE_POSTGRES_IN_PRODUCTION:
            raise
        if ACTIVE_DATABASE_URL == DATABASE_FALLBACK_URL:
            raise
        engine = _build_engine(DATABASE_FALLBACK_URL)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
        ACTIVE_DATABASE_URL = DATABASE_FALLBACK_URL
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ACTIVE_DATABASE_URL


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    import english_tech.db_models  # noqa: F401

    active_database_url = ensure_database_connection()
    alembic_config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", active_database_url)
    command.upgrade(alembic_config, "head")
