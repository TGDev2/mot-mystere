import unittest
from pathlib import Path
import shutil
import uuid

from motmystere.database import get_word_rotation_state, setup_database
from motmystere.progression import build_progression_snapshot
from motmystere.solo_game_service import (
    build_catalog_exploration_snapshot,
    build_guided_objective,
    build_guided_recommendation,
    build_review_recommendation,
    build_review_session_state,
    create_session_for_player,
    create_review_session,
    evaluate_review_session,
    evaluate_guided_objective,
    get_progression_bundle,
    prepare_player,
    resolve_round,
)


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class FixedChoice:
    def choice(self, values):
        return values[0]


class SoloGameServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_service_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.db_path = self.runtime_dir / "service_runtime.db"
        setup_database(self.db_path)
        self.categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}
        self.category_availability = {"animaux": ("Facile",)}
        self.player = prepare_player("Alice", db_path=self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_session_avoids_repeat_until_rotation_is_exhausted(self):
        words = []
        for _ in range(5):
            session = create_session_for_player(
                self.player["id"],
                self.categories,
                "animaux",
                "Facile",
                rng=FixedChoice(),
                db_path=self.db_path,
            )
            words.append(session.secret_word)

        self.assertEqual(words, ["CHAT", "LION", "OURS", "LOUP", "VACHE"])

        next_session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )

        self.assertEqual(next_session.secret_word, "CHAT")

    def test_resolve_round_returns_progression_without_ui(self):
        session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )
        for letter in "CHAT":
            session.guess(letter)

        outcome = resolve_round(
            self.player,
            session,
            "won",
            self.category_availability,
            db_path=self.db_path,
        )

        self.assertEqual(outcome["title"], "Victoire")
        self.assertGreater(outcome["score_earned"], 0)
        self.assertEqual(
            outcome["mastery_updates"][0]["title"],
            "Animaux / Facile valide",
        )
        self.assertEqual(
            outcome["progression_snapshot"]["primary_goal"]["key"],
            "mastery_board",
        )

    def test_guided_objective_maps_primary_goal_to_concrete_pair_target(self):
        bundle = get_progression_bundle(
            self.player,
            self.category_availability,
            db_path=self.db_path,
        )

        objective = build_guided_objective(bundle["snapshot"], source="primary_goal")
        recommendation = build_guided_recommendation(
            objective,
            bundle["player"],
            bundle["dashboard"],
            bundle["snapshot"],
        )

        self.assertEqual(objective["metric"], "pair_wins")
        self.assertEqual(objective["title"], "Valider Animaux en Facile")
        self.assertEqual(objective["target_value"], 1)
        self.assertEqual(objective["progress_text"], "0/1 victoire(s)")
        self.assertEqual(recommendation["category"], "animaux")
        self.assertEqual(recommendation["difficulty"], "Facile")

    def test_guided_objective_completes_after_target_win(self):
        bundle = get_progression_bundle(
            self.player,
            self.category_availability,
            db_path=self.db_path,
        )
        objective = build_guided_objective(bundle["snapshot"], source="primary_goal")

        session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )
        for letter in "CHAT":
            session.guess(letter)

        outcome = resolve_round(
            self.player,
            session,
            "won",
            self.category_availability,
            db_path=self.db_path,
        )
        progress = evaluate_guided_objective(
            objective,
            outcome["player"],
            outcome["dashboard"],
            outcome["progression_snapshot"],
        )

        self.assertTrue(progress["completed"])
        self.assertEqual(progress["progress_text"], "1/1 victoire(s)")

    def test_guided_recommendation_handles_recent_form_objective(self):
        snapshot = build_progression_snapshot(
            {"score_total": 260},
            {
                "selection_stats": [
                    {"category": "animaux", "difficulty": "Facile", "games_played": 4, "wins": 3},
                ],
                "favorite_category": {"category": "animaux"},
                "best_difficulty": {"difficulty": "Facile"},
                "recent_form": {"recent_games": 5, "recent_wins": 2},
            },
            self.category_availability,
        )

        objective = build_guided_objective(snapshot, source="featured_challenge")
        recommendation = build_guided_recommendation(
            objective,
            {"score_total": 260},
            {"recent_form": {"recent_games": 5, "recent_wins": 2}},
            snapshot,
        )

        self.assertEqual(objective["metric"], "recent_wins")
        self.assertEqual(objective["target_value"], 3)
        self.assertEqual(recommendation["category"], "animaux")
        self.assertEqual(recommendation["difficulty"], "Facile")
        self.assertIn("Encore 1 victoire(s) recentes", recommendation["detail"])

    def test_catalog_exploration_snapshot_starts_with_a_fresh_pool(self):
        snapshot = build_catalog_exploration_snapshot(
            self.player["id"],
            self.categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )

        selected = snapshot["selected_state"]
        self.assertEqual(selected["state_label"], "Pool largement neuf")
        self.assertEqual(selected["progress_text"], "5/5 mot(s) frais")
        self.assertEqual(selected["detail"], "5 mot(s) encore frais dans cette rotation.")

    def test_catalog_exploration_snapshot_tracks_consumption_and_cycle_restart(self):
        for _ in range(4):
            create_session_for_player(
                self.player["id"],
                self.categories,
                "animaux",
                "Facile",
                rng=FixedChoice(),
                db_path=self.db_path,
            )

        imminent_snapshot = build_catalog_exploration_snapshot(
            self.player["id"],
            self.categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )["selected_state"]
        self.assertEqual(imminent_snapshot["state_label"], "Cycle imminent")
        self.assertEqual(imminent_snapshot["progress_text"], "1/5 mot(s) frais")

        create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )

        restarted_snapshot = build_catalog_exploration_snapshot(
            self.player["id"],
            self.categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )["selected_state"]
        self.assertEqual(restarted_snapshot["state_label"], "Cycle imminent")
        self.assertEqual(restarted_snapshot["progress_text"], "0/5 mot(s) frais")
        self.assertEqual(
            restarted_snapshot["detail"],
            "Rotation terminee, la prochaine manche relancera 4 mot(s) frais.",
        )

    def test_catalog_exploration_snapshot_recalibrates_when_catalog_changes(self):
        create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )
        updated_categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE", "PANDA"]}

        recalibrated = build_catalog_exploration_snapshot(
            self.player["id"],
            updated_categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )["selected_state"]

        self.assertTrue(recalibrated["catalog_recalibrated"])
        self.assertEqual(recalibrated["state_label"], "Pool largement neuf")
        self.assertEqual(recalibrated["progress_text"], "5/5 mot(s) frais")
        self.assertEqual(recalibrated["note"], "Pool recalibre sur le catalogue actuel.")

    def test_review_failed_words_session_forces_target_without_touching_rotation(self):
        lost_session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )
        resolve_round(
            self.player,
            lost_session,
            "attempts",
            self.category_availability,
            db_path=self.db_path,
        )

        bundle = get_progression_bundle(
            self.player,
            self.category_availability,
            db_path=self.db_path,
        )
        review_option = bundle["snapshot"]["review_options"]["failed_words"]
        review_session = build_review_session_state(review_option, self.categories)
        rotation_before = get_word_rotation_state(
            self.player["id"],
            "animaux",
            "Facile",
            db_path=self.db_path,
        )

        review_round = create_review_session(review_session, self.categories, rng=FixedChoice())

        rotation_after = get_word_rotation_state(
            self.player["id"],
            "animaux",
            "Facile",
            db_path=self.db_path,
        )

        self.assertEqual(review_round.secret_word, "CHAT")
        self.assertEqual(rotation_before, rotation_after)
        self.assertEqual(review_session["max_rounds"], 1)

    def test_review_weak_pair_session_stays_on_exact_pair_until_resolution(self):
        review_session = build_review_session_state(
            {
                "kind": "weak_pair",
                "title": "Travailler mon reglage fragile",
                "driver": "time_pressure",
                "driver_label": "Temps",
                "category": "animaux",
                "difficulty": "Facile",
                "target_value": 2,
                "max_rounds": 3,
            },
            self.categories,
        )

        first_round = create_review_session(review_session, self.categories, rng=FixedChoice())
        review_session["rounds"].append(
            {
                "category": first_round.category,
                "difficulty": first_round.difficulty,
                "secret_word": first_round.secret_word,
                "won": True,
                "qualified": True,
            }
        )
        first_progress = evaluate_review_session(review_session)
        first_recommendation = build_review_recommendation(review_session)

        second_round = create_review_session(review_session, self.categories, rng=FixedChoice())
        review_session["rounds"].append(
            {
                "category": second_round.category,
                "difficulty": second_round.difficulty,
                "secret_word": second_round.secret_word,
                "won": True,
                "qualified": True,
            }
        )
        second_progress = evaluate_review_session(review_session)

        self.assertEqual(first_round.category, "animaux")
        self.assertEqual(first_round.difficulty, "Facile")
        self.assertFalse(first_progress["completed"])
        self.assertEqual(first_recommendation["category"], "animaux")
        self.assertEqual(first_recommendation["difficulty"], "Facile")
        self.assertTrue(second_progress["completed"])
        self.assertEqual(second_progress["resolution_status"], "resolved")

    def test_review_session_verdicts_cover_improved_and_still_fragile(self):
        failed_words_session = build_review_session_state(
            {
                "kind": "failed_words",
                "title": "Reviser mes mots rates",
                "targets": (
                    {
                        "category": "animaux",
                        "difficulty": "Facile",
                        "secret_word": "CHAT",
                        "label": "Animaux en Facile",
                    },
                    {
                        "category": "animaux",
                        "difficulty": "Facile",
                        "secret_word": "LION",
                        "label": "Animaux en Facile",
                    },
                ),
            },
            self.categories,
        )
        failed_words_session["rounds"] = [
            {
                "category": "animaux",
                "difficulty": "Facile",
                "secret_word": "CHAT",
                "won": True,
            },
            {
                "category": "animaux",
                "difficulty": "Facile",
                "secret_word": "LION",
                "won": False,
            },
        ]

        weak_pair_session = build_review_session_state(
            {
                "kind": "weak_pair",
                "title": "Travailler mon reglage fragile",
                "driver": "error_pressure",
                "driver_label": "Erreurs",
                "category": "animaux",
                "difficulty": "Facile",
                "target_value": 2,
                "max_rounds": 3,
            },
            self.categories,
        )
        weak_pair_session["rounds"] = [
            {"qualified": False},
            {"qualified": False},
            {"qualified": False},
        ]

        failed_progress = evaluate_review_session(failed_words_session)
        weak_progress = evaluate_review_session(weak_pair_session)

        self.assertTrue(failed_progress["completed"])
        self.assertEqual(failed_progress["resolution_status"], "improved")
        self.assertTrue(weak_progress["completed"])
        self.assertEqual(weak_progress["resolution_status"], "still_fragile")

    def test_rotation_progression_advances_after_a_lost_round(self):
        before_state = build_catalog_exploration_snapshot(
            self.player["id"],
            self.categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )["selected_state"]
        session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )

        resolve_round(
            self.player,
            session,
            "attempts",
            self.category_availability,
            db_path=self.db_path,
        )

        after_state = build_catalog_exploration_snapshot(
            self.player["id"],
            self.categories,
            self.category_availability,
            selected_category="animaux",
            selected_difficulty="Facile",
            db_path=self.db_path,
        )["selected_state"]

        self.assertEqual(before_state["progress_text"], "5/5 mot(s) frais")
        self.assertEqual(after_state["progress_text"], "4/5 mot(s) frais")
        self.assertEqual(after_state["detail"], "4 mot(s) encore frais dans cette rotation.")


if __name__ == "__main__":
    unittest.main()
