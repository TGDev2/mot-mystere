import unittest
from pathlib import Path
import shutil
import uuid

from motmystere.database import setup_database
from motmystere.progression import build_progression_snapshot
from motmystere.solo_game_service import (
    build_guided_objective,
    build_guided_recommendation,
    create_session_for_player,
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


if __name__ == "__main__":
    unittest.main()
