#!/usr/bin/env bash
set -euo pipefail
cd /home/aseda/Desktop/english_tech
export ENGLISH_TECH_ENV=development
export ENGLISH_TECH_DATABASE_URL='postgresql+psycopg://english_tech:english_tech@127.0.0.1:5432/english_tech'
export ENGLISH_TECH_DATABASE_FALLBACK_URL='sqlite:////home/aseda/Desktop/english_tech/data/english_tech.db'
export ENGLISH_TECH_RATE_LIMIT_BACKEND=redis
export ENGLISH_TECH_REDIS_URL='redis://127.0.0.1:6379/0'
PYTHONPATH=backend .uv-venv/bin/python -m alembic upgrade head
PYTHONPATH=backend .uv-venv/bin/uvicorn english_tech.main:app --host 0.0.0.0 --port 8091
