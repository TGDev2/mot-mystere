import unittest
from unittest.mock import patch

from motmystere.workflows.round_loop import RoundLoopWorkflow


class StubVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class StubButton:
    def __init__(self):
        self.states = []

    def config(self, **kwargs):
        self.states.append(kwargs)


class StubDialog:
    def __init__(self):
        self.errors = []

    def show_error(self, title, message):
        self.errors.append((title, message))


class StubGuidedWorkflow:
    def __init__(self, payload=None):
        self.payload = payload or {
            "guided_progress": None,
            "guided_recommendation": None,
            "completed": False,
        }
        self.calls = []

    def handle_round_outcome(self, *, reason, outcome):
        self.calls.append((reason, outcome["title"]))
        return self.payload


class StubSession:
    def __init__(self):
        self.category = "animaux"
        self.difficulty = "Facile"
        self.secret_word = "CHAT"
        self.attempts_left = 5
        self.time_remaining = 42


class RoundLoopWorkflowTestCase(unittest.TestCase):
    def test_start_round_surfaces_unavailable_game_and_resets_selection_state(self):
        app = type("App", (), {})()
        app.guided_session = None
        app.category_display_var = StubVar("Animaux")
        app.category_labels = {"Animaux": "animaux"}
        app.category_var = StubVar("animaux")
        app.difficulty_var = StubVar("Facile")
        app.round_exploration_before = None
        app._load_player_from_form = lambda: {"id": 7}
        app._build_catalog_exploration_snapshot = lambda: {"selected_state": {"label": "avant"}}

        calls = []
        app.refresh_difficulty_options = lambda: calls.append("refresh")
        app.update_category_hint = lambda: calls.append("hint")
        app.show_game_screen = lambda: calls.append("screen")

        dialog = StubDialog()
        workflow = RoundLoopWorkflow(app, dialog_port=dialog)
        workflow.create_session_for_current_selection = lambda: (_ for _ in ()).throw(ValueError("indisponible"))

        workflow.start_round()

        self.assertIsNone(app.round_exploration_before)
        self.assertEqual(dialog.errors, [("Partie indisponible", "indisponible")])
        self.assertEqual(calls, ["refresh", "hint"])

    def test_finish_round_routes_summary_with_rotation_payload(self):
        app = type("App", (), {})()
        app.player = {"id": 7, "name": "Alice"}
        app.session = StubSession()
        app.category_availability = {"animaux": ("Facile",)}
        app.round_exploration_before = {"label": "avant", "state_label": "1/3", "progress_text": "1/3"}
        app.letter_buttons = {"A": StubButton()}
        app.progress_var = StubVar("")
        app.progression_snapshot = None
        app._build_surface_action_plan = lambda dashboard, snapshot, *, surface, round_result=None: {
            "surface": surface,
            "round_result": round_result,
            "primary_action": {"callback_id": "start_personalized_recommendation"},
        }

        calls = []
        app.cancel_timer = lambda: calls.append("cancel")
        app._build_catalog_exploration_snapshot = lambda **_kwargs: {
            "selected_state": {"label": "apres", "state_label": "2/3", "progress_text": "2/3"}
        }
        app._build_player_summary = lambda player: f"resume {player['name']}"
        app._ensure_guided_session_workflow = lambda: StubGuidedWorkflow()
        app.show_round_summary = lambda *args, **kwargs: calls.append(("summary", args, kwargs))

        workflow = RoundLoopWorkflow(app)
        with patch(
            "motmystere.workflows.round_loop.resolve_round",
            return_value={
                "player": {"id": 7, "name": "Alice"},
                "dashboard": {},
                "progression_snapshot": {"primary_goal": None},
                "completed_goals": [],
                "mastery_updates": [],
                "score_earned": 120,
                "score_summary": "120 pts",
                "breakdown": {"base_points": 40},
                "title": "Victoire",
                "result_message": "Mot trouve.",
            },
        ):
            workflow.finish_round("won")

        self.assertIn("cancel", calls)
        self.assertEqual(app.progress_var.get(), "resume Alice")
        self.assertEqual(app.letter_buttons["A"].states[-1]["state"], "disabled")
        summary_call = next(call for call in calls if isinstance(call, tuple) and call[0] == "summary")
        self.assertEqual(
            summary_call[2]["catalog_rotation"],
            {
                "before": {"label": "avant", "state_label": "1/3", "progress_text": "1/3"},
                "after": {"label": "apres", "state_label": "2/3", "progress_text": "2/3"},
            },
        )
        self.assertEqual(
            summary_call[2]["surface_action_plan"],
            {
                "surface": "round_summary",
                "round_result": "won",
                "primary_action": {"callback_id": "start_personalized_recommendation"},
            },
        )

    def test_on_timer_tick_finishes_round_when_session_expires(self):
        app = type("App", (), {})()

        class ExpiringSession:
            def tick(self):
                return "lost"

        app.session = ExpiringSession()
        workflow = RoundLoopWorkflow(app)

        calls = []
        workflow.refresh_game_view = lambda: calls.append("refresh")
        workflow.finish_round = lambda reason: calls.append(("finish", reason))

        workflow.on_timer_tick()

        self.assertEqual(calls, ["refresh", ("finish", "time")])

    def test_return_to_menu_clears_round_state_and_emits_guided_banner(self):
        app = type("App", (), {})()
        app.guided_session = {"status": "active", "mode_label": "Session guidee"}
        app.session = object()
        calls = []
        app.show_main_menu = lambda banner_message="": calls.append(banner_message)

        workflow = RoundLoopWorkflow(app)
        workflow.return_to_menu()

        self.assertIsNone(app.guided_session)
        self.assertIsNone(app.session)
        self.assertEqual(calls, ["Session guidee arretee."])


if __name__ == "__main__":
    unittest.main()
