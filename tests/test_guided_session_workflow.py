import unittest
from unittest.mock import patch

from motmystere.workflows.guided_session import GuidedSessionWorkflow


class GuidedSessionWorkflowTestCase(unittest.TestCase):
    def test_start_guided_session_sets_state_and_starts_round(self):
        app = type("App", (), {})()
        app.player = {"id": 7}
        app.guided_session = None
        app._load_player_from_form = lambda: app.player
        app._get_progression_bundle = lambda: ({"recent_games": []}, {"primary_goal": {"title": "Objectif"}})

        calls = []
        app._sync_selection_to = lambda category, difficulty: calls.append(("sync", category, difficulty))
        app._start_round = lambda preserve_guided_session=False, review_mode=False: calls.append(
            ("start_round", preserve_guided_session, review_mode)
        )

        workflow = GuidedSessionWorkflow(app)
        workflow.build_guided_session_state = lambda objective, dashboard, snapshot, *, source: {
            "session_kind": "guided_goal",
            "status": "active",
            "recommendation": {
                "category": "animaux",
                "difficulty": "Facile",
            },
        }

        with patch(
            "motmystere.workflows.guided_session.build_guided_objective",
            return_value={"title": "Objectif"},
        ):
            workflow.start_guided_session("primary_goal")

        self.assertEqual(app.guided_session["session_kind"], "guided_goal")
        self.assertEqual(
            calls,
            [
                ("sync", "animaux", "Facile"),
                ("start_round", True, False),
            ],
        )

    def test_continue_guided_session_uses_review_mode_for_review_sessions(self):
        app = type("App", (), {})()
        app.guided_session = {
            "status": "active",
            "session_kind": "review_failed_words",
            "recommendation": {
                "category": "animaux",
                "difficulty": "Facile",
            },
        }

        calls = []
        app._sync_selection_to = lambda category, difficulty: calls.append(("sync", category, difficulty))
        app._start_round = lambda preserve_guided_session=False, review_mode=False: calls.append(
            ("start_round", preserve_guided_session, review_mode)
        )
        app.replay_current_selection = lambda preserve_guided_session=False: calls.append(
            ("replay", preserve_guided_session)
        )
        app.show_main_menu = lambda banner_message="": calls.append(("menu", banner_message))
        app.show_guided_session_summary = lambda: calls.append(("summary",))

        workflow = GuidedSessionWorkflow(app)
        workflow.continue_guided_session()

        self.assertEqual(
            calls,
            [
                ("sync", "animaux", "Facile"),
                ("start_round", True, True),
            ],
        )

    def test_handle_round_outcome_marks_completed_session_and_opens_summary(self):
        app = type("App", (), {})()
        app.session = type(
            "Session",
            (),
            {
                "category": "animaux",
                "difficulty": "Facile",
                "secret_word": "CHAT",
            },
        )()
        app.guided_session = {
            "status": "active",
            "session_kind": "guided_goal",
            "objective": {"title": "Valider animaux"},
            "rounds": [],
        }

        calls = []
        app.show_guided_session_summary = lambda: calls.append("summary")

        workflow = GuidedSessionWorkflow(app)
        with patch(
            "motmystere.workflows.guided_session.evaluate_guided_objective",
            return_value={
                "title": "Valider animaux",
                "progress_text": "1/1",
                "detail": "Objectif atteint.",
                "completed": True,
                "resolution_status": "resolved",
            },
        ), patch(
            "motmystere.workflows.guided_session.build_guided_recommendation",
            return_value={"category": "animaux", "difficulty": "Facile"},
        ):
            result = workflow.handle_round_outcome(
                reason="won",
                outcome={
                    "title": "Victoire",
                    "result_message": "Mot trouve.",
                    "score_earned": 120,
                    "completed_goals": [],
                    "mastery_updates": [],
                    "player": {"id": 7},
                    "dashboard": {},
                    "progression_snapshot": {"primary_goal": None},
                },
            )

        self.assertTrue(result["completed"])
        self.assertEqual(app.guided_session["status"], "completed")
        self.assertEqual(len(app.guided_session["rounds"]), 1)
        self.assertEqual(calls, ["summary"])


if __name__ == "__main__":
    unittest.main()
