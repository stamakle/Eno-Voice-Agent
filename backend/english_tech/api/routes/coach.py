from __future__ import annotations

import asyncio
import base64
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from english_tech.auth.deps import get_verified_user, resolve_ws_verified_user
from english_tech.config import (
    AUTH_RATE_LIMIT_PER_MINUTE,
    COACH_WS_RATE_LIMIT_PER_MINUTE,
    LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE,
    STREAM_AUDIO_CHUNK_BYTES,
    STREAM_PARTIAL_AUDIO_BYTES,
    STREAM_PARTIAL_CHUNK_INTERVAL,
)
from english_tech.coaching.models import CoachConversationTurn, CoachSessionSnapshot
from english_tech.coaching.orchestrator import CoachOrchestrator
from english_tech.observability.metrics import metrics_store
from english_tech.security.rate_limit import allow_websocket_rate_limit, enforce_http_rate_limit
from english_tech.speech import speech_service

router = APIRouter()
orchestrator = CoachOrchestrator()


async def send_json(ws: WebSocket, payload: dict) -> None:
    await ws.send_text(json.dumps(payload))


async def stream_assistant_audio(ws: WebSocket, *, text: str, rate: str | None = None) -> None:
    clean_text = ' '.join(text.split()).strip()
    if not clean_text:
        return
    segments = speech_service.split_tts_segments(clean_text)
    for segment_index, segment_text in enumerate(segments):
        await send_json(
            ws,
            {
                'type': 'coach_audio_start',
                'mime_type': 'audio/wav',
                'text': segment_text,
                'segment_index': segment_index,
                'segment_total': len(segments),
            },
        )
        # Collect all audio bytes into one complete WAV buffer.
        # Streaming partial WAV chunks cannot be decoded by browser HTML5 Audio;
        # it requires a complete well-formed WAV file.
        try:
            audio_buffer = bytearray()
            async for chunk in speech_service.synthesize_speech_stream(segment_text, chunk_size=STREAM_AUDIO_CHUNK_BYTES, rate=rate):
                audio_buffer.extend(chunk)
        except Exception:
            await send_json(ws, {'type': 'coach_audio_error', 'message': 'TTS synthesis failed'})
            return

        total_bytes = len(audio_buffer)
        if audio_buffer:
            await send_json(
                ws,
                {
                    'type': 'coach_audio_chunk',
                    'sequence': 0,
                    'segment_index': segment_index,
                    'segment_total': len(segments),
                    'data': base64.b64encode(bytes(audio_buffer)).decode('ascii'),
                },
            )

        await send_json(
            ws,
            {
                'type': 'coach_audio_complete',
                'bytes': total_bytes,
                'segment_index': segment_index,
                'segment_total': len(segments),
                'is_final_segment': segment_index == len(segments) - 1,
            },
        )


@router.get('/bootstrap')
def coach_bootstrap(request: Request, user=Depends(get_verified_user)):
    enforce_http_rate_limit(
        request,
        category='coach_bootstrap',
        key_material=user.user_id,
        limit=AUTH_RATE_LIMIT_PER_MINUTE,
    )
    return orchestrator.build_bootstrap(user.learner_id).model_dump(mode='json')


