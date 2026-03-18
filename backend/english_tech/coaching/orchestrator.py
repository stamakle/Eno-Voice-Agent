from __future__ import annotations

from english_tech.coaching.analysis import classify_learner, level_label
from english_tech.coaching.llm import SemanticCoachClient
from english_tech.coaching.messages import (
    build_next_step,
    build_progress_summary,
    build_resume_offer,
    build_spoken_greeting,
)
from english_tech.coaching.models import CoachBootstrap, CoachConversationTurn, CoachTurnResponse, SemanticCoachDecision
from english_tech.curriculum.agent import CurriculumAgent, NextLessonRequest
from english_tech.curriculum.models import LevelBand, NextLessonSelection
from english_tech.curriculum.store import CurriculumStore
from english_tech.learners.results import LessonResultStore
from english_tech.learners.store import LearnerStore




class CoachOrchestrator:
    def __init__(self, *, curriculum_store: CurriculumStore | None = None, curriculum_agent: CurriculumAgent | None = None, learner_store: LearnerStore | None = None, result_store: LessonResultStore | None = None, semantic_client: SemanticCoachClient | None = None):
        self.curriculum_store = curriculum_store or CurriculumStore()
        self.curriculum_agent = curriculum_agent or CurriculumAgent(store=self.curriculum_store)
        self.learner_store = learner_store or LearnerStore()
        self.result_store = result_store or LessonResultStore()
        self.semantic_client = semantic_client or SemanticCoachClient()

    def build_bootstrap(self, learner_id: str) -> CoachBootstrap:
        profile = self.learner_store.get_or_create_profile(learner_id)
        results = self.result_store.list_results(learner_id)
        selection = self.curriculum_agent.select_next_lesson(
            NextLessonRequest(
                learner_id=learner_id,
                course_id=profile.level_band.value,
                completed_lessons=profile.completed_lessons,
                weak_topics=profile.weak_topics,
                review_queue=profile.review_queue,
                learner_goals=profile.goals,
            )
        )
        recommended_title = self._lesson_title(selection)
        due_reviews = self.learner_store.due_reviews(learner_id)
        classification = classify_learner(profile, results)
        needs_onboarding = not profile.onboarding_completed
        has_resume_lesson = selection is not None and len(profile.completed_lessons) > 0
        bootstrap = CoachBootstrap(
            learner_id=profile.learner_id,
            display_name=profile.display_name,
            level_band=profile.level_band.value,
            level_label=level_label(profile.level_band),
            needs_onboarding=needs_onboarding,
            has_resume_lesson=has_resume_lesson,
            total_completed_lessons=len(profile.completed_lessons),
            review_count_due=len(due_reviews),
            weak_topics=profile.weak_topics,
            recommended_next_lesson=selection,
            recommended_lesson_title=recommended_title,
            spoken_greeting=build_spoken_greeting(
                display_name=profile.display_name,
                level_label=level_label(profile.level_band),
                needs_onboarding=needs_onboarding,
                has_resume_lesson=has_resume_lesson,
                recommended_title=recommended_title,
            ),
            spoken_progress_summary=build_progress_summary(
                classification,
                total_completed_lessons=len(profile.completed_lessons),
                review_count_due=len(due_reviews),
            ),
            spoken_next_step="Preparing next step.",
            spoken_resume_offer=build_resume_offer(recommended_title),
            classification=classification,
        )
        bootstrap.spoken_next_step = build_next_step(bootstrap=bootstrap)
        return bootstrap

    def handle_turn(self, learner_id: str, text: str, *, history: list[CoachConversationTurn] | None = None) -> CoachTurnResponse:
        normalized = self._normalize(text)
        bootstrap = self.build_bootstrap(learner_id)
        semantic_decision = self._semantic_decision(bootstrap=bootstrap, learner_text=text, history=history or [])
        if semantic_decision is not None:
            response = self._apply_semantic_decision(
                learner_id=learner_id,
                bootstrap=bootstrap,
                decision=semantic_decision,
                normalized=normalized,
            )
            if response is not None:
                return response

        reply = "I didn't quite catch that. Could you repeat it?"
        if bootstrap.needs_onboarding:
            reply = "I still need your level. Tell me if you are a beginner, advanced, or fluent."

        return CoachTurnResponse(spoken_reply=reply, action="none", bootstrap=bootstrap)

    def _semantic_decision(self, *, bootstrap: CoachBootstrap, learner_text: str, history: list[CoachConversationTurn]) -> SemanticCoachDecision | None:
        return self.semantic_client.generate_decision(
            bootstrap=bootstrap,
            learner_text=learner_text,
            history=history,
        )

    def _apply_semantic_decision(self, *, learner_id: str, bootstrap: CoachBootstrap, decision: SemanticCoachDecision, normalized: str) -> CoachTurnResponse | None:
        intent = decision.intent.strip().lower()
        reply = decision.reply.strip()
        if not reply:
            return None
            
        if decision.extracted_memory:
            profile = self.learner_store.get_or_create_profile(learner_id)
            for mem in decision.extracted_memory:
                if mem and mem not in profile.memory_notes:
                    profile.memory_notes.append(mem)
            self.learner_store.save_profile(profile)
            bootstrap = self.build_bootstrap(learner_id)

        if intent == "set_level" and bootstrap.needs_onboarding:
            level_value = self._normalize_level_value(decision.selected_level)
            if level_value is None:
                return None
            updated_profile = self.learner_store.get_or_create_profile(learner_id)
            updated_profile.level_band = LevelBand(level_value)
            updated_profile.onboarding_completed = True
            self.learner_store.save_profile(updated_profile)
            updated_bootstrap = self.build_bootstrap(learner_id)
            return CoachTurnResponse(spoken_reply=reply, action="none", bootstrap=updated_bootstrap)

        if intent == "progress_report":
            return CoachTurnResponse(spoken_reply=reply, action="none", bootstrap=bootstrap)

        if intent == "improvement_plan":
            return CoachTurnResponse(spoken_reply=reply, action="none", bootstrap=bootstrap)

        if intent == "open_lesson" and bootstrap.recommended_next_lesson is not None and not bootstrap.needs_onboarding:
            return CoachTurnResponse(
                spoken_reply=reply,
                action="open_lesson",
                lesson_to_open=bootstrap.recommended_next_lesson,
                bootstrap=bootstrap,
            )

        if intent == "none":
            return CoachTurnResponse(spoken_reply=reply, action="none", bootstrap=bootstrap)

        return None



    def _normalize_level_value(self, level: str | None) -> str | None:
        if level is None:
            return None
        normalized = self._normalize(level)
        if normalized in {"beginner", "advanced", "proficiency"}:
            return normalized
        if normalized == "fluent":
            return "proficiency"
        return None

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _lesson_title(self, selection: NextLessonSelection | None) -> str | None:
        """Return the human-readable title for the selected lesson, or None."""
        if selection is None:
            return None
        try:
            template = self.curriculum_store.get_template(selection.course_id)
            if template is None:
                return None
            for chapter in template.chapters:
                if chapter.chapter_id == selection.chapter_id:
                    for lesson in chapter.lessons:
                        if lesson.lesson_id == selection.lesson_id:
                            return lesson.title
        except Exception:
            return None
        return None
