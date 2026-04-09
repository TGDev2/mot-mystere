import unittest

from motmystere.progression import (
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

    def _recent_game(
        self,
        category,
        difficulty,
        *,
        secret_word=None,
        won,
        end_reason,
        attempts_left,
        time_remaining,
    ):
        return {
            "category": category,
            "difficulty": difficulty,
            "secret_word": secret_word,
            "won": won,
            "end_reason": end_reason,
            "attempts_left": attempts_left,
            "time_remaining": time_remaining,
        }

    def test_snapshot_starts_with_mastery_grid_and_validation_goal(self):
        snapshot = build_progression_snapshot(
            {"score_total": 0},
            {
                "selection_stats": [],
                "favorite_category": None,
                "best_difficulty": None,
                "recent_form": {"recent_games": 0, "recent_wins": 0},
            },
            self.category_availability,
        )

        mastery = snapshot["mastery"]
        goals = {goal["key"]: goal for goal in snapshot["goals"]}
        challenges = snapshot["challenges"]

        self.assertEqual(snapshot["primary_goal"]["key"], "validation_board")
        self.assertEqual(snapshot["featured_challenge"]["key"], challenges[0]["key"])
        self.assertEqual(mastery["total_pairs"], 6)
        self.assertEqual(mastery["validated_pairs"], 0)
        self.assertEqual(mastery["mastered_pairs"], 0)
        self.assertEqual(mastery["focus_pair"]["category"], "animaux")
        self.assertEqual(mastery["focus_pair"]["difficulty"], "Facile")
        self.assertEqual(goals["validation_board"]["progress_text"], "0/6 paires validees")
        self.assertEqual(goals["validation_board"]["family"], "validation_board")
        self.assertEqual(goals["validation_board"]["current_value"], 0)
        self.assertEqual(goals["validation_board"]["target_value"], 6)
        self.assertEqual(challenges[0]["title"], "Defi de validation")
        self.assertEqual(challenges[0]["progress_text"], "0/1 victoire(s)")
        self.assertEqual(challenges[0]["family"], "challenge_pair")
        self.assertEqual(challenges[0]["target_value"], 1)

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
                "recent_form": {"recent_games": 5, "recent_wins": 2},
            },
            self.category_availability,
        )

        mastery = snapshot["mastery"]
        goals = {goal["key"]: goal for goal in snapshot["goals"]}
        challenges = {challenge["key"]: challenge for challenge in snapshot["challenges"]}

        self.assertEqual(mastery["focus_pair"]["category"], "pays")
        self.assertEqual(mastery["focus_pair"]["difficulty"], "Difficile")
        self.assertEqual(mastery["mastery_focus_pair"]["category"], "animaux")
        self.assertEqual(mastery["mastery_focus_pair"]["difficulty"], "Facile")
        self.assertEqual(goals["mastery_board"]["progress_text"], "1/6 paires maitrisees")
        self.assertEqual(goals["score_milestone"]["progress_text"], "260/500 pts")
        self.assertEqual(goals["score_milestone"]["family"], "score_milestone")
        self.assertEqual(goals["score_milestone"]["target_value"], 500)
        self.assertEqual(challenges["challenge_recent_form_3"]["progress_text"], "2/3 victoire(s) recentes")
        self.assertEqual(challenges["challenge_recent_form_3"]["family"], "challenge_recent_form")
        self.assertEqual(challenges["challenge_recent_form_3"]["target_value"], 3)
        self.assertEqual(snapshot["featured_challenge"]["key"], "challenge_pair_pays_Difficile_1")

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
                "recent_form": {"recent_games": 2, "recent_wins": 1},
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
                "recent_form": {"recent_games": 3, "recent_wins": 2},
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

    def test_personalized_recommendation_falls_back_to_mastery_without_strong_recent_signal(self):
        snapshot = build_progression_snapshot(
            {"score_total": 120},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 1, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 2, "wins": 0},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 2, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=25,
                    ),
                    self._recent_game(
                        "animaux",
                        "Facile",
                        won=True,
                        end_reason="won",
                        attempts_left=7,
                        time_remaining=40,
                    ),
                ],
            },
            self.category_availability,
        )

        recommendation = snapshot["personalized_recommendation"]

        self.assertEqual(snapshot["learning_profile"]["dominant_driver"], "mastery_gap")
        self.assertEqual(recommendation["driver"], "mastery_gap")
        self.assertEqual(recommendation["category"], "pays")
        self.assertEqual(recommendation["difficulty"], "Facile")
        self.assertIsNone(snapshot["review_options"]["weak_pair"])

    def test_review_options_expose_recent_failed_words_with_dedup_and_original_settings(self):
        snapshot = build_progression_snapshot(
            {"score_total": 120},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 1, "wins": 0},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 5, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "animaux",
                        "Facile",
                        secret_word="CHAT",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=33,
                    ),
                    self._recent_game(
                        "animaux",
                        "Facile",
                        secret_word="CHAT",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=12,
                    ),
                    self._recent_game(
                        "pays",
                        "Difficile",
                        secret_word="JAPON",
                        won=False,
                        end_reason="time",
                        attempts_left=2,
                        time_remaining=0,
                    ),
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        secret_word="LOUP",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=19,
                    ),
                    self._recent_game(
                        "sports",
                        "Facile",
                        secret_word="GOLF",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=17,
                    ),
                ],
            },
            self.category_availability,
        )

        failed_words = snapshot["review_options"]["failed_words"]
        targets = failed_words["targets"]

        self.assertEqual(failed_words["kind"], "failed_words")
        self.assertEqual(failed_words["count"], 3)
        self.assertEqual(
            [(target["category"], target["difficulty"], target["secret_word"]) for target in targets],
            [
                ("animaux", "Facile", "CHAT"),
                ("pays", "Difficile", "JAPON"),
                ("animaux", "Moyen", "LOUP"),
            ],
        )

    def test_review_options_keep_exact_fragile_pair_instead_of_lowered_recommendation(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 1, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 1, "wins": 1},
                    {"category": "pays", "difficulty": "Moyen", "games_played": 1, "wins": 1},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 2, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=False,
                        end_reason="time",
                        attempts_left=2,
                        time_remaining=0,
                    ),
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=True,
                        end_reason="won",
                        attempts_left=2,
                        time_remaining=8,
                    ),
                ],
            },
            self.category_availability,
        )

        recommendation = snapshot["personalized_recommendation"]
        weak_pair = snapshot["review_options"]["weak_pair"]

        self.assertEqual(recommendation["difficulty"], "Moyen")
        self.assertEqual(weak_pair["driver"], "time_pressure")
        self.assertEqual(weak_pair["category"], "pays")
        self.assertEqual(weak_pair["difficulty"], "Difficile")

    def test_personalized_recommendation_switches_to_time_pressure(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 1, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 1, "wins": 1},
                    {"category": "pays", "difficulty": "Moyen", "games_played": 1, "wins": 1},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 2, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=False,
                        end_reason="time",
                        attempts_left=2,
                        time_remaining=0,
                    ),
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=True,
                        end_reason="won",
                        attempts_left=2,
                        time_remaining=8,
                    ),
                ],
            },
            self.category_availability,
        )

        recommendation = snapshot["personalized_recommendation"]

        self.assertEqual(snapshot["learning_profile"]["dominant_driver"], "time_pressure")
        self.assertEqual(recommendation["driver"], "time_pressure")
        self.assertEqual(recommendation["category"], "pays")
        self.assertEqual(recommendation["difficulty"], "Moyen")
        self.assertIn("La carte de maitrise reste Pays en Difficile", recommendation["detail"])

    def test_personalized_recommendation_switches_to_error_pressure(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 2, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 1, "wins": 1},
                    {"category": "pays", "difficulty": "Moyen", "games_played": 1, "wins": 1},
                    {"category": "pays", "difficulty": "Difficile", "games_played": 1, "wins": 1},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Moyen"},
                "recent_form": {"recent_games": 2, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=19,
                    ),
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        won=True,
                        end_reason="won",
                        attempts_left=1,
                        time_remaining=18,
                    ),
                ],
            },
            self.category_availability,
        )

        recommendation = snapshot["personalized_recommendation"]

        self.assertEqual(snapshot["learning_profile"]["dominant_driver"], "error_pressure")
        self.assertEqual(recommendation["driver"], "error_pressure")
        self.assertEqual(recommendation["category"], "animaux")
        self.assertEqual(recommendation["difficulty"], "Moyen")
        self.assertIn("la paire n'a pas encore de victoire", recommendation["detail"])

    def test_recent_driver_pivots_when_latest_pattern_changes(self):
        shared_dashboard = {
            "selection_stats": [
                {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                {"category": "animaux", "difficulty": "Moyen", "games_played": 2, "wins": 0},
                {"category": "pays", "difficulty": "Facile", "games_played": 1, "wins": 1},
                {"category": "pays", "difficulty": "Moyen", "games_played": 1, "wins": 1},
            ],
            "favorite_category": {"category": "animaux"},
            "best_difficulty": {"difficulty": "Moyen"},
            "recent_form": {"recent_games": 2, "recent_wins": 1},
        }

        time_snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                **shared_dashboard,
                "recent_games": [
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=False,
                        end_reason="time",
                        attempts_left=2,
                        time_remaining=0,
                    ),
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=True,
                        end_reason="won",
                        attempts_left=2,
                        time_remaining=8,
                    ),
                ],
            },
            self.category_availability,
        )
        error_snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                **shared_dashboard,
                "recent_games": [
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        won=False,
                        end_reason="attempts",
                        attempts_left=0,
                        time_remaining=19,
                    ),
                    self._recent_game(
                        "animaux",
                        "Moyen",
                        won=True,
                        end_reason="won",
                        attempts_left=1,
                        time_remaining=18,
                    ),
                ],
            },
            self.category_availability,
        )

        self.assertEqual(time_snapshot["learning_profile"]["dominant_driver"], "time_pressure")
        self.assertEqual(error_snapshot["learning_profile"]["dominant_driver"], "error_pressure")
        self.assertNotEqual(
            time_snapshot["personalized_recommendation"]["category"],
            error_snapshot["personalized_recommendation"]["category"],
        )

    def test_learning_profile_exposes_three_axes_with_single_dominant_status(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 2, "wins": 1},
                    {"category": "animaux", "difficulty": "Moyen", "games_played": 1, "wins": 0},
                    {"category": "pays", "difficulty": "Facile", "games_played": 1, "wins": 1},
                    {"category": "pays", "difficulty": "Moyen", "games_played": 1, "wins": 1},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 2, "recent_wins": 1},
                "recent_games": [
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=False,
                        end_reason="time",
                        attempts_left=2,
                        time_remaining=0,
                    ),
                    self._recent_game(
                        "pays",
                        "Difficile",
                        won=True,
                        end_reason="won",
                        attempts_left=2,
                        time_remaining=8,
                    ),
                ],
            },
            self.category_availability,
        )

        axes = snapshot["learning_profile"]["axes"]

        self.assertEqual(len(axes), 3)
        self.assertEqual(sum(1 for axis in axes if axis["status"] == "Dominant"), 1)


if __name__ == "__main__":
    unittest.main()
