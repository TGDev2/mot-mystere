import unittest

from progression import (
    build_progression_snapshot,
    get_newly_completed_goals,
    get_newly_reached_mastery_states,
)


class ProgressionTestCase(unittest.TestCase):
    def setUp(self):
        self.category_availability = {
            "animaux": ("Facile", "Moyen"),
            "pays": ("Facile", "Moyen", "Difficile"),
            "sports": ("Facile",),
        }

    def test_snapshot_starts_with_mastery_grid_and_validation_goal(self):
        snapshot = build_progression_snapshot(
            {"score_total": 0},
            {
                "selection_stats": [],
                "favorite_category": None,
                "best_difficulty": None,
            },
            self.category_availability,
        )

        mastery = snapshot["mastery"]
        goals = {goal["key"]: goal for goal in snapshot["goals"]}

        self.assertEqual(snapshot["primary_goal"]["key"], "validation_board")
        self.assertEqual(mastery["total_pairs"], 6)
        self.assertEqual(mastery["validated_pairs"], 0)
        self.assertEqual(mastery["mastered_pairs"], 0)
        self.assertEqual(mastery["focus_pair"]["category"], "animaux")
        self.assertEqual(mastery["focus_pair"]["difficulty"], "Facile")
        self.assertEqual(goals["validation_board"]["progress_text"], "0/6 paires validees")

    def test_snapshot_recommends_next_unvalidated_pair_then_mastery(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 1, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 4, "wins": 3},
                    {"category": "pays", "difficulty": "Moyen", "games_played": 2, "wins": 1},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
            },
            self.category_availability,
        )

        mastery = snapshot["mastery"]
        goals = {goal["key"]: goal for goal in snapshot["goals"]}

        self.assertEqual(mastery["focus_pair"]["category"], "pays")
        self.assertEqual(mastery["focus_pair"]["difficulty"], "Difficile")
        self.assertEqual(mastery["mastery_focus_pair"]["category"], "animaux")
        self.assertEqual(mastery["mastery_focus_pair"]["difficulty"], "Facile")
        self.assertEqual(goals["mastery_board"]["progress_text"], "1/6 paires maitrisees")
        self.assertEqual(goals["score_milestone"]["progress_text"], "260/500 pts")

    def test_new_mastery_states_detect_validation_and_mastery(self):
        before = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 1, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 2, "wins": 2},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
            },
            self.category_availability,
        )
        after = build_progression_snapshot(
            {"score_total": 520},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "pays", "difficulty": "Facile", "games_played": 3, "wins": 3},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Difficile"},
            },
            self.category_availability,
        )

        completed = {goal["key"] for goal in get_newly_completed_goals(before, after)}
        mastery_updates = {
            update["title"] for update in get_newly_reached_mastery_states(before, after)
        }

        self.assertEqual(completed, set())
        self.assertEqual(
            mastery_updates,
            {"Animaux / Facile valide", "Pays / Facile maitrise"},
        )


if __name__ == "__main__":
    unittest.main()
