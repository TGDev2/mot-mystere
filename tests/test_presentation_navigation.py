import unittest

from motmystere.game_logic import HangmanApp
from motmystere.presentation.navigation import (
    GUIDED_SESSION_SUMMARY_SCREEN,
    LEADERBOARD_OVERLAY,
    MAIN_MENU_SCREEN,
    PLAYER_DASHBOARD_OVERLAY,
    ROUND_SCREEN,
    ROUND_SUMMARY_SCREEN,
)


class StubVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class RecordingRouter:
    def __init__(self):
        self.calls = []

    def show_screen(self, route, **payload):
        self.calls.append(("screen", route, payload))

    def open_overlay(self, route, **payload):
        self.calls.append(("overlay", route, payload))


class PresentationNavigationTestCase(unittest.TestCase):
    def test_critical_flow_routes_main_screens_and_overlays(self):
        app = HangmanApp.__new__(HangmanApp)
        app.presentation_router = RecordingRouter()

        app.show_main_menu(banner_message="Profil recharge")
        app.show_game_screen()
        app.show_round_summary(
            "Victoire",
            "Mot trouve.",
            "Score mis a jour.",
            120,
            {"goals": [], "challenges": [], "mastery": {}, "primary_goal": None},
            [],
            [],
            None,
        )
        app.show_player_dashboard(7)
        app.show_leaderboard()
        app.show_guided_session_summary()

        self.assertEqual(
            app.presentation_router.calls,
            [
                ("screen", MAIN_MENU_SCREEN, {"banner_message": "Profil recharge"}),
                ("screen", ROUND_SCREEN, {}),
                (
                    "screen",
                    ROUND_SUMMARY_SCREEN,
                    {
                        "title": "Victoire",
                        "result_message": "Mot trouve.",
                        "score_summary": "Score mis a jour.",
                        "score_earned": 120,
                        "progression_snapshot": {
                            "goals": [],
                            "challenges": [],
                            "mastery": {},
                            "primary_goal": None,
                        },
                        "completed_goals": [],
                        "mastery_updates": [],
                        "breakdown": None,
                        "guided_progress": None,
                        "guided_recommendation": None,
                    },
                ),
                ("overlay", PLAYER_DASHBOARD_OVERLAY, {"player_id": 7}),
                ("overlay", LEADERBOARD_OVERLAY, {}),
                ("screen", GUIDED_SESSION_SUMMARY_SCREEN, {}),
            ],
        )

    def test_refresh_difficulty_options_is_safe_without_menu_widget(self):
        app = HangmanApp.__new__(HangmanApp)
        app.category_availability = {"animaux": ("Facile", "Moyen")}
        app.category_var = StubVar("animaux")
        app.difficulty_var = StubVar("Difficile")
        app.difficulty_menu = None

        app.refresh_difficulty_options()

        self.assertEqual(app.difficulty_var.get(), "Facile")


if __name__ == "__main__":
    unittest.main()
