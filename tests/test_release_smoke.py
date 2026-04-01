from pathlib import Path
import unittest

from release_smoke import run_release_smoke_test


class ReleaseSmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "release_smoke_runtime.db"
        if self.db_path.exists():
            self.db_path.unlink()

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_release_smoke_runs_end_to_end(self):
        result = run_release_smoke_test(db_path=self.db_path)

        self.assertTrue(self.db_path.exists())
        self.assertEqual(result["games_played"], 2)
        self.assertGreater(result["score_total"], 0)
        self.assertGreaterEqual(result["leaderboard_size"], 1)


if __name__ == "__main__":
    unittest.main()
