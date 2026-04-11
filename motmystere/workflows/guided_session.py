from datetime import datetime

from ..solo_game_service import (
    build_guided_objective,
    build_guided_recommendation,
    build_review_recommendation,
    build_review_session_state,
    evaluate_guided_objective,
    evaluate_review_session,
    is_review_round_qualified,
)
from .ports import NullDialogPort


class GuidedSessionWorkflow:
    def __init__(self, app, *, dialog_port=None):
        self.app = app
        self.dialog_port = dialog_port or getattr(app, "dialog_port", None) or NullDialogPort()

    def build_guided_session_state(self, objective, dashboard, snapshot, *, source):
        objective_state = evaluate_guided_objective(
            objective,
            self.app.player,
            dashboard,
            snapshot,
        )
        recommendation = build_guided_recommendation(
            objective,
            self.app.player,
            dashboard,
            snapshot,
        )
        return {
            "session_kind": "guided_goal" if source == "primary_goal" else "guided_challenge",
            "mode_label": "Session guidee",
            "objective": objective,
            "objective_state": objective_state,
            "initial_progress_text": objective_state["progress_text"],
            "rounds": [],
            "recommendation": recommendation,
            "status": "active",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "resolution_status": None,
            "max_rounds": None,
            "targets": (),
        }

    def start_guided_session(self, source):
        player = self.app._load_player_from_form()
        if player is None:
            return

        dashboard, snapshot = self.app._get_progression_bundle()
        objective = build_guided_objective(snapshot, source=source)
        if objective is None:
            self.dialog_port.show_info(
                "Session guidee",
                "Aucun objectif concret n'est disponible pour lancer une session guidee.",
            )
            return

        guided_session = self.build_guided_session_state(
            objective,
            dashboard,
            snapshot,
            source=source,
        )
        recommendation = guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            self.dialog_port.show_info(
                "Session guidee",
                "La recommandation suivante n'est pas exploitable pour le moment.",
            )
            return

        self.app.guided_session = guided_session
        self.app._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self.app._start_round(preserve_guided_session=True)

    def start_review_session(self, review_key):
        player = self.app._load_player_from_form()
        if player is None:
            return

        _dashboard, snapshot = self.app._get_progression_bundle()
        review_options = (snapshot or {}).get("review_options") or {}
        review_option = review_options.get(review_key)
        if review_option is None:
            self.dialog_port.show_info(
                "Revision ciblee",
                "Aucune session de revision exploitable n'est disponible pour le moment.",
            )
            return

        review_session = build_review_session_state(review_option, self.app.categories)
        if review_session is None:
            self.dialog_port.show_info(
                "Revision ciblee",
                "Les cibles de revision ne sont plus jouables avec le catalogue actif.",
            )
            return

        recommendation = review_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            self.dialog_port.show_info(
                "Revision ciblee",
                "La revision ne peut pas demarrer sur une cible jouable.",
            )
            return

        self.app.guided_session = review_session
        self.app._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self.app._start_round(preserve_guided_session=True, review_mode=True)

    def handle_round_outcome(self, *, reason, outcome):
        guided_progress = None
        guided_recommendation = None
        if self.app.guided_session is None or self.app.guided_session.get("status") != "active":
            return {
                "guided_progress": None,
                "guided_recommendation": None,
                "completed": False,
            }

        session_kind = str(self.app.guided_session.get("session_kind") or "")
        round_record = {
            "title": outcome["title"],
            "result_message": outcome["result_message"],
            "category": self.app.session.category,
            "difficulty": self.app.session.difficulty,
            "secret_word": self.app.session.secret_word,
            "won": reason == "won",
            "end_reason": reason,
            "score_earned": outcome["score_earned"],
            "completed_goals": outcome["completed_goals"],
            "mastery_updates": outcome["mastery_updates"],
        }
        if session_kind == "review_weak_pair":
            round_record["qualified"] = is_review_round_qualified(
                self.app.guided_session,
                self.app.session,
                reason,
            )
        self.app.guided_session["rounds"].append(round_record)
        if session_kind.startswith("review_"):
            guided_progress = evaluate_review_session(self.app.guided_session)
            guided_recommendation = build_review_recommendation(self.app.guided_session)
        else:
            guided_progress = evaluate_guided_objective(
                self.app.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
            guided_recommendation = build_guided_recommendation(
                self.app.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
        self.app.guided_session["objective_state"] = guided_progress
        self.app.guided_session["recommendation"] = guided_recommendation
        self.app.guided_session["resolution_status"] = (
            guided_progress.get("resolution_status") if guided_progress is not None else None
        )
        if guided_progress is not None and guided_progress.get("completed"):
            self.app.guided_session["status"] = "completed"
            self.app.show_guided_session_summary()
            return {
                "guided_progress": guided_progress,
                "guided_recommendation": guided_recommendation,
                "completed": True,
            }

        return {
            "guided_progress": guided_progress,
            "guided_recommendation": guided_recommendation,
            "completed": False,
        }

    def continue_guided_session(self):
        if self.app.guided_session is None or self.app.guided_session.get("status") != "active":
            self.app.show_main_menu()
            return

        recommendation = self.app.guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            self.app.show_guided_session_summary()
            return

        self.app._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        review_mode = str(self.app.guided_session.get("session_kind") or "").startswith("review_")
        if review_mode:
            self.app._start_round(preserve_guided_session=True, review_mode=True)
            return
        self.app.replay_current_selection(preserve_guided_session=True)

    def stop_guided_session_after_round(self):
        if self.app.guided_session is None:
            self.app.show_main_menu()
            return

        self.app.guided_session["status"] = "stopped"
        self.app.show_guided_session_summary()

    def stop_guided_session_from_game(self):
        mode_label = (
            self.app.guided_session.get("mode_label", "Session active")
            if self.app.guided_session is not None
            else "Session active"
        )
        self.app.guided_session = None
        self.app.session = None
        self.app.show_main_menu(banner_message=f"{mode_label} arretee avant la fin de la manche.")

    def start_primary_goal(self):
        if self.app.player is not None and self.app.progression_snapshot is None:
            _, self.app.progression_snapshot = self.app._get_progression_bundle()

        if self.app.progression_snapshot and self.app.progression_snapshot.get("primary_goal"):
            self.app._sync_selection_from_goal(self.app.progression_snapshot["primary_goal"])

        self.app.start_game()

    def start_featured_challenge(self):
        if self.app.player is not None and self.app.progression_snapshot is None:
            _, self.app.progression_snapshot = self.app._get_progression_bundle()

        if self.app.progression_snapshot and self.app.progression_snapshot.get("featured_challenge"):
            self.app._sync_selection_from_goal(self.app.progression_snapshot["featured_challenge"])

        self.app.start_game()

    def start_personalized_recommendation(self):
        if self.app.player is not None:
            _, self.app.progression_snapshot = self.app._get_progression_bundle()

        if self.app.progression_snapshot and self.app.progression_snapshot.get("personalized_recommendation"):
            self.app._sync_selection_from_goal(self.app.progression_snapshot["personalized_recommendation"])

        self.app.start_game()
