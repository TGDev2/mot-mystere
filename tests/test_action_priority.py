import unittest

from motmystere.action_priority import build_surface_action_plan


class ActionPriorityTestCase(unittest.TestCase):
    def test_home_new_player_exposes_single_primary_action_and_disabled_profile(self):
        plan = build_surface_action_plan(None, None, surface="home")

        self.assertEqual(plan["primary_action"]["callback_id"], "start_game")
        self.assertEqual(plan["secondary_actions"], [])
        profile_action = next(
            action for action in plan["utility_actions"] if action["callback_id"] == "open_player_dashboard"
        )
        self.assertFalse(profile_action["enabled"])

    def test_home_history_prioritizes_personalized_recommendation_then_last_selection(self):
        dashboard = {
            "recent_games": [
                {
                    "category": "animaux",
                    "difficulty": "Facile",
                    "won": False,
                }
            ]
        }
        snapshot = {
            "personalized_recommendation": {
                "category": "pays",
                "difficulty": "Moyen",
                "title": "Reprendre Pays en Moyen",
                "detail": "La pression recente reste surtout sur ce reglage.",
            },
            "review_options": {
                "failed_words": {
                    "category": "animaux",
                    "difficulty": "Facile",
                    "title": "Reviser mes mots rates",
                    "detail": "Deux mots recusent encore la progression.",
                },
                "weak_pair": {
                    "category": "sports",
                    "difficulty": "Difficile",
                    "title": "Travailler mon reglage fragile",
                    "detail": "Le chrono reste fragile sur cette paire.",
                },
            },
            "primary_goal": {
                "title": "Carte de validation",
                "detail": "Encore une paire a valider.",
            },
            "featured_challenge": {
                "title": "Defi de regularite",
                "detail": "Enchainez les victoires recentes.",
            },
        }

        plan = build_surface_action_plan(dashboard, snapshot, surface="home")

        self.assertEqual(plan["primary_action"]["callback_id"], "start_personalized_recommendation")
        self.assertEqual(
            [action["callback_id"] for action in plan["secondary_actions"]],
            [
                "start_last_selection",
                "start_review_failed_words",
                "start_review_weak_pair",
                "start_guided_primary_goal_session",
                "start_guided_featured_challenge_session",
                "start_game",
            ],
        )

    def test_round_summary_win_prioritizes_recommendation_then_replay(self):
        dashboard = {
            "recent_games": [
                {
                    "category": "animaux",
                    "difficulty": "Facile",
                    "won": True,
                }
            ]
        }
        snapshot = {
            "personalized_recommendation": {
                "category": "pays",
                "difficulty": "Moyen",
                "title": "Reprendre Pays en Moyen",
                "detail": "Le moteur propose un autre levier.",
            },
            "primary_goal": {
                "title": "Carte de maitrise",
                "detail": "Poursuivez la paire la plus rentable.",
            },
        }

        plan = build_surface_action_plan(
            dashboard,
            snapshot,
            surface="round_summary",
            round_result="won",
        )

        self.assertEqual(plan["primary_action"]["callback_id"], "start_personalized_recommendation")
        self.assertEqual(
            [action["callback_id"] for action in plan["secondary_actions"]],
            [
                "replay_current_selection",
                "start_guided_primary_goal_session",
                "return_to_menu",
            ],
        )

    def test_round_summary_loss_prioritizes_review_before_recommendation(self):
        dashboard = {
            "recent_games": [
                {
                    "category": "animaux",
                    "difficulty": "Facile",
                    "won": False,
                }
            ]
        }
        snapshot = {
            "personalized_recommendation": {
                "category": "pays",
                "difficulty": "Moyen",
                "title": "Reprendre Pays en Moyen",
                "detail": "Le moteur propose un autre levier.",
            },
            "review_options": {
                "failed_words": {
                    "category": "animaux",
                    "difficulty": "Facile",
                    "title": "Reviser mes mots rates",
                    "detail": "Transformez les defaites recentes en revision.",
                },
                "weak_pair": {
                    "category": "sports",
                    "difficulty": "Difficile",
                    "title": "Travailler mon reglage fragile",
                    "detail": "Le chrono reste fragile sur cette paire.",
                },
            },
            "primary_goal": {
                "title": "Carte de validation",
                "detail": "Encore une paire a valider.",
            },
        }

        plan = build_surface_action_plan(
            dashboard,
            snapshot,
            surface="round_summary",
            round_result="attempts",
        )

        self.assertEqual(plan["primary_action"]["callback_id"], "start_review_failed_words")
        self.assertEqual(
            [action["callback_id"] for action in plan["secondary_actions"]],
            [
                "start_review_weak_pair",
                "start_personalized_recommendation",
                "replay_current_selection",
                "start_guided_primary_goal_session",
                "return_to_menu",
            ],
        )
        self.assertEqual(plan["reason_line"], plan["primary_action"]["reason_line"])


if __name__ == "__main__":
    unittest.main()
