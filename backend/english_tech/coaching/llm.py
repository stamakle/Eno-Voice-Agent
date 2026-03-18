from __future__ import annotations

from english_tech.coaching.models import CoachBootstrap, CoachConversationTurn, SemanticCoachDecision
from english_tech.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_TIMEOUT_SECONDS
from english_tech.llm.client import JsonLlmClient


class SemanticCoachClient:
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

    def generate_decision(
        self,
        *,
        bootstrap: CoachBootstrap,
        learner_text: str,
        history: list[CoachConversationTurn],
    ) -> SemanticCoachDecision | None:
        if not self.enabled:
            return None
        prompt = self._build_prompt(bootstrap=bootstrap, learner_text=learner_text, history=history)
        payload = self.client.generate_json(prompt)
        if payload is None:
            return None
        try:
            return SemanticCoachDecision.model_validate(payload)
        except Exception:
            return None

    def _build_prompt(self, *, bootstrap: CoachBootstrap, learner_text: str, history: list[CoachConversationTurn]) -> str:
        history_lines = []
        for turn in history[-6:]:
            history_lines.append(f'{turn.role}: {turn.text}')
        history_block = '\n'.join(history_lines) if history_lines else '(no prior turns)'
        
        if bootstrap.level_band in ("proficiency", "advanced", "fluent"):
            level_guidance = (
                "Provide stylistic recasting. Actively challenge the learner using a 'Debate & Devil's Advocate' mode on complex topics. "
                "Use advanced idioms, phrasal verbs, and dry sarcasm. If they ask 'why' a grammar rule exists, explain its deep etymology or history. "
                "DO NOT just say 'good job'. "
            )
        elif bootstrap.level_band == "intermediate":
            level_guidance = (
                "Provide Contextual Synonym Expansion: actively suggest better vocabulary if they overuse basic words like 'good'. "
                "Recognize and respond playfully to mild humor or sarcasm. If they drop a word in another language (Code-Switching), seamlessly translate it and teach the English equivalent. "
                "Praise them if they recognize and self-correct their own mistakes mid-sentence. "
            )
        elif bootstrap.level_band == "beginner":
            level_guidance = (
                "Use simple vocabulary, keep sentences very short, and gently correct basic grammar. "
                "Explicitly praise them if they recognize their own mistakes and self-correct mid-sentence. "
                "If they drop a word in their native language (Code-Switching), gently provide the English translation."
            )
            
        scenario_guidance = ""
        if bootstrap.preferred_scenario and bootstrap.preferred_scenario.lower() != "general conversation":
            scenario_guidance = (
                f"=== SCENARIO ROLEPLAY ===\n"
                f"You are currently conducting a specific roleplay scenario: '{bootstrap.preferred_scenario}'. "
                f"You must act as the appropriate persona(s) for this scenario. If the scenario involves multiple people (e.g., a panel job interview), you should act as multiple speakers, changing your tone/voice prefix for each."
            )
            
        memory_block = ""
        if bootstrap.memory_notes:
            notes = "\n- ".join(bootstrap.memory_notes)
            memory_block = f"=== LONG-TERM MEMORY ===\nYou know these facts about the user from previous sessions:\n- {notes}\nUse these to personalize the conversation."
            
        return (
            'You are Aura, an English coach assistant. '
            'You must choose only one intent from this set: set_level, progress_report, improvement_plan, open_lesson, none. '
            'You must reply in strict JSON with keys reply, intent, selected_level, extracted_memory. '
            'If the learner mentions a new persistent personal fact (like their job, hobbies, family, or goals), add a concise summary of it to the extracted_memory string array. '
            'Never invent lesson ids or curriculum paths. '
            f'{scenario_guidance}\n'
            f'{memory_block}\n'
            f'Learner level band: {bootstrap.level_band}. {level_guidance}'
            f'Needs onboarding: {str(bootstrap.needs_onboarding).lower()}. '
            f'Has resume lesson: {str(bootstrap.has_resume_lesson).lower()}. '
            f'Recommended lesson title: {bootstrap.recommended_lesson_title or "none"}. '
            f'Improvement focus: {", ".join(bootstrap.classification.improvement_focus) or "none"}. '
            'Valid level selections are beginner, advanced, proficiency. '
            f'Conversation history:\n{history_block}\n'
            f'Learner said: {learner_text}\n'
            'Return JSON only.'
        )
