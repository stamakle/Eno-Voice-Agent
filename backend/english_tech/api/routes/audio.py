from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from english_tech.auth.deps import get_verified_user
from english_tech.config import AUDIO_RATE_LIMIT_PER_MINUTE
from english_tech.security.rate_limit import enforce_http_rate_limit
from english_tech.speech import speech_service

router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = Field(default=None, max_length=120)
    rate: str | None = Field(default=None, max_length=20)


@router.post("/stt")
async def speech_to_text(
    request: Request,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    user=Depends(get_verified_user),
):
    enforce_http_rate_limit(
        request,
        category='audio_stt',
        key_material=user.user_id,
        limit=AUDIO_RATE_LIMIT_PER_MINUTE,
    )
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    try:
        return speech_service.transcribe_wav(payload, language=language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - runtime service failure
        raise HTTPException(status_code=500, detail=f"STT failed: {exc}") from exc


@router.post("/tts")
async def text_to_speech(request: TTSRequest, http_request: Request, user=Depends(get_verified_user)):
    enforce_http_rate_limit(
        http_request,
        category='audio_tts',
        key_material=user.user_id,
        limit=AUDIO_RATE_LIMIT_PER_MINUTE,
    )

    async def audio_generator():
        try:
            async for chunk in speech_service.synthesize_speech_stream(
                request.text,
                voice=request.voice,
                rate=request.rate,
            ):
                yield chunk
        except Exception as exc:  # pragma: no cover
            pass

    return StreamingResponse(
        audio_generator(),
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="ama-tts.wav"'},
    )
