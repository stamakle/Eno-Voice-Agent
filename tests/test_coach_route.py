from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'backend'))

TEST_DIR = tempfile.mkdtemp(prefix='english_tech_auth_tests_')
TEST_DB = Path(TEST_DIR) / 'auth_test.db'
os.environ['ENGLISH_TECH_ENV'] = 'development'
os.environ['ENGLISH_TECH_DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['ENGLISH_TECH_DATABASE_FALLBACK_URL'] = f'sqlite:///{TEST_DB}'
os.environ['ENGLISH_TECH_DB_AUTO_CREATE'] = 'true'
os.environ['ENGLISH_TECH_LLM_PROVIDER'] = 'none'

from fastapi.testclient import TestClient

from english_tech.api.routes import auth as auth_routes
from english_tech.api.routes import live_lesson as live_lesson_routes
from english_tech.coaching.models import SemanticCoachDecision
from english_tech.coaching.orchestrator import CoachOrchestrator
from english_tech.curriculum.agent import CurriculumAgent
from english_tech.curriculum.models import ExerciseFeedback
from english_tech.curriculum.store import CurriculumStore
from english_tech.db import init_db
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore
from english_tech.main import app
from english_tech.security.rate_limit import rate_limiter


class _FakeSemanticClient:
    @property
    def enabled(self) -> bool:
        return True

    def generate_decision(self, *, bootstrap, learner_text, history):
        return SemanticCoachDecision(
            reply='Understood. I will place you at the beginner level.',
            intent='set_level',
            selected_level='beginner',
        )


class CoachRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)
        cls.result_store = LessonResultStore()
        cls.learner_store = LearnerStore()
        cls.curriculum_store = CurriculumStore()
        cls.curriculum_agent = CurriculumAgent(store=cls.curriculum_store)

    def setUp(self) -> None:
        rate_limiter._events.clear()

    def _register(self, email: str, display_name: str = 'Test Learner'):
        response = self.client.post(
            '/api/auth/register',
            json={
                'email': email,
                'password': 'supersecret1',
                'display_name': display_name,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _drain_audio_events(self, ws) -> None:
        while True:
            event = ws.receive_json()
            if event['type'] in {'assistant_audio_complete', 'coach_audio_complete'} and event.get('is_final_segment', True):
                return

    def test_register_and_me(self) -> None:
        session = self._register('auth_me@example.com', 'Auth User')
        self.assertTrue(session['refresh_token'])
        me = self.client.get(
            '/api/auth/me',
            headers={'Authorization': f"Bearer {session['token']}"},
        )
        self.assertEqual(me.status_code, 200)
        payload = me.json()
        self.assertEqual(payload['email'], 'auth_me@example.com')
        self.assertTrue(payload['learner_id'].startswith('learner_'))

    def test_refresh_rotates_session(self) -> None:
        session = self._register('refresh@example.com', 'Refresh User')
        refresh = self.client.post(
            '/api/auth/refresh',
            json={'refresh_token': session['refresh_token']},
        )
        self.assertEqual(refresh.status_code, 200)
        refreshed = refresh.json()
        self.assertNotEqual(refreshed['token'], session['token'])
        self.assertNotEqual(refreshed['refresh_token'], session['refresh_token'])
        me = self.client.get(
            '/api/auth/me',
            headers={'Authorization': f"Bearer {refreshed['token']}"},
        )
        self.assertEqual(me.status_code, 200)

    def test_auth_rate_limit_kicks_in(self) -> None:
        original_limit = auth_routes.AUTH_RATE_LIMIT_PER_MINUTE
        auth_routes.AUTH_RATE_LIMIT_PER_MINUTE = 1
        try:
            first = self.client.post(
                '/api/auth/login',
                json={'email': 'nobody@example.com', 'password': 'supersecret1'},
            )
            self.assertEqual(first.status_code, 401)
            second = self.client.post(
                '/api/auth/login',
                json={'email': 'nobody@example.com', 'password': 'supersecret1'},
            )
            self.assertEqual(second.status_code, 429)
        finally:
            auth_routes.AUTH_RATE_LIMIT_PER_MINUTE = original_limit

    def test_coach_websocket_bootstrap_and_open_lesson(self) -> None:
        session = self._register('coach_ws@example.com', 'Coach User')
        token = session['token']

        with self.client.websocket_connect(f'/api/coach/ws/coach?token={token}') as ws:
            coach_session = ws.receive_json()
            self.assertEqual(coach_session['type'], 'coach_session')

            bootstrap_event = ws.receive_json()
            self.assertEqual(bootstrap_event['type'], 'coach_bootstrap')
            self.assertTrue(bootstrap_event['bootstrap']['needs_onboarding'])

            reply_event = ws.receive_json()
            self.assertEqual(reply_event['type'], 'coach_reply')
            self.assertIn('beginner, advanced, or fluent', reply_event['text'])
            self._drain_audio_events(ws)

            ws.send_json({'type': 'learner_text', 'text': 'I am fluent'})
            ws.receive_json()  # coach_session
            updated_bootstrap = ws.receive_json()
            self.assertEqual(updated_bootstrap['type'], 'coach_bootstrap')
            self.assertFalse(updated_bootstrap['bootstrap']['needs_onboarding'])
            self.assertEqual(updated_bootstrap['bootstrap']['level_band'], 'proficiency')
            ws.receive_json()  # coach_reply
            self._drain_audio_events(ws)

            ws.send_json({'type': 'learner_text', 'text': 'start lesson'})
            ws.receive_json()  # coach_session
            ws.receive_json()  # coach_bootstrap
            ws.receive_json()  # coach_reply
            self._drain_audio_events(ws)
            action_event = ws.receive_json()
            self.assertEqual(action_event['type'], 'open_lesson')
            self.assertEqual(action_event['lesson']['course_id'], 'proficiency')

    def test_coach_audio_streaming_flow(self) -> None:
        session = self._register('coach_stream@example.com', 'Coach Stream User')
        token = session['token']

        import english_tech.api.routes.coach as coach_routes

        original_transcribe = coach_routes.speech_service.transcribe_pcm16
        original_synthesize = coach_routes.speech_service.synthesize_speech

        async def fake_synthesize(text: str, **kwargs):
            return (b'RIFF' + text.encode('utf-8')) * 4

        def fake_transcribe(pcm_bytes: bytes, *, sample_rate: int = 16000, language: str | None = None):
            self.assertTrue(len(pcm_bytes) > 0)
            return {'text': 'I am beginner', 'language': 'en', 'duration_seconds': 0.6}

        coach_routes.speech_service.transcribe_pcm16 = fake_transcribe
        coach_routes.speech_service.synthesize_speech = fake_synthesize
        try:
            with self.client.websocket_connect(f'/api/coach/ws/coach?token={token}') as ws:
                self.assertEqual(ws.receive_json()['type'], 'coach_session')
                self.assertEqual(ws.receive_json()['type'], 'coach_bootstrap')
                self.assertEqual(ws.receive_json()['type'], 'coach_reply')
                self.assertEqual(ws.receive_json()['type'], 'coach_audio_start')
                self._drain_audio_events(ws)

                payload = base64.b64encode(b'\x00\x00\x10\x00' * 5000).decode('ascii')
                ws.send_json({'type': 'audio_input_start', 'sample_rate': 16000})
                self.assertEqual(ws.receive_json()['type'], 'audio_input_ack')
                for _ in range(12):
                    ws.send_json({'type': 'audio_chunk', 'data': payload})
                partial = ws.receive_json()
                self.assertEqual(partial['type'], 'stt_partial')
                ws.send_json({'type': 'audio_commit'})
                result = ws.receive_json()
                self.assertEqual(result['type'], 'stt_result')
                self.assertEqual(result['text'], 'I am beginner')
                self.assertEqual(ws.receive_json()['type'], 'coach_session')
                bootstrap = ws.receive_json()
                self.assertEqual(bootstrap['type'], 'coach_bootstrap')
                reply = ws.receive_json()
                self.assertEqual(reply['type'], 'coach_reply')
                self.assertTrue(reply['text'])
                self.assertEqual(ws.receive_json()['type'], 'coach_audio_start')
                self._drain_audio_events(ws)
        finally:
            coach_routes.speech_service.transcribe_pcm16 = original_transcribe
            coach_routes.speech_service.synthesize_speech = original_synthesize

    def test_lesson_websocket_uses_authenticated_learner_identity(self) -> None:
        session = self._register('lesson_ws@example.com', 'Lesson User')
        token = session['token']
        learner_id = session['user']['learner_id']
        profile = self.learner_store.get_or_create_profile(learner_id)
        profile.onboarding_completed = True
        self.learner_store.save_profile(profile)

        with self.client.websocket_connect(f'/ws/lesson?token={token}') as ws:
            ws.send_json({
                'type': 'join_lesson',
                'course_id': 'beginner',
                'chapter_id': 'introductions',
                'lesson_id': 'beg_intro_01',
            })
            session_state = ws.receive_json()
            self.assertEqual(session_state['type'], 'session_state')
            self.assertEqual(session_state['session']['learner_id'], learner_id)

    def test_semantic_coach_can_handle_non_keyword_level_language(self) -> None:
        session = self._register('semantic@example.com', 'Semantic User')
        learner_id = session['user']['learner_id']
        orchestrator = CoachOrchestrator(
            curriculum_store=self.curriculum_store,
            curriculum_agent=self.curriculum_agent,
            learner_store=self.learner_store,
            result_store=self.result_store,
            semantic_client=_FakeSemanticClient(),
        )
        response = orchestrator.handle_turn(learner_id, 'I am just getting started with English')
        self.assertEqual(response.bootstrap.level_band, 'beginner')
        self.assertFalse(response.bootstrap.needs_onboarding)

    def test_lesson_audio_streaming_flow(self) -> None:
        session = self._register('streaming@example.com', 'Streaming User')
        token = session['token']
        learner_id = session['user']['learner_id']
        profile = self.learner_store.get_or_create_profile(learner_id)
        profile.onboarding_completed = True
        self.learner_store.save_profile(profile)

        original_transcribe = live_lesson_routes.speech_service.transcribe_pcm16
        original_synthesize = live_lesson_routes.speech_service.synthesize_speech

        async def fake_synthesize(text: str, **kwargs):
            return (b'RIFF' + text.encode('utf-8')) * 8

        def fake_transcribe(pcm_bytes: bytes, *, sample_rate: int = 16000, language: str | None = None):
            self.assertEqual(sample_rate, 16000)
            self.assertTrue(len(pcm_bytes) > 0)
            return {
                'text': 'My name is Sam',
                'language': language or 'en',
                'duration_seconds': 0.5,
            }

        live_lesson_routes.speech_service.transcribe_pcm16 = fake_transcribe
        live_lesson_routes.speech_service.synthesize_speech = fake_synthesize
        try:
            with self.client.websocket_connect(f'/ws/lesson?token={token}') as ws:
                ws.send_json({
                    'type': 'join_lesson',
                    'course_id': 'beginner',
                    'chapter_id': 'introductions',
                    'lesson_id': 'beg_intro_01',
                })
                self.assertEqual(ws.receive_json()['type'], 'session_state')
                self.assertEqual(ws.receive_json()['type'], 'assistant_message')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)
                prompt = ws.receive_json()
                self.assertEqual(prompt['type'], 'lesson_prompt')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)

                pcm_chunk = base64.b64decode(base64.b64encode(b'\x00\x00\x10\x00' * 400))
                ws.send_json({'type': 'audio_input_start', 'sample_rate': 16000})
                ack = ws.receive_json()
                self.assertEqual(ack['type'], 'audio_input_ack')
                ws.send_json({'type': 'audio_chunk', 'data': base64.b64encode(pcm_chunk).decode('ascii')})
                ws.send_json({'type': 'audio_commit'})

                stt_result = ws.receive_json()
                self.assertEqual(stt_result['type'], 'stt_result')
                self.assertEqual(stt_result['text'], 'My name is Sam')

                correction = ws.receive_json()
                self.assertEqual(correction['type'], 'correction')
                self.assertIn('My name is Sam', correction['feedback']['original_text'])
                self.assertEqual(ws.receive_json()['type'], 'session_state')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)
        finally:
            live_lesson_routes.speech_service.transcribe_pcm16 = original_transcribe
            live_lesson_routes.speech_service.synthesize_speech = original_synthesize

    def test_lesson_stream_emits_partial_transcript(self) -> None:
        session = self._register('partial@example.com', 'Partial User')
        token = session['token']
        learner_id = session['user']['learner_id']
        profile = self.learner_store.get_or_create_profile(learner_id)
        profile.onboarding_completed = True
        self.learner_store.save_profile(profile)

        original_transcribe = live_lesson_routes.speech_service.transcribe_pcm16
        original_synthesize = live_lesson_routes.speech_service.synthesize_speech
        calls = {'count': 0}

        async def fake_synthesize(text: str, **kwargs):
            return b'RIFFtest'

        def fake_transcribe(pcm_bytes: bytes, *, sample_rate: int = 16000, language: str | None = None):
            calls['count'] += 1
            if calls['count'] == 1:
                return {'text': 'My name', 'language': 'en', 'duration_seconds': 0.5}
            return {'text': 'My name is Sam', 'language': 'en', 'duration_seconds': 1.0}

        live_lesson_routes.speech_service.transcribe_pcm16 = fake_transcribe
        live_lesson_routes.speech_service.synthesize_speech = fake_synthesize
        try:
            with self.client.websocket_connect(f'/ws/lesson?token={token}') as ws:
                ws.send_json({
                    'type': 'join_lesson',
                    'course_id': 'beginner',
                    'chapter_id': 'introductions',
                    'lesson_id': 'beg_intro_01',
                })
                self.assertEqual(ws.receive_json()['type'], 'session_state')
                self.assertEqual(ws.receive_json()['type'], 'assistant_message')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)
                self.assertEqual(ws.receive_json()['type'], 'lesson_prompt')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)

                ws.send_json({'type': 'audio_input_start', 'sample_rate': 16000})
                ws.receive_json()  # ack
                payload = base64.b64encode(b'\x00\x00\x10\x00' * 5000).decode('ascii')
                for _ in range(12):
                    ws.send_json({'type': 'audio_chunk', 'data': payload})
                partial = ws.receive_json()
                self.assertEqual(partial['type'], 'stt_partial')
                self.assertEqual(partial['text'], 'My name')
        finally:
            live_lesson_routes.speech_service.transcribe_pcm16 = original_transcribe
            live_lesson_routes.speech_service.synthesize_speech = original_synthesize

    def test_semantic_lesson_feedback_is_used_when_available(self) -> None:
        session = self._register('semantic_lesson@example.com', 'Semantic Lesson User')
        token = session['token']
        learner_id = session['user']['learner_id']
        profile = self.learner_store.get_or_create_profile(learner_id)
        profile.onboarding_completed = True
        self.learner_store.save_profile(profile)

        original_semantic = live_lesson_routes.semantic_lesson_client.evaluate
        original_synthesize = live_lesson_routes.speech_service.synthesize_speech

        async def fake_synthesize(text: str, **kwargs):
            return b'RIFFsemantic'

        def fake_semantic(**kwargs):
            exercise = kwargs['exercise']
            attempt_number = kwargs['attempt_number']
            return ExerciseFeedback(
                exercise_id=exercise.exercise_id,
                passed=True,
                should_advance=True,
                error_type='semantic_success',
                original_text=kwargs['learner_text'],
                corrected_text=None,
                feedback_text='Semantic grading accepted your answer.',
                retry_prompt=None,
                focus=['meaning'],
                attempt_number=attempt_number,
            )

        live_lesson_routes.semantic_lesson_client.evaluate = fake_semantic
        live_lesson_routes.speech_service.synthesize_speech = fake_synthesize
        try:
            with self.client.websocket_connect(f'/ws/lesson?token={token}') as ws:
                ws.send_json({
                    'type': 'join_lesson',
                    'course_id': 'beginner',
                    'chapter_id': 'introductions',
                    'lesson_id': 'beg_intro_01',
                })
                self.assertEqual(ws.receive_json()['type'], 'session_state')
                self.assertEqual(ws.receive_json()['type'], 'assistant_message')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)
                self.assertEqual(ws.receive_json()['type'], 'lesson_prompt')
                self.assertEqual(ws.receive_json()['type'], 'assistant_audio_start')
                self._drain_audio_events(ws)

                ws.send_json({'type': 'learner_text', 'text': 'Hello there, my name is Sam'})
                correction = ws.receive_json()
                self.assertEqual(correction['type'], 'correction')
                self.assertEqual(correction['text'], 'Semantic grading accepted your answer.')
        finally:
            live_lesson_routes.semantic_lesson_client.evaluate = original_semantic
            live_lesson_routes.speech_service.synthesize_speech = original_synthesize


if __name__ == '__main__':
    unittest.main()