@router.websocket('/ws/coach')
async def coach_websocket(ws: WebSocket):
    try:
        user = resolve_ws_verified_user(ws)
    except HTTPException:
        await ws.close(code=4401)
        return

    await ws.accept()
    history: list[CoachConversationTurn] = []
    session = CoachSessionSnapshot(
        session_id=f'coach_{uuid4().hex[:16]}',
        learner_id=user.learner_id,
        turn_count=0,
        last_action='none',
    )
    bootstrap = orchestrator.build_bootstrap(user.learner_id)
    intro = ' '.join(
        part.strip()
        for part in [bootstrap.spoken_greeting, bootstrap.spoken_progress_summary, bootstrap.spoken_next_step]
        if part.strip()
    )
    audio_buffer = bytearray()
    audio_stream_active = False
    audio_sample_rate = 16000
    audio_chunk_count = 0
    last_partial_text = ''

    async def handle_turn_text(text: str) -> None:
        nonlocal bootstrap
        history.append(CoachConversationTurn(role='learner', text=text))
        session.turn_count += 1
        response = orchestrator.handle_turn(user.learner_id, text, history=history)
        bootstrap = response.bootstrap
        session.last_action = response.action
        history.append(CoachConversationTurn(role='assistant', text=response.spoken_reply))

        rate = "115%" if bootstrap.level_band in ("proficiency", "advanced", "fluent") else "85%" if bootstrap.level_band == "beginner" else "100%"

        await send_json(ws, {'type': 'coach_session', 'session': session.model_dump(mode='json')})
        await send_json(ws, {'type': 'coach_bootstrap', 'bootstrap': bootstrap.model_dump(mode='json')})
        await send_json(ws, {'type': 'coach_reply', 'text': response.spoken_reply})
        # Note: stream_assistant_audio is awaitable and might take time.
        # We send the text first so the UI can show the bubble immediately.
        await stream_assistant_audio(ws, text=response.spoken_reply, rate=rate)
        if response.action == 'open_lesson' and response.lesson_to_open is not None:
            await send_json(
                ws,
                {
                    'type': 'open_lesson',
                    'lesson': response.lesson_to_open.model_dump(mode='json'),
                },
            )

    try:
        metrics_store.record_ws_event(channel='coach', event_type='connect')
        print(f"Coach WS connected: {user.learner_id}")

        rate = "115%" if bootstrap.level_band in ("proficiency", "advanced", "fluent") else "85%" if bootstrap.level_band == "beginner" else "100%"

        # Send initialization sequence immediately
        await send_json(ws, {'type': 'coach_session', 'session': session.model_dump(mode='json')})
        await send_json(ws, {'type': 'coach_bootstrap', 'bootstrap': bootstrap.model_dump(mode='json')})
        await send_json(ws, {'type': 'coach_reply', 'text': intro})
        history.append(CoachConversationTurn(role='assistant', text=intro))

        # Stream intro audio
        await stream_assistant_audio(ws, text=intro, rate=rate)

        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get('type')
            metrics_store.record_ws_event(channel='coach', event_type=str(msg_type or 'unknown'))
            if msg_type == 'audio_chunk':
                allowed = allow_websocket_rate_limit(
                    ws,
                    category='coach_audio_chunk',
                    key_material=user.user_id,
                    limit=LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE,
                )
            else:
                allowed = allow_websocket_rate_limit(
                    ws,
                    category='coach_message',
                    key_material=user.user_id,
                    limit=COACH_WS_RATE_LIMIT_PER_MINUTE,
                )
            if not allowed:
                await send_json(ws, {'type': 'error', 'message': 'Coach rate limit exceeded'})
                continue

            if msg_type == 'request_bootstrap':
                bootstrap = orchestrator.build_bootstrap(user.learner_id)
                await send_json(ws, {'type': 'coach_bootstrap', 'bootstrap': bootstrap.model_dump(mode='json')})
                continue

            if msg_type == 'audio_input_start':
                audio_buffer.clear()
                audio_stream_active = True
                audio_sample_rate = int(payload.get('sample_rate') or 16000)
                audio_chunk_count = 0
                last_partial_text = ''
                await send_json(ws, {'type': 'audio_input_ack', 'sample_rate': audio_sample_rate})
                continue

            if msg_type == 'audio_chunk':
                if not audio_stream_active:
                    await send_json(ws, {'type': 'error', 'message': 'Audio stream is not active'})
                    continue
                encoded = payload.get('data')
                if not encoded:
                    await send_json(ws, {'type': 'error', 'message': 'Audio chunk is missing data'})
                    continue
                try:
                    audio_buffer.extend(base64.b64decode(encoded))
                except Exception:
                    await send_json(ws, {'type': 'error', 'message': 'Audio chunk could not be decoded'})
                    continue
                audio_chunk_count += 1
                if len(audio_buffer) >= STREAM_PARTIAL_AUDIO_BYTES and audio_chunk_count % STREAM_PARTIAL_CHUNK_INTERVAL == 0:
                    try:
                        partial = await asyncio.to_thread(
                            speech_service.transcribe_pcm16,
                            bytes(audio_buffer),
                            sample_rate=audio_sample_rate,
                        )
                    except Exception:
                        partial = None
                    if partial is not None:
                        partial_text = str(partial.get('text') or '').strip()
                        if partial_text and partial_text != last_partial_text:
                            last_partial_text = partial_text
                            await send_json(
                                ws,
                                {
                                    'type': 'stt_partial',
                                    'text': partial_text,
                                    'duration_seconds': partial.get('duration_seconds'),
                                },
                            )
                continue

            if msg_type == 'audio_commit':
                if not audio_stream_active:
                    # Audio was never started; send a soft empty result instead of erroring.
                    await send_json(ws, {'type': 'stt_result', 'text': '', 'language': None, 'duration_seconds': 0})
                    continue
                audio_stream_active = False
                if not audio_buffer:
                    # No audio data received; treat as silence, not an error.
                    await send_json(ws, {'type': 'stt_result', 'text': '', 'language': None, 'duration_seconds': 0})
                    continue
                try:
                    transcription = await asyncio.to_thread(
                        speech_service.transcribe_pcm16,
                        bytes(audio_buffer),
                        sample_rate=audio_sample_rate,
                    )
                except ValueError as exc:
                    await send_json(ws, {'type': 'stt_result', 'text': '', 'language': None, 'duration_seconds': 0})
                    audio_buffer.clear()
                    continue
                except Exception:
                    await send_json(ws, {'type': 'stt_result', 'text': '', 'language': None, 'duration_seconds': 0})
                    audio_buffer.clear()
                    continue
                finally:
                    audio_buffer.clear()

                transcript = (transcription.get('text') or '').strip()
                
                filler_count = 0
                total_words = 0
                lexical_diversity = 0.0
                import re
                
                if transcript:
                    filler_count = len(re.findall(r'\b(um|uh|like)\b', transcript.lower()))
                    words = re.findall(r'\b\w+\b', transcript.lower())
                    total_words = len(words)
                    if total_words > 0:
                        unique_words = set(words)
                        lexical_diversity = round(len(unique_words) / total_words, 2)
                
                await send_json(
                    ws,
                    {
                        'type': 'stt_result',
                        'text': transcript,
                        'language': transcription.get('language'),
                        'duration_seconds': transcription.get('duration_seconds'),
                        'filler_words': filler_count,
                        'total_words': total_words,
                        'lexical_diversity': lexical_diversity,
                    },
                )
                if transcript:
                    await handle_turn_text(transcript)
                # If empty transcript, client already handles with "(no speech detected)" display.
                continue

            if msg_type == 'learner_text':
                text = str(payload.get('text', '')).strip()
                if not text:
                    await send_json(ws, {'type': 'error', 'message': 'Text is required'})
                    continue
                
                filler_count = 0
                total_words = 0
                lexical_diversity = 0.0
                import re
                
                if text:
                    filler_count = len(re.findall(r'\b(um|uh|like)\b', text.lower()))
                    words = re.findall(r'\b\w+\b', text.lower())
                    total_words = len(words)
                    if total_words > 0:
                        unique_words = set(words)
                        lexical_diversity = round(len(unique_words) / total_words, 2)
                
                await send_json(
                    ws,
                    {
                        'type': 'stt_result',
                        'text': text,
                        'language': 'en',
                        'duration_seconds': 0,
                        'filler_words': filler_count,
                        'total_words': total_words,
                        'lexical_diversity': lexical_diversity,
                    },
                )
                
                await handle_turn_text(text)
                continue

            await send_json(ws, {'type': 'error', 'message': f'Unsupported message type: {msg_type}'})
    except WebSocketDisconnect:
        return
