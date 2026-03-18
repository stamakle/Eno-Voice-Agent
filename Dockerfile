FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY alembic ./alembic
COPY docs ./docs
COPY scripts ./scripts
COPY data/curriculum ./data/curriculum

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

# Pre-bake Piper TTS and Faster-Whisper models into the image
RUN python3 -c "import os; os.environ['HUGGINGFACE_HUB_CACHE'] = '/app/data'; from english_tech.speech.service import speech_service; speech_service._ensure_piper_assets(); speech_service._get_model()"

ENV ENGLISH_TECH_ENV=production \
    ENGLISH_TECH_REQUIRE_POSTGRES_IN_PRODUCTION=true \
    ENGLISH_TECH_DB_AUTO_CREATE=false

EXPOSE 8091

CMD ["uvicorn", "english_tech.main:app", "--host", "0.0.0.0", "--port", "8091"]
