from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from english_tech.auth.deps import resolve_ws_verified_user
from english_tech.config import (
    LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE,
    LESSON_WS_RATE_LIMIT_PER_MINUTE,
    STREAM_AUDIO_CHUNK_BYTES,
    STREAM_PARTIAL_AUDIO_BYTES,
    STREAM_PARTIAL_CHUNK_INTERVAL,
)
from english_tech.curriculum.agent import CurriculumAgent
from english_tech.curriculum.models import LessonCompletionRequest, LessonPointer, LessonResult
from english_tech.curriculum.runtime import (
    build_lesson_intro,
    build_lesson_summary,
    build_lesson_system_prompt,
    build_review_items,
    derive_weak_topics,
    evaluate_exercise_response,
)
from english_tech.curriculum.semantic import semantic_lesson_client
from english_tech.curriculum.session import TutorSessionState
from english_tech.curriculum.store import CurriculumStore
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore
from english_tech.observability.metrics import metrics_store
from english_tech.security.rate_limit import allow_websocket_rate_limit
from english_tech.speech import speech_service

router = APIRouter()
store = CurriculumStore()
agent = CurriculumAgent(store=store)
learner_store = LearnerStore()
result_store = LessonResultStore()


async def send_json(ws: WebSocket, payload: dict) -> None:
    await ws.send_text(json.dumps(payload))


async def stream_assistant_audio(ws: WebSocket, *, text: str) -> None:
    clean_text = ' '.join(text.split()).strip()
    if not clean_text:
        return
    segments = speech_service.split_tts_segments(clean_text)
    for segment_index, segment_text in enumerate(segments):
        await send_json(
            ws,
            {
                'type': 'assistant_audio_start',
                'mime_type': 'audio/wav',
                'text': segment_text,
                'segment_index': segment_index,
                'segment_total': len(segments),
            },
        )
        sequence = 0
        total_bytes = 0
        try:
            async for chunk in speech_service.synthesize_speech_stream(segment_text, chunk_size=STREAM_AUDIO_CHUNK_BYTES):
                await send_json(
                    ws,
                    {
                        'type': 'assistant_audio_chunk',
                        'sequence': sequence,
                        'segment_index': segment_index,
                        'segment_total': len(segments),
                        'data': base64.b64encode(chunk).decode('ascii'),
                    },
                )
                sequence += 1
                total_bytes += len(chunk)
        except Exception:
            await send_json(ws, {'type': 'assistant_audio_error', 'message': 'TTS synthesis failed'})
            return

        await send_json(
            ws,
            {
                'type': 'assistant_audio_complete',
                'bytes': total_bytes,
                'segment_index': segment_index,
                'segment_total': len(segments),
                'is_final_segment': segment_index == len(segments) - 1,
            },
        )


