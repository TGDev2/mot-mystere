import unittest
from pathlib import Path

from database import get_leaderboard_data, get_or_create_player, record_game_result, setup_database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "test_runtime.db"
        if self.db_path.exists():
            self.db_path.unlink()
        setup_database(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            get_or_create_player("   ", db_path=self.db_path)

    def test_record_game_result_updates_progression(self):
        player = get_or_create_player("Theo", db_path=self.db_path)

        updated = record_game_result(player["id"], won=True, score_earned=180, db_path=self.db_path)

        self.assertEqual(updated["games_played"], 1)
        self.assertEqual(updated["games_won"], 1)
        self.assertEqual(updated["score_total"], 180)
        self.assertEqual(updated["best_score"], 180)

    def test_leaderboard_sorts_by_total_score(self):
        alice = get_or_create_player("Alice", db_path=self.db_path)
        bob = get_or_create_player("Bob", db_path=self.db_path)

        record_game_result(alice["id"], won=True, score_earned=120, db_path=self.db_path)
        record_game_result(bob["id"], won=True, score_earned=260, db_path=self.db_path)

        leaderboard = get_leaderboard_data(db_path=self.db_path)

        self.assertEqual(leaderboard[0]["name"], "Bob")
        self.assertEqual(leaderboard[1]["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
