import unittest

from progression import build_progression_snapshot, get_newly_completed_goals


class ProgressionTestCase(unittest.TestCase):
    def setUp(self):
        self.category_availability = {
            "animaux": ("Facile", "Moyen"),
            "pays": ("Facile", "Moyen", "Difficile"),
            "sports": ("Facile",),
        }

    def test_snapshot_starts_with_explicit_primary_goal(self):
        snapshot = build_progression_snapshot(
            {"score_total": 0},
            {
                "category_stats": [],
                "difficulty_stats": [],
                "favorite_category": None,
                "best_difficulty": None,
            },
            self.category_availability,
        )

        goals = {goal["key"]: goal for goal in snapshot["goals"]}

        self.assertEqual(snapshot["primary_goal"]["key"], "difficulty_passport")
        self.assertEqual(goals["difficulty_passport"]["category"], "animaux")
        self.assertEqual(goals["difficulty_passport"]["difficulty"], "Facile")
        self.assertEqual(goals["category_tour"]["progress_text"], "0/3 categories teste(es)")

    def test_snapshot_recommends_missing_difficulty_and_unplayed_category(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "category_stats": [
                    {"category": "animaux", "games_played": 2, "wins": 1},
                    {"category": "pays", "games_played": 1, "wins": 1},
                ],
                "difficulty_stats": [
                    {"difficulty": "Facile", "games_played": 2, "wins": 1, "average_score": 180},
                    {"difficulty": "Moyen", "games_played": 1, "wins": 1, "average_score": 140},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
            },
            self.category_availability,
        )

        goals = {goal["key"]: goal for goal in snapshot["goals"]}

        self.assertEqual(goals["difficulty_passport"]["difficulty"], "Difficile")
        self.assertEqual(goals["difficulty_passport"]["category"], "pays")
        self.assertEqual(goals["category_tour"]["category"], "sports")
        self.assertEqual(goals["score_milestone"]["progress_text"], "260/500 pts")

    def test_newly_completed_goals_are_detected(self):
        before = build_progression_snapshot(
            {"score_total": 260},
            {
                "category_stats": [{"category": "animaux", "games_played": 1, "wins": 1}],
                "difficulty_stats": [{"difficulty": "Facile", "games_played": 1, "wins": 1}],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
            },
            self.category_availability,
        )
        after = build_progression_snapshot(
            {"score_total": 520},
            {
                "category_stats": [
                    {"category": "animaux", "games_played": 2, "wins": 1},
                    {"category": "pays", "games_played": 2, "wins": 1},
                    {"category": "sports", "games_played": 1, "wins": 1},
                ],
                "difficulty_stats": [
                    {"difficulty": "Facile", "games_played": 2, "wins": 1, "average_score": 140},
                    {"difficulty": "Moyen", "games_played": 2, "wins": 1, "average_score": 170},
                    {"difficulty": "Difficile", "games_played": 1, "wins": 1, "average_score": 240},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Difficile"},
            },
            self.category_availability,
        )

        completed = {goal["key"] for goal in get_newly_completed_goals(before, after)}

        self.assertEqual(completed, {"difficulty_passport", "category_tour"})


if __name__ == "__main__":
    unittest.main()