@router.websocket('/ws/lesson')
async def lesson_websocket(ws: WebSocket):
    try:
        user = resolve_ws_verified_user(ws)
    except HTTPException:
        await ws.close(code=4401)
        return

    await ws.accept()
    session: TutorSessionState | None = None
    learner_profile = None
    audio_buffer = bytearray()
    audio_stream_active = False
    audio_sample_rate = 16000
    audio_chunk_count = 0
    last_partial_text = ''

    async def reject_rate_limit(message: str) -> None:
        await send_json(ws, {'type': 'error', 'message': message})

    async def handle_learner_text(learner_text: str) -> None:
        nonlocal session
        if session is None:
            await send_json(ws, {'type': 'error', 'message': 'Join a lesson before sending lesson events'})
            return

        exercise = session.current_exercise()
        if exercise is None:
            await send_json(ws, {'type': 'error', 'message': 'No active exercise'})
            return

        session.turn_count += 1
        session.add_turn('learner', learner_text or '[empty]')
        attempt_number = session.register_attempt()
        feedback = evaluate_exercise_response(
            session.lesson,
            exercise,
            learner_text,
            attempt_number=attempt_number,
        )
        if learner_profile is not None:
            semantic_feedback = semantic_lesson_client.evaluate(
                lesson=session.lesson,
                exercise=exercise,
                attempt_number=attempt_number,
                level_band=learner_profile.level_band.value,
                system_prompt=session.system_prompt,
            )
            if semantic_feedback is not None:
                feedback = semantic_feedback
        session.record_feedback(feedback, learner_text)
        session.add_turn('assistant', feedback.feedback_text)

        await send_json(
            ws,
            {
                'type': 'correction',
                'text': feedback.feedback_text,
                'focus': feedback.focus,
                'feedback': feedback.model_dump(mode='json'),
            },
        )
        await send_json(ws, {'type': 'session_state', 'session': session.snapshot().model_dump(mode='json')})
        await stream_assistant_audio(ws, text=feedback.feedback_text)

        next_exercise = session.current_exercise()
        if feedback.should_advance and next_exercise is not None:
            await send_json(
                ws,
                {
                    'type': 'lesson_prompt',
                    'exercise': next_exercise.model_dump(mode='json'),
                    'retry': False,
                },
            )
            await stream_assistant_audio(ws, text=next_exercise.prompt)
            return

        if not feedback.should_advance and exercise is not None:
            retry_prompt = feedback.retry_prompt or exercise.prompt
            await send_json(
                ws,
                {
                    'type': 'lesson_prompt',
                    'exercise': exercise.model_dump(mode='json'),
                    'retry': True,
                    'retry_prompt': feedback.retry_prompt,
                },
            )
            await stream_assistant_audio(ws, text=retry_prompt)
            return

        session.lesson_summary = build_lesson_summary(session.lesson, session.ordered_exercise_results())
        await send_json(ws, {'type': 'session_state', 'session': session.snapshot().model_dump(mode='json')})
        await send_json(
            ws,
            {
                'type': 'assistant_summary',
                'text': session.lesson_summary,
                'weak_topics': derive_weak_topics(session.lesson, session.ordered_exercise_results()),
            },
        )
        await stream_assistant_audio(ws, text=session.lesson_summary)
        await send_json(
            ws,
            {
                'type': 'lesson_ready_to_complete',
                'message': 'All lesson exercises are complete. Submit completion to save progress.',
            },
        )

    try:
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get('type')
            metrics_store.record_ws_event(channel='lesson', event_type=str(msg_type or 'unknown'))

            if msg_type == 'audio_chunk':
                allowed = allow_websocket_rate_limit(
                    ws,
                    category='lesson_audio_chunk',
                    key_material=user.user_id,
                    limit=LESSON_AUDIO_CHUNK_RATE_LIMIT_PER_MINUTE,
                )
            else:
                allowed = allow_websocket_rate_limit(
                    ws,
                    category='lesson_message',
                    key_material=user.user_id,
                    limit=LESSON_WS_RATE_LIMIT_PER_MINUTE,
                )
            if not allowed:
                await reject_rate_limit('Lesson rate limit exceeded')
                continue

            if msg_type == 'join_lesson':
                course_id = payload['course_id']
                chapter_id = payload['chapter_id']
                lesson_id = payload['lesson_id']

                learner_profile = learner_store.get_or_create_profile(user.learner_id)
                variant = agent.prepare_lesson(
                    learner_profile,
                    course_id=course_id,
                    chapter_id=chapter_id,
                    lesson_id=lesson_id,
                )
                system_prompt = build_lesson_system_prompt(
                    variant.lesson,
                    learner_profile,
                    personalization_focus=variant.personalization_focus,
                )
                session = TutorSessionState(
                    learner_id=user.learner_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                    lesson=variant.lesson,
                    variant_id=variant.variant_id,
                    personalization_focus=variant.personalization_focus,
                    system_prompt=system_prompt,
                )
                intro = build_lesson_intro(variant.lesson, learner_profile)
                session.add_turn('assistant', intro)
                await send_json(ws, {'type': 'session_state', 'session': session.snapshot().model_dump(mode='json')})
                await send_json(
                    ws,
                    {
                        'type': 'assistant_message',
                        'text': intro,
                        'system_prompt': system_prompt,
                        'variant_id': variant.variant_id,
                    },
                )
                await stream_assistant_audio(ws, text=intro)
                exercise = session.current_exercise()
                if exercise is not None:
                    await send_json(
                        ws,
                        {
                            'type': 'lesson_prompt',
                            'exercise': exercise.model_dump(mode='json'),
                            'retry': False,
                        },
                    )
                    await stream_assistant_audio(ws, text=exercise.prompt)
                continue

            if session is None:
                await send_json(ws, {'type': 'error', 'message': 'Join a lesson before sending lesson events'})
                continue

            if msg_type == 'request_state':
                await send_json(ws, {'type': 'session_state', 'session': session.snapshot().model_dump(mode='json')})
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
                    await send_json(ws, {'type': 'error', 'message': 'Audio stream is not active'})
                    continue
                audio_stream_active = False
                if not audio_buffer:
                    await send_json(ws, {'type': 'error', 'message': 'Audio stream is empty'})
                    continue
                try:
                    transcription = await asyncio.to_thread(
                        speech_service.transcribe_pcm16,
                        bytes(audio_buffer),
                        sample_rate=audio_sample_rate,
                    )
                except ValueError as exc:
                    await send_json(ws, {'type': 'error', 'message': str(exc)})
                    audio_buffer.clear()
                    continue
                except Exception as exc:
                    await send_json(ws, {'type': 'error', 'message': f'STT failed: {exc}'})
                    audio_buffer.clear()
                    continue
                finally:
                    audio_buffer.clear()

                transcript = (transcription.get('text') or '').strip()
                await send_json(
                    ws,
                    {
                        'type': 'stt_result',
                        'text': transcript,
                        'language': transcription.get('language'),
                        'duration_seconds': transcription.get('duration_seconds'),
                    },
                )
                if transcript:
                    await handle_learner_text(transcript)
                else:
                    await send_json(ws, {'type': 'error', 'message': 'No speech detected'})
                continue

            if msg_type == 'learner_text':
                learner_text = str(payload.get('text', '')).strip()
                if not learner_text:
                    await send_json(ws, {'type': 'error', 'message': 'Text is required'})
                    continue
                await handle_learner_text(learner_text)
                continue

            if msg_type == 'complete_lesson':
                if session.status != 'ready_for_completion':
                    await send_json(
                        ws,
                        {
                            'type': 'error',
                            'message': 'Complete the remaining exercises before marking the lesson complete.',
                        },
                    )
                    continue

                lesson_pointer = LessonPointer(
                    course_id=session.course_id,
                    chapter_id=session.chapter_id,
                    lesson_id=session.lesson.lesson_id,
                )
                exercise_results = session.ordered_exercise_results()
                
                total_exercises = len([r for r in exercise_results if r.exercise_type.value != 'recap'])
                passed_exercises = sum(1 for r in exercise_results if r.mastered and r.exercise_type.value != 'recap')
                grammar_accuracy = passed_exercises / total_exercises if total_exercises > 0 else 1.0

                weak_topics = payload.get('weak_topics') or derive_weak_topics(session.lesson, exercise_results)
                request = LessonCompletionRequest(
                    learner_id=session.learner_id,
                    lesson=lesson_pointer,
                    variant_id=session.variant_id,
                    completed=True,
                    grammar_accuracy=grammar_accuracy,
                    pronunciation_accuracy=payload.get('pronunciation_accuracy'),
                    notes=payload.get('notes', []),
                    weak_topics=weak_topics,
                    summary_text=payload.get('summary_text') or session.lesson_summary,
                    exercise_results=exercise_results,
                    turn_count=session.turn_count,
                )
                result = LessonResult(
                    learner_id=request.learner_id,
                    lesson=request.lesson,
                    variant_id=request.variant_id,
                    completed=request.completed,
                    grammar_accuracy=request.grammar_accuracy,
                    pronunciation_accuracy=request.pronunciation_accuracy,
                    weak_topics=request.weak_topics,
                    notes=request.notes,
                    summary_text=request.summary_text,
                    exercise_results=request.exercise_results,
                    turn_count=request.turn_count,
                )
                result_store.append_result(result)

                base_lesson = store.get_lesson(
                    course_id=session.course_id,
                    chapter_id=session.chapter_id,
                    lesson_id=session.lesson.lesson_id,
                ) or session.lesson
                review_items = build_review_items(
                    lesson_pointer=lesson_pointer,
                    lesson=base_lesson,
                    weak_topics=weak_topics,
                    completed_at=result.completed_at,
                )
                learner_store.apply_lesson_result(session.learner_id, result, review_items=review_items)
                session.status = 'completed'
                await send_json(ws, {'type': 'session_state', 'session': session.snapshot().model_dump(mode='json')})
                completion_text = 'Lesson complete. Great work today.'
                await send_json(
                    ws,
                    {
                        'type': 'lesson_completed',
                        'result': result.model_dump(mode='json'),
                        'review_items': [item.model_dump(mode='json') for item in review_items],
                        'text': completion_text,
                    },
                )
                await stream_assistant_audio(ws, text=completion_text)
                continue

            await send_json(ws, {'type': 'error', 'message': f'Unsupported message type: {msg_type}'})
    except WebSocketDisconnect:
        return
