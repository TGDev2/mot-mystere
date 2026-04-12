import unittest

from motmystere.presentation.screens.main_menu import MainMenuScreen
from motmystere.presentation.screens.round_summary import RoundSummaryScreen


class FakeWidget:
    def __init__(self, bg="white"):
        self.bg = bg

    def cget(self, key):
        if key == "bg":
            return self.bg
        return None

    def pack(self, *args, **kwargs):
        return None


class FakeLabel(FakeWidget):
    pass


class RecordingUI:
    def __init__(self):
        self.calls = []

    def card(self, parent, **kwargs):
        self.calls.append(("card", kwargs))
        return FakeWidget(bg=kwargs.get("bg", "white"))

    def section_title(self, parent, text):
        self.calls.append(("section_title", text))

    def render_surface_action_card(self, parent, action, **kwargs):
        self.calls.append(("primary", action["callback_id"], kwargs))

    def render_action_list(self, parent, actions, **kwargs):
        self.calls.append(("secondary", [action["callback_id"] for action in actions], kwargs))

    def render_utility_actions(self, parent, actions, **kwargs):
        self.calls.append(("utility", [action["callback_id"] for action in actions], kwargs))

    def label(self, parent, **kwargs):
        self.calls.append(("label", kwargs.get("text")))
        return FakeLabel(bg=kwargs.get("bg", "white"))


class PriorityScreensTestCase(unittest.TestCase):
    def test_main_menu_priority_panel_renders_single_primary_then_secondary(self):
        screen = MainMenuScreen()
        ui = RecordingUI()
        app = type("App", (), {})()
        app.ui = ui
        app._get_action_callback = lambda callback_id: lambda: callback_id

        screen._render_priority_panel(
            app,
            FakeWidget(),
            {
                "primary_action": {
                    "callback_id": "start_personalized_recommendation",
                    "title": "Reco",
                    "label": "Manche recommandee",
                },
                "secondary_actions": [
                    {
                        "callback_id": "start_last_selection",
                        "title": "Reprise",
                        "label": "Reprise rapide",
                    }
                ],
            },
        )

        self.assertEqual(
            [call[0] for call in ui.calls],
            ["section_title", "primary", "section_title", "secondary"],
        )

    def test_main_menu_utility_zone_keeps_maintenance_separate(self):
        screen = MainMenuScreen()
        ui = RecordingUI()
        app = type("App", (), {})()
        app.ui = ui
        app._get_action_callback = lambda callback_id: lambda: callback_id
        app._build_catalog_summary = lambda: "Catalogue stable."

        screen._render_utility_zone(
            app,
            FakeWidget(),
            {
                "utility_actions": [
                    {"callback_id": "open_player_dashboard", "cta_text": "Profil"},
                    {"callback_id": "show_leaderboard", "cta_text": "Classement"},
                    {"callback_id": "show_editorial_cockpit_overlay", "cta_text": "Cockpit"},
                ]
            },
        )

        self.assertIn(("section_title", "Utilitaires"), ui.calls)
        self.assertIn(
            (
                "utility",
                [
                    "open_player_dashboard",
                    "show_leaderboard",
                    "show_editorial_cockpit_overlay",
                ],
                {"command_resolver": app._get_action_callback},
            ),
            ui.calls,
        )

    def test_round_summary_guided_follow_up_keeps_single_continue_primary(self):
        screen = RoundSummaryScreen()

        plan = screen._build_guided_follow_up_plan(
            {"utility_actions": [{"callback_id": "show_leaderboard"}]},
            {"mode_label": "Revision ciblee", "detail": "Encore une manche.", "session_kind": "review_failed_words"},
            {
                "category": "animaux",
                "difficulty": "Facile",
                "detail": "Le mot exact reste force hors rotation normale.",
            },
        )

        self.assertEqual(plan["primary_action"]["callback_id"], "continue_guided_session")
        self.assertEqual(plan["secondary_actions"][0]["callback_id"], "stop_guided_session_after_round")
        self.assertEqual(plan["utility_actions"], [{"callback_id": "show_leaderboard"}])


if __name__ == "__main__":
    unittest.main()
