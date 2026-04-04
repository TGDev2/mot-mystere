from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.release_smoke import run_release_smoke_test


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class ReleaseSmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_smoke_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.db_path = self.runtime_dir / "release_smoke_runtime.db"

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
