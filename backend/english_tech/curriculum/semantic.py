from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from english_tech.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_TIMEOUT_SECONDS
from english_tech.curriculum.models import Exercise, ExerciseFeedback, Lesson
from english_tech.llm.client import JsonLlmClient


class SemanticExerciseDecision(BaseModel):
    passed: bool = False
    should_advance: bool = False
    error_type: str = Field(default='clarity', min_length=1, max_length=120)
    corrected_text: str | None = Field(default=None, max_length=2000)
    feedback_text: str = Field(min_length=1, max_length=3000)
    retry_prompt: str | None = Field(default=None, max_length=2000)
    focus: list[str] = Field(default_factory=list)

    @field_validator('focus', mode='before')
    @classmethod
    def _coerce_focus(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator('error_type', mode='before')
    @classmethod
    def _coerce_error_type(cls, value):
        if value is None or str(value).strip() == '':
            return 'success'
        return value


class SemanticLessonClient:
    def __init__(self) -> None:
        self.client = JsonLlmClient(
            provider=LLM_PROVIDER,
            base_url=LLM_BASE_URL,
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            timeout_seconds=LLM_TIMEOUT_SECONDS,
        )

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    def evaluate(
        self,
        *,
        lesson: Lesson,
        exercise: Exercise,
        learner_text: str,
        attempt_number: int,
        level_band: str,
        system_prompt: str = "You are an English lesson evaluator.",
    ) -> ExerciseFeedback | None:
        if not self.enabled:
            return None
        payload = self.client.generate_json(
            self._build_prompt(
                lesson=lesson,
                exercise=exercise,
                learner_text=learner_text,
                attempt_number=attempt_number,
                level_band=level_band,
            ),
            system_prompt=f"{system_prompt} Return strict JSON only."
        )
        if payload is None:
            return None
        try:
            decision = SemanticExerciseDecision.model_validate(payload)
        except Exception:
            return None

        focus = decision.focus or exercise.correction_focus or ['clarity']
        should_advance = bool(decision.should_advance)
        if decision.passed and not should_advance:
            should_advance = True
        if attempt_number >= exercise.max_attempts and not should_advance:
            should_advance = True
        feedback_text = decision.feedback_text.strip()
        if should_advance and not decision.passed and 'move on' not in feedback_text.lower():
            feedback_text = f'{feedback_text} We will move on, but keep practicing {", ".join(focus)}.'

        return ExerciseFeedback(
            exercise_id=exercise.exercise_id,
            passed=bool(decision.passed),
            should_advance=should_advance,
            error_type=decision.error_type,
            original_text=' '.join(learner_text.split()),
            corrected_text=decision.corrected_text,
            feedback_text=feedback_text,
            retry_prompt=decision.retry_prompt,
            focus=focus,
            attempt_number=attempt_number,
        )

    def _build_prompt(
        self,
        *,
        lesson: Lesson,
        exercise: Exercise,
        learner_text: str,
        attempt_number: int,
        level_band: str,
    ) -> str:
        expected = exercise.expected_answer or 'none'
        sample = exercise.sample_answer or 'none'
        focus = ', '.join(exercise.correction_focus) or 'clarity'
        vocab = ', '.join(lesson.target_vocabulary) or 'none'
        grammar = ', '.join(lesson.target_grammar) or 'none'
        pronunciation = ', '.join(lesson.pronunciation_focus) or 'none'
        return (
            'Return strict JSON only with keys: '
            'passed, should_advance, error_type, corrected_text, feedback_text, retry_prompt, focus. '
            'You must respect the lesson structure. '
            'If the expected answer contains blanks or placeholder names, treat a grammatically correct substitution as valid. '
            'If the learner answer is semantically correct but phrased differently, you may still pass it. '
            'Do not invent new lesson goals. '
            f'Learner level: {level_band}. '
            f'Lesson title: {lesson.title}. Lesson goal: {lesson.goal}. '
            f'Exercise type: {exercise.exercise_type.value}. '
            f'Exercise prompt: {exercise.prompt}. '
            f'Expected answer: {expected}. Sample answer: {sample}. '
            f'Correction focus: {focus}. '
            f'Target vocabulary: {vocab}. Target grammar: {grammar}. Pronunciation focus: {pronunciation}. '
            f'Attempt number: {attempt_number} of {exercise.max_attempts}. '
            f'Learner answer: {learner_text}. '
            'Keep feedback concise and spoken. '
            'Return JSON only.'
        )


semantic_lesson_client = SemanticLessonClient()
