import unittest
from pathlib import Path
import shutil
import uuid

from motmystere.database import (
    get_leaderboard_data,
    get_or_create_player,
    get_player_dashboard,
    get_recent_players,
    get_recent_games,
    get_word_rotation_state,
    record_game_result,
    save_word_rotation_state,
    setup_database,
)


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_db_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.db_path = self.runtime_dir / "test_runtime.db"
        setup_database(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            get_or_create_player("   ", db_path=self.db_path)

    def test_record_game_result_updates_progression_and_history(self):
        player = get_or_create_player("Theo", db_path=self.db_path)

        updated = record_game_result(
            player["id"],
            won=True,
            score_earned=180,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=8,
            time_remaining=50,
            word_complexity=20,
            db_path=self.db_path,
        )
        recent_games = get_recent_games(player["id"], db_path=self.db_path)

        self.assertEqual(updated["games_played"], 1)
        self.assertEqual(updated["games_won"], 1)
        self.assertEqual(updated["score_total"], 180)
        self.assertEqual(updated["best_score"], 180)
        self.assertEqual(len(recent_games), 1)
        self.assertEqual(recent_games[0]["category"], "animaux")
        self.assertEqual(recent_games[0]["difficulty"], "Facile")

    def test_leaderboard_sorts_by_total_score(self):
        alice = get_or_create_player("Alice", db_path=self.db_path)
        bob = get_or_create_player("Bob", db_path=self.db_path)

        record_game_result(alice["id"], won=True, score_earned=120, db_path=self.db_path)
        record_game_result(bob["id"], won=True, score_earned=260, db_path=self.db_path)

        leaderboard = get_leaderboard_data(db_path=self.db_path)

        self.assertEqual(leaderboard[0]["name"], "Bob")
        self.assertEqual(leaderboard[1]["name"], "Alice")

    def test_dashboard_exposes_progression_insights(self):
        player = get_or_create_player("Alice", db_path=self.db_path)
        record_game_result(
            player["id"],
            won=True,
            score_earned=210,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=9,
            time_remaining=55,
            word_complexity=20,
            db_path=self.db_path,
        )
        record_game_result(
            player["id"],
            won=False,
            score_earned=0,
            category="pays",
            difficulty="Difficile",
            secret_word="KAZAKHSTAN",
            end_reason="attempts",
            attempts_left=0,
            time_remaining=14,
            word_complexity=47,
            db_path=self.db_path,
        )

        dashboard = get_player_dashboard(player["id"], db_path=self.db_path)

        self.assertEqual(dashboard["overview"]["games_recorded"], 2)
        self.assertEqual(dashboard["best_difficulty"]["difficulty"], "Facile")
        self.assertEqual(dashboard["favorite_category"]["category"], "animaux")
        self.assertEqual(dashboard["weakest_category"]["category"], "pays")
        self.assertEqual(dashboard["category_stats"][0]["category"], "animaux")
        self.assertEqual(dashboard["difficulty_stats"][0]["difficulty"], "Facile")
        self.assertEqual(dashboard["selection_stats"][0]["category"], "animaux")
        self.assertEqual(dashboard["recent_games"][0]["difficulty"], "Difficile")

    def test_word_rotation_state_persists_remaining_pool(self):
        player = get_or_create_player("Alice", db_path=self.db_path)

        save_word_rotation_state(
            player["id"],
            "animaux",
            "Facile",
            ["CHAT", "LION", "OURS"],
            last_word="VACHE",
            db_path=self.db_path,
        )

        state = get_word_rotation_state(
            player["id"],
            "animaux",
            "Facile",
            db_path=self.db_path,
        )

        self.assertEqual(state["remaining_words"], ["CHAT", "LION", "OURS"])
        self.assertEqual(state["last_word"], "VACHE")

    def test_recent_players_expose_last_selection_context(self):
        alice = get_or_create_player("Alice", db_path=self.db_path)
        bob = get_or_create_player("Bob", db_path=self.db_path)

        record_game_result(
            alice["id"],
            won=True,
            score_earned=120,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=8,
            time_remaining=44,
            word_complexity=20,
            db_path=self.db_path,
        )
        record_game_result(
            bob["id"],
            won=False,
            score_earned=0,
            category="pays",
            difficulty="Moyen",
            secret_word="CANADA",
            end_reason="attempts",
            attempts_left=0,
            time_remaining=11,
            word_complexity=24,
            db_path=self.db_path,
        )
        record_game_result(
            bob["id"],
            won=True,
            score_earned=210,
            category="sports",
            difficulty="Difficile",
            secret_word="BASKETBALL",
            end_reason="won",
            attempts_left=2,
            time_remaining=12,
            word_complexity=38,
            db_path=self.db_path,
        )

        recent_players = get_recent_players(db_path=self.db_path)

        self.assertEqual(recent_players[0]["name"], "Bob")
        self.assertEqual(recent_players[0]["last_category"], "sports")
        self.assertEqual(recent_players[0]["last_difficulty"], "Difficile")
        self.assertTrue(recent_players[0]["last_won"])
        self.assertEqual(recent_players[1]["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
