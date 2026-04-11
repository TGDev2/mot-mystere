import unittest

from motmystere.game_logic import HangmanApp
from motmystere.presentation.navigation import (
    CATALOG_OVERLAY,
    EDITORIAL_COCKPIT_OVERLAY,
    DIFFICULTY_CALIBRATION_OVERLAY,
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
        app.show_editorial_cockpit_overlay(banner_message="Priorites actualisees.")
        app.show_catalog_overlay(banner_message="Catalogue actualise.")
        app.show_difficulty_calibration_overlay()
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
                        "catalog_rotation": None,
                        "guided_progress": None,
                        "guided_recommendation": None,
                    },
                ),
                ("overlay", PLAYER_DASHBOARD_OVERLAY, {"player_id": 7}),
                ("overlay", LEADERBOARD_OVERLAY, {}),
                ("overlay", EDITORIAL_COCKPIT_OVERLAY, {"banner_message": "Priorites actualisees."}),
                ("overlay", CATALOG_OVERLAY, {"banner_message": "Catalogue actualise."}),
                ("overlay", DIFFICULTY_CALIBRATION_OVERLAY, {}),
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

    def test_start_personalized_recommendation_syncs_selection_before_starting(self):
        app = HangmanApp.__new__(HangmanApp)
        app.player = {"id": 7}
        app.progression_snapshot = {
            "personalized_recommendation": {
                "category": "pays",
                "difficulty": "Moyen",
            }
        }
        calls = []

        def fake_get_progression_bundle():
            snapshot = {
                "personalized_recommendation": {
                    "category": "pays",
                    "difficulty": "Moyen",
                }
            }
            app.progression_snapshot = snapshot
            return None, snapshot

        app._get_progression_bundle = fake_get_progression_bundle
        app._sync_selection_from_goal = lambda goal: calls.append(
            ("sync", goal["category"], goal["difficulty"])
        )
        app.start_game = lambda: calls.append(("start",))

        app.start_personalized_recommendation()

        self.assertEqual(
            calls,
            [
                ("sync", "pays", "Moyen"),
                ("start",),
            ],
        )

    def test_start_review_failed_words_syncs_selection_and_uses_review_mode(self):
        app = HangmanApp.__new__(HangmanApp)
        app.player = {"id": 7}
        app.categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}
        calls = []

        app._load_player_from_form = lambda: app.player
        app._get_progression_bundle = lambda: (
            None,
            {
                "review_options": {
                    "failed_words": {
                        "kind": "failed_words",
                        "title": "Reviser mes mots rates",
                        "targets": (
                            {
                                "category": "animaux",
                                "difficulty": "Facile",
                                "secret_word": "CHAT",
                                "label": "Animaux en Facile",
                            },
                        ),
                    }
                }
            },
        )
        app._sync_selection_to = lambda category, difficulty: calls.append(("sync", category, difficulty))
        app._start_round = lambda preserve_guided_session=False, review_mode=False: calls.append(
            ("start_round", preserve_guided_session, review_mode)
        )

        app.start_review_failed_words()

        self.assertEqual(app.guided_session["session_kind"], "review_failed_words")
        self.assertEqual(
            calls,
            [
                ("sync", "animaux", "Facile"),
                ("start_round", True, True),
            ],
        )

    def test_start_review_weak_pair_syncs_selection_and_uses_review_mode(self):
        app = HangmanApp.__new__(HangmanApp)
        app.player = {"id": 7}
        app.categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}
        calls = []

        app._load_player_from_form = lambda: app.player
        app._get_progression_bundle = lambda: (
            None,
            {
                "review_options": {
                    "weak_pair": {
                        "kind": "weak_pair",
                        "title": "Travailler mon reglage fragile",
                        "driver": "time_pressure",
                        "driver_label": "Temps",
                        "category": "animaux",
                        "difficulty": "Facile",
                        "target_value": 2,
                        "max_rounds": 3,
                    }
                }
            },
        )
        app._sync_selection_to = lambda category, difficulty: calls.append(("sync", category, difficulty))
        app._start_round = lambda preserve_guided_session=False, review_mode=False: calls.append(
            ("start_round", preserve_guided_session, review_mode)
        )

        app.start_review_weak_pair()

        self.assertEqual(app.guided_session["session_kind"], "review_weak_pair")
        self.assertEqual(
            calls,
            [
                ("sync", "animaux", "Facile"),
                ("start_round", True, True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
